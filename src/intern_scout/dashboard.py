from __future__ import annotations

import html
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs

from .applications import approve_application, load_facts
from .config import load_profile
from .db import VALID_STATUSES, get_job, list_jobs, stats, update_status
from .resume import generate_tailored_resume, load_resume_facts


def _page(db_path: str | Path, message: str = "") -> bytes:
    jobs = list_jobs(db_path, limit=250)
    summary = stats(db_path)
    cards: list[str] = []
    for job in jobs:
        reasons = "".join(f"<li>{html.escape(reason)}</li>" for reason in job["score_reasons"][:5])
        checks = "".join(f"<li>{html.escape(reason)}</li>" for reason in job["eligibility_reasons"][:5])
        buttons = "".join(
            f'<button name="status" value="{status}">{status.replace("_", " ").title()}</button>'
            for status in ("maybe", "rejected", "applied", "interview")
        )
        cards.append(
            f"""
            <article class="card {html.escape(job['eligibility'])}">
              <div class="score">{job['score']:.0f}</div>
              <div class="content">
                <h2><a href="{html.escape(job['url'], quote=True)}" target="_blank" rel="noreferrer">{html.escape(job['title'])}</a></h2>
                <p class="meta">{html.escape(job['company'])} · {html.escape(job['location'])} ·
                  <strong>{html.escape(job['eligibility'])}</strong> · {html.escape(job['review_status'])}</p>
                <details><summary>Ranking</summary><ul>{reasons}</ul></details>
                <details><summary>Eligibility checks</summary><ul>{checks}</ul></details>
                <form method="post" action="/status">
                  <input type="hidden" name="job_id" value="{job['id']}">{buttons}
                </form>
                <form method="post" action="/approve">
                  <input type="hidden" name="job_id" value="{job['id']}">
                  <button class="primary" type="submit">Approve, tailor &amp; prepare</button>
                </form>
              </div>
            </article>
            """
        )
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Intern Scout</title>
<style>
:root {{ color-scheme: light; font-family: Inter, ui-sans-serif, system-ui, sans-serif; background:#f4f6f8; color:#17202a; }}
body {{ margin:0 auto; max-width:1050px; padding:32px 20px 60px; }}
header {{ display:flex; justify-content:space-between; gap:20px; align-items:end; margin-bottom:24px; }}
h1 {{ margin:0; font-size:2rem; }} .muted,.meta {{ color:#5d6d7e; }}
.card {{ display:flex; gap:20px; background:white; border:1px solid #dfe6e9; border-left:5px solid #f39c12; border-radius:12px; padding:20px; margin:14px 0; box-shadow:0 3px 12px #0000000c; }}
.card.eligible {{ border-left-color:#27ae60; }} .card.ineligible {{ border-left-color:#c0392b; opacity:.76; }}
.score {{ flex:0 0 58px; height:58px; border-radius:50%; background:#17202a; color:white; display:grid; place-items:center; font-size:1.3rem; font-weight:700; }}
.content {{ flex:1; min-width:0; }} h2 {{ margin:0 0 6px; font-size:1.15rem; }} a {{ color:#145a9c; }}
details {{ margin:10px 0; }} button {{ margin:8px 8px 0 0; padding:7px 11px; border:1px solid #aab7b8; border-radius:7px; background:#fff; cursor:pointer; }}
button:hover {{ background:#eef4fa; }} .message {{ background:#e8f8f5; padding:10px 14px; border-radius:8px; }}
button.primary {{ background:#145a9c; color:white; border-color:#145a9c; font-weight:700; }}
button.primary:hover {{ background:#0e477d; }}
@media(max-width:620px) {{ header {{ display:block; }} .card {{ gap:12px; }} .score {{ flex-basis:46px; height:46px; }} }}
</style></head><body>
<header><div><h1>Intern Scout</h1><div class="muted">Human-approved Singapore internship queue</div></div>
<div>{summary.get('total', 0)} opportunities</div></header>
{f'<p class="message">{html.escape(message)}</p>' if message else ''}
{''.join(cards) or '<p>No opportunities yet. Run the init or refresh command.</p>'}
</body></html>"""
    return body.encode("utf-8")


def make_handler(
    db_path: str | Path,
    profile_path: str | Path,
    facts_path: str | Path,
    applications_path: str | Path,
    resume_facts_path: str | Path,
    resume_output_path: str | Path,
):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:  # noqa: N802
            content = _page(db_path)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self) -> None:  # noqa: N802
            if self.path not in {"/status", "/approve"}:
                self.send_error(404)
                return
            length = int(self.headers.get("Content-Length", "0"))
            values = parse_qs(self.rfile.read(length).decode("utf-8"))
            try:
                job_id = int(values["job_id"][0])
                if self.path == "/approve":
                    job = get_job(db_path, job_id)
                    if job is None:
                        raise ValueError(f"Job {job_id} was not found")
                    profile = load_profile(profile_path)
                    resume = generate_tailored_resume(
                        job,
                        profile,
                        load_resume_facts(resume_facts_path),
                        resume_output_path,
                    )
                    directory = approve_application(
                        db_path,
                        job_id,
                        profile,
                        load_facts(facts_path),
                        applications_path,
                        resume_path=resume,
                    )
                    message = f"Approved job {job_id}; tailored resume and private packet created at {directory}."
                else:
                    status = values["status"][0]
                    if status not in VALID_STATUSES:
                        raise ValueError("invalid status")
                    changed = update_status(db_path, job_id, status)
                    message = f"Updated job {job_id} to {status}." if changed else f"Job {job_id} was not found."
            except (KeyError, ValueError, IndexError, FileNotFoundError) as exc:
                message = str(exc) if str(exc) else "Invalid review request."
            content = _page(db_path, message)
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def log_message(self, format: str, *args) -> None:
            return

    return Handler


def serve(
    db_path: str | Path,
    host: str = "127.0.0.1",
    port: int = 8765,
    *,
    profile_path: str | Path = "data/profile.json",
    facts_path: str | Path = "data/candidate_facts.json",
    applications_path: str | Path = "applications",
    resume_facts_path: str | Path = "data/resume_facts.json",
    resume_output_path: str | Path = "output/pdf",
) -> None:
    server = ThreadingHTTPServer(
        (host, port),
        make_handler(
            db_path,
            profile_path,
            facts_path,
            applications_path,
            resume_facts_path,
            resume_output_path,
        ),
    )
    print(f"Intern Scout dashboard: http://{host}:{port}")
    print("Press Ctrl-C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
