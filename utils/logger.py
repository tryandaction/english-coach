"""
Structured logging system for English Coach.
Provides leveled logging with rotation and sensitive data masking.
"""
from __future__ import annotations

import logging
import os
import re
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional


class SensitiveDataFilter(logging.Filter):
    """Filter to mask sensitive information in logs."""

    PATTERNS = [
        (re.compile(r'(api[_-]?key["\s:=]+)([a-zA-Z0-9_-]{20,})'), r'\1***MASKED***'),
        (re.compile(r'(sk-[a-zA-Z0-9]{20,})'), r'sk-***MASKED***'),
        (re.compile(r'(Bearer\s+)([a-zA-Z0-9_-]{20,})'), r'\1***MASKED***'),
        (re.compile(r'(password["\s:=]+)([^\s,}"]+)'), r'\1***MASKED***'),
        (re.compile(r'(token["\s:=]+)([a-zA-Z0-9_-]{20,})'), r'\1***MASKED***'),
    ]

    def filter(self, record: logging.LogRecord) -> bool:
        """Mask sensitive data in log message."""
        if isinstance(record.msg, str):
            for pattern, replacement in self.PATTERNS:
                record.msg = pattern.sub(replacement, record.msg)
        return True


class EnglishCoachLogger:
    """Centralized logging system with rotation and filtering."""

    def __init__(
        self,
        name: str = "english_coach",
        log_dir: Optional[Path] = None,
        level: int = logging.INFO,
        max_bytes: int = 10 * 1024 * 1024,  # 10MB
        backup_count: int = 5,
    ):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(level)
        self.logger.handlers.clear()

        # Determine log directory
        if log_dir is None:
            log_dir = Path(os.path.expanduser("~")) / ".english_coach" / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)

        # Main log file with rotation
        log_file = log_dir / f"{name}.log"
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(level)

        # Error log file (errors only)
        error_file = log_dir / f"{name}_error.log"
        error_handler = RotatingFileHandler(
            error_file,
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        error_handler.setLevel(logging.ERROR)

        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        file_handler.setFormatter(formatter)
        error_handler.setFormatter(formatter)

        # Add sensitive data filter
        sensitive_filter = SensitiveDataFilter()
        file_handler.addFilter(sensitive_filter)
        error_handler.addFilter(sensitive_filter)

        # Add handlers
        self.logger.addHandler(file_handler)
        self.logger.addHandler(error_handler)

        self.log_dir = log_dir
        self.log_file = log_file
        self.error_file = error_file

    def debug(self, msg: str, *args, **kwargs) -> None:
        """Log debug message."""
        self.logger.debug(msg, *args, **kwargs)

    def info(self, msg: str, *args, **kwargs) -> None:
        """Log info message."""
        self.logger.info(msg, *args, **kwargs)

    def warning(self, msg: str, *args, **kwargs) -> None:
        """Log warning message."""
        self.logger.warning(msg, *args, **kwargs)

    def error(self, msg: str, *args, **kwargs) -> None:
        """Log error message."""
        self.logger.error(msg, *args, **kwargs)

    def critical(self, msg: str, *args, **kwargs) -> None:
        """Log critical message."""
        self.logger.critical(msg, *args, **kwargs)

    def exception(self, msg: str, *args, **kwargs) -> None:
        """Log exception with traceback."""
        self.logger.exception(msg, *args, **kwargs)

    def get_log_path(self) -> Path:
        """Get path to main log file."""
        return self.log_file

    def get_error_log_path(self) -> Path:
        """Get path to error log file."""
        return self.error_file

    def export_logs(self, output_path: Path) -> None:
        """Export all logs to a single file for support."""
        with open(output_path, "w", encoding="utf-8") as out:
            out.write(f"=== English Coach Logs Export ===\n")
            out.write(f"Generated: {datetime.now().isoformat()}\n\n")

            # Export main log
            out.write("=== Main Log ===\n")
            if self.log_file.exists():
                with open(self.log_file, "r", encoding="utf-8") as f:
                    out.write(f.read())
            else:
                out.write("(no main log found)\n")

            out.write("\n\n=== Error Log ===\n")
            if self.error_file.exists():
                with open(self.error_file, "r", encoding="utf-8") as f:
                    out.write(f.read())
            else:
                out.write("(no error log found)\n")


# Global logger instance
_global_logger: Optional[EnglishCoachLogger] = None


def get_logger() -> EnglishCoachLogger:
    """Get or create global logger instance."""
    global _global_logger
    if _global_logger is None:
        _global_logger = EnglishCoachLogger()
    return _global_logger


def init_logger(
    log_dir: Optional[Path] = None,
    level: int = logging.INFO,
) -> EnglishCoachLogger:
    """Initialize global logger with custom settings."""
    global _global_logger
    _global_logger = EnglishCoachLogger(log_dir=log_dir, level=level)
    return _global_logger
