"""
Çoklu Örnek Çakışma Önleyici & Lider Seçimi Modülü (src/lock.py)

Problem:
Kullanıcı aynı anda hem Antigravity Desktop, hem `agy` CLI, hem de Antigravity IDE
açtığında (veya birden fazla pencere/oturum başlattığında), her istemci kendi
`antigravity-quota-mcp` alt sürecini (child process) başlatır.

Eğer 2 farklı MCP süreci aynı anda CDP (Chrome DevTools Protocol) üzerinden
pencereye bağlanıp DOM'u güncellemeye çalışırsa yarış durumu (race condition)
ve gereksiz soket trafiği oluşur. Ancak ikinci sürecin tamamen kapanması da
istemcinin "MCP sunucusu çöktü" hatası vermesine yol açar.

Çözüm (Linux Kernel `fcntl.flock` Lider Seçimi):
1. Her MCP süreci kendi `stdio` (JSON-RPC) kanalını açık tutar; böylece tüm
   istemcilerde MCP araçları (`get_quota_status` vb.) kesintisiz çalışır.
2. UI Enjektörü ise `LOCK_FILE_PATH` üzerinde bloklamayan çekirdek kilidi
   (`fcntl.LOCK_EX | fcntl.LOCK_NB`) talep eder:
   - Kilidi alan ilk süreç **LİDER (Leader)** olur ve UI izleme görevini yürütür.
   - İkinci/üçüncü süreçler kilidin dolu olduğunu görür, **YEDEK (Standby)** modda
     bekler ve CDP portuna dokunmaz.
   - Lider süreç kapanırsa (hatta `SIGKILL` ile ölse bile), Linux çekirdeği kilidi
     anında serbest bırakır ve yedekteki süreç otomatik olarak Liderliği devralır.
"""

from __future__ import annotations

import fcntl
import os
from pathlib import Path
from typing import IO

import config
from src.logger import get_logger

log = get_logger("lock")


class LeaderLock:
    """Çekirdek düzeyinde (`fcntl.flock`) tekil UI liderliği yöneticisi."""

    def __init__(self, lock_path: Path = config.LOCK_FILE_PATH) -> None:
        self.lock_path: Path = lock_path
        self._fp: IO[str] | None = None
        self._is_leader: bool = False

    @property
    def is_leader(self) -> bool:
        """Bu sürecin aktif UI lideri olup olmadığını döndürür."""
        return self._is_leader

    def try_acquire(self) -> bool:
        """
        Bloklamadan liderlik kilidini almaya çalışır.
        Zaten liderse True döner. Başka bir süreç liderse False döner.
        """
        if self._is_leader and self._fp is not None:
            return True

        try:
            self.lock_path.parent.mkdir(parents=True, exist_ok=True)
            if self._fp is None:
                self._fp = open(self.lock_path, "a+", encoding="utf-8")

            fcntl.flock(self._fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)

            # Kilidi aldık; dosya içine kendi PID bilgimizi yazalım
            self._fp.seek(0)
            self._fp.truncate()
            self._fp.write(f"{os.getpid()}\n")
            self._fp.flush()

            self._is_leader = True
            log.info(f"UI Liderlik kilidi alındı ({self.lock_path})")
            return True

        except (BlockingIOError, OSError):
            self._is_leader = False
            return False

    def read_holder_pid(self) -> int | None:
        """Şu an kilidi elinde tutan lider sürecin PID numarasını okur."""
        try:
            if self.lock_path.exists():
                content = self.lock_path.read_text(encoding="utf-8").strip()
                if content.isdigit():
                    return int(content)
        except OSError:
            pass
        return None

    def release(self) -> None:
        """Liderlik kilidini güvenli biçimde serbest bırakır."""
        if self._fp is not None:
            try:
                if self._is_leader:
                    fcntl.flock(self._fp.fileno(), fcntl.LOCK_UN)
                    log.info("UI Liderlik kilidi serbest bırakıldı.")
            except OSError:
                pass
            finally:
                try:
                    self._fp.close()
                except OSError:
                    pass
                self._fp = None
                self._is_leader = False
