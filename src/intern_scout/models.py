from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from hashlib import sha256
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit


def _clean_url(url: str) -> str:
    """Remove tracking parameters while preserving identifiers used by job pages."""
    if not url:
        return ""
    parts = urlsplit(url.strip())
    dropped = {"src", "source", "ref", "refid", "trackingid", "trk", "team"}
    query = [
        (key, value)
        for key, value in parse_qsl(parts.query, keep_blank_values=True)
        if not key.lower().startswith("utm_") and key.lower() not in dropped
    ]
    return urlunsplit((parts.scheme.lower(), parts.netloc.lower(), parts.path.rstrip("/"), urlencode(query), ""))


def parse_date(value: str | date | None) -> date | None:
    if value is None or value == "":
        return None
    if isinstance(value, date):
        return value
    value = value.strip()
    for candidate in (value, value[:10]):
        try:
            return date.fromisoformat(candidate)
        except ValueError:
            continue
    return None


@dataclass(slots=True)
class AvailabilityWindow:
    start: date
    end: date
    label: str = ""

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "AvailabilityWindow":
        start = parse_date(data.get("start"))
        end = parse_date(data.get("end"))
        if not start or not end:
            raise ValueError("Availability windows require ISO start and end dates")
        if end < start:
            raise ValueError("Availability window end cannot precede start")
        return cls(start=start, end=end, label=str(data.get("label", "")))


@dataclass(slots=True)
class Profile:
    name: str
    citizenship: str
    gpa: float | None
    gpa_scale: float | None
    degree: str
    graduation_date: str
    availability: list[AvailabilityWindow]
    interests: list[str]
    skills: list[str]
    preferred_sectors: list[str]
    preferred_work_styles: list[str]
    defence_roles_ok: bool = False
    location: str = "Singapore"

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Profile":
        return cls(
            name=str(data["name"]),
            citizenship=str(data["citizenship"]),
            gpa=float(data["gpa"]) if data.get("gpa") is not None else None,
            gpa_scale=float(data["gpa_scale"]) if data.get("gpa_scale") is not None else None,
            degree=str(data.get("degree", "")),
            graduation_date=str(data.get("graduation_date", "")),
            availability=[AvailabilityWindow.from_dict(item) for item in data.get("availability", [])],
            interests=[str(item) for item in data.get("interests", [])],
            skills=[str(item) for item in data.get("skills", [])],
            preferred_sectors=[str(item) for item in data.get("preferred_sectors", [])],
            preferred_work_styles=[str(item) for item in data.get("preferred_work_styles", [])],
            defence_roles_ok=bool(data.get("defence_roles_ok", False)),
            location=str(data.get("location", "Singapore")),
        )


@dataclass(slots=True)
class Job:
    source: str
    title: str
    company: str
    location: str
    url: str
    description: str = ""
    source_id: str = ""
    date_posted: str = ""
    deadline: str = ""
    start_date: str = ""
    end_date: str = ""
    work_style: str = ""
    tags: list[str] = field(default_factory=list)
    discovered_at: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec="seconds"))
    raw: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.title = " ".join(self.title.split())
        self.company = " ".join(self.company.split())
        self.location = " ".join(self.location.split())
        self.url = _clean_url(self.url)
        self.description = " ".join(self.description.split())
        self.tags = sorted({tag.strip().lower() for tag in self.tags if tag.strip()})

    @property
    def fingerprint(self) -> str:
        if self.url:
            material = self.url.lower()
        else:
            material = "|".join((self.company.lower(), self.title.lower(), self.location.lower()))
        return sha256(material.encode("utf-8")).hexdigest()

    @classmethod
    def from_dict(cls, data: dict[str, Any], *, default_source: str = "seed") -> "Job":
        return cls(
            source=str(data.get("source", default_source)),
            source_id=str(data.get("source_id", data.get("identifier", ""))),
            title=str(data.get("title", "Untitled internship")),
            company=str(data.get("company", "Unknown company")),
            location=str(data.get("location", "Singapore")),
            url=str(data.get("url", "")),
            description=str(data.get("description", "")),
            date_posted=str(data.get("date_posted", "")),
            deadline=str(data.get("deadline", "")),
            start_date=str(data.get("start_date", "")),
            end_date=str(data.get("end_date", "")),
            work_style=str(data.get("work_style", "")),
            tags=list(data.get("tags", [])),
            discovered_at=str(data.get("discovered_at", datetime.now().astimezone().isoformat(timespec="seconds"))),
            raw=dict(data.get("raw", {})),
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Assessment:
    score: float
    score_reasons: list[str]
    eligibility: str
    eligibility_reasons: list[str]
