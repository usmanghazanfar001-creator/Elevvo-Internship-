#!/usr/bin/env python3
"""Create a throw-away sandbox folder with sample files for testing.

Run it, copy the printed path, and point organizer.py at that path. Nothing
outside the temporary folder is ever touched.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

# Files placed at the top level of the sandbox: name -> content.
SAMPLE_FILES: dict[str, str] = {
    "photo.jpg": "INCOMING",       # clashes with images/photo.jpg below
    "UPPER.JPG": "upper-case extension",
    "report.pdf": "pdf",
    "notes.txt": "text",
    "song.mp3": "audio",
    "clip.mp4": "video",
    "backup.zip": "zip",
    "archive.tar.gz": "tarball",
    "script.py": "print('hi')",
    "Makefile": "no extension",
    "weird.xyz": "unknown extension",
    ".hidden_config": "hidden file",
}


def build_sample_tree(root: Path) -> None:
    """Populate ``root`` with sample files, an existing duplicate and an
    empty sub-folder."""
    for name, content in SAMPLE_FILES.items():
        (root / name).write_text(content, encoding="utf-8")
    (root / "images").mkdir()
    (root / "images" / "photo.jpg").write_text("ORIGINAL", encoding="utf-8")
    (root / "empty_folder").mkdir()


def main() -> int:
    """Create the sandbox and print how to use and remove it."""
    root = Path(tempfile.mkdtemp(prefix="organizer_sandbox_"))
    build_sample_tree(root)
    print(f"Sandbox created: {root}\n")
    print("Try:")
    print(f'  python organizer.py "{root}" --dry-run')
    print(f'  python organizer.py "{root}" -v')
    print("\nRemove it afterwards with:")
    print(f'  python -c "import shutil; shutil.rmtree(r\'{root}\')"')
    return 0


if __name__ == "__main__":
    sys.exit(main())
