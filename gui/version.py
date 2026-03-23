"""
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
