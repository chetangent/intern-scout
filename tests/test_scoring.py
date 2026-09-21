import unittest

from intern_scout.models import Job, Profile, infer_date_range
from intern_scout.scoring import score_job


def profile() -> Profile:
    return Profile.from_dict(
        {
            "name": "Chetan",
            "citizenship": "Singapore citizen",
            "gpa": 4.0,
            "gpa_scale": 5.0,
            "degree": "Computer Science",
            "graduation_date": "2029-05",
            "availability": [
                {"start": "2027-05-01", "end": "2027-08-15", "label": "summer"},
                {"start": "2027-08-01", "end": "2027-12-31", "label": "semester"},
            ],
            "interests": ["cloud computing", "software engineering"],
            "skills": ["Python", "Java"],
            "preferred_sectors": ["public sector"],
            "preferred_work_styles": ["hybrid"],
            "defence_roles_ok": True,
        }
    )


class ScoringTests(unittest.TestCase):
    def test_infers_month_range_from_title(self) -> None:
        self.assertEqual(
            infer_date_range("Uni Internship Jan to July 2027 - Cloud"),
            ("2027-01-01", "2027-07-31"),
        )

    def test_inferred_incompatible_dates_are_ineligible(self) -> None:
        job = Job(
            source="test",
            title="Uni Internship Jan to July 2027 - Cloud",
            company="Agency",
            location="Singapore",
            url="https://example.gov.sg/job/4",
        )
        assessment = score_job(job, profile())
        self.assertEqual(assessment.eligibility, "ineligible")

    def test_ite_role_is_ineligible_for_university_profile(self) -> None:
        job = Job(
            source="test",
            title="ITE Internship Oct 2026 to Sep 2027",
            company="Agency",
            location="Singapore",
            url="https://example.gov.sg/job/5",
        )
        assessment = score_job(job, profile())
        self.assertEqual(assessment.eligibility, "ineligible")
        self.assertIn("Role is restricted to ITE students", assessment.eligibility_reasons)

    def test_matching_public_hybrid_role_scores_highly(self) -> None:
        job = Job(
            source="test",
            title="Cloud Software Engineering Intern",
            company="GovTech",
            location="Singapore",
            url="https://example.gov.sg/job/1",
            description="Public-sector hybrid internship with Python, Java and structured mentorship.",
            start_date="2027-05-10",
            end_date="2027-08-01",
        )
        assessment = score_job(job, profile())
        self.assertEqual(assessment.eligibility, "eligible")
        self.assertGreaterEqual(assessment.score, 85)

    def test_january_to_june_role_is_ineligible(self) -> None:
        job = Job(
            source="test",
            title="Software Engineer Intern",
            company="Cloud Company",
            location="Singapore",
            url="https://example.com/job/2",
            start_date="2027-01-04",
            end_date="2027-06-30",
        )
        assessment = score_job(job, profile())
        self.assertEqual(assessment.eligibility, "ineligible")
        self.assertTrue(any("outside availability" in reason for reason in assessment.eligibility_reasons))

    def test_citizenship_requirement_is_satisfied(self) -> None:
        job = Job(
            source="test",
            title="Technology Intern",
            company="Agency",
            location="Singapore",
            url="https://example.gov.sg/job/3",
            description="Applicants must be Singapore Citizens.",
            start_date="2027-08-01",
            end_date="2027-12-01",
        )
        assessment = score_job(job, profile())
        self.assertEqual(assessment.eligibility, "eligible")
        self.assertTrue(any("citizen" in reason.lower() for reason in assessment.eligibility_reasons))


if __name__ == "__main__":
    unittest.main()
