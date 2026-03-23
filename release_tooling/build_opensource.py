#!/usr/bin/env python3
"""
Build script for english-coach OPEN SOURCE version (self-hosted API keys).
Usage: python build_opensource.py
Output: releases/english-coach-opensource.exe
"""

import subprocess
import sys
import shutil
import os
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

VERSION_FILE = ROOT / "gui" / "version.py"
LICENSE_DEFAULTS_FILE = ROOT / "gui" / "cloud_license_defaults.py"
CONFIG_FILE = ROOT / "config.yaml"
RELEASE_CONFIG_FILE = ROOT / "release_tooling" / "config.release.yaml"
SYNC_RELEASE_DOCS = ROOT / "scripts" / "sync_release_docs.py"
INSTALLER_SCRIPT = ROOT / "release_tooling" / "installers" / "installer_opensource.iss"
BUILD_LOCK_FILE = ROOT / ".build_release.lock"
ZIP_NAME = "english-coach-v2.0.0-opensource.zip"
ZIP_ROOT = "english-coach-opensource"
ZIP_FILES = [
    ".env.example",
    ".env.template",
    "config.yaml",
    "DEPLOYMENT_CHECKLIST.md",
    "english-coach-opensource.exe",
    "PRODUCT_EDITIONS.md",
    "QUICK_START_v2.0.md",
    "README_v2.0.txt",
    "README.txt",
    "RELEASE_NOTES_v2.0.md",
    "使用指南.md",
]
SOURCE_DEFAULT = '''"""
Version configuration for English Coach.
Set at build time to distinguish between opensource and cloud versions.
"""

# This will be set by the build script.
# Keep source-tree runs in opensource mode by default.
VERSION_MODE = "opensource"  # or "cloud"


def is_opensource():
    """Check if this is the opensource version."""
    return VERSION_MODE == "opensource"


def is_cloud():
    """Check if this is the cloud version."""
    return VERSION_MODE == "cloud"


def get_version_mode():
    """Get the current version mode."""
    return VERSION_MODE
'''
SOURCE_LICENSE_DEFAULTS = '''"""
Build-time defaults for the commercial Cloud activation flow.

The source tree keeps these values empty by default.
`build_cloud.py` can temporarily inject public activation settings into this
module before packaging the cloud executable, then restore the file.

Important:
- `WORKER_URL` is public.
- `CLIENT_TOKEN` is the buyer-side activation token for `/activate` and `/verify`.
- It must NOT be the same as the seller/admin token used by key generation.
"""

WORKER_URL = ""
CLIENT_TOKEN = ""
'''


