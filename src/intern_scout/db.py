from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Iterator

from .models import Assessment, Job


SCHEMA = """
CREATE TABLE IF NOT EXISTS jobs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    fingerprint TEXT NOT NULL UNIQUE,
    source TEXT NOT NULL,
    source_id TEXT NOT NULL DEFAULT '',
    title TEXT NOT NULL,
    company TEXT NOT NULL,
    location TEXT NOT NULL,
    url TEXT NOT NULL,
    description TEXT NOT NULL DEFAULT '',
    date_posted TEXT NOT NULL DEFAULT '',
    deadline TEXT NOT NULL DEFAULT '',
    start_date TEXT NOT NULL DEFAULT '',
    end_date TEXT NOT NULL DEFAULT '',
    work_style TEXT NOT NULL DEFAULT '',
    tags_json TEXT NOT NULL DEFAULT '[]',
    score REAL NOT NULL DEFAULT 0,
    score_reasons_json TEXT NOT NULL DEFAULT '[]',
    eligibility TEXT NOT NULL DEFAULT 'needs_review',
    eligibility_reasons_json TEXT NOT NULL DEFAULT '[]',
    review_status TEXT NOT NULL DEFAULT 'new',
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL,
    raw_json TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_jobs_score ON jobs(score DESC);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(review_status, eligibility);
"""

VALID_STATUSES = {"new", "approved", "maybe", "rejected", "applied", "interview", "offer", "closed"}


@contextmanager
def connect(path: str | Path) -> Iterator[sqlite3.Connection]:
    db_path = Path(path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(db_path)
    connection.row_factory = sqlite3.Row
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def initialise(path: str | Path) -> None:
    with connect(path) as connection:
        connection.executescript(SCHEMA)


def upsert_job(path: str | Path, job: Job, assessment: Assessment) -> int:
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    with connect(path) as connection:
        connection.execute(
            """
            INSERT INTO jobs (
                fingerprint, source, source_id, title, company, location, url, description,
                date_posted, deadline, start_date, end_date, work_style, tags_json, score,
                score_reasons_json, eligibility, eligibility_reasons_json, first_seen, last_seen, raw_json
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(fingerprint) DO UPDATE SET
                source=excluded.source,
                source_id=CASE WHEN excluded.source_id <> '' THEN excluded.source_id ELSE jobs.source_id END,
                title=excluded.title,
                company=excluded.company,
                location=excluded.location,
                url=excluded.url,
                description=CASE WHEN excluded.description <> '' THEN excluded.description ELSE jobs.description END,
                date_posted=CASE WHEN excluded.date_posted <> '' THEN excluded.date_posted ELSE jobs.date_posted END,
                deadline=CASE WHEN excluded.deadline <> '' THEN excluded.deadline ELSE jobs.deadline END,
                start_date=CASE WHEN excluded.start_date <> '' THEN excluded.start_date ELSE jobs.start_date END,
                end_date=CASE WHEN excluded.end_date <> '' THEN excluded.end_date ELSE jobs.end_date END,
                work_style=CASE WHEN excluded.work_style <> '' THEN excluded.work_style ELSE jobs.work_style END,
                tags_json=excluded.tags_json,
                score=excluded.score,
                score_reasons_json=excluded.score_reasons_json,
                eligibility=excluded.eligibility,
                eligibility_reasons_json=excluded.eligibility_reasons_json,
                last_seen=excluded.last_seen,
                raw_json=excluded.raw_json
            """,
            (
                job.fingerprint,
                job.source,
                job.source_id,
                job.title,
                job.company,
                job.location,
                job.url,
                job.description,
                job.date_posted,
                job.deadline,
                job.start_date,
                job.end_date,
                job.work_style,
                json.dumps(job.tags, ensure_ascii=False),
                assessment.score,
                json.dumps(assessment.score_reasons, ensure_ascii=False),
                assessment.eligibility,
                json.dumps(assessment.eligibility_reasons, ensure_ascii=False),
                now,
                now,
                json.dumps(job.raw, ensure_ascii=False),
            ),
        )
        row = connection.execute("SELECT id FROM jobs WHERE fingerprint = ?", (job.fingerprint,)).fetchone()
        return int(row["id"])


def list_jobs(
    path: str | Path,
    *,
    status: str | None = None,
    eligibility: str | None = None,
    limit: int = 100,
) -> list[dict]:
    clauses: list[str] = []
    parameters: list[object] = []
    if status:
        clauses.append("review_status = ?")
        parameters.append(status)
    if eligibility:
        clauses.append("eligibility = ?")
        parameters.append(eligibility)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    parameters.append(limit)
    with connect(path) as connection:
        rows = connection.execute(
            f"SELECT * FROM jobs {where} ORDER BY score DESC, deadline ASC, id DESC LIMIT ?",
            parameters,
        ).fetchall()
    results: list[dict] = []
    for row in rows:
        item = dict(row)
        for key in ("tags_json", "score_reasons_json", "eligibility_reasons_json", "raw_json"):
            item[key.removesuffix("_json")] = json.loads(item.pop(key))
        results.append(item)
    return results


def get_job(path: str | Path, job_id: int) -> dict | None:
    with connect(path) as connection:
        row = connection.execute("SELECT * FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if row is None:
        return None
    item = dict(row)
    for key in ("tags_json", "score_reasons_json", "eligibility_reasons_json", "raw_json"):
        item[key.removesuffix("_json")] = json.loads(item.pop(key))
    return item


def update_status(path: str | Path, job_id: int, status: str) -> bool:
    if status not in VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}; choose from {sorted(VALID_STATUSES)}")
    with connect(path) as connection:
        cursor = connection.execute("UPDATE jobs SET review_status = ? WHERE id = ?", (status, job_id))
        return cursor.rowcount == 1


def stats(path: str | Path) -> dict[str, int]:
    with connect(path) as connection:
        total = connection.execute("SELECT COUNT(*) AS count FROM jobs").fetchone()["count"]
        rows = connection.execute(
            "SELECT review_status || ':' || eligibility AS key, COUNT(*) AS count FROM jobs GROUP BY key"
        ).fetchall()
    result = {"total": int(total)}
    result.update({str(row["key"]): int(row["count"]) for row in rows})
    return result
