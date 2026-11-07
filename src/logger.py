"""
Standart MCP Uyumlu Loglama Modülü (src/logger.py)

Altın Kural:
MCP stdio sunucularında `stdout` yalnızca JSON-RPC 2.0 mesajlarını taşır.
`stdout` üzerine tek bir karakter dahi basılması protokolü bozar.
Bu modül tüm çıktıları kesin olarak `sys.stderr` akışına yönlendirir ve
etiketleri 4 karaktere (`INFO`, `WARN`, `ERR `, `DBG `) hizalar.
"""

from __future__ import annotations

import logging
import os
import sys

import config


class AlignedStderrFormatter(logging.Formatter):
    """Log seviyelerini 4 karaktere sabitleyen biçimlendirici."""

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
    """Belirtilen modül adı için stderr tabanlı logger döndürür."""
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(AlignedStderrFormatter())
        logger.addHandler(handler)
        level = getattr(logging, config.LOG_LEVEL, logging.INFO)
        logger.setLevel(level)
        logger.propagate = False
    return logger
