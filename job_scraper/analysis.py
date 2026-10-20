"""Market analysis on the cleaned job listings DataFrame."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional

import matplotlib

matplotlib.use("Agg")  # headless backend: write files, never open a window
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

logger = logging.getLogger(__name__)


def top_skills(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    """Most in-demand skills (each skill counted once per listing)."""
    counts = (
        df["skills"].explode().dropna().loc[lambda s: s != ""]
        .value_counts().head(n)
    )
    out = counts.rename_axis("skill").reset_index(name="listings")
    out["share_%"] = (out["listings"] / max(len(df), 1) * 100).round(1)
    return out


def count_by(df: pd.DataFrame, column: str, n: Optional[int] = None) -> pd.DataFrame:
    """Number of listings per value of ``column`` (title, location, company)."""
    out = df[column].value_counts().rename_axis(column).reset_index(name="jobs")
    return out.head(n) if n else out


def plot_top_skills(skills: pd.DataFrame, path: Path) -> Optional[Path]:
    """Save a horizontal bar chart of the top skills; return the path."""
    if skills.empty:
        logger.warning("No skills found - skipping chart.")
        return None
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered = skills.sort_values("listings")  # biggest bar on top
    fig, ax = plt.subplots(figsize=(8, 5))
    bars = ax.barh(ordered["skill"], ordered["listings"], color="#3b6ea5")
    ax.bar_label(bars, padding=3)
    ax.set_xlabel("Number of listings")
    ax.set_title(f"Top {len(skills)} most in-demand skills")
    ax.spines[["top", "right"]].set_visible(False)
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    logger.info("Saved chart to %s", path)
    return path


def _print_table(title: str, table: pd.DataFrame) -> None:
    print(f"\n=== {title} ===")
    print(table.to_string(index=False) if not table.empty else "(no data)")


def run_analysis(df: pd.DataFrame, chart_path: Path, top_n: int = 10) -> None:
    """Print all summary tables and save the skills chart."""
    if df.empty:
        print("\nNo data to analyse.")
        return

    print(f"\nListings analysed: {len(df)}")
    dates = df["posted_date"].dropna()
    if not dates.empty:
        print(f"Posted between {dates.min():%Y-%m-%d} and {dates.max():%Y-%m-%d}")

    skills = top_skills(df, top_n)
    _print_table(f"Top {top_n} skills", skills)
    _print_table("Most common job titles", count_by(df, "title", top_n))
    _print_table("Jobs per location", count_by(df, "location"))
    _print_table("Jobs per company", count_by(df, "company"))
    plot_top_skills(skills, chart_path)
