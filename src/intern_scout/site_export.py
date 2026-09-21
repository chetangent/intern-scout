from __future__ import annotations

import json
import shutil
from datetime import datetime
from pathlib import Path

from .db import list_jobs


def export_site(db_path: str | Path, site_dir: str | Path, *, limit: int = 500) -> Path:
    destination = Path(site_dir)
    destination.mkdir(parents=True, exist_ok=True)
    jobs = list_jobs(db_path, limit=limit)
    public_jobs = []
    for job in jobs:
        public_jobs.append(
            {
                "id": job["id"],
                "key": job["fingerprint"],
                "title": job["title"],
                "company": job["company"],
                "location": job["location"],
                "url": job["url"],
                "description": job["description"],
                "date_posted": job["date_posted"],
                "deadline": job["deadline"],
                "start_date": job["start_date"],
                "end_date": job["end_date"],
                "work_style": job["work_style"],
                "tags": job["tags"],
                "score": job["score"],
                "score_reasons": job["score_reasons"],
                "eligibility": job["eligibility"],
                "eligibility_reasons": job["eligibility_reasons"],
                "source": job["source"],
            }
        )
    payload = {
        "generated_at": datetime.now().astimezone().isoformat(timespec="seconds"),
        "count": len(public_jobs),
        "jobs": public_jobs,
    }
    output = destination / "jobs.json"
    output.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output


def build_pages_artifact(source_site: str | Path, output_dir: str | Path) -> Path:
    source = Path(source_site)
    destination = Path(output_dir)
    if destination.exists():
        shutil.rmtree(destination)
    shutil.copytree(source, destination)
    return destination
