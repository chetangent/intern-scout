from __future__ import annotations

import json
import re
import time
import urllib.robotparser
from html.parser import HTMLParser
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin, urlsplit
from urllib.request import Request, urlopen

from .models import Job


USER_AGENT = "InternScout/0.1 (+personal internship research; respectful rate limiting)"


class ExtractionError(RuntimeError):
    pass


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.anchors: list[tuple[str, str]] = []
        self.json_ld: list[str] = []
        self.title = ""
        self._anchor_href: str | None = None
        self._anchor_text: list[str] = []
        self._in_json_ld = False
        self._script_text: list[str] = []
        self._in_title = False
        self._title_text: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        if tag.lower() == "a" and attrs_dict.get("href"):
            self._anchor_href = attrs_dict["href"]
            self._anchor_text = []
        elif tag.lower() == "script" and (attrs_dict.get("type") or "").lower() == "application/ld+json":
            self._in_json_ld = True
            self._script_text = []
        elif tag.lower() == "title":
            self._in_title = True
            self._title_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "a" and self._anchor_href is not None:
            self.anchors.append((self._anchor_href, " ".join("".join(self._anchor_text).split())))
            self._anchor_href = None
            self._anchor_text = []
        elif tag.lower() == "script" and self._in_json_ld:
            self.json_ld.append("".join(self._script_text).strip())
            self._in_json_ld = False
            self._script_text = []
        elif tag.lower() == "title" and self._in_title:
            self.title = " ".join("".join(self._title_text).split())
            self._in_title = False

    def handle_data(self, data: str) -> None:
        if self._anchor_href is not None:
            self._anchor_text.append(data)
        if self._in_json_ld:
            self._script_text.append(data)
        if self._in_title:
            self._title_text.append(data)


def _robots_allowed(url: str, opener: Callable[..., Any] = urlopen) -> bool:
    parts = urlsplit(url)
    robots_url = f"{parts.scheme}://{parts.netloc}/robots.txt"
    parser = urllib.robotparser.RobotFileParser()
    parser.set_url(robots_url)
    try:
        request = Request(robots_url, headers={"User-Agent": USER_AGENT})
        with opener(request, timeout=10) as response:
            parser.parse(response.read().decode("utf-8", errors="replace").splitlines())
    except (HTTPError, URLError, TimeoutError, OSError):
        return True
    return parser.can_fetch(USER_AGENT, url)


def fetch_html(url: str, *, timeout: int = 20, opener: Callable[..., Any] = urlopen) -> str:
    if not _robots_allowed(url, opener=opener):
        raise ExtractionError(f"robots.txt disallows collection: {url}")
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"})
    try:
        with opener(request, timeout=timeout) as response:
            content_type = response.headers.get_content_charset() or "utf-8"
            return response.read().decode(content_type, errors="replace")
    except (HTTPError, URLError, TimeoutError, OSError) as exc:
        raise ExtractionError(f"could not fetch {url}: {exc}") from exc


