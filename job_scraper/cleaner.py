"""Clean raw scraped listings into an analysis-ready pandas DataFrame."""

from __future__ import annotations

import logging
import re
from pathlib import Path
from typing import Any, Iterable, Optional

import pandas as pd

logger = logging.getLogger(__name__)

COLUMNS = ["title", "company", "location", "skills", "posted_date"]
UNKNOWN = "Unknown"

# Small alias table so "JS" and "javascript" count as the same skill.
SKILL_ALIASES = {
    "js": "javascript",
    "py": "python",
    "postgres": "postgresql",
    "node": "node.js",
    "nodejs": "node.js",
    "reactjs": "react",
    "ml": "machine learning",
}


def _normalise_ws(value: Any) -> Optional[str]:
    """Collapse runs of whitespace; return None for empty / null-like values."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return None
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if text and text.lower() not in {"n/a", "na", "none", "null", "-"} else None


def _smart_title(value: Optional[str]) -> Optional[str]:
    """Title-case only strings that are ALL CAPS or all lowercase.

    Mixed-case values such as "IBM", "iOS Developer" or "McKinsey" are kept.
    """
    # pandas turns None into NaN (a float) between .map() calls, so test for str.
    if not isinstance(value, str):
        return None
    return value.title() if value.isupper() or value.islower() else value


def _clean_skills(value: Any) -> list[str]:
    """Return a de-duplicated, lower-cased skill list (order preserved)."""
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return []
    items = re.split(r"[,;|/]+", value) if isinstance(value, str) else list(value)
    cleaned: list[str] = []
    for item in items:
        skill = _normalise_ws(item)
        if not skill:
            continue
        skill = SKILL_ALIASES.get(skill.lower(), skill.lower())
        if skill not in cleaned:
            cleaned.append(skill)
    return cleaned


def clean_jobs(records: Iterable[dict[str, Any]]) -> pd.DataFrame:
    """Turn raw listing dicts into a clean DataFrame.

    Steps: strip whitespace -> standardise case -> split skills into lists ->
    parse dates -> fill missing values -> drop rows without a title -> drop
    duplicates.
    """
    df = pd.DataFrame(list(records))
    for column in COLUMNS:  # tolerate scrapers that omit a column entirely
        if column not in df.columns:
            df[column] = None
    df = df[COLUMNS].copy()
    rows_in = len(df)
    if rows_in == 0:
        logger.warning("No records to clean.")
        return df.assign(posted_date=pd.to_datetime(df["posted_date"]))

    for column in ("title", "company", "location"):
        df[column] = df[column].map(_normalise_ws).map(_smart_title)

    df["skills"] = df["skills"].map(_clean_skills)

    # errors="coerce": unparseable dates become NaT instead of raising.
    # utc=True handles mixed formats/timezones; we then drop tz and the time.
    parsed = pd.to_datetime(df["posted_date"], errors="coerce", utc=True)
    df["posted_date"] = parsed.dt.tz_localize(None).dt.normalize()
    bad_dates = int(parsed.isna().sum())
    if bad_dates:
        logger.warning("%d rows have a missing/unparseable posted date", bad_dates)

    no_title = df["title"].isna()
    if no_title.any():
        logger.warning("Dropping %d rows with no title", int(no_title.sum()))
        df = df[~no_title]

    df["company"] = df["company"].fillna(UNKNOWN)
    df["location"] = df["location"].fillna(UNKNOWN)

    # Skills are lists (unhashable), so dedupe on the scalar columns, comparing
    # titles/companies/locations case-insensitively.
    key = df[["title", "company", "location", "posted_date"]].copy()
    for column in ("title", "company", "location"):
        key[column] = key[column].str.lower()
    df = df[~key.duplicated(keep="first")]

    df = df.reset_index(drop=True)
    logger.info("Cleaned %d raw rows -> %d rows", rows_in, len(df))
    return df


def save_csv(df: pd.DataFrame, path: Path) -> Path:
    """Write ``df`` to CSV; skills are joined with ';' for a flat file."""
    path.parent.mkdir(parents=True, exist_ok=True)
    flat = df.copy()
    flat["skills"] = flat["skills"].map(lambda s: ";".join(s))
    flat.to_csv(path, index=False, date_format="%Y-%m-%d")
    logger.info("Saved %d rows to %s", len(flat), path)
    return path


def load_csv(path: Path) -> pd.DataFrame:
    """Read a CSV written by :func:`save_csv` back into the clean schema."""
    df = pd.read_csv(path, parse_dates=["posted_date"])
    df["skills"] = df["skills"].fillna("").map(
        lambda s: [x for x in s.split(";") if x]
    )
    return df
