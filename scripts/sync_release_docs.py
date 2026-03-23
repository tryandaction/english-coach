#!/usr/bin/env python3
from __future__ import annotations

import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RELEASES = ROOT / "releases"
RELEASE_DOCS = ROOT / "docs" / "release"

DOCS_TO_SYNC = {
    RELEASE_DOCS / "DEPLOYMENT_CHECKLIST.md": RELEASES / "DEPLOYMENT_CHECKLIST.md",
    RELEASE_DOCS / "PRODUCT_EDITIONS.md": RELEASES / "PRODUCT_EDITIONS.md",
    RELEASE_DOCS / "QUICK_START_v2.0.md": RELEASES / "QUICK_START_v2.0.md",
    RELEASE_DOCS / "README.txt": RELEASES / "README.txt",
    RELEASE_DOCS / "README_v2.0.txt": RELEASES / "README_v2.0.txt",
    RELEASE_DOCS / "RELEASE_NOTES_v2.0.md": RELEASES / "RELEASE_NOTES_v2.0.md",
    RELEASE_DOCS / "使用指南.md": RELEASES / "使用指南.md",
}


def main() -> int:
    RELEASES.mkdir(exist_ok=True)
    for src, dst in DOCS_TO_SYNC.items():
        if not src.exists():
            raise FileNotFoundError(f"Missing source doc: {src}")
        shutil.copyfile(src, dst)
        print(f"synced {src.name} -> releases/{dst.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
