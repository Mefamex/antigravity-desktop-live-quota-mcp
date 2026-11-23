"""
Multi-Instance Conflict Prevention & Leader Election Module (src/lock.py)

Problem:
When a user runs Antigravity Desktop, `agy` CLI, and Antigravity IDE simultaneously
(or opens multiple windows/sessions), each client spawns its own
`antigravity-quota-mcp` child process.

If two different MCP processes connect to the window via CDP (Chrome DevTools
Protocol) at the same time and attempt to mutate the DOM, a race condition and
unnecessary socket traffic occur. However, exiting the second process outright
causes the client to report an "MCP server crashed" error.

Solution (Linux Kernel `fcntl.flock` Leader Election):
1. Every MCP process keeps its own `stdio` (JSON-RPC) channel open so MCP tools
   (`get_quota_status`, etc.) work uninterrupted across all clients.
2. The UI Injector requests a non-blocking kernel lock on `LOCK_FILE_PATH`
   (`fcntl.LOCK_EX | fcntl.LOCK_NB`):
   - The first process to acquire the lock becomes the **Leader** and runs the UI watcher.
   - Second/third processes see the lock is held, stay in **Standby** mode, and
     do not touch the CDP port.
   - If the Leader process exits (even via `SIGKILL`), the Linux kernel immediately
     releases the lock and a standby process automatically takes over leadership.
"""

from __future__ import annotations

import ctypes
import os
import sys
from pathlib import Path
from typing import IO

try:
    import fcntl
except ImportError:
    fcntl = None  # type: ignore[assignment]

try:
    import msvcrt
except ImportError:
    msvcrt = None  # type: ignore[assignment]

import config
from src.logger import get_logger

log = get_logger("lock")


class LeaderLock:
    """Kernel-level (`fcntl.flock`) singleton UI leadership manager."""

    def __init__(self, lock_path: Path = config.LOCK_FILE_PATH) -> None:
        self.lock_path: Path = lock_path
        self._fp: IO[str] | None = None
        self._is_leader: bool = False

    @property
    def is_leader(self) -> bool:
        """Returns whether this process is the active UI leader."""
        return self._is_leader

    def try_acquire(self) -> bool:
        """
        Attempts to acquire the leadership lock without blocking.
        Returns True if already leader or acquired. Returns False if another process holds it.
        """
        if self._is_leader and self._fp is not None:
            return True

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            if self._fp is None:
                self._fp = open(self.lock_path, "a+", encoding="utf-8")

            if fcntl is not None:
                fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            elif msvcrt is not None:
                self._fp.seek(0)
                msvcrt.locking(self._fp.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                raise OSError("No file locking backend available on this platform.")

            # Lock acquired; write our PID into the lock file
            self._fp.seek(0)
            self._fp.truncate()
            self._fp.write(f"{os.getpid()}\n")
            self._fp.flush()

            self._is_leader = True
            log.info(f"UI leadership lock acquired ({self.lock_path})")
            return True

        except (BlockingIOError, OSError):
            self._is_leader = False
            return False

    @staticmethod
    def _is_pid_alive(pid: int) -> bool:
        """Checks whether a process with the given PID is currently alive."""
        if pid <= 0:
            return False
        if sys.platform == "win32":
            kernel32 = getattr(ctypes, "windll", None)
            if kernel32 is None:
                return True
            process_query_limited_info = 0x1000
            still_active = 259
            handle = kernel32.kernel32.OpenProcess(process_query_limited_info, False, pid)
            if not handle:
                return ctypes.GetLastError() == 5  # ERROR_ACCESS_DENIED => alive
            try:
                exit_code = ctypes.c_ulong()
                if kernel32.kernel32.GetExitCodeProcess(handle, ctypes.byref(exit_code)):
                    return exit_code.value == still_active
                return True
            finally:
                kernel32.kernel32.CloseHandle(handle)
        try:
            os.kill(pid, 0)
            return True
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError:
            return False

    def read_holder_pid(self) -> int | None:
        """Reads the PID of the live leader process currently holding the lock."""
        try:
            if self.lock_path.exists():
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content.isdigit():
                    pid = int(content)
                    return pid if self._is_pid_alive(pid) else None
        except OSError:
            pass
        return None

    def release(self) -> None:
        """Safely releases the leadership lock."""
        if self._fp is not None:
            try:
                if self._is_leader:
                    if fcntl is not None:
                        fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
                    elif msvcrt is not None:
                        self._fp.seek(0)
                        msvcrt.locking(self._fp.fileno(), msvcrt.LK_UNLCK, 1)
                    log.info("UI leadership lock released.")
            except OSError:
                pass
            finally:
                try:
                    self._fp.close()
                except OSError:
                    pass
                self._fp = None
                self._is_leader = False
