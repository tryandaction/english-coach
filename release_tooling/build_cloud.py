#!/usr/bin/env python3
"""
Build script for english-coach CLOUD version (license-based with cloud API).
Usage: python build_cloud.py
Output:
- releases/english-coach-cloud.exe (portable onefile)
- releases/english-coach-cloud-installer/ (installer payload onedir)

Activation config resolution priority:
1. EC_WORKER_URL + EC_WORKER_CLIENT_TOKEN
2. private_commercial/cloud_activation_config.json
3. cloud_activation_config.json
4. releases/cloud_activation_config.json
"""

import subprocess
import sys
import shutil
import os
import json
from zipfile import ZIP_DEFLATED, ZipFile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from utils.private_paths import cloud_activation_config_candidates, display_path

VERSION_FILE = ROOT / "gui" / "version.py"
LICENSE_DEFAULTS_FILE = ROOT / "gui" / "cloud_license_defaults.py"
CONFIG_FILE = ROOT / "config.yaml"
RELEASE_CONFIG_FILE = ROOT / "release_tooling" / "config.release.yaml"
RELEASE_CLOUD_CONFIG = ROOT / "releases" / "cloud_activation_config.json"
SYNC_RELEASE_DOCS = ROOT / "scripts" / "sync_release_docs.py"
INSTALLER_SCRIPT = ROOT / "release_tooling" / "installers" / "installer_cloud.iss"
PORTABLE_SPEC = ROOT / "release_tooling" / "specs" / "english_coach_cloud.spec"
INSTALLER_SPEC = ROOT / "release_tooling" / "specs" / "english_coach_cloud_installer.spec"
BUILD_LOCK_FILE = ROOT / ".build_release.lock"
ZIP_NAME = "english-coach-v2.0.0-cloud.zip"
ZIP_ROOT = "english-coach-cloud"
INSTALLER_PAYLOAD_DIRNAME = "english-coach-cloud-installer"
ZIP_FILES = [
    ".env.example",
    ".env.template",
    "config.yaml",
    "DEPLOYMENT_CHECKLIST.md",
    "english-coach-cloud.exe",
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
CLOUD_LICENSE_DEFAULTS = '''"""
Build-time defaults for the commercial Cloud activation flow.

The source tree keeps these values empty by default.
`build_cloud.py` can temporarily inject public activation settings into this
module before packaging the cloud executable, then restore the file.

Important:
- `WORKER_URL` is public.
- `CLIENT_TOKEN` is the buyer-side activation token for `/activate` and `/verify`.
- It must NOT be the same as the seller/admin token used by key generation.
"""

WORKER_URL = "{worker_url}"
CLIENT_TOKEN = "{client_token}"
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
RUNTIME_CLOUD_CONFIG = '''{{
  "worker_url": "{worker_url}",
  "client_token": "{client_token}"
}}
'''
CLOUD_VERSION = '''"""
Version configuration for English Coach.
Set at build time to distinguish between opensource and cloud versions.
"""

# This will be set by the build script.
VERSION_MODE = "cloud"  # or "opensource"


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
    payload_dir = releases_dir / INSTALLER_PAYLOAD_DIRNAME
    if not payload_dir.exists():
        raise FileNotFoundError(f"Installer payload not found: {payload_dir}")
    print(f"Building installer with: {iscc}")
    subprocess.run([iscc, str(INSTALLER_SCRIPT)], cwd=str(ROOT), check=True)
    installer_path = releases_dir / "english-coach-cloud-setup.exe"
    if not installer_path.exists():
        raise FileNotFoundError(f"Installer not found after build: {installer_path}")
    return installer_path


def _build_zip_bundle(releases_dir: Path, include_runtime_activation: bool) -> Path:
    zip_path = releases_dir / ZIP_NAME
    names = list(ZIP_FILES)
    if include_runtime_activation:
        names.append("cloud_activation_config.json")
    with ZipFile(zip_path, "w", compression=ZIP_DEFLATED) as zf:
        for name in names:
            path = releases_dir / name
            if not path.exists():
                raise FileNotFoundError(f"Missing release file for zip bundle: {path}")
            zf.write(path, arcname=f"{ZIP_ROOT}/{path.name}")
    return zip_path


def _load_activation_settings_from_file(path: Path) -> tuple[str, str] | None:
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None
    worker_url = str(payload.get("worker_url", "") or "").strip()
    client_token = str(payload.get("client_token", "") or "").strip()
    if not worker_url or not client_token:
        return None
    if "replace-with" in client_token.lower():
        return None
    return worker_url, client_token


def _resolve_activation_settings() -> tuple[str, str, str]:
    worker_url = os.environ.get("EC_WORKER_URL", "").strip()
    client_token = os.environ.get("EC_WORKER_CLIENT_TOKEN", "").strip()
    if bool(worker_url) != bool(client_token):
        raise SystemExit("EC_WORKER_URL 和 EC_WORKER_CLIENT_TOKEN 必须同时提供。")
    if worker_url and client_token:
        return worker_url, client_token, "environment"

    for path in cloud_activation_config_candidates():
        resolved = _load_activation_settings_from_file(path)
        if resolved:
            return resolved[0], resolved[1], display_path(path)

    raise SystemExit(
        "缺少商业版激活配置。请提供 EC_WORKER_URL + EC_WORKER_CLIENT_TOKEN，"
        "或在本地放置有效的 cloud_activation_config.json "
        "(优先读取 private_commercial/cloud_activation_config.json)。"
    )


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


def _run_pyinstaller(spec_path: Path, releases_dir: Path, work_dir: Path) -> None:
    work_dir.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        sys.executable, "-m", "PyInstaller",
        "--clean",
        "--noconfirm",
        "--distpath", str(releases_dir),
        "--workpath", str(work_dir),
        str(spec_path),
    ]
    print(f"Running: {' '.join(cmd)}\n")
    result = subprocess.run(cmd, cwd=str(ROOT))
    if result.returncode != 0:
        raise SystemExit(f"Build FAILED for spec: {spec_path.name}")


