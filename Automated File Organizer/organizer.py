#!/usr/bin/env python3
"""Automated File Organizer.

Scans a directory (non-recursively) and moves every file into a sub-folder
chosen by its extension (images, documents, videos, ...). Existing files are
never overwritten: on a name clash the incoming file gets a numeric suffix
(``photo_1.jpg``) or a timestamp suffix.

Only the Python standard library is used.

Exit codes:
    0  finished without errors
    1  finished, but at least one file could not be processed
    2  invalid target path / bad arguments
    130  interrupted by the user (Ctrl+C)
"""

from __future__ import annotations

import argparse
import logging
import os
import shutil
import stat
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Mapping, Optional, Sequence

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Folder name -> extensions (lower-case, with leading dot). Edit freely.
EXTENSION_MAP: dict[str, tuple[str, ...]] = {
    "images": (".jpg", ".jpeg", ".png", ".gif", ".bmp", ".tiff", ".webp",
               ".svg", ".heic", ".ico"),
    "documents": (".pdf", ".doc", ".docx", ".txt", ".rtf", ".odt", ".xls",
                  ".xlsx", ".ppt", ".pptx", ".csv", ".md"),
    "videos": (".mp4", ".mkv", ".mov", ".avi", ".wmv", ".flv", ".webm"),
    "audio": (".mp3", ".wav", ".flac", ".aac", ".ogg", ".m4a"),
    "archives": (".zip", ".rar", ".7z", ".tar", ".gz", ".bz2", ".xz"),
    "code": (".py", ".js", ".ts", ".html", ".css", ".java", ".c", ".cpp",
             ".h", ".go", ".rs", ".sh", ".json", ".yaml", ".yml", ".sql"),
}
DEFAULT_FOLDER = "others"  # files with unknown or no extension
DEFAULT_LOG_FILE = "organizer.log"
LOGGER_NAME = "organizer"
DRY_PREFIX = "[DRY-RUN] "
SUMMARY = {"summary": True}  # marks log records that always show on console


# --------------------------------------------------------------------------- #
# Data / logging helpers
# --------------------------------------------------------------------------- #
@dataclass
class Stats:
    """Counters for a run. ``renamed`` is a subset of ``moved``."""

    moved: int = 0
    renamed: int = 0
    skipped: int = 0
    errors: int = 0  # subset of ``skipped`` caused by failures


class ConsoleFilter(logging.Filter):
    """Keep the console short: summary + warnings, or everything if verbose."""

    def __init__(self, verbose: bool) -> None:
        super().__init__()
        self.verbose = verbose

    def filter(self, record: logging.LogRecord) -> bool:
        return self.verbose or bool(getattr(record, "summary", False))


def close_logging(logger: logging.Logger) -> None:
    """Detach and close every handler so file handles are released."""
    for handler in list(logger.handlers):
        logger.removeHandler(handler)
        handler.close()


def setup_logging(log_file: Path, verbose: bool = False) -> logging.Logger:
    """Configure the organizer logger.

    The log file receives every event. The console shows a short summary
    (or every move with ``verbose``); warnings and errors go to stderr.
    If the log file cannot be opened, the script continues console-only.
    """
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.propagate = False
    close_logging(logger)

    out = logging.StreamHandler(sys.stdout)
    out.setLevel(logging.INFO)
    out.addFilter(lambda record: record.levelno < logging.WARNING)
    out.addFilter(ConsoleFilter(verbose))
    out.setFormatter(logging.Formatter("%(message)s"))
    logger.addHandler(out)

    err = logging.StreamHandler(sys.stderr)
    err.setLevel(logging.WARNING)
    err.setFormatter(logging.Formatter("%(levelname)s: %(message)s"))
    logger.addHandler(err)

    try:
        file_handler = logging.FileHandler(log_file, encoding="utf-8")
    except OSError as exc:
        logger.warning("Cannot open log file %s (%s); console only.",
                       log_file, exc)
    else:
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(logging.Formatter(
            "%(asctime)s | %(levelname)-8s | %(message)s"))
        logger.addHandler(file_handler)
    return logger


# --------------------------------------------------------------------------- #
# Core logic
# --------------------------------------------------------------------------- #
def build_extension_lookup(mapping: Mapping[str, Sequence[str]]) -> dict[str, str]:
    """Invert ``{folder: extensions}`` into ``{extension: folder}``."""
    return {ext.lower(): folder
            for folder, extensions in mapping.items()
            for ext in extensions}


