import unittest

from intern_scout.extract import collect_source


class ExtractionTests(unittest.TestCase):
    def test_word_boundary_does_not_match_internet(self) -> None:
        html = '<a href="/internet">Internet Hygiene Portal</a><a href="/intern">Intern Programme</a>'
        source = {
            "name": "Agency",
            "company": "Agency",
            "url": "https://example.gov.sg/careers",
            "mode": "links",
            "include_title_patterns": [r"\bintern(?:ship)?\b"],
        }
        jobs = collect_source(source, html=html)
        self.assertEqual([job.title for job in jobs], ["Intern Programme"])

    def test_extracts_json_ld_job_and_matching_links(self) -> None:
        html = """
        <html><head><title>Jobs</title>
        <script type="application/ld+json">
        {"@context":"https://schema.org","@type":"JobPosting","title":"Cloud Intern",
         "url":"https://jobs.example.com/job/123","description":"Build Python cloud services",
         "hiringOrganization":{"name":"Example"},"jobLocation":{"address":{"addressLocality":"Singapore"}}}
        </script></head><body>
        <a href="/job/456">Software Engineering Intern</a>
        <a href="/about">About us</a>
        </body></html>
        """
        source = {
            "name": "Example careers",
            "company": "Example",
            "url": "https://jobs.example.com/internships",
            "mode": "auto",
            "include_url_patterns": ["/job/"],
            "include_title_patterns": ["intern"],
        }
        jobs = collect_source(source, html=html)
        self.assertEqual({job.title for job in jobs}, {"Cloud Intern", "Software Engineering Intern"})


if __name__ == "__main__":
    unittest.main()
