"""
Standard MCP-Compliant Logging Module (src/logger.py)

Golden Rule:
In MCP stdio servers, `stdout` carries ONLY JSON-RPC 2.0 messages.
Printing even a single extra character to `stdout` breaks the protocol.
This module strictly directs all output to `sys.stderr` and aligns
severity labels to 4 characters (`INFO`, `WARN`, `ERR `, `DBG `).
"""

from __future__ import annotations

import logging
import os
import sys

import config


class AlignedStderrFormatter(logging.Formatter):
    """Formatter that aligns log levels to 4 characters."""

    LEVEL_MAP = {
        logging.DEBUG: "DBG ",
        logging.INFO: "INFO",
        logging.WARNING: "WARN",
        logging.ERROR: "ERR ",
        logging.CRITICAL: "CRIT",
    }

    def format(self, record: logging.LogRecord) -> str:
        lvl = self.LEVEL_MAP.get(record.levelno, "INFO")
        ts = self.formatTime(record, "%H:%M:%S")
        pid = os.getpid()
        return f"[{ts}] [{lvl}] [pid:{pid}] [{record.name}] {record.getMessage()}"


def get_logger(name: str) -> logging.Logger:
    """Returns a stderr-based logger for the specified module name."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(AlignedStderrFormatter())
        logger.addHandler(handler)
        level = getattr(logging, config.LOG_LEVEL, logging.INFO)
        logger.setLevel(level)
        logger.propagate = False
    return logger
