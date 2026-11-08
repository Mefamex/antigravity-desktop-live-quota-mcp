"""
Antigravity Scratch & Geçici Dosya Temizleyicisi (src/scratch_cleaner.py)

Bu modül, Antigravity Desktop'un oturumlar sırasında oluşturduğu geçici
`scratch` dizinlerini (~/.gemini/antigravity/brain/*/scratch/) güvenli
ve kontrollü şekilde temizler.

Kırmızı Çizgiler & Güvenlik Kısıtları:
- Asla `transcript.jsonl`, planlar veya ana dizin dosyalarına DOKUNMAZ.
- Yalnızca `scratch/` alt dizini altındaki dosyaları hedefler.
- `dry_run=True` moduyla silme yapmadan silinecek boyutu ve dosya sayısını hesaplar.
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
    """Byte değerini insan tarafından okunabilir birime (KB, MB, GB) dönüştürür."""
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
    Antigravity brain dizinleri altındaki `scratch` klasörlerini temizler.

    :param brain_dir: Brain kök dizini (varsayılan: ~/.gemini/antigravity/brain)
    :param older_than_hours: Belirtilen saatten daha eski dosyaları temizler (0 ise tümü).
    :param dry_run: True ise işlem yapmadan temizlenecek dosyaları raporlar.
    :return: Temizlenen dosya sayısı ve kazanılan alan bilgisi.
    """
    root = Path(brain_dir) if brain_dir else DEFAULT_BRAIN_DIR
    if not root.is_dir():
        return {
            "ok": True,
            "freed_bytes": 0,
            "freed_human": "0 B",
            "deleted_files_count": 0,
            "dry_run": dry_run,
            "message": f"Dizin bulunamadı: {root}",
            "cleaned_dirs": [],
        }

    now = time.time()
    cutoff_time = now - (older_than_hours * 3600.0) if older_than_hours > 0 else now + 1.0

    total_bytes = 0
    total_files = 0
    cleaned_scratch_dirs: list[str] = []

    try:
        # brain altındaki UUID dizinlerini tara
        for session_dir in root.iterdir():
            if not session_dir.is_dir():
                continue

            scratch_dir = session_dir / "scratch"
            if not scratch_dir.is_dir():
                continue

            # Sadece scratch klasörünün içeriğini güvenle tara
            dir_has_files = False
            for item in scratch_dir.rglob("*"):
                if item.is_file():
                    dir_has_files = True
                    try:
                        stat = item.stat()
                        # Yaş kontrolü
                        if older_than_hours > 0 and stat.st_mtime > cutoff_time:
                            continue

                        total_bytes += stat.st_size
                        total_files += 1

                        if not dry_run:
                            try:
                                item.unlink(missing_ok=True)
                            except OSError as err:
                                log.warning(f"Dosya silinemedi: {item} ({err})")
                    except OSError:
                        continue

            if dir_has_files:
                cleaned_scratch_dirs.append(str(scratch_dir))
                if not dry_run:
                    # Boş kalan alt klasörleri temizle
                    for sub in sorted(scratch_dir.glob("**/*"), reverse=True):
                        if sub.is_dir() and not any(sub.iterdir()):
                            try:
                                sub.rmdir()
                            except OSError:
                                pass

    except Exception as exc:
        log.error(f"Scratch temizliği sırasında hata oluştu: {exc}")
        return {
            "ok": False,
            "error": str(exc),
            "freed_bytes": total_bytes,
            "freed_human": _format_bytes(total_bytes),
            "deleted_files_count": total_files,
            "dry_run": dry_run,
            "cleaned_dirs": cleaned_scratch_dirs,
        }

    action_word = "Simüle edildi (dry_run)" if dry_run else "Temizlendi"
    log.info(
        f"Scratch Temizliği: {action_word} - {total_files} dosya, {_format_bytes(total_bytes)} alan kazanıldı."
    )

    return {
        "ok": True,
        "freed_bytes": total_bytes,
        "freed_human": _format_bytes(total_bytes),
        "deleted_files_count": total_files,
        "dry_run": dry_run,
        "cleaned_dirs": cleaned_scratch_dirs,
    }
