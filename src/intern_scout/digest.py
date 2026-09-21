from __future__ import annotations

from datetime import date
from pathlib import Path

from .db import list_jobs
from .models import Profile


def build_digest(db_path: str | Path, profile: Profile, *, limit: int = 20) -> str:
    jobs = list_jobs(db_path, limit=limit)
    lines = [
        f"# Internship digest - {date.today().isoformat()}",
        "",
        f"Profile: {profile.name} | {profile.citizenship} | GPA {profile.gpa}/{profile.gpa_scale}",
        "Availability: " + "; ".join(
            f"{window.label or 'window'} ({window.start.isoformat()} to {window.end.isoformat()})"
            for window in profile.availability
        ),
        "",
        "## Ranked opportunities",
        "",
    ]
    if not jobs:
        lines.append("No jobs collected yet. Run `intern-scout init` or `intern-scout refresh`.")
        return "\n".join(lines) + "\n"
    for job in jobs:
        deadline = f" | deadline {job['deadline']}" if job["deadline"] else ""
        lines.extend(
            [
                f"### {job['score']:.0f} - [{job['title']}]({job['url']})",
                "",
                f"{job['company']} | {job['location']} | {job['eligibility']} | {job['review_status']}{deadline}",
                "",
                "Why it ranked here: " + "; ".join(job["score_reasons"][:4]),
                "",
                "Checks: " + "; ".join(job["eligibility_reasons"][:4]),
                "",
            ]
        )
    lines.extend(
        [
            "## Review commands",
            "",
            "```bash",
            "intern-scout review JOB_ID approved",
            "intern-scout review JOB_ID rejected",
            "intern-scout serve",
            "```",
            "",
        ]
    )
    return "\n".join(lines)


def write_digest(path: str | Path, content: str) -> Path:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(content, encoding="utf-8")
    return output

