import json
import tempfile
import unittest
from pathlib import Path

from intern_scout.applications import prepare_application
from intern_scout.db import initialise, upsert_job
from intern_scout.models import Assessment, Job, Profile
from intern_scout.site_export import export_site


def candidate() -> Profile:
    return Profile.from_dict(
        {
            "name": "Test Candidate",
            "citizenship": "Singapore citizen",
            "gpa": 4.0,
            "gpa_scale": 5,
            "degree": "Computer Science",
            "graduation_date": "2029-05",
            "availability": [{"start": "2027-05-01", "end": "2027-08-15"}],
            "interests": ["cloud computing"],
            "skills": ["Python"],
            "preferred_sectors": ["public sector"],
            "preferred_work_styles": ["hybrid"],
            "defence_roles_ok": True,
        }
    )


class MilestoneTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.db_path = self.root / "jobs.db"
        initialise(self.db_path)
        self.job = Job(
            source="official",
            title="Cloud Engineering Intern",
            company="Example Agency",
            location="Singapore",
            url="https://example.gov.sg/intern",
            description="Build Python cloud services in a hybrid team.",
            tags=["public sector", "cloud"],
        )
        self.job_id = upsert_job(
            self.db_path,
            self.job,
            Assessment(88, ["Cloud match"], "needs_review", ["Confirm dates"]),
        )

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_public_site_export_contains_jobs_not_profile(self) -> None:
        output = export_site(self.db_path, self.root / "site")
        payload = json.loads(output.read_text(encoding="utf-8"))
        self.assertEqual(payload["count"], 1)
        self.assertEqual(payload["jobs"][0]["title"], "Cloud Engineering Intern")
        self.assertEqual(payload["jobs"][0]["key"], self.job.fingerprint)
        self.assertNotIn("profile", payload)
        self.assertNotIn("gpa", output.read_text(encoding="utf-8").lower())

    def test_prepare_application_creates_private_workspace(self) -> None:
        facts = {
            "work_authorisation": "I am a Singapore citizen.",
            "evidence": [
                {
                    "name": "Cloud project",
                    "keywords": ["cloud", "python"],
                    "reason": "building Python cloud services",
                    "bullets": ["Built and tested a service."],
                }
            ],
        }
        output = prepare_application(self.db_path, self.job_id, candidate(), facts, self.root / "applications")
        self.assertEqual(
            {path.name for path in output.iterdir()},
            {"opportunity.md", "resume-plan.md", "draft-answers.md", "checklist.md"},
        )
        self.assertIn("Cloud project", (output / "resume-plan.md").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
