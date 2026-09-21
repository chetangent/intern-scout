import tempfile
import unittest
from pathlib import Path

from intern_scout.db import get_job, initialise, list_jobs, update_status, upsert_job
from intern_scout.models import Assessment, Job


class DatabaseTests(unittest.TestCase):
    def test_upsert_deduplicates_and_preserves_review_status(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "test.db"
            initialise(db_path)
            job = Job(
                source="test",
                title="Intern",
                company="Example",
                location="Singapore",
                url="https://example.com/job/1",
                deadline="2027-02-01",
            )
            assessment = Assessment(80, ["fit"], "needs_review", ["dates"])
            job_id = upsert_job(db_path, job, assessment)
            self.assertTrue(update_status(db_path, job_id, "approved"))
            job.description = "Updated"
            job.deadline = ""
            upsert_job(db_path, job, assessment)
            jobs = list_jobs(db_path)
            self.assertEqual(len(jobs), 1)
            self.assertEqual(jobs[0]["description"], "Updated")
            self.assertEqual(jobs[0]["review_status"], "approved")
            self.assertEqual(jobs[0]["deadline"], "2027-02-01")
            self.assertEqual(get_job(db_path, job_id)["title"], "Intern")


if __name__ == "__main__":
    unittest.main()
