"""Command-line entry point: scrape -> clean -> save -> analyse."""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from analysis import run_analysis
from board_scraper import SOURCE_NAME, ArbeitnowScraper
from cleaner import clean_jobs, save_csv
from scraper import FetchError, PracticePageScraper, RobotsDisallowedError

logger = logging.getLogger("main")
DATA_DIR = Path(__file__).parent / "data"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Job listings scraper & analysis")
    parser.add_argument(
        "--source", choices=["practice", "board"], default="practice",
        help="practice = the Elevvo practice page (default); "
             "board = Arbeitnow public API (bonus)")
    parser.add_argument(
        "--url", default=os.environ.get("ELEVVO_URL", ""),
        help="practice page URL (or set the ELEVVO_URL environment variable)")
    parser.add_argument("--max-pages", type=int, default=None,
                        help="pages to fetch (default: 1 practice / 3 board)")
    parser.add_argument("--delay", type=float, default=2.0,
                        help="seconds to wait between page requests")
    parser.add_argument("--out-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--top", type=int, default=10, help="rows in top-N tables")
    parser.add_argument("-v", "--verbose", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)-7s %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        if args.source == "practice":
            if not args.url.startswith(("http://", "https://")):
                logger.error("Provide the practice page with --url https://... "
                             "(or set ELEVVO_URL).")
                return 2
            scraper = PracticePageScraper(
                args.url, max_pages=args.max_pages or 1, delay=args.delay)
        else:
            scraper = ArbeitnowScraper(
                max_pages=args.max_pages or 3, delay=args.delay)
            print(f"Data source: {SOURCE_NAME} - please credit it if you share results.")
        records = scraper.run()
    except RobotsDisallowedError as exc:
        logger.error("%s - not scraping.", exc)
        return 3
    except FetchError as exc:
        logger.error("Could not download data: %s", exc)
        return 4
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130

    if not records:
        logger.error("0 listings extracted. Check the selectors in scraper.py "
                     "(see README: 'If the layout changes').")
        return 5

    df = clean_jobs(records)
    stem = "jobs_clean" if args.source == "practice" else "jobs_board_clean"
    csv_path = save_csv(df, args.out_dir / f"{stem}.csv")
    run_analysis(df, args.out_dir / f"{stem.replace('_clean', '')}_top_skills.png",
                 top_n=args.top)
    print(f"\nCleaned CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
