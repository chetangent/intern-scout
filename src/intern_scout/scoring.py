from __future__ import annotations

import re
from datetime import date

from .models import Assessment, Job, Profile, parse_date


INTEREST_TERMS = {
    "algorithms": ("algorithm", "data structure", "optimisation", "optimization", "graph", "search", "research"),
    "cloud computing": ("cloud", "aws", "gcp", "distributed system", "infrastructure", "platform", "devops", "site reliability", "sre"),
    "agentic software engineering": ("agentic", "ai agent", "llm", "generative ai", "genai", "tool calling", "automation", "ai-native"),
    "software engineering": ("software engineer", "software development", "backend", "full stack", "full-stack", "developer", "application development"),
}

PUBLIC_TERMS = (
    "govtech",
    "government",
    "public sector",
    "public service",
    "dsta",
    "csit",
    "htx",
    "csa",
    "synapxe",
    "open government products",
)

MENTORSHIP_TERMS = ("mentor", "mentorship", "structured", "learning", "training", "workshop", "guided")
FLEX_TERMS = ("hybrid", "remote", "flexible work", "work-life", "work life", "office hours")
INTERNSHIP_TERMS = ("intern", "undergraduate", "student")


def _text(job: Job) -> str:
    return " ".join(
        [job.title, job.company, job.location, job.description, job.work_style, " ".join(job.tags)]
    ).lower()


def _windows_cover_job(profile: Profile, start: date, end: date) -> bool:
    return any(window.start <= start and window.end >= end for window in profile.availability)


def assess_eligibility(job: Job, profile: Profile) -> tuple[str, list[str]]:
    text = _text(job)
    reasons: list[str] = []
    hard_failure = False
    needs_review = False

    if job.location and "singapore" not in job.location.lower() and "remote" not in job.location.lower():
        hard_failure = True
        reasons.append(f"Location is {job.location}, not Singapore/remote")
    else:
        reasons.append("Singapore location")

    citizenship = profile.citizenship.lower()
    if "singapore citizen" in text or "singaporean" in text:
        if "singapore" in citizenship and "citizen" in citizenship:
            reasons.append("Meets Singapore-citizen requirement")
        else:
            hard_failure = True
            reasons.append("Does not meet stated citizenship requirement")

    if any(term in text for term in ("defence", "defense", "national security")) and not profile.defence_roles_ok:
        hard_failure = True
        reasons.append("Defence roles are disabled in profile")

    if re.search(r"\bite internship\b", text):
        hard_failure = True
        reasons.append("Role is restricted to ITE students")

    start = parse_date(job.start_date)
    end = parse_date(job.end_date)
    if start and end:
        if _windows_cover_job(profile, start, end):
            reasons.append(f"Dates {start.isoformat()} to {end.isoformat()} fit an availability window")
        else:
            hard_failure = True
            reasons.append(f"Dates {start.isoformat()} to {end.isoformat()} are outside availability")
    elif start:
        if any(window.start <= start <= window.end for window in profile.availability):
            needs_review = True
            reasons.append("Start date fits, but end date needs confirmation")
        else:
            hard_failure = True
            reasons.append(f"Start date {start.isoformat()} is outside availability")
    else:
        needs_review = True
        reasons.append("Internship dates need confirmation")

    if not any(term in text for term in INTERNSHIP_TERMS):
        needs_review = True
        reasons.append("Posting is a programme/monitor rather than a confirmed internship role")

    deadline = parse_date(job.deadline)
    if deadline and deadline < date.today():
        hard_failure = True
        reasons.append(f"Deadline passed on {deadline.isoformat()}")

    if hard_failure:
        return "ineligible", reasons
    if needs_review:
        return "needs_review", reasons
    return "eligible", reasons


def score_job(job: Job, profile: Profile) -> Assessment:
    text = _text(job)
    eligibility, eligibility_reasons = assess_eligibility(job, profile)
    score = 30.0
    reasons: list[str] = []

    matched_interests: list[str] = []
    for interest in profile.interests:
        terms = INTEREST_TERMS.get(interest.lower(), (interest.lower(),))
        if any(term in text for term in terms):
            matched_interests.append(interest)
    if matched_interests:
        interest_points = min(30, 10 + 7 * len(matched_interests))
        score += interest_points
        reasons.append(f"Interest match: {', '.join(matched_interests)} (+{interest_points})")

    skill_hits = [skill for skill in profile.skills if re.search(rf"\b{re.escape(skill.lower())}\b", text)]
    if skill_hits:
        skill_points = min(12, len(skill_hits) * 2)
        score += skill_points
        reasons.append(f"Skill match: {', '.join(skill_hits[:6])} (+{skill_points})")

    if any(term in text for term in PUBLIC_TERMS):
        score += 12
        reasons.append("Public-sector/public-impact alignment (+12)")

    if any(term in text for term in MENTORSHIP_TERMS):
        score += 7
        reasons.append("Learning or mentorship signal (+7)")

    if any(term in text for term in FLEX_TERMS):
        score += 9
        reasons.append("Hybrid/flexible work signal (+9)")

    if eligibility == "eligible":
        score += 8
        reasons.append("Confirmed availability and eligibility (+8)")
    elif eligibility == "needs_review":
        reasons.append("Dates or programme details still need confirmation")
    else:
        score -= 45
        reasons.append("Currently ineligible (-45)")

    deadline = parse_date(job.deadline)
    if deadline:
        days = (deadline - date.today()).days
        if 0 <= days <= 21:
            score += 4
            reasons.append(f"Deadline in {days} days (+4 urgency)")

    return Assessment(
        score=round(max(0.0, min(100.0, score)), 1),
        score_reasons=reasons or ["No strong preference signals found"],
        eligibility=eligibility,
        eligibility_reasons=eligibility_reasons,
    )
