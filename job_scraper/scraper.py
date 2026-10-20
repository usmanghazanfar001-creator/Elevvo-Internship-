"""HTTP helpers and the practice-page scraper.

This module contains:

* ``check_robots``      - robots.txt compliance check (urllib.robotparser).
* ``fetch_with_retry``  - GET with timeouts and exponential backoff.
* ``PracticePageScraper`` - selector-driven HTML scraper for a listings page.

All CSS selectors live in ``DEFAULT_SELECTORS`` so that a layout change only
needs a config edit, not a code change.
"""

from __future__ import annotations

import logging
import random
import re
import time
from dataclasses import dataclass, field
from typing import Any, Optional
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import requests
from bs4 import BeautifulSoup, Tag

logger = logging.getLogger(__name__)

USER_AGENT = (
    "JobMarketAnalysisBot/1.0 (educational internship project; "
    "contact: your-email@example.com)"
)
DEFAULT_TIMEOUT = 10  # seconds
RETRYABLE_STATUS = {429, 500, 502, 503, 504}

# One dict per listing: the cleaner expects exactly these keys.
RECORD_FIELDS = ("title", "company", "location", "skills", "posted_date")

# Comma-separated selectors act as fallbacks (first match in the document wins).
# EDIT THESE after inspecting the real page (see README, "If the layout changes").
DEFAULT_SELECTORS: dict[str, str] = {
    "card": "div.job-card, div.card-content, article.job, li.job, div.job",
    "title": "h2.title, .job-title, h2, h3.title",
    "company": ".company, h3.company, .company-name",
    "location": ".location, p.location, .job-location",
    "skills": ".skills, .job-skills, .tags",
    "date": "time, .date, .posted, .posted-date",
    "next_page": "a.next, a[rel='next'], li.next a",
}


class RobotsDisallowedError(Exception):
    """Raised when robots.txt forbids fetching a URL for our User-Agent."""


class FetchError(Exception):
    """Raised when a page cannot be fetched after all retries."""


# --------------------------------------------------------------------------- #
# robots.txt
# --------------------------------------------------------------------------- #
def check_robots(
    url: str,
    user_agent: str = USER_AGENT,
    timeout: int = DEFAULT_TIMEOUT,
    session: Optional[requests.Session] = None,
) -> bool:
    """Return True only if robots.txt allows ``user_agent`` to fetch ``url``.

    Policy (follows RFC 9309):
    * robots.txt missing (404 / other 4xx except 401/403): everything allowed.
    * 401/403 on robots.txt, 5xx, or network failure: treated as disallowed
      (fail closed - the polite choice when we cannot verify permission).

    The file is fetched with ``requests`` (so we get a timeout and our own
    User-Agent) and then parsed with ``RobotFileParser.parse``.
    """
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    http = session or requests.Session()
    parser = RobotFileParser()

    try:
        response = http.get(
            robots_url, headers={"User-Agent": user_agent}, timeout=timeout
        )
    except requests.RequestException as exc:
        logger.warning("Could not fetch %s (%s); failing closed.", robots_url, exc)
        print(f"[robots.txt] {robots_url} unreachable -> NOT allowed (fail closed)")
        return False

    if response.status_code in (401, 403) or response.status_code >= 500:
        logger.warning("robots.txt returned %s; failing closed.", response.status_code)
        print(f"[robots.txt] HTTP {response.status_code} -> NOT allowed (fail closed)")
        return False
    if response.status_code >= 400:
        print(f"[robots.txt] none found (HTTP {response.status_code}) -> allowed")
        return True

    parser.parse(response.text.splitlines())
    allowed = parser.can_fetch(user_agent, url)
    verdict = "ALLOWED" if allowed else "DISALLOWED"
    print(f"[robots.txt] {robots_url} -> {verdict} for path "
          f"'{parsed.path or '/'}' (User-Agent: {user_agent.split('/')[0]})")
    delay = parser.crawl_delay(user_agent)
    if delay:
        print(f"[robots.txt] site requests Crawl-delay: {delay}s")
    return allowed


# --------------------------------------------------------------------------- #
# HTTP with retries
# --------------------------------------------------------------------------- #
def fetch_with_retry(
    url: str,
    session: Optional[requests.Session] = None,
    *,
    params: Optional[dict[str, Any]] = None,
    timeout: int = DEFAULT_TIMEOUT,
    max_retries: int = 3,
    backoff_base: float = 1.0,
    user_agent: str = USER_AGENT,
) -> requests.Response:
    """GET ``url``, retrying transient failures with exponential backoff.

    Retries on timeouts, connection errors and 429/5xx responses. The wait is
    ``backoff_base * 2**attempt`` plus up to 0.5s of jitter (1s, 2s, 4s, ...),
    or the server's ``Retry-After`` header when it sends a number of seconds.
    Other 4xx responses are permanent and raise immediately.

    Raises:
        FetchError: after exhausting retries or on a non-retryable status.
    """
    http = session or requests.Session()
    headers = {"User-Agent": user_agent, "Accept": "text/html,application/json"}
    last_error = "unknown error"

    for attempt in range(max_retries + 1):
        wait = backoff_base * (2 ** attempt) + random.uniform(0, 0.5)
        try:
            response = http.get(url, params=params, headers=headers, timeout=timeout)
        except (requests.Timeout, requests.ConnectionError) as exc:
            last_error = f"{type(exc).__name__}: {exc}"
            logger.warning("Attempt %d/%d failed: %s",
                           attempt + 1, max_retries + 1, last_error)
        except requests.RequestException as exc:  # invalid URL etc. - no retry
            raise FetchError(f"Request failed for {url}: {exc}") from exc
        else:
            status = response.status_code
            if status < 400:
                return response
            last_error = f"HTTP {status}"
            if status not in RETRYABLE_STATUS:
                raise FetchError(f"{url} returned non-retryable HTTP {status}")
            retry_after = response.headers.get("Retry-After", "")
            if retry_after.isdigit():
                wait = float(retry_after)
            logger.warning("Attempt %d/%d got HTTP %d.",
                           attempt + 1, max_retries + 1, status)

        if attempt < max_retries:
            logger.info("Retrying in %.1fs ...", wait)
            time.sleep(wait)

    raise FetchError(f"Giving up on {url} after {max_retries + 1} attempts "
                     f"({last_error})")


