from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .config import load_profile, load_seed_jobs, load_sources
from .applications import approve_application, load_facts, prepare_application
from .dashboard import serve
from .db import VALID_STATUSES, initialise, list_jobs, stats, update_status, upsert_job
from .digest import build_digest, write_digest
from .extract import collect_all
from .scoring import score_job
from .site_export import export_site


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_DB = ROOT / "data" / "intern_scout.db"
DEFAULT_PROFILE = ROOT / "data" / "profile.json"
DEFAULT_SOURCES = ROOT / "data" / "sources.json"
DEFAULT_SEEDS = ROOT / "data" / "seed_jobs.json"
DEFAULT_DIGEST = ROOT / "data" / "digest.md"
DEFAULT_FACTS = ROOT / "data" / "candidate_facts.json"
DEFAULT_APPLICATIONS = ROOT / "applications"
DEFAULT_SITE = ROOT / "site"


def _add_shared(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--db", type=Path, default=DEFAULT_DB, help="SQLite database path")
    parser.add_argument("--profile", type=Path, default=DEFAULT_PROFILE, help="Candidate profile JSON")


def _ingest(db_path: Path, profile_path: Path, jobs) -> int:
    profile = load_profile(profile_path)
    count = 0
    for job in jobs:
        upsert_job(db_path, job, score_job(job, profile))
        count += 1
    return count


def cmd_init(args: argparse.Namespace) -> int:
    initialise(args.db)
    jobs = load_seed_jobs(args.seeds)
    count = _ingest(args.db, args.profile, jobs)
    print(f"Initialised {args.db} with {count} curated opportunities.")
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    initialise(args.db)
    sources = load_sources(args.sources)
    if args.source:
        sources = [source for source in sources if source["name"].lower() == args.source.lower()]
        if not sources:
            print(f"Source not found: {args.source}", file=sys.stderr)
            return 2
    jobs, errors = collect_all(sources, delay_seconds=args.delay)
    count = _ingest(args.db, args.profile, jobs)
    print(f"Collected and ranked {count} opportunities from {len(sources)} sources.")
    for error in errors:
        print(f"warning: {error}", file=sys.stderr)
    return 0 if jobs or not errors else 1


def cmd_list(args: argparse.Namespace) -> int:
    initialise(args.db)
    jobs = list_jobs(args.db, status=args.status, eligibility=args.eligibility, limit=args.limit)
    if args.json:
        print(json.dumps(jobs, indent=2, ensure_ascii=False))
        return 0
    if not jobs:
        print("No matching opportunities.")
        return 0
    print(f"{'ID':>3}  {'SCORE':>5}  {'ELIGIBILITY':<12}  {'STATUS':<9}  ROLE")
    for job in jobs:
        role = f"{job['company']} - {job['title']}"
        print(f"{job['id']:>3}  {job['score']:>5.0f}  {job['eligibility']:<12}  {job['review_status']:<9}  {role[:90]}")
    return 0


def cmd_digest(args: argparse.Namespace) -> int:
    initialise(args.db)
    content = build_digest(args.db, load_profile(args.profile), limit=args.limit)
    output = write_digest(args.output, content)
    print(f"Wrote digest to {output}")
    return 0


def cmd_review(args: argparse.Namespace) -> int:
    initialise(args.db)
    if not update_status(args.db, args.job_id, args.status):
        print(f"Job {args.job_id} not found.", file=sys.stderr)
        return 1
    print(f"Updated job {args.job_id} to {args.status}.")
    return 0


def cmd_stats(args: argparse.Namespace) -> int:
    initialise(args.db)
    print(json.dumps(stats(args.db), indent=2))
    return 0


def cmd_serve(args: argparse.Namespace) -> int:
    initialise(args.db)
    serve(
        args.db,
        host=args.host,
        port=args.port,
        profile_path=args.profile,
        facts_path=args.facts,
        applications_path=args.output,
    )
    return 0


def cmd_export_site(args: argparse.Namespace) -> int:
    initialise(args.db)
    output = export_site(args.db, args.output, limit=args.limit)
    print(f"Exported {output}")
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    initialise(args.db)
    try:
        directory = prepare_application(
            args.db,
            args.job_id,
            load_profile(args.profile),
            load_facts(args.facts),
            args.output,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Prepared application workspace: {directory}")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    initialise(args.db)
    try:
        directory = approve_application(
            args.db,
            args.job_id,
            load_profile(args.profile),
            load_facts(args.facts),
            args.output,
            resume_path=args.resume,
        )
    except (ValueError, FileNotFoundError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    print(f"Approved job {args.job_id} and prepared: {directory}")
    if args.resume is None:
        print("No tailored PDF attached yet; add one before starting the employer form.")
    else:
        print("Tailored resume attached. The application still requires final form review before submission.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="intern-scout", description="Discover, rank, and review internships")
    subparsers = parser.add_subparsers(dest="command", required=True)

    init_parser = subparsers.add_parser("init", help="Create the database and load curated current targets")
    _add_shared(init_parser)
    init_parser.add_argument("--seeds", type=Path, default=DEFAULT_SEEDS)
    init_parser.set_defaults(func=cmd_init)

    refresh_parser = subparsers.add_parser("refresh", help="Collect from configured official sources")
    _add_shared(refresh_parser)
    refresh_parser.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
    refresh_parser.add_argument("--source", help="Refresh only one named source")
    refresh_parser.add_argument("--delay", type=float, default=1.0, help="Seconds between sources")
    refresh_parser.set_defaults(func=cmd_refresh)

    list_parser = subparsers.add_parser("list", help="Show ranked opportunities")
    _add_shared(list_parser)
    list_parser.add_argument("--status", choices=sorted(VALID_STATUSES))
    list_parser.add_argument("--eligibility", choices=["eligible", "needs_review", "ineligible"])
    list_parser.add_argument("--limit", type=int, default=100)
    list_parser.add_argument("--json", action="store_true")
    list_parser.set_defaults(func=cmd_list)

    digest_parser = subparsers.add_parser("digest", help="Write a daily Markdown digest")
    _add_shared(digest_parser)
    digest_parser.add_argument("--output", type=Path, default=DEFAULT_DIGEST)
    digest_parser.add_argument("--limit", type=int, default=20)
    digest_parser.set_defaults(func=cmd_digest)

    review_parser = subparsers.add_parser("review", help="Change an opportunity's review state")
    _add_shared(review_parser)
    review_parser.add_argument("job_id", type=int)
    review_parser.add_argument("status", choices=sorted(VALID_STATUSES))
    review_parser.set_defaults(func=cmd_review)

    stats_parser = subparsers.add_parser("stats", help="Show database counts")
    _add_shared(stats_parser)
    stats_parser.set_defaults(func=cmd_stats)

    serve_parser = subparsers.add_parser("serve", help="Run the local review dashboard")
    _add_shared(serve_parser)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8765)
    serve_parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    serve_parser.add_argument("--output", type=Path, default=DEFAULT_APPLICATIONS)
    serve_parser.set_defaults(func=cmd_serve)

    export_parser = subparsers.add_parser("export-site", help="Export public opportunity data for GitHub Pages")
    _add_shared(export_parser)
    export_parser.add_argument("--output", type=Path, default=DEFAULT_SITE)
    export_parser.add_argument("--limit", type=int, default=500)
    export_parser.set_defaults(func=cmd_export_site)

    prepare_parser = subparsers.add_parser("prepare", help="Create a private application workspace for one job")
    _add_shared(prepare_parser)
    prepare_parser.add_argument("job_id", type=int)
    prepare_parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    prepare_parser.add_argument("--output", type=Path, default=DEFAULT_APPLICATIONS)
    prepare_parser.set_defaults(func=cmd_prepare)

    approve_parser = subparsers.add_parser(
        "approve", help="Approve a viable role and create its private application packet"
    )
    _add_shared(approve_parser)
    approve_parser.add_argument("job_id", type=int)
    approve_parser.add_argument("--facts", type=Path, default=DEFAULT_FACTS)
    approve_parser.add_argument("--output", type=Path, default=DEFAULT_APPLICATIONS)
    approve_parser.add_argument("--resume", type=Path, help="Optimised resume PDF to attach")
    approve_parser.set_defaults(func=cmd_approve)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":
    raise SystemExit(main())