def categorize(path: Path, lookup: Mapping[str, str]) -> str:
    """Return the destination folder name for ``path``."""
    return lookup.get(path.suffix.lower(), DEFAULT_FOLDER)


def is_hidden(path: Path) -> bool:
    """True for dot-files (Unix) and files with the hidden attribute (Windows)."""
    if path.name.startswith("."):
        return True
    try:
        attributes = getattr(path.stat(), "st_file_attributes", 0)
    except OSError:
        return False
    return bool(attributes & stat.FILE_ATTRIBUTE_HIDDEN)


def skip_reason(path: Path, include_hidden: bool,
                ignore: set[Path]) -> Optional[str]:
    """Return why ``path`` must be skipped, or None if it can be moved."""
    if path.is_symlink():
        return "symbolic link"
    if not include_hidden and is_hidden(path):
        return "hidden file"
    try:
        resolved = path.resolve()
    except OSError:
        resolved = path
    if resolved in ignore:
        return "organizer's own file"
    return None


def _is_taken(path: Path, reserved: Optional[set[Path]]) -> bool:
    """True if ``path`` exists (even as a broken symlink) or is reserved."""
    return path.exists() or path.is_symlink() or (
        reserved is not None and path in reserved)


def get_unique_destination(dest: Path, reserved: Optional[set[Path]] = None,
                           strategy: str = "number") -> Path:
    """Return a destination path that does not collide with anything.

    ``photo.jpg`` becomes ``photo_1.jpg``, ``photo_2.jpg``, ... or, with the
    ``timestamp`` strategy, ``photo_20261019_203300.jpg``. ``reserved`` holds
    destinations already planned in a dry run (nothing exists on disk yet).
    """
    if not _is_taken(dest, reserved):
        return dest

    stem, suffix = dest.stem, dest.suffix
    if strategy == "timestamp":
        stem = f"{stem}_{datetime.now():%Y%m%d_%H%M%S}"
        candidate = dest.with_name(f"{stem}{suffix}")
        if not _is_taken(candidate, reserved):
            return candidate

    counter = 1
    while True:
        candidate = dest.with_name(f"{stem}_{counter}{suffix}")
        if not _is_taken(candidate, reserved):
            return candidate
        counter += 1


def collect_files(target: Path, stats: Stats,
                  logger: logging.Logger) -> list[Path]:
    """List regular files (and symlinks) directly inside ``target``."""
    try:
        entries = sorted(target.iterdir(), key=lambda p: p.name.lower())
    except OSError as exc:
        logger.error("Cannot read directory %s: %s", target, exc)
        stats.errors += 1
        return []

    files: list[Path] = []
    for entry in entries:
        try:
            if entry.is_symlink() or entry.is_file():
                files.append(entry)
        except OSError as exc:
            logger.warning("Cannot inspect %s: %s", entry, exc)
            stats.skipped += 1
            stats.errors += 1
    return files


def process_file(src: Path, target: Path, lookup: Mapping[str, str],
                 stats: Stats, reserved: set[Path], *, dry_run: bool,
                 strategy: str, logger: logging.Logger) -> None:
    """Move (or simulate moving) one file, updating ``stats``."""
    prefix = DRY_PREFIX if dry_run else ""
    dest_dir = target / categorize(src, lookup)
    dest = get_unique_destination(dest_dir / src.name,
                                  reserved if dry_run else None, strategy)
    renamed = dest.name != src.name

    try:
        if not dry_run:
            dest_dir.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dest))
    except PermissionError as exc:
        logger.error("%sPermission denied, skipped %s: %s", prefix, src, exc)
        stats.skipped += 1
        stats.errors += 1
        return
    except OSError as exc:
        logger.error("%sFailed to move %s: %s", prefix, src, exc)
        stats.skipped += 1
        stats.errors += 1
        return

    if dry_run:
        reserved.add(dest)
    stats.moved += 1
    if renamed:
        stats.renamed += 1
        logger.info("%sMOVED+RENAMED %s -> %s | %s -> %s",
                    prefix, src.name, dest.name, src, dest)
    else:
        logger.info("%sMOVED %s | %s -> %s", prefix, src.name, src, dest)