# --------------------------------------------------------------------------- #
# HTML parsing helpers
# --------------------------------------------------------------------------- #
def _text(node: Optional[Tag]) -> Optional[str]:
    """Return whitespace-normalised text of ``node`` or None if empty/missing."""
    if node is None:
        return None
    value = " ".join(node.get_text(" ", strip=True).split())
    return value or None


def _select_text(card: Tag, selector: str) -> Optional[str]:
    """Text of the first element matching ``selector`` inside ``card``."""
    try:
        return _text(card.select_one(selector))
    except Exception:  # noqa: BLE001 - invalid selector must not crash the run
        logger.error("Invalid CSS selector: %r", selector)
        return None


def _extract_skills(card: Tag, selector: str) -> list[str]:
    """Extract skills from either child elements (tags/list items) or a string."""
    container = card.select_one(selector)
    if container is None:
        return []
    children = container.select("span, li, a, .tag, .badge")
    if children:
        items = [_text(child) or "" for child in children]
    else:
        items = re.split(r"[,;|/\n]+", container.get_text(" ", strip=True))
    return [item.strip() for item in items if item and item.strip()]


def _extract_date(card: Tag, selector: str) -> Optional[str]:
    """Prefer the machine-readable ``datetime`` attribute, else visible text."""
    node = card.select_one(selector)
    if node is None:
        return None
    return node.get("datetime") or _text(node)  # type: ignore[return-value]


def parse_listings(html: str, selectors: dict[str, str]) -> list[dict[str, Any]]:
    """Parse one HTML page into a list of raw listing dicts.

    A missing field becomes ``None`` (or ``[]`` for skills); it never raises.
    """
    soup = BeautifulSoup(html, "html.parser")
    cards = soup.select(selectors["card"])
    if not cards:
        logger.warning("No listing cards matched %r - has the layout changed?",
                       selectors["card"])
        return []

    records: list[dict[str, Any]] = []
    for index, card in enumerate(cards):
        record = {
            "title": _select_text(card, selectors["title"]),
            "company": _select_text(card, selectors["company"]),
            "location": _select_text(card, selectors["location"]),
            "skills": _extract_skills(card, selectors["skills"]),
            "posted_date": _extract_date(card, selectors["date"]),
        }
        missing = [k for k, v in record.items() if v in (None, [])]
        if missing:
            logger.debug("Card %d missing fields: %s", index, missing)
        records.append(record)
    return records


# --------------------------------------------------------------------------- #
# Scraper
# --------------------------------------------------------------------------- #
@dataclass
class PracticePageScraper:
    """Scrape a (possibly paginated) HTML job listings page."""

    url: str
    selectors: dict[str, str] = field(default_factory=lambda: dict(DEFAULT_SELECTORS))
    max_pages: int = 1
    delay: float = 1.5
    max_retries: int = 3
    user_agent: str = USER_AGENT

    def run(self) -> list[dict[str, Any]]:
        """Check robots.txt, then scrape up to ``max_pages`` pages.

        Raises:
            RobotsDisallowedError: if robots.txt does not permit the URL.
            FetchError: if the *first* page cannot be fetched. Later-page
                failures are logged and the records gathered so far returned.
        """
        session = requests.Session()
        if not check_robots(self.url, self.user_agent, session=session):
            raise RobotsDisallowedError(f"robots.txt disallows scraping {self.url}")

        records: list[dict[str, Any]] = []
        next_url: Optional[str] = self.url
        seen_urls: set[str] = set()

        for page_number in range(1, self.max_pages + 1):
            if not next_url or next_url in seen_urls:
                break
            seen_urls.add(next_url)
            if page_number > 1:
                time.sleep(self.delay)  # polite delay between requests
                if not check_robots(next_url, self.user_agent, session=session):
                    logger.warning("Next page disallowed by robots.txt; stopping.")
                    break

            try:
                response = fetch_with_retry(
                    next_url, session, max_retries=self.max_retries,
                    user_agent=self.user_agent,
                )
            except FetchError:
                if page_number == 1:
                    raise
                logger.exception("Stopping pagination at page %d", page_number)
                break

            page_records = parse_listings(response.text, self.selectors)
            logger.info("Page %d: %d listings", page_number, len(page_records))
            records.extend(page_records)
            next_url = self._find_next(response.text, next_url)

        logger.info("Scraped %d raw listings in total", len(records))
        return records

    def _find_next(self, html: str, current_url: str) -> Optional[str]:
        """Return the absolute URL of the next page, if the page has one."""
        link = BeautifulSoup(html, "html.parser").select_one(
            self.selectors.get("next_page", "a.next")
        )
        href = link.get("href") if link else None
        return urljoin(current_url, href) if href else None