def _iter_json_objects(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _iter_json_objects(child)
    elif isinstance(value, list):
        for child in value:
            yield from _iter_json_objects(child)


def _plain_text(value: Any) -> str:
    text = re.sub(r"<[^>]+>", " ", str(value or ""))
    return " ".join(text.split())


def _location_from_json(data: dict[str, Any]) -> str:
    location = data.get("jobLocation") or data.get("applicantLocationRequirements") or "Singapore"
    if isinstance(location, list):
        location = location[0] if location else {}
    if isinstance(location, str):
        return location
    if isinstance(location, dict):
        address = location.get("address", location)
        if isinstance(address, str):
            return address
        if isinstance(address, dict):
            parts = [address.get(key, "") for key in ("addressLocality", "addressRegion", "addressCountry")]
            return ", ".join(part for part in parts if part) or "Singapore"
    return "Singapore"


def jobs_from_json_ld(parser: PageParser, page_url: str, source: dict[str, Any]) -> list[Job]:
    jobs: list[Job] = []
    for block in parser.json_ld:
        try:
            payload = json.loads(block)
        except json.JSONDecodeError:
            continue
        for item in _iter_json_objects(payload):
            item_type = item.get("@type", "")
            types = item_type if isinstance(item_type, list) else [item_type]
            if "JobPosting" not in types:
                continue
            organisation = item.get("hiringOrganization") or {}
            company = organisation.get("name", "") if isinstance(organisation, dict) else str(organisation)
            identifier = item.get("identifier") or ""
            if isinstance(identifier, dict):
                identifier = identifier.get("value", "")
            jobs.append(
                Job(
                    source=str(source["name"]),
                    source_id=str(identifier),
                    title=str(item.get("title", parser.title or "Internship")),
                    company=str(company or source.get("company", "Unknown company")),
                    location=_location_from_json(item),
                    url=str(item.get("url", page_url)),
                    description=_plain_text(item.get("description", "")),
                    date_posted=str(item.get("datePosted", "")),
                    deadline=str(item.get("validThrough", "")),
                    work_style="remote" if item.get("jobLocationType") == "TELECOMMUTE" else "",
                    tags=list(source.get("tags", [])),
                    raw=item,
                )
            )
    return jobs


def jobs_from_links(parser: PageParser, page_url: str, source: dict[str, Any]) -> list[Job]:
    include_urls = [re.compile(pattern, re.I) for pattern in source.get("include_url_patterns", [])]
    include_titles = [re.compile(pattern, re.I) for pattern in source.get("include_title_patterns", [])]
    exclude_titles = [re.compile(pattern, re.I) for pattern in source.get("exclude_title_patterns", [])]
    jobs: list[Job] = []
    seen: set[str] = set()
    for href, title in parser.anchors:
        absolute_url = urljoin(page_url, href)
        if not title or absolute_url in seen:
            continue
        if include_urls and not any(pattern.search(absolute_url) for pattern in include_urls):
            continue
        if include_titles and not any(pattern.search(title) for pattern in include_titles):
            continue
        if any(pattern.search(title) for pattern in exclude_titles):
            continue
        seen.add(absolute_url)
        jobs.append(
            Job(
                source=str(source["name"]),
                title=title,
                company=str(source.get("company", "Unknown company")),
                location=str(source.get("location", "Singapore")),
                url=absolute_url,
                description=str(source.get("description", "")),
                tags=list(source.get("tags", [])),
            )
        )
    return jobs


def collect_source(source: dict[str, Any], *, html: str | None = None) -> list[Job]:
    page_url = str(source["url"])
    html = fetch_html(page_url) if html is None else html
    parser = PageParser()
    parser.feed(html)
    jobs = jobs_from_json_ld(parser, page_url, source)
    if source.get("mode", "auto") in {"auto", "links"}:
        jobs.extend(jobs_from_links(parser, page_url, source))
    if source.get("emit_page"):
        jobs.append(
            Job(
                source=str(source["name"]),
                title=str(source.get("title", parser.title or "Internship programme")),
                company=str(source.get("company", "Unknown company")),
                location=str(source.get("location", "Singapore")),
                url=page_url,
                description=str(source.get("description", "")),
                work_style=str(source.get("work_style", "")),
                tags=list(source.get("tags", [])),
            )
        )
    unique: dict[str, Job] = {job.fingerprint: job for job in jobs}
    return list(unique.values())


def collect_all(sources: list[dict[str, Any]], *, delay_seconds: float = 1.0) -> tuple[list[Job], list[str]]:
    jobs: list[Job] = []
    errors: list[str] = []
    for index, source in enumerate(sources):
        try:
            jobs.extend(collect_source(source))
        except ExtractionError as exc:
            errors.append(f"{source.get('name', 'unknown source')}: {exc}")
        if index < len(sources) - 1 and delay_seconds:
            time.sleep(delay_seconds)
    return jobs, errors