def organize(target: Path, *, dry_run: bool = False,
             include_hidden: bool = False, strategy: str = "number",
             ignore: Optional[set[Path]] = None,
             logger: Optional[logging.Logger] = None) -> Stats:
    """Organize the files directly inside ``target`` and return the counters."""
    logger = logger or logging.getLogger(LOGGER_NAME)
    ignore = ignore or set()
    stats = Stats()
    lookup = build_extension_lookup(EXTENSION_MAP)

    files = collect_files(target, stats, logger)
    if not files:
        if not stats.errors:
            logger.info("Nothing to organize: no files found in %s", target,
                        extra=SUMMARY)
        return stats

    reserved: set[Path] = set()
    for src in files:
        reason = skip_reason(src, include_hidden, ignore)
        if reason:
            stats.skipped += 1
            logger.info("%sSKIPPED %s (%s)", DRY_PREFIX if dry_run else "",
                        src, reason)
            continue
        process_file(src, target, lookup, stats, reserved, dry_run=dry_run,
                     strategy=strategy, logger=logger)
    return stats


def print_summary(stats: Stats, target: Path, dry_run: bool) -> None:
    """Log the final counters (always visible on the console)."""
    logger = logging.getLogger(LOGGER_NAME)
    verb = "Would move" if dry_run else "Moved"
    logger.info("-" * 44, extra=SUMMARY)
    logger.info("%sSummary for %s", DRY_PREFIX if dry_run else "", target,
                extra=SUMMARY)
    logger.info("  %-11s %d (renamed on conflict: %d)", verb + ":",
                stats.moved, stats.renamed, extra=SUMMARY)
    logger.info("  %-11s %d (failed: %d)", "Skipped:", stats.skipped,
                stats.errors, extra=SUMMARY)


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #
def validate_target(raw: str) -> Path:
    """Resolve and validate the target directory or raise a clear error."""
    path = Path(raw).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"Target path does not exist: {path}")
    if not path.is_dir():
        raise NotADirectoryError(f"Target is not a directory: {path}")
    if not os.access(path, os.R_OK | os.X_OK):
        raise PermissionError(f"No permission to read directory: {path}")
    resolved = path.resolve()
    if resolved.parent == resolved:
        raise ValueError("Refusing to organize a filesystem root.")
    return resolved


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Move files into sub-folders by extension, never "
                    "overwriting existing files.",
        epilog="example: python organizer.py ~/Downloads --dry-run",
    )
    parser.add_argument("target", help="directory to organize")
    parser.add_argument("-n", "--dry-run", action="store_true",
                        help="preview all moves without touching any file")
    parser.add_argument("-v", "--verbose", action="store_true",
                        help="show every move on the console")
    parser.add_argument("--include-hidden", action="store_true",
                        help="also organize hidden files (skipped by default)")
    parser.add_argument("--on-conflict", choices=("number", "timestamp"),
                        default="number",
                        help="how to rename on a name clash (default: number)")
    parser.add_argument("--log-file", type=Path,
                        default=Path(DEFAULT_LOG_FILE),
                        help=f"log file path (default: ./{DEFAULT_LOG_FILE})")
    return parser.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    """Entry point. Returns a process exit code and never raises."""
    args = parse_args(argv)
    logger = setup_logging(args.log_file, args.verbose)
    try:
        try:
            target = validate_target(args.target)
        except (OSError, ValueError) as exc:
            logger.error("%s", exc)
            return 2

        logger.debug("Run started: target=%s dry_run=%s include_hidden=%s "
                     "on_conflict=%s", target, args.dry_run,
                     args.include_hidden, args.on_conflict)
        ignore = {args.log_file.resolve(), Path(__file__).resolve()}
        stats = organize(target, dry_run=args.dry_run,
                         include_hidden=args.include_hidden,
                         strategy=args.on_conflict, ignore=ignore,
                         logger=logger)
        print_summary(stats, target, args.dry_run)
        return 1 if stats.errors else 0
    except KeyboardInterrupt:
        logger.warning("Interrupted by user.")
        return 130
    except Exception as exc:  # last-resort guard: never show a traceback
        logger.error("Unexpected error: %s", exc)
        logger.debug("Details", exc_info=True)  # traceback goes to the log file
        return 1
    finally:
        close_logging(logger)


if __name__ == "__main__":
    sys.exit(main())
