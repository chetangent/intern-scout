# Intern Scout

Intern Scout is a human-in-the-loop internship discovery and ranking tool for Singapore technology internships.

It intentionally does **not** scrape or automate activity on LinkedIn. It collects from configured public employer pages, checks eligibility, ranks opportunities, produces a digest, and lets the user approve or reject roles before any application work begins.

## Candidate profile

- Singapore citizen
- Computer Science and Mathematics undergraduate, graduating in 2029
- Available May–August 2027 and August–December 2027
- Interested in algorithms, cloud computing, agentic SWE and general software engineering
- Defence roles are acceptable
- Prefers hybrid/remote arrangements and regular office hours

The real local profile is stored in `data/profile.json` and is intentionally excluded from Git. The hosted dashboard uses the name-free [`data/profile.public.json`](data/profile.public.json). Copy [`data/profile.example.json`](data/profile.example.json) when setting up a fresh clone.

## Quick start

Requires Python 3.11 or newer. The application has no runtime dependencies outside the Python standard library.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -e .

cp data/profile.example.json data/profile.json
cp data/candidate_facts.example.json data/candidate_facts.json
# Edit the two local files with truthful personal details.

intern-scout init
intern-scout list
intern-scout digest
intern-scout serve
```

Then open <http://127.0.0.1:8765> to review the ranked queue.

You can also run it without installing:

```bash
PYTHONPATH=src python -m intern_scout.cli init
PYTHONPATH=src python -m intern_scout.cli list
PYTHONPATH=src python -m intern_scout.cli serve
```

## Refresh official sources

```bash
intern-scout refresh
intern-scout refresh --source "Synapxe Internships"
```

The collector:

- checks `robots.txt` before fetching;
- uses a descriptive user agent;
- waits between source requests;
- extracts `JobPosting` JSON-LD when available;
- supports source-specific link filters; and
- reports blocked or unavailable sources without aborting the full refresh.

Sources are configured in [`data/sources.json`](data/sources.json). Add official employer pages there rather than authenticated social-network pages.

## Review workflow

```bash
intern-scout list --eligibility needs_review
intern-scout review 3 approved
intern-scout review 8 rejected
intern-scout list --status approved
```

Supported states are `new`, `approved`, `maybe`, `rejected`, `applied`, `interview`, `offer`, and `closed`.

The SQLite database is stored at `data/intern_scout.db` and deliberately ignored by Git because it contains personal workflow state.

## Prepare an application

Once a role looks promising, create a private application workspace:

```bash
intern-scout prepare 3
```

This writes four files under the ignored `applications/` directory:

- the source opportunity and eligibility record;
- a role-specific resume emphasis plan;
- draft answers for human review; and
- a submission checklist.

The drafts use facts from the ignored `data/candidate_facts.json`. They never invent metrics and never submit anything.

## GitHub Pages

The static dashboard under [`site/`](site/) can be exported locally:

```bash
intern-scout export-site
python -m http.server 8000 --directory site
```

The Pages workflow:

- runs all tests;
- loads the curated opportunities;
- attempts a respectful refresh of official sources;
- exports only public opportunity data;
- deploys the static dashboard; and
- repeats daily at 00:17 UTC / 08:17 Singapore time.

Review decisions on the public site are stored in the visitor's browser using `localStorage`. They are not uploaded. The local profile, GPA, application drafts, resume and SQLite state are excluded from Git.

GitHub repository setup:

```bash
gh auth login --web
gh repo create intern-scout --public --source=. --remote=origin --push
```

In the repository's **Settings → Pages**, choose **GitHub Actions** as the source if it is not selected automatically. The included workflow uses GitHub's supported Pages actions.

## Ranking behaviour

Eligibility is evaluated before preference scoring:

- Singapore or remote location;
- citizenship requirements;
- defence preference;
- internship dates fully contained within an availability window; and
- application deadline.

Ranking then considers interest matches, known skills, public-impact alignment, learning/mentorship signals, hybrid/flexible-work signals, confirmed availability, and deadline urgency. Every score includes human-readable reasons in the CLI, digest and dashboard.

Unknown dates produce `needs_review`; they do not silently become eligible. Known incompatible dates produce `ineligible`.

## Tests

The tests use Python's built-in test runner:

```bash
PYTHONPATH=src python -m unittest discover -s tests -v
```

No test dependency installation is required.

## Current limitation and next milestone

The application workspace now creates role-specific resume guidance and draft answers. The next safe milestone is generating final role-specific resume PDFs from an approved draft, followed by opening the official form for final human review. It should not submit applications or answer declarations autonomously.