def main():
    print("=== english-coach CLOUD build ===")
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
    worker_url, client_token, activation_source = _resolve_activation_settings()

    with _BuildLock(BUILD_LOCK_FILE):
        try:
            # Set version mode to cloud
            VERSION_FILE.write_text(CLOUD_VERSION, encoding="utf-8")
            print("Set VERSION_MODE = 'cloud'")
            CONFIG_FILE.write_text(release_config, encoding="utf-8")
            print("Injected release-safe config.yaml for packaging")
            LICENSE_DEFAULTS_FILE.write_text(
                CLOUD_LICENSE_DEFAULTS.format(
                    worker_url=worker_url.replace("\\", "\\\\").replace('"', '\\"'),
                    client_token=client_token.replace("\\", "\\\\").replace('"', '\\"'),
                ),
                encoding="utf-8",
            )
            print(f"Embedded cloud activation defaults from {activation_source}")

            # Clean previous build artifacts
            for d in ["build", "dist"]:
                p = ROOT / d
                if p.exists():
                    shutil.rmtree(p)
                    print(f"Cleaned {d}/")

            # Ensure releases dir exists
            releases_dir = ROOT / "releases"
            releases_dir.mkdir(exist_ok=True)
            installer_payload_dir = releases_dir / INSTALLER_PAYLOAD_DIRNAME
            if installer_payload_dir.exists():
                shutil.rmtree(installer_payload_dir)
                print(f"Cleaned previous installer payload: {installer_payload_dir.name}")
            (releases_dir / "config.yaml").write_text(release_config, encoding="utf-8")
            subprocess.run([sys.executable, str(SYNC_RELEASE_DOCS)], cwd=str(ROOT), check=True)
            print("Synced release docs into releases/")
            RELEASE_CLOUD_CONFIG.write_text(
                RUNTIME_CLOUD_CONFIG.format(
                    worker_url=worker_url.replace("\\", "\\\\").replace('"', '\\"'),
                    client_token=client_token.replace("\\", "\\\\").replace('"', '\\"'),
                ),
                encoding="utf-8",
            )
            print(f"Wrote {RELEASE_CLOUD_CONFIG.name} for cloud packaging")

            # Portable onefile stays unchanged for direct distribution.
            _run_pyinstaller(
                PORTABLE_SPEC,
                releases_dir,
                ROOT / "build" / "pyinstaller-cloud-portable",
            )
            portable_exe_path = releases_dir / ("english-coach-cloud.exe" if sys.platform == "win32" else "english-coach-cloud")
            if not portable_exe_path.exists():
                raise FileNotFoundError(f"Portable executable not found: {portable_exe_path}")

            # Installer gets a dedicated onedir payload to reduce cold-start cost.
            _run_pyinstaller(
                INSTALLER_SPEC,
                releases_dir,
                ROOT / "build" / "pyinstaller-cloud-installer",
            )
            installer_payload_exe = installer_payload_dir / ("english-coach-cloud.exe" if sys.platform == "win32" else "english-coach-cloud")
            if not installer_payload_exe.exists():
                raise FileNotFoundError(f"Installer payload executable not found: {installer_payload_exe}")

            # Check output
            exe_name = "english-coach-cloud.exe" if sys.platform == "win32" else "english-coach-cloud"
            exe_path = releases_dir / exe_name
            if exe_path.exists():
                size_mb = exe_path.stat().st_size / 1024 / 1024
                installer_path = _build_installer(releases_dir)
                zip_path = _build_zip_bundle(releases_dir, include_runtime_activation=True)
                print(f"\nBuild SUCCESS: {exe_path}  ({size_mb:.1f} MB)")
                print(f"Installer payload READY: {installer_payload_dir}")
                if installer_path:
                    print(f"Installer READY: {installer_path}")
                print(f"Zip READY: {zip_path}")
                print("\n=== CLOUD VERSION ===")
                print("Users activate with license key (XXXX-XXXX-XXXX-XXXX)")
                print("API key provided by cloud service")
                print("\nTo distribute:")
                print(f"  1. Use {exe_path}, the setup package, or the zip bundle in releases/")
                print("  2. Launch the desktop app and complete Setup on first run")
                print("  3. Activate with license key in setup wizard if this build includes activation settings")
                print("  4. Optionally run: python scripts/smoke_test_release.py --expected-version-mode cloud --portable-exe releases/english-coach-cloud.exe --installer-exe releases/english-coach-cloud-setup.exe --keep-temp")
            else:
                print("\nBuild completed but executable not found.")
                sys.exit(1)
        finally:
            # Never leave the source tree in cloud mode after packaging.
            VERSION_FILE.write_text(original_version or SOURCE_DEFAULT, encoding="utf-8")
            LICENSE_DEFAULTS_FILE.write_text(original_license_defaults or SOURCE_LICENSE_DEFAULTS, encoding="utf-8")
            if original_config:
                CONFIG_FILE.write_text(original_config, encoding="utf-8")
            print("Restored source-tree VERSION_MODE state")


if __name__ == "__main__":
    main()
