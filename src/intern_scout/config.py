from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .models import Job, Profile


def load_json(path: str | Path) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_profile(path: str | Path) -> Profile:
    return Profile.from_dict(load_json(path))


def load_sources(path: str | Path) -> list[dict[str, Any]]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError("sources.json must contain a JSON array")
    return [item for item in data if item.get("enabled", True)]


def load_seed_jobs(path: str | Path) -> list[Job]:
    data = load_json(path)
    if not isinstance(data, list):
        raise ValueError("seed_jobs.json must contain a JSON array")
    return [Job.from_dict(item, default_source="curated-seed") for item in data]

