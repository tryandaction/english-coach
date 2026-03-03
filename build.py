#!/usr/bin/env python3
"""
Build script for english-coach standalone executable.
Usage: python build.py
Output: dist/english-coach.exe (Windows) or dist/english-coach (Linux/Mac)
"""

import subprocess
import sys
import shutil
from pathlib import Path

ROOT = Path(__file__).parent


def main():
    print("=== english-coach build ===")
    print(f"Python: {sys.executable}")
    print(f"Root: {ROOT}")
    print()

    # Clean previous build
    for d in ["build", "dist"]:
        p = ROOT / d
        if p.exists():
            shutil.rmtree(p)
            print(f"Cleaned {d}/")

    # Run PyInstaller
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        str(ROOT / "english_coach.spec"),
    ]
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(ROOT))

    if result.returncode != 0:
        print("\nBuild FAILED.")
        sys.exit(1)

    # Check output
    exe_name = "english-coach.exe" if sys.platform == "win32" else "english-coach"
    exe_path = ROOT / "dist" / exe_name
    if exe_path.exists():
        size_mb = exe_path.stat().st_size / 1024 / 1024
        print(f"\nBuild SUCCESS: {exe_path}  ({size_mb:.1f} MB)")
        print("\nTo distribute:")
        print(f"  1. Copy {exe_path} to any machine")
        print(f"  2. Run: english-coach setup")
        print(f"  3. Run: english-coach ingest ./your-content")
    else:
        print("\nBuild completed but executable not found.")
        sys.exit(1)


if __name__ == "__main__":
    main()
