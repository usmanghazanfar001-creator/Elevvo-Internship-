"""Bonus scraper: Arbeitnow's public job board API (https://www.arbeitnow.com).

Why Arbeitnow?
* Its robots.txt allows all paths (checked in code on every run).
* It publishes a free, documented JSON API for exactly this use.
* Be a good citizen: polite delay, clear User-Agent, few pages, and credit
  Arbeitnow as the data source wherever you show the results.

Please also read Arbeitnow's terms of service yourself before using the data
beyond this learning project - terms can change.

The API has no "skills" field, so skills are extracted from the HTML job
description with BeautifulSoup and a keyword list (SKILL_KEYWORDS).
"""

from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import requests
from bs4 import BeautifulSoup

from scraper import (
    USER_AGENT,
    FetchError,
    RobotsDisallowedError,
    check_robots,
    fetch_with_retry,
)

logger = logging.getLogger(__name__)

API_URL = "https://www.arbeitnow.com/api/job-board-api"
SOURCE_NAME = "Arbeitnow (https://www.arbeitnow.com)"

SKILL_KEYWORDS = [
    "python", "java", "javascript", "typescript", "c++", "c#", "go", "rust",
    "php", "ruby", "swift", "kotlin", "sql", "postgresql", "mysql", "mongodb",
    "redis", "react", "angular", "vue", "node.js", "django", "flask",
    "fastapi", "spring", "docker", "kubernetes", "aws", "azure", "gcp",
    "terraform", "linux", "git", "ci/cd", "rest", "graphql", "pandas",
    "numpy", "tensorflow", "pytorch", "machine learning", "excel", "power bi",
    "tableau", "scrum", "agile",
]
# Word-boundary-ish patterns; lookarounds handle symbols like "c++" and "c#".
_SKILL_PATTERNS = {
    skill: re.compile(rf"(?<![\w+#.]){re.escape(skill)}(?![\w+#])", re.IGNORECASE)
    for skill in SKILL_KEYWORDS
}


def extract_skills(description_html: str) -> list[str]:
    """Find known skill keywords in an HTML job description."""
    text = BeautifulSoup(description_html or "", "html.parser").get_text(" ")
    return [skill for skill, pattern in _SKILL_PATTERNS.items() if pattern.search(text)]


def _to_iso_date(timestamp: Any) -> Optional[str]:
    """Convert a Unix timestamp (seconds) to YYYY-MM-DD; None if invalid."""
    try:
        return datetime.fromtimestamp(int(timestamp), tz=timezone.utc).strftime("%Y-%m-%d")
    except (TypeError, ValueError, OverflowError, OSError):
        return None


def parse_job(item: dict[str, Any]) -> dict[str, Any]:
    """Map one API job object to our common record format (never raises)."""
    return {
        "title": item.get("title"),
        "company": item.get("company_name"),
        "location": item.get("location"),
        "skills": extract_skills(item.get("description", "")),
        "posted_date": _to_iso_date(item.get("created_at")),
    }


@dataclass
class ArbeitnowScraper:
    """Fetch a few pages of jobs from the Arbeitnow API, politely."""

    api_url: str = API_URL
    max_pages: int = 3
    delay: float = 2.0
    max_retries: int = 3

    def run(self) -> list[dict[str, Any]]:
        """Check robots.txt, then fetch ``max_pages`` pages with a delay."""
        session = requests.Session()
        if not check_robots(self.api_url, USER_AGENT, session=session):
            raise RobotsDisallowedError(f"robots.txt disallows {self.api_url}")

        records: list[dict[str, Any]] = []
        for page in range(1, self.max_pages + 1):
            if page > 1:
                time.sleep(self.delay)
            try:
                response = fetch_with_retry(
                    self.api_url, session, params={"page": page},
                    max_retries=self.max_retries,
                )
                payload = response.json()
            except (FetchError, ValueError) as exc:  # ValueError: bad JSON
                logger.error("Page %d failed: %s", page, exc)
                if page == 1:
                    raise FetchError(f"Could not load first page: {exc}") from exc
                break

            jobs = payload.get("data", []) if isinstance(payload, dict) else []
            if not jobs:
                logger.info("Page %d empty; stopping.", page)
                break
            records.extend(parse_job(job) for job in jobs if isinstance(job, dict))
            logger.info("Page %d: %d jobs", page, len(jobs))

        logger.info("Source: %s - %d raw listings", SOURCE_NAME, len(records))
        return records
