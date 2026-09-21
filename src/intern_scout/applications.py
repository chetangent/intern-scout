from __future__ import annotations

import json
import re
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import get_job, update_status
from .models import Profile


def _slug(value: str) -> str:
    result = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    return result[:90] or "application"


def load_facts(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _job_text(job: dict) -> str:
    return " ".join(
        [job["title"], job["company"], job["description"], " ".join(job["tags"])]
    ).lower()


def _relevant_evidence(job: dict, facts: dict[str, Any]) -> list[dict[str, Any]]:
    job_text = _job_text(job)
    evidence: list[tuple[int, dict[str, Any]]] = []
    for item in facts.get("evidence", []):
        keywords = [str(keyword).lower() for keyword in item.get("keywords", [])]
        matches = sum(1 for keyword in keywords if keyword in job_text)
        evidence.append((matches, item))
    evidence.sort(key=lambda pair: pair[0], reverse=True)
    return [item for matches, item in evidence if matches > 0][:4] or [item for _, item in evidence[:3]]


def _resume_plan(job: dict, evidence: list[dict[str, Any]]) -> str:
    lines = [
        "# Resume tailoring plan",
        "",
        f"Target: {job['title']} at {job['company']}",
        "",
        "## Recommended emphasis",
        "",
    ]
    for item in evidence:
        lines.append(f"- **{item['name']}**: {item.get('reason', 'Relevant evidence for this role.')}")
        for bullet in item.get("bullets", [])[:3]:
            lines.append(f"  - {bullet}")
    lines.extend(
        [
            "",
            "## Before submitting",
            "",
            "- Mirror only truthful keywords from the job description.",
            "- Put the most relevant projects above general leadership for technical roles.",
            "- Add measured outcomes where they are known; never invent metrics.",
            "- Confirm dates, work arrangement, and eligibility before generating a final PDF.",
            "",
        ]
    )
    return "\n".join(lines)


def _draft_answers(job: dict, profile: Profile, evidence: list[dict[str, Any]], facts: dict[str, Any]) -> str:
    lead = evidence[0] if evidence else {"name": "my software projects", "reason": "relevant technical experience"}
    availability = " or ".join(
        f"{window.start.strftime('%B %Y')} to {window.end.strftime('%B %Y')}" for window in profile.availability
    )
    why_company = (
        f"I am interested in the {job['title']} opportunity because it combines practical technology work "
        f"with the chance to contribute at {job['company']}. My experience with {lead['name']} gives me a "
        f"foundation in {lead.get('reason', 'building and delivering software')}. I would be excited to learn "
        "from the team, take ownership of a well-scoped project, and contribute dependable work during the internship."
    )
    lines = [
        "# Draft application answers",
        "",
        "> Drafts require human review. Do not submit them without checking role-specific accuracy.",
        "",
        "## Why are you interested in this role?",
        "",
        why_company,
        "",
        "## Work authorisation",
        "",
        facts.get("work_authorisation", "I am a Singapore citizen and do not require employment sponsorship in Singapore."),
        "",
        "## Availability",
        "",
        f"I am available for a full-time internship during {availability}, subject to the role's exact dates.",
        "",
        "## Academic information",
        "",
        f"Current GPA: {profile.gpa}/{profile.gpa_scale}. Expected graduation: {profile.graduation_date}.",
        "",
        "## Questions that still require confirmation",
        "",
        "- Exact internship start and end dates",
        "- Expected on-site days and normal working hours",
        "- Compensation expectations, if requested",
        "- Any security-clearance or conflict-of-interest declarations",
        "",
    ]
    return "\n".join(lines)


def prepare_application(
    db_path: str | Path,
    job_id: int,
    profile: Profile,
    facts: dict[str, Any],
    output_root: str | Path,
) -> Path:
    job = get_job(db_path, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} was not found")
    directory = Path(output_root) / _slug(f"{job['company']}-{job['title']}")
    directory.mkdir(parents=True, exist_ok=True)
    evidence = _relevant_evidence(job, facts)

    job_summary = "\n".join(
        [
            "# Opportunity record",
            "",
            f"- Role: {job['title']}",
            f"- Company: {job['company']}",
            f"- Location: {job['location']}",
            f"- Eligibility: {job['eligibility']}",
            f"- Score: {job['score']:.0f}/100",
            f"- Deadline: {job['deadline'] or 'Confirm on official page'}",
            f"- Official link: {job['url']}",
            "",
            "## Ranking reasons",
            "",
            *[f"- {reason}" for reason in job["score_reasons"]],
            "",
            "## Eligibility checks",
            "",
            *[f"- {reason}" for reason in job["eligibility_reasons"]],
            "",
            "## Source description",
            "",
            job["description"] or "No description was extracted. Review the official page.",
            "",
        ]
    )
    (directory / "opportunity.md").write_text(job_summary, encoding="utf-8")
    (directory / "resume-plan.md").write_text(_resume_plan(job, evidence), encoding="utf-8")
    (directory / "draft-answers.md").write_text(
        _draft_answers(job, profile, evidence, facts), encoding="utf-8"
    )
    (directory / "checklist.md").write_text(
        "\n".join(
            [
                "# Application checklist",
                "",
                "- [ ] Confirm the role is still open on the official page",
                "- [ ] Confirm internship dates fit an availability window",
                "- [ ] Confirm hybrid/on-site expectations and office hours",
                "- [ ] Tailor and proofread the resume",
                "- [ ] Review every drafted answer for accuracy",
                "- [ ] Attach transcript or student-status letter if requested",
                "- [ ] Submit manually",
                "- [ ] Mark the role as applied in Intern Scout",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return directory


def approve_application(
    db_path: str | Path,
    job_id: int,
    profile: Profile,
    facts: dict[str, Any],
    output_root: str | Path,
    *,
    resume_path: str | Path | None = None,
) -> Path:
    """Approve a viable role and create its private application packet.

    Approval authorises preparation, not submission. The manifest is designed for
    a later browser-filling step that must stop before the employer's final submit.
    """
    job = get_job(db_path, job_id)
    if job is None:
        raise ValueError(f"Job {job_id} was not found")
    if job["eligibility"] == "ineligible":
        raise ValueError(
            f"Job {job_id} is marked ineligible. Resolve the eligibility conflict before approving it."
        )

    directory = prepare_application(db_path, job_id, profile, facts, output_root)
    attached_resume = ""
    if resume_path is not None:
        source = Path(resume_path).expanduser().resolve()
        if not source.is_file():
            raise FileNotFoundError(f"Resume PDF was not found: {source}")
        if source.suffix.lower() != ".pdf" or source.read_bytes()[:4] != b"%PDF":
            raise ValueError(f"Resume must be a valid PDF: {source}")
        destination = directory / "tailored-resume.pdf"
        shutil.copy2(source, destination)
        attached_resume = destination.name

    update_status(db_path, job_id, "approved")
    manifest = {
        "schema_version": 1,
        "job_id": job_id,
        "job_fingerprint": job["fingerprint"],
        "role": job["title"],
        "company": job["company"],
        "official_url": job["url"],
        "eligibility": job["eligibility"],
        "approval": "approved_to_prepare",
        "approved_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "resume": attached_resume or None,
        "submission": "not_started",
        "requires_final_review": True,
    }
    (directory / "application.json").write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    return directory
