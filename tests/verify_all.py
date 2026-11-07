#!/usr/bin/env python3
"""
antigravity-quota-mcp — Uçtan Uca Doğrulama ve Çakışma Testi (tests/verify_all.py)

Test Edilen Senaryolar:
1. Soğuk Başlangıç (Cold Start) Gecikmesi: Süreç başlatma + JSON-RPC `initialize` süresi (ms).
2. MCP Araç Çağrıları: `tools/list`, `get_quota_status`, `reinject_badge`.
3. Çoklu Örnek Çakışma Önleme (Multi-Instance Collision & Failover Test):
   - Aynı anda 2 ayrı MCP sunucu süreci başlatılır (Süreç A ve Süreç B).
   - Süreç A'nın `LEADER`, Süreç B'nin `STANDBY` olduğu doğrulanır.
   - Süreç A kapatılır; Süreç B'nin otomatik olarak `LEADER` rolünü devraldığı (Failover) doğrulanır.
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import json
import os
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = str(PROJECT_ROOT / "main.py")


def send_rpc(proc: subprocess.Popen[str], req: dict[str, Any]) -> dict[str, Any]:
    assert proc.stdin is not None and proc.stdout is not None
    proc.stdin.write(json.dumps(req) + "\n")
    proc.stdin.flush()
    line = proc.stdout.readline()
    return json.loads(line)


def call_tool(proc: subprocess.Popen[str], req_id: int, name: str, args: dict[str, Any] | None = None) -> dict[str, Any]:
    resp = send_rpc(
        proc,
        {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": "tools/call",
            "params": {"name": name, "arguments": args or {}},
        },
    )
    text = resp["result"]["content"][0]["text"]
    return json.loads(text)


def main() -> int:
    print("=" * 68)
    print("1. SOĞUK BAŞLANGIÇ (COLD START) & MCP EL SIKIŞMA TESTİ")
    print("=" * 68)

    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env["AGY_WATCHER_CHECK_SEC"] = "1"
    test_runtime_dir = tempfile.mkdtemp(prefix="agy_quota_test_")
    env["XDG_RUNTIME_DIR"] = test_runtime_dir

    t0 = time.perf_counter()
    try:
        proc1 = subprocess.Popen(
            [sys.executable, "-B", MAIN_PY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )

        init_resp = send_rpc(
            proc1,
            {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "initialize",
                "params": {"protocolVersion": "2025-11-25"},
            },
        )
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        print(f"[PASS] Süreç 1 (PID: {proc1.pid}) initialize el sıkışması: {elapsed_ms:.1f} ms")
        assert init_resp["result"]["serverInfo"]["name"] == "antigravity-desktop-live-quota-mcp"

        # Watcher thread'in kilidi alması için 150ms bekle
        time.sleep(0.15)

        print("\n" + "=" * 68)
        print("2. ÇOKLU ÖRNEK (2 EŞZAMANLI MCP SÜRECİ) ÇAKIŞMA ÖNLEME TESTİ")
        print("=" * 68)

        proc2 = subprocess.Popen(
            [sys.executable, "-B", MAIN_PY],
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            env=env,
        )
        send_rpc(proc2, {"jsonrpc": "2.0", "id": 1, "method": "initialize", "params": {}})
        time.sleep(0.15)

        status1 = call_tool(proc1, 2, "get_instance_status")
        status2 = call_tool(proc2, 2, "get_instance_status")

        print(f"• Süreç 1 Durumu: PID={status1['pid']}, Rol={status1['role']}, LiderPID={status1['leader_pid']}")
        print(f"• Süreç 2 Durumu: PID={status2['pid']}, Rol={status2['role']}, LiderPID={status2['leader_pid']}")

        assert status1["role"] == "LEADER", "Süreç 1 LEADER olmalıydı!"
        assert status2["role"] == "STANDBY", "Süreç 2 STANDBY olmalıydı!"
        assert status2["leader_pid"] == proc1.pid, "Süreç 2, Lider olarak Süreç 1'i göstermeliydi!"
        print("[PASS] Çakışma önleme doğrulandı: Sadece 1 süreç LEADER, 2. süreç STANDBY!")

        print("\n" + "=" * 68)
        print("3. HER İKİ SÜREÇTE MCP ARAÇLARININ VE CANLI KOTANIN TESTİ")
        print("=" * 68)

        q1 = call_tool(proc1, 3, "get_quota_status")
        q2 = call_tool(proc2, 3, "get_quota_status")
        print(f"• Süreç 1 Kota Yanıtı: {q1['summary_text']}")
        print(f"• Süreç 2 Kota Yanıtı: {q2['summary_text']}")
        assert q1["ok"] is True and q2["ok"] is True
        print("[PASS] Her iki MCP süreci de stdio üzerinden kota sorgularına kusursuz yanıt veriyor!")

        print("\n" + "=" * 68)
        print("4. LİDER DÜŞMESİ VE OTOMATİK DEVİR (FAILOVER) TESTİ")
        print("=" * 68)

        proc1.terminate()
        proc1.wait(timeout=3)
        print(f"• Süreç 1 (PID: {proc1.pid}) sonlandırıldı. Süreç 2'nin liderliği devralması bekleniyor...")

        time.sleep(1.2)
        status2_after = call_tool(proc2, 4, "get_instance_status")
        print(f"• Süreç 2 Yeni Durumu: PID={status2_after['pid']}, Rol={status2_after['role']}, LiderPID={status2_after['leader_pid']}")
        assert status2_after["role"] == "LEADER", "Süreç 1 kapandığında Süreç 2 otomatik LEADER olmalıydı!"
        print("[PASS] Otomatik Failover doğrulandı: Süreç 2 kesintisiz şekilde LEADER oldu!")

        print("\n" + "=" * 68)
        print("5. CANLI PENCERE ROZET ENJEKSİYONU (CDP) TESTİ")
        print("=" * 68)

        inj = call_tool(proc2, 5, "reinject_badge", {"force": True})
        print(f"• Enjeksiyon Sonucu: {json.dumps(inj, ensure_ascii=False)}")
        assert inj["ok"] is True

        proc2.terminate()
        proc2.wait(timeout=3)

        print("\n[SUCCESS] Tüm testler (Soğuk başlangıç, Çoklu Örnek Kilit, Failover, Kota ve CDP UI) başarıyla geçti!")
        return 0
    finally:
        try:
            proc1.terminate()
        except Exception:
            pass
        try:
            proc2.terminate()
        except Exception:
            pass
        shutil.rmtree(test_runtime_dir, ignore_errors=True)


if __name__ == "__main__":
    sys.exit(main())