def _find_iscc() -> str | None:
    candidates = [
        shutil.which("ISCC.exe"),
        shutil.which("iscc"),
        str(Path(r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe")),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def _build_installer(releases_dir: Path) -> Path | None:
    iscc = _find_iscc()
    if not iscc:
        print("Skipped installer build: Inno Setup compiler not found")
        return None
    print(f"Building installer with: {iscc}")
    subprocess.run([iscc, str(INSTALLER_SCRIPT)], cwd=str(ROOT), check=True)
    installer_path = releases_dir / "english-coach-opensource-setup.exe"
    if not installer_path.exists():
        raise FileNotFoundError(f"Installer not found after build: {installer_path}")
    return installer_path


def _build_zip_bundle(releases_dir: Path) -> Path:
    zip_path = releases_dir / ZIP_NAME
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for name in ZIP_FILES:
            path = releases_dir / name
            if not path.exists():
                raise FileNotFoundError(f"Missing release file for zip bundle: {path}")
            zf.write(path, arcname=f"{ZIP_ROOT}/{path.name}")
    return zip_path


class _BuildLock:
    def __init__(self, lock_path: Path):
        self.lock_path = lock_path
        self.fd: int | None = None

    def __enter__(self):
        try:
            self.fd = os.open(str(self.lock_path), os.O_CREAT | os.O_EXCL | os.O_RDWR)
        except FileExistsError as exc:
            raise SystemExit(f"已有另一个发布构建正在运行，请等待结束后再试：{self.lock_path.name}") from exc
        os.write(self.fd, f"pid={os.getpid()}".encode("utf-8"))
        return self

    def __exit__(self, exc_type, exc, tb):
        try:
            if self.fd is not None:
                os.close(self.fd)
        finally:
            try:
                self.lock_path.unlink()
            except FileNotFoundError:
                pass


def main():
    print("=== english-coach OPEN SOURCE build ===")
    print(f"Python: {sys.executable}")
    print(f"Root: {ROOT}")
    print()

    original_version = VERSION_FILE.read_text(encoding="utf-8") if VERSION_FILE.exists() else SOURCE_DEFAULT
    original_license_defaults = (
        LICENSE_DEFAULTS_FILE.read_text(encoding="utf-8")
        if LICENSE_DEFAULTS_FILE.exists() else SOURCE_LICENSE_DEFAULTS
    )
    original_config = CONFIG_FILE.read_text(encoding="utf-8") if CONFIG_FILE.exists() else ""
    release_config = RELEASE_CONFIG_FILE.read_text(encoding="utf-8")

    with _BuildLock(BUILD_LOCK_FILE):
        try:
            # Set version mode to opensource
            VERSION_FILE.write_text(SOURCE_DEFAULT, encoding="utf-8")
            print("Set VERSION_MODE = 'opensource'")
            LICENSE_DEFAULTS_FILE.write_text(SOURCE_LICENSE_DEFAULTS, encoding="utf-8")
            print("Cleared cloud activation defaults for opensource build")
            CONFIG_FILE.write_text(release_config, encoding="utf-8")
            print("Injected release-safe config.yaml for packaging")

            # Clean previous build artifacts
            for d in ["build", "dist"]:
                p = ROOT / d
                if p.exists():
                    shutil.rmtree(p)
                    print(f"Cleaned {d}/")

            # Ensure releases dir exists
            releases_dir = ROOT / "releases"
            releases_dir.mkdir(exist_ok=True)
            (releases_dir / "config.yaml").write_text(release_config, encoding="utf-8")
            subprocess.run([sys.executable, str(SYNC_RELEASE_DOCS)], cwd=str(ROOT), check=True)
            print("Synced release docs into releases/")

            # Run PyInstaller with opensource spec
            cmd = [
                sys.executable, "-m", "PyInstaller",
                "--clean",
                "--noconfirm",
                "--distpath", str(releases_dir),
                str(ROOT / "release_tooling" / "specs" / "english_coach_opensource.spec"),
            ]
            print(f"Running: {' '.join(cmd)}\n")
            result = subprocess.run(cmd, cwd=str(ROOT))

            if result.returncode != 0:
                print("\nBuild FAILED.")
                sys.exit(1)

            # Check output
            exe_name = "english-coach-opensource.exe" if sys.platform == "win32" else "english-coach-opensource"
            exe_path = releases_dir / exe_name
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / 1024 / 1024
                installer_path = _build_installer(releases_dir)
                zip_path = _build_zip_bundle(releases_dir)
                print(f"\nBuild SUCCESS: {exe_path}  ({size_mb:.1f} MB)")
                if installer_path:
                    print(f"Installer READY: {installer_path}")
                print(f"Zip READY: {zip_path}")
                print("\n=== OPEN SOURCE VERSION ===")
                print("Users need to provide their own API keys (DeepSeek/Claude/OpenAI/Qwen)")
                print("\nTo distribute:")
                print(f"  1. Use {exe_path}, the setup package, or the zip bundle in releases/")
                print("  2. Launch the desktop app and complete Setup on first run")
                print("  3. Optionally run: python scripts/smoke_test_release.py --keep-temp")
            else:
                print("\nBuild completed but executable not found.")
                sys.exit(1)
        finally:
            VERSION_FILE.write_text(original_version or SOURCE_DEFAULT, encoding="utf-8")
            LICENSE_DEFAULTS_FILE.write_text(original_license_defaults or SOURCE_LICENSE_DEFAULTS, encoding="utf-8")
            if original_config:
                CONFIG_FILE.write_text(original_config, encoding="utf-8")
            print("Restored source-tree VERSION_MODE state")


if __name__ == "__main__":
    main()
