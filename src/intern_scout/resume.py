from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

from pypdf import PdfReader
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import BaseDocTemplate, Frame, PageTemplate, Paragraph, Spacer, Table, TableStyle

from .models import Profile


NAVY = colors.HexColor("#123B68")
INK = colors.HexColor("#111827")
MUTED = colors.HexColor("#4B5563")


def load_resume_facts(path: str | Path) -> dict[str, Any]:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _slug(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")[:70] or "role"


def _tokens(value: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9+#.]+", value.lower())
        if len(token) > 2
    }


def _job_tokens(job: dict[str, Any]) -> set[str]:
    return _tokens(
        " ".join(
            [
                str(job.get("title", "")),
                str(job.get("company", "")),
                str(job.get("description", "")),
                " ".join(job.get("tags", [])),
            ]
        )
    )


def _entry_score(entry: dict[str, Any], wanted: set[str]) -> int:
    keywords = _tokens(" ".join(entry.get("keywords", [])))
    text = _tokens(" ".join([entry.get("name", ""), *entry.get("bullets", [])]))
    return 3 * len(keywords & wanted) + len(text & wanted)


def _ranked(entries: list[dict[str, Any]], wanted: set[str]) -> list[dict[str, Any]]:
    return sorted(entries, key=lambda item: _entry_score(item, wanted), reverse=True)


def _styles() -> dict[str, ParagraphStyle]:
    return {
        "name": ParagraphStyle("name", fontName="Helvetica-Bold", fontSize=22, leading=24, alignment=TA_CENTER, textColor=INK, spaceAfter=4),
        "contact": ParagraphStyle("contact", fontName="Helvetica", fontSize=8.6, leading=10.5, alignment=TA_CENTER, textColor=MUTED, spaceAfter=5),
        "section": ParagraphStyle("section", fontName="Helvetica-Bold", fontSize=10.3, leading=11.5, textColor=NAVY, spaceBefore=6, spaceAfter=2.5),
        "body": ParagraphStyle("body", fontName="Helvetica", fontSize=8.8, leading=11.2, textColor=INK, spaceAfter=1.3),
        "small": ParagraphStyle("small", fontName="Helvetica", fontSize=8.45, leading=10.2, textColor=INK, spaceAfter=1.2),
        "bullet": ParagraphStyle("bullet", fontName="Helvetica", fontSize=8.55, leading=10.45, leftIndent=8, firstLineIndent=-5, textColor=INK, spaceAfter=1.4),
        "title": ParagraphStyle("title", fontName="Helvetica-Bold", fontSize=9.05, leading=10.6, textColor=INK),
        "right": ParagraphStyle("right", fontName="Helvetica", fontSize=8.4, leading=10.6, alignment=2, textColor=MUTED),
    }


def generate_tailored_resume(
    job: dict[str, Any],
    profile: Profile,
    facts: dict[str, Any],
    output_dir: str | Path,
) -> Path:
    """Generate a deterministic, truthful one-page resume tailored to a job."""
    styles = _styles()
    wanted = _job_tokens(job)
    output = Path(output_dir)
    output.mkdir(parents=True, exist_ok=True)
    destination = output / f"Chetan_Gullapalli_{_slug(job['company'])}_{_slug(job['title'])}_Resume.pdf"

    def section(title: str) -> list[Any]:
        rule = Table([[""]], colWidths=[7.15 * inch], rowHeights=[0.5])
        rule.setStyle(TableStyle([("BACKGROUND", (0, 0), (-1, -1), NAVY)]))
        return [Paragraph(title.upper(), styles["section"]), rule, Spacer(1, 2.5)]

    def row(left: str, right: str) -> Table:
        table = Table(
            [[Paragraph(left, styles["title"]), Paragraph(right, styles["right"])]],
            colWidths=[5.55 * inch, 1.6 * inch],
            hAlign="LEFT",
        )
        table.setStyle(TableStyle([
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("LEFTPADDING", (0, 0), (-1, -1), 0),
            ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
        ]))
        return table

    def add_entries(story: list[Any], entries: list[dict[str, Any]], limit: int) -> None:
        for index, entry in enumerate(entries[:limit]):
            story.append(row(entry["name"], entry.get("dates", "")))
            for bullet_text in entry.get("bullets", [])[:2]:
                story.append(Paragraph(f"- {bullet_text}", styles["bullet"]))
            if index + 1 < min(limit, len(entries)):
                story.append(Spacer(1, 1))

    contact = facts["contact"]
    links = " &nbsp;|&nbsp; ".join(
        [contact["phone"], contact["email"], contact["linkedin"], contact["github"], contact["website"]]
    )
    focus_rules = [
        ("algorithms", {"algorithms", "algorithmic"}),
        ("cloud computing", {"cloud", "infrastructure", "platform"}),
        ("agentic software engineering", {"agentic", "llm", "agents"}),
        ("distributed systems", {"distributed", "scalable", "platform"}),
        ("cybersecurity", {"cybersecurity", "security"}),
        ("software engineering", {"software", "engineering", "systems", "technology"}),
    ]
    focus_candidates = [phrase for phrase, signals in focus_rules if signals & wanted]
    focus = ", ".join(focus_candidates[:3]) or "software engineering and dependable systems"
    impact = " public-impact" if {"public", "government", "defence", "healthtech"} & wanted else ""
    summary = (
        f"Singapore citizen and NUS Computer Science and Mathematics undergraduate (GPA {profile.gpa}/{profile.gpa_scale}) "
        f"with full-stack engineering, automated testing, computational thinking, and large-team leadership experience. "
        f"Interested in {focus} and building dependable{impact} technology."
    )

    story: list[Any] = [
        Paragraph(facts["name"], styles["name"]),
        Paragraph(links, styles["contact"]),
        *section("Profile"),
        Paragraph(summary, styles["body"]),
        *section("Education"),
        row(facts["education"]["programme"], facts["education"]["dates"]),
        Paragraph(f"Relevant Coursework: {', '.join(facts['education']['coursework'])}", styles["small"]),
        *section("Technical Skills"),
    ]

    for category, values in facts["skills"].items():
        ordered = sorted(values, key=lambda item: (not bool(_tokens(item) & wanted), values.index(item)))
        story.append(Paragraph(f"<b>{category}:</b> {', '.join(ordered)}", styles["small"]))

    story += section("Projects")
    add_entries(story, _ranked(facts.get("projects", []), wanted), 2)
    story += section("Experience")
    add_entries(story, _ranked(facts.get("experience", []), wanted), 1)
    story += section("Leadership")
    add_entries(story, _ranked(facts.get("leadership", []), wanted), 2)
    story += section("Certifications")
    certifications = sorted(
        facts.get("certifications", []),
        key=lambda item: (not bool(_tokens(item) & wanted), facts["certifications"].index(item)),
    )[:4]
    story.append(Paragraph("; ".join(certifications), styles["small"]))

    doc = BaseDocTemplate(
        str(destination),
        pagesize=letter,
        leftMargin=0.48 * inch,
        rightMargin=0.48 * inch,
        topMargin=0.36 * inch,
        bottomMargin=0.36 * inch,
        title=f"{facts['name']} - {job['title']} Resume",
        author=facts["name"],
        subject=f"Resume tailored to {job['title']} at {job['company']}",
    )
    frame = Frame(doc.leftMargin, doc.bottomMargin, doc.width, doc.height, id="resume", leftPadding=0, rightPadding=0, topPadding=0, bottomPadding=0)
    doc.addPageTemplates([PageTemplate(id="resume-page", frames=[frame])])
    doc.build(story)

    pages = len(PdfReader(str(destination)).pages)
    if pages != 1:
        destination.unlink(missing_ok=True)
        raise ValueError(f"Generated resume was {pages} pages; refusing to attach it")
    return destination
