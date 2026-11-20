"""
Antigravity Scratch & Temporary File Cleaner (src/scratch_cleaner.py)

This module safely and selectively cleans temporary `scratch` directories
(~/.gemini/antigravity/brain/*/scratch/) created by Antigravity Desktop
during sessions.

Red Lines & Safety Constraints:
- NEVER touches `transcript.jsonl`, plans, or root session files.
- Targets only files inside the `scratch/` subdirectory.
- Supports `dry_run=True` to calculate cleanable size and file count without deleting.
"""

from __future__ import annotations

import os
import shutil
import time
from pathlib import Path
from typing import Any

from src.logger import get_logger

log = get_logger("scratch_cleaner")

DEFAULT_BRAIN_DIR = Path.home() / ".gemini" / "antigravity" / "brain"


def _format_bytes(bytes_count: int) -> str:
    """Converts a byte count into a human-readable unit (KB, MB, GB)."""
    if bytes_count < 1024:
        return f"{bytes_count} B"
    elif bytes_count < 1024 * 1024:
        return f"{bytes_count / 1024:.1f} KB"
    elif bytes_count < 1024 * 1024 * 1024:
        return f"{bytes_count / (1024 * 1024):.1f} MB"
    return f"{bytes_count / (1024 * 1024 * 1024):.2f} GB"


def clean_scratch_cache(
    brain_dir: Path | str | None = None,
    older_than_hours: float = 0.0,
    dry_run: bool = False,
) -> dict[str, Any]:
    """
    Cleans `scratch` folders under Antigravity brain directories.

    :param brain_dir: Brain root directory (default: ~/.gemini/antigravity/brain)
    :param older_than_hours: Cleans files older than the specified hours (0 means all).
    :param dry_run: If True, reports cleanable files without deleting them.
    :return: Dictionary containing cleaned file count and freed space info.
    """
    root = Path(brain_dir) if brain_dir else DEFAULT_BRAIN_DIR
    if not root.is_dir():
        return {
            "ok": True,
            "freed_bytes": 0,
            "freed_human": "0 B",
            "deleted_files_count": 0,
            "dry_run": dry_run,
            "message": f"Directory not found: {root}",
            "cleaned_dirs": [],
        }

    now = time.time()
    cutoff_time = now - (older_than_hours * 3600.0) if older_than_hours > 0 else now + 1.0

    total_bytes = 0
    total_files = 0
    cleaned_scratch_dirs: list[str] = []

    try:
        # Scan UUID directories under brain
        for session_dir in root.iterdir():
            if not session_dir.is_dir():
                continue

            scratch_dir = session_dir / "scratch"
            if not scratch_dir.is_dir():
                continue

            # Safely scan only the contents of the scratch folder
            dir_has_files = False
            for item in scratch_dir.rglob("*"):
                if item.is_file():
                    dir_has_files = True
                    try:
                        stat = item.stat()
                        # Age check
                        if older_than_hours > 0 and stat.st_mtime > cutoff_time:
                            continue

                        total_bytes += stat.st_size
                        total_files += 1

                        if not dry_run:
                            try:
                                item.unlink(missing_ok=True)
                            except OSError as err:
                                log.warning(f"Failed to delete file: {item} ({err})")
                    except OSError:
                        continue

            if dir_has_files:
                cleaned_scratch_dirs.append(str(scratch_dir))
                if not dry_run:
                    # Remove empty subdirectories
                    for sub in sorted(scratch_dir.glob("**/*"), reverse=True):
                        if sub.is_dir() and not any(sub.iterdir()):
                            try:
                                sub.rmdir()
                            except OSError:
                                pass

    except Exception as exc:
        log.error(f"Error occurred during scratch cleanup: {exc}")
        return {
            "ok": False,
            "error": str(exc),
            "freed_bytes": total_bytes,
            "freed_human": _format_bytes(total_bytes),
            "deleted_files_count": total_files,
            "dry_run": dry_run,
            "cleaned_dirs": cleaned_scratch_dirs,
        }

    action_word = "Simulated (dry_run)" if dry_run else "Cleaned"
    log.info(
        f"Scratch Cleanup: {action_word} - {total_files} files, {_format_bytes(total_bytes)} freed."
    )

    return {
        "ok": True,
        "freed_bytes": total_bytes,
        "freed_human": _format_bytes(total_bytes),
        "deleted_files_count": total_files,
        "dry_run": dry_run,
        "cleaned_dirs": cleaned_scratch_dirs,
    }
