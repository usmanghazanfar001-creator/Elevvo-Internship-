#!/usr/bin/env python3
"""Automated tests for organizer.py. Everything runs in temporary folders.

Run with:  python -m unittest -v test_organizer
"""

from __future__ import annotations

import logging
import os
import tempfile
import unittest
from pathlib import Path

import organizer
from make_sandbox import build_sample_tree


def snapshot(root: Path) -> set[str]:
    """All paths under ``root`` (relative), used to prove nothing changed."""
    return {str(p.relative_to(root)) for p in root.rglob("*")}


class OrganizerTests(unittest.TestCase):
    def setUp(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        base = Path(tmp.name)
        self.root = base / "sandbox"
        self.root.mkdir()
        self.log_file = base / "organizer.log"  # kept outside the sandbox
        build_sample_tree(self.root)

        self.logger = logging.getLogger("organizer_test_quiet")
        self.logger.propagate = False
        self.logger.addHandler(logging.NullHandler())

    def run_organize(self, **kwargs: object) -> organizer.Stats:
        return organizer.organize(self.root, logger=self.logger, **kwargs)

    def test_dry_run_changes_nothing(self) -> None:
        before = snapshot(self.root)
        stats = self.run_organize(dry_run=True)
        self.assertEqual(before, snapshot(self.root))
        self.assertEqual(stats.moved, 11)
        self.assertEqual(stats.renamed, 1)

    def test_never_overwrites_existing_file(self) -> None:
        stats = self.run_organize()
        images = self.root / "images"
        self.assertEqual((images / "photo.jpg").read_text(), "ORIGINAL")
        self.assertEqual((images / "photo_1.jpg").read_text(), "INCOMING")
        self.assertEqual(stats.renamed, 1)
        self.assertFalse((self.root / "photo.jpg").exists())

    def test_categories_and_edge_files(self) -> None:
        self.run_organize()
        self.assertTrue((self.root / "images" / "UPPER.JPG").exists())
        self.assertTrue((self.root / "documents" / "report.pdf").exists())
        self.assertTrue((self.root / "audio" / "song.mp3").exists())
        self.assertTrue((self.root / "videos" / "clip.mp4").exists())
        self.assertTrue((self.root / "archives" / "backup.zip").exists())
        self.assertTrue((self.root / "archives" / "archive.tar.gz").exists())
        self.assertTrue((self.root / "code" / "script.py").exists())
        self.assertTrue((self.root / "others" / "Makefile").exists())
        self.assertTrue((self.root / "others" / "weird.xyz").exists())
        self.assertTrue((self.root / "empty_folder").is_dir())

    def test_hidden_files_skipped_by_default(self) -> None:
        stats = self.run_organize()
        self.assertTrue((self.root / ".hidden_config").exists())
        self.assertEqual(stats.skipped, 1)

    def test_hidden_files_included_on_request(self) -> None:
        self.run_organize(include_hidden=True)
        self.assertFalse((self.root / ".hidden_config").exists())
        self.assertTrue((self.root / "others" / ".hidden_config").exists())

    def test_second_run_numbers_continue(self) -> None:
        self.run_organize()
        (self.root / "photo.jpg").write_text("SECOND", encoding="utf-8")
        self.run_organize()
        self.assertEqual((self.root / "images" / "photo_2.jpg").read_text(),
                         "SECOND")

    def test_timestamp_strategy(self) -> None:
        self.run_organize(strategy="timestamp")
        names = {p.name for p in (self.root / "images").iterdir()}
        self.assertIn("photo.jpg", names)
        self.assertEqual(len([n for n in names if n.startswith("photo_")]), 1)

    def test_empty_directory(self) -> None:
        with tempfile.TemporaryDirectory() as empty:
            stats = organizer.organize(Path(empty), logger=self.logger)
        self.assertEqual((stats.moved, stats.skipped, stats.errors), (0, 0, 0))

    def test_missing_target_returns_2(self) -> None:
        code = organizer.main([str(self.root / "does_not_exist"),
                               "--log-file", str(self.log_file)])
        self.assertEqual(code, 2)

    def test_file_as_target_returns_2(self) -> None:
        code = organizer.main([str(self.root / "report.pdf"),
                               "--log-file", str(self.log_file)])
        self.assertEqual(code, 2)

    def test_main_success_writes_log(self) -> None:
        code = organizer.main([str(self.root), "--log-file",
                               str(self.log_file)])
        self.assertEqual(code, 0)
        self.assertIn("MOVED+RENAMED", self.log_file.read_text("utf-8"))

    @unittest.skipIf(os.name == "nt" or (hasattr(os, "geteuid")
                                          and os.geteuid() == 0),
                     "needs POSIX permissions and a non-root user")
    def test_permission_error_is_handled(self) -> None:
        locked = self.root / "documents"
        locked.mkdir()
        locked.chmod(0o555)
        self.addCleanup(locked.chmod, 0o755)
        stats = self.run_organize()  # must not raise
        self.assertGreaterEqual(stats.errors, 1)
        self.assertTrue((self.root / "report.pdf").exists())  # left in place


if __name__ == "__main__":
    unittest.main(verbosity=2)
