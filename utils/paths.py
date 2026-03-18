"""Path utilities for handling PyInstaller bundled resources."""
import sys
from pathlib import Path


def get_content_dir() -> Path:
    """Return content directory path: handles both frozen (PyInstaller) and dev mode."""
    if getattr(sys, "frozen", False):
        # When frozen, content is bundled in _MEIPASS temp directory
        return Path(sys._MEIPASS) / "content"
    # In dev mode, content is in project root
    return Path(__file__).parent.parent / "content"


def get_data_dir() -> Path:
    """Return data directory path: handles both frozen (PyInstaller) and dev mode."""
    if getattr(sys, "frozen", False):
        # When frozen, use user's AppData directory
        import os
        appdata = os.getenv("APPDATA") or os.path.expanduser("~")
        return Path(appdata) / "EnglishCoach" / "data"
    # In dev mode, data is in project root
    return Path(__file__).parent.parent / "data"

