#!/usr/bin/env python3
"""
antigravity-quota-mcp — End-to-End Verification & Collision Test (tests/verify_all.py)

Tested Scenarios:
1. Cold Start Latency: Process startup + JSON-RPC `initialize` duration (ms).
2. MCP Tool Calls: `tools/list`, `get_quota_status`, `reinject_badge`.
3. Multi-Instance Collision & Failover Test:
   - Starts 2 separate MCP server processes simultaneously (Process A and Process B).
   - Verifies Process A is `LEADER` and Process B is `STANDBY`.
   - Terminates Process A; verifies Process B automatically takes over `LEADER` (Failover).
"""

from __future__ import annotations

import sys

sys.dont_write_bytecode = True

import argparse
import json
import os
import shutil
import socket
import struct
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MAIN_PY = str(PROJECT_ROOT / "main.py")
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


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


def _run_ui_payload_js_checks(js_payload: str) -> None:
    """Verifies syntax and runtime behavior of the generated UI JS payload when Node.js is available."""
    node_bin = shutil.which("node")
    if not node_bin:
        print("[SKIP/INFO] Node.js not found; skipping headless JS behavior test.")
        return

    import config

    syntax_proc = subprocess.run(
        [node_bin, "--check"],
        input=js_payload,
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert syntax_proc.returncode == 0, f"UI JS syntax error: {syntax_proc.stderr}"

    harness = f"""
const assert = require("node:assert/strict");
const vm = require("node:vm");

const BADGE_ID = {json.dumps(config.BADGE_ELEMENT_ID)};
const BAR_SELECTOR = {json.dumps(config.TARGET_BAR_SELECTOR)};
const JS_CODE = {json.dumps(js_payload)};

async function main() {{
    let fakeNow = 100000;
    const RealDate = Date;
    class FakeDate extends RealDate {{
        constructor(...args) {{
            if (args.length === 0) super(fakeNow);
            else super(...args);
        }}
        static now() {{ return fakeNow; }}
    }}

    let disconnectedCount = 0;
    const clearedIntervals = [];
    const cancelledFrames = [];
    let nextTimerId = 100;
    let nextRafId = 500;
    let intervalCallbacks = [];
    let rafCallbacks = new Map();
    let observerCallback = null;

    let modelBtnAria = "Select model, current: Orchestrator (Neon) (high)";
    let modelBtnText = "Orchestrator (Neon)";
    let extraButtons = [];
    let hasModelTriggerBtn = true;

    let styleEl = null;
    let badgeEl = null;
    const barEl = {{
        appendChild(el) {{
            if (el.id === BADGE_ID) badgeEl = el;
        }}
    }};

    let currentQuotaResp = {{
        groups: [
            {{
                displayName: "Gemini Models",
                description: "Models within this group: Gemini 4 Neon, Gemini 4 Hydrogen, Orchestrator (Neon), Gemini 3.8 Flash",
                buckets: [
                    {{ window: "weekly", remainingFraction: 0.74, resetTime: "2026-11-28T00:00:00Z" }},
                    {{ window: "5h", remainingFraction: 0.50, resetTime: "2026-11-21T05:00:00Z" }}
                ]
            }},
            {{
                displayName: "Claude and GPT models",
                description: "Models within this group: Claude Opus 5.5, Claude Sonnet 5.5, GPT-OSS 120B, FutureModel Alpha",
                buckets: [
                    {{ window: "weekly", remainingFraction: 0.80, resetTime: "2026-11-28T00:00:00Z" }},
                    {{ window: "5h", remainingFraction: 0.90, resetTime: "2026-11-21T05:00:00Z" }}
                ]
            }},
            {{
                displayName: "Gemini 4 Argon",
                description: "For paid Pro plans, Argon quota is separate. Higher Argon quota (included as part of the larger Gemini quota bucket) is available on Ultra plans.",
                buckets: [
                    {{ window: "weekly", remainingFraction: 0.95, resetTime: "2026-11-28T00:00:00Z" }}
                ]
            }}
        ]
    }};

    const mockWindow = {{
        __APP_CONFIG__: {{ csrfToken: "test-csrf" }},
        __AGY_QUOTA_STATE__: {{
            fetchTimerId: 91,
            renderTimerId: 92,
            observer: {{ disconnect() {{ disconnectedCount++; }} }},
            history: [{{ t: 1000, g5h: 42, c5h: 88 }}]
        }}
    }};

    const mockDocument = {{
        head: {{ appendChild(el) {{ if (el.id) styleEl = el; }} }},
        body: {{}},
        getElementById(id) {{
            if (id === BADGE_ID) return badgeEl;
            if (id === "agy-quota-pulse-style") return styleEl;
            return null;
        }},
        createElement(tag) {{
            return {{ tagName: tag.toUpperCase(), id: "", style: {{}}, textContent: "", innerHTML: "", title: "" }};
        }},
        querySelector(sel) {{
            if (sel === BAR_SELECTOR) return barEl;
            if (sel.includes("model-selector-trigger") && hasModelTriggerBtn) {{
                return {{
                    getAttribute(name) {{ return name === "aria-label" ? modelBtnAria : null; }},
                    get innerText() {{ return modelBtnText; }}
                }};
            }}
            return null;
        }},
        querySelectorAll(sel) {{
            if (sel === "button") return extraButtons;
            return [];
        }}
    }};

    const sandbox = {{
        window: mockWindow,
        document: mockDocument,
        Date: FakeDate,
        console,
        MutationObserver: class {{
            constructor(cb) {{ observerCallback = cb; }}
            observe() {{}}
            disconnect() {{ disconnectedCount++; }}
        }},
        requestAnimationFrame(cb) {{
            const id = ++nextRafId;
            rafCallbacks.set(id, cb);
            return id;
        }},
        cancelAnimationFrame(id) {{
            cancelledFrames.push(id);
            rafCallbacks.delete(id);
        }},
        setInterval(fn, ms) {{
            const id = ++nextTimerId;
            intervalCallbacks.push({{ id, fn, ms }});
            return id;
        }},
        clearInterval(id) {{ clearedIntervals.push(id); }},
        setTimeout() {{ return 999; }},
        fetch: async () => ({{ ok: true, json: async () => ({{ response: currentQuotaResp }}) }}),
        Array, String, Math, Boolean, JSON, Promise, Number, Object, Error
    }};

    const flush = async () => {{
        for (let i = 0; i < 6; i++) await new Promise(r => setImmediate(r));
    }};

    // 1. Safe migration from legacy state (legacy history array + undefined reattachFrameId)
    const res1 = vm.runInNewContext(JS_CODE, sandbox);
    assert.equal(res1, "OK");
    assert.equal(disconnectedCount, 1);
    assert.ok(clearedIntervals.includes(91) && clearedIntervals.includes(92));
    assert.equal(cancelledFrames.length, 0, "cancelAnimationFrame must not be called for undefined reattachFrameId");
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.reattachFrameId, null);
    assert.ok(Array.isArray(mockWindow.__AGY_QUOTA_STATE__.history.g5h));
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h[0].pct, 42);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.c5h[0].pct, 88);

    await flush();
    assert.ok(badgeEl !== null, "Badge should be attached to the DOM");
    assert.ok(badgeEl.title.includes("Active Model Group: gemini"), badgeEl.title);

    // 2. Dynamic model description and effort token stripping checks
    const fetchCycle = intervalCallbacks[0].fn;
    const renderCycle = intervalCallbacks[1].fn;

    modelBtnAria = "Select model, current: FutureModel Alpha (medium)";
    renderCycle();
    assert.ok(badgeEl.title.includes("Active Model Group: claude"), badgeEl.title);

    modelBtnAria = "Select model, current: Gemini 4 Argon (low)";
    renderCycle();
    assert.ok(badgeEl.title.includes("Active Model Group: argon"), badgeEl.title);

    modelBtnAria = "Select model, current: Gemini 3 Pro minimal";
    renderCycle();
    assert.ok(badgeEl.title.includes("Active Model Group: gemini"), badgeEl.title);

    hasModelTriggerBtn = false;
    extraButtons = [{{ innerText: "FutureModel Alpha (high)" }}];
    renderCycle();
    assert.ok(badgeEl.title.includes("Active Model Group: claude"), badgeEl.title);
    hasModelTriggerBtn = true;

    // 3. Per-bucket burn rate reset test
    // g5h: 42 -> 50 (+8 > +5) resets -> [50]; c5h: 88 -> 90 (+2 <= +5) preserved -> [88, 90]
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h.length, 1);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h[0].pct, 50);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.c5h.length, 2);

    fakeNow += 60000;
    currentQuotaResp.groups[0].buckets[1].remainingFraction = 0.40;
    currentQuotaResp.groups[1].buckets[1].remainingFraction = 0.80;
    await fetchCycle();
    await flush();
    assert.ok(badgeEl.title.includes("Gemini (5h) Burn Rate: 🔥"), badgeEl.title);
    assert.ok(badgeEl.title.includes("Claude/GPT (5h) Burn Rate: 🔥"), badgeEl.title);
    assert.ok(badgeEl.title.includes("%/hr (Est. depletion: ~"), badgeEl.title);
    assert.ok(badgeEl.innerHTML.includes("40%"), badgeEl.innerHTML);

    // Gemini 5h resets (40 -> 100), Claude 5h continues burning (80 -> 75)
    fakeNow += 60000;
    currentQuotaResp.groups[0].buckets[1].remainingFraction = 1.0;
    currentQuotaResp.groups[1].buckets[1].remainingFraction = 0.75;
    await fetchCycle();
    await flush();
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h.length, 1);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h[0].pct, 100);
    assert.ok(!badgeEl.title.includes("Gemini (5h) Burn Rate:"), badgeEl.title);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.c5h.length, 4);
    assert.ok(badgeEl.title.includes("Claude/GPT (5h) Burn Rate: 🔥"), badgeEl.title);

    // Gemini 5h burns in new cycle (100 -> 95), Claude experiences small fluctuation (+3 <= +5) (75 -> 78)
    fakeNow += 60000;
    currentQuotaResp.groups[0].buckets[1].remainingFraction = 0.95;
    currentQuotaResp.groups[1].buckets[1].remainingFraction = 0.78;
    await fetchCycle();
    await flush();
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.g5h.length, 2);
    assert.ok(badgeEl.title.includes("Gemini (5h) Burn Rate: 🔥"), badgeEl.title);
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.history.c5h.length, 5);

    // 4. Debounced MutationObserver and cancelAnimationFrame on reinjection
    badgeEl = null;
    for (let i = 0; i < 5; i++) observerCallback();
    assert.equal(rafCallbacks.size, 1, "5 DOM mutations should schedule a single requestAnimationFrame");
    const pendingRafId = mockWindow.__AGY_QUOTA_STATE__.reattachFrameId;
    assert.ok(pendingRafId !== null);
    rafCallbacks.get(pendingRafId)();
    assert.equal(mockWindow.__AGY_QUOTA_STATE__.reattachFrameId, null);
    assert.ok(badgeEl !== null, "Badge should be reattached after rAF");

    badgeEl = null;
    observerCallback();
    const cancelTargetId = mockWindow.__AGY_QUOTA_STATE__.reattachFrameId;
    assert.ok(cancelTargetId !== null);
    const res2 = vm.runInNewContext(JS_CODE, sandbox);
    assert.equal(res2, "OK");
    assert.ok(cancelledFrames.includes(cancelTargetId), "Pending reattachFrameId should be cancelled");
    assert.equal(disconnectedCount, 2);
    await flush();
}}

main().catch((err) => {{
    console.error(err);
    process.exit(1);
}});
"""
    run_proc = subprocess.run(
        [node_bin, "-e", harness],
        text=True,
        capture_output=True,
        timeout=10,
    )
    assert run_proc.returncode == 0, f"Headless JS behavior test failed:\n{run_proc.stderr}\n{run_proc.stdout}"
    print("[PASS] Headless Node.js test: dynamic model mapping, per-bucket burn-rate reset, and rAF-debounced MutationObserver verified!")


def main() -> int:
    parser = argparse.ArgumentParser(description="Antigravity Quota MCP Verification Tests")
    parser.add_argument(
        "--strict-cdp",
        action="store_true",
        help="Fail instead of skipping if no CDP target is found.",
    )
    args = parser.parse_args()

    print("=" * 68)
    print("1. COLD START & MCP HANDSHAKE TEST")
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
        print(f"[PASS] Process 1 (PID: {proc1.pid}) initialize handshake: {elapsed_ms:.1f} ms")
        assert init_resp["result"]["serverInfo"]["name"] == "antigravity-desktop-live-quota-mcp"

        # Wait 150ms for watcher thread to acquire the lock
        time.sleep(0.15)

        print("\n" + "=" * 68)
        print("2. MULTI-INSTANCE (2 CONCURRENT MCP PROCESSES) COLLISION PREVENTION TEST")
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

        print(f"• Process 1 Status: PID={status1['pid']}, Role={status1['role']}, LeaderPID={status1['leader_pid']}")
        print(f"• Process 2 Status: PID={status2['pid']}, Role={status2['role']}, LeaderPID={status2['leader_pid']}")

        assert status1["role"] == "LEADER", "Process 1 should have been LEADER!"
        assert status2["role"] == "STANDBY", "Process 2 should have been STANDBY!"
        assert status2["leader_pid"] == proc1.pid, "Process 2 should report Process 1 as Leader!"
        print("[PASS] Collision prevention verified: Only 1 process is LEADER, 2nd process is STANDBY!")

        print("\n" + "=" * 68)
        print("3. MCP TOOLS & LIVE QUOTA TEST ON BOTH PROCESSES")
        print("=" * 68)

        q1 = call_tool(proc1, 3, "get_quota_status")
        q2 = call_tool(proc2, 3, "get_quota_status")
        print(f"• Process 1 Quota Response: {q1['summary_text']}")
        print(f"• Process 2 Quota Response: {q2['summary_text']}")
        assert q1["ok"] is True and q2["ok"] is True
        print("[PASS] Both MCP processes respond cleanly to quota queries over stdio!")

        print("\n" + "=" * 68)
        print("4. LEADER FAILURE & AUTOMATIC FAILOVER TEST")
        print("=" * 68)

        proc1.terminate()
        proc1.wait(timeout=3)
        print(f"• Process 1 (PID: {proc1.pid}) terminated. Waiting for Process 2 to take over leadership...")

        time.sleep(1.2)
        status2_after = call_tool(proc2, 4, "get_instance_status")
        print(f"• Process 2 New Status: PID={status2_after['pid']}, Role={status2_after['role']}, LeaderPID={status2_after['leader_pid']}")
        assert status2_after["role"] == "LEADER", "Process 2 should automatically become LEADER when Process 1 exits!"
        assert status2_after.get("server_version") == "1.4.0", f"Expected version 1.4.0, got: {status2_after.get('server_version')}"
        cdp_status = status2_after.get("cdp_status", {})
        for req_key in ("cdp_available", "reason", "fix_hint", "antigravity_running", "has_remote_debugging_flag"):
            assert req_key in cdp_status, f"Missing '{req_key}' field in cdp_status!"
        if cdp_status.get("cdp_available"):
            assert cdp_status.get("antigravity_running") is True, "antigravity_running must be True when CDP is available!"
        print(f"• CDP Diagnostics: available={cdp_status['cdp_available']}, running={cdp_status['antigravity_running']}, reason={cdp_status['reason']}")
        print("[PASS] Automatic Failover, version (1.4.0), and cdp_status fields verified!")

        print("\n" + "=" * 68)
        print("5. LIVE WINDOW BADGE INJECTION (CDP) & PAYLOAD TEST")
        print("=" * 68)

        from src.ui_payload import build_injection_js

        js_payload = build_injection_js()
        for token in (
            "model-selector-trigger",
            "orchestrator",
            "neon",
            "hydrogen",
            "fetchSeq",
            "lastAppliedSeq",
            "detectActiveModelGroup(quota)",
            "g.description",
            "reattachFrameId",
            "requestAnimationFrame",
            "cancelAnimationFrame",
            "history.g5h",
            "history.c5h",
            "+ 5",
        ):
            assert token in js_payload, f"'{token}' not found in UI JS payload!"
        print("[PASS] UI JS payload contains dynamic model detection, rAF debouncing, per-bucket burn-rate, and fetchSeq guard!")

        _run_ui_payload_js_checks(js_payload)

        inj = call_tool(proc2, 5, "reinject_badge", {"force": True})
        print(f"• Injection Result: {json.dumps(inj, ensure_ascii=False)}")
        if cdp_status.get("cdp_available") or args.strict_cdp:
            assert inj["ok"] is True, f"Injection failed even though CDP is available/strict: {inj}"
        else:
            assert inj["ok"] is False
            assert "diagnostics" in inj and inj["diagnostics"].get("reason") != ""
            assert inj.get("message", "") != ""
            print(f"[SKIP/INFO] Live CDP window is currently closed (Reason: {inj['diagnostics']['reason']}). Message verified.")

        print("\n" + "=" * 68)
        print("6. SCRATCH CLEANUP & ALL MCP TOOLS (TOOLS/LIST) TEST")
        print("=" * 68)

        tools_resp = send_rpc(proc2, {"jsonrpc": "2.0", "id": 6, "method": "tools/list", "params": {}})
        tool_names = [t["name"] for t in tools_resp["result"]["tools"]]
        print(f"• Registered MCP Tools ({len(tool_names)}): {', '.join(tool_names)}")
        assert "clean_scratch_cache" in tool_names
        assert "get_quota_status" in tool_names
        assert "reinject_badge" in tool_names
        assert "get_instance_status" in tool_names

        clean_res = call_tool(proc2, 7, "clean_scratch_cache", {"dry_run": True})
        print(f"• Scratch Cleanup (Dry-Run): ok={clean_res.get('ok')}, cleanable={clean_res.get('deleted_files_count')}, size={clean_res.get('freed_human')}")
        assert clean_res.get("ok") is True

        print("\n" + "=" * 68)
        print("7. DESKTOP NOTIFICATION (NOTIFIER) & CRITICAL THRESHOLD/RESET LOGIC TEST")
        print("=" * 68)

        from src.models import BucketQuota, GroupQuota, QuotaReport
        from src.notifier import QuotaNotifier, is_notify_send_available

        print(f"• notify-send availability: {is_notify_send_available()}")
        notifier = QuotaNotifier()

        # Simulation 1: Quota report below critical threshold (10%)
        critical_report = QuotaReport(
            ok=True,
            gemini_weekly_pct=80,
            gemini_5h_pct=10,
            claude_weekly_pct=90,
            claude_5h_pct=80,
            argon_weekly_pct=70,
            groups=[
                GroupQuota(
                    display_name="Gemini Models",
                    description="Models within this group",
                    buckets=[
                        BucketQuota(
                            bucket_id="gemini-5h",
                            display_name="Five Hour Limit",
                            window="5h",
                            remaining_fraction=0.10,
                            remaining_percent=10,
                            reset_time="2026-11-08T05:00:00Z",
                            description="Running low",
                        )
                    ],
                )
            ],
        )

        # Should not emit alerts in standby mode
        standby_alerts = notifier.check_and_notify(critical_report, is_leader=False)
        assert len(standby_alerts) == 0, "Standby process must not send notifications!"

        # Should emit alert in leader mode
        leader_alerts = notifier.check_and_notify(critical_report, is_leader=True)
        print(f"• Critical Threshold Alert: {leader_alerts}")
        assert len(leader_alerts) == 1, "Should have emitted 1 notification at critical threshold!"
        assert "⚠️ Critical AI Quota Alert:" in leader_alerts[0], f"Unexpected critical alert title: {leader_alerts[0]}"

        # Should not emit duplicate alerts during cooldown (anti-spam)
        cooldown_alerts = notifier.check_and_notify(critical_report, is_leader=True)
        assert len(cooldown_alerts) == 0, "Spam should be suppressed during cooldown!"

        # Simulation 2: Quota refreshed (95%)
        reset_report = QuotaReport(
            ok=True,
            gemini_weekly_pct=80,
            gemini_5h_pct=95,
            claude_weekly_pct=90,
            claude_5h_pct=80,
            argon_weekly_pct=70,
            groups=[
                GroupQuota(
                    display_name="Gemini Models",
                    description="Models within this group",
                    buckets=[
                        BucketQuota(
                            bucket_id="gemini-5h",
                            display_name="Five Hour Limit",
                            window="5h",
                            remaining_fraction=0.95,
                            remaining_percent=95,
                            reset_time="2026-11-08T10:00:00Z",
                            description="Refreshed",
                        )
                    ],
                )
            ],
        )
        reset_alerts = notifier.check_and_notify(reset_report, is_leader=True)
        print(f"• Quota Refresh Alert: {reset_alerts}")
        assert len(reset_alerts) == 1, "Should have emitted refresh notification when quota reset!"
        assert "🔄 AI Quota Refreshed:" in reset_alerts[0], f"Unexpected refresh alert title: {reset_alerts[0]}"
        print("[PASS] Notifier alert logic, anti-spam cooldown, and leader guard verified!")

        print("\n" + "=" * 68)
        print("8. RFC-6455 WEBSOCKET FRAGMENTATION & PING/PONG TEST")
        print("=" * 68)

        from src.cdp_client import _recv_ws_text_frame

        def _send_server_frame(sock: socket.socket, fin: bool, opcode: int, payload: bytes) -> None:
            first_byte = (0x80 if fin else 0x00) | (opcode & 0x0F)
            length = len(payload)
            header = bytearray([first_byte])
            if length <= 125:
                header.append(length)
            elif length <= 65535:
                header.append(126)
                header.extend(struct.pack("!H", length))
            else:
                header.append(127)
                header.extend(struct.pack("!Q", length))
            sock.sendall(bytes(header) + payload)

        def _read_exact(sock: socket.socket, n: int) -> bytes:
            buf = bytearray()
            while len(buf) < n:
                chunk = sock.recv(n - len(buf))
                assert chunk, "Client Pong frame closed earlier than expected!"
                buf.extend(chunk)
            return bytes(buf)

        server_sock, client_sock = socket.socketpair()
        try:
            client_sock.settimeout(2.0)
            server_sock.settimeout(2.0)

            _send_server_frame(server_sock, fin=False, opcode=0x01, payload=b'{"id": 1, "res')
            _send_server_frame(server_sock, fin=True, opcode=0x09, payload=b"ping-123")
            _send_server_frame(server_sock, fin=True, opcode=0x00, payload=b'ult": "ok"}')

            got = _recv_ws_text_frame(client_sock)
            assert got == '{"id": 1, "result": "ok"}', f"Failed to receive expected reassembled text: {got!r}"

            pong_head = _read_exact(server_sock, 2)
            pong_fin = bool(pong_head[0] & 0x80)
            pong_opcode = pong_head[0] & 0x0F
            pong_masked = bool(pong_head[1] & 0x80)
            pong_len = pong_head[1] & 0x7F
            if pong_len == 126:
                pong_len = struct.unpack("!H", _read_exact(server_sock, 2))[0]
            elif pong_len == 127:
                pong_len = struct.unpack("!Q", _read_exact(server_sock, 8))[0]

            assert pong_fin is True, "Pong frame must have FIN=1!"
            assert pong_opcode == 0x0A, f"Expected opcode 0x0A (Pong), got: {pong_opcode:#x}"
            assert pong_masked is True, "Client-sent Pong frame must be masked!"

            mask_key = _read_exact(server_sock, 4)
            masked_payload = _read_exact(server_sock, pong_len)
            unmasked_payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(masked_payload))
            assert unmasked_payload == b"ping-123", f"Expected Pong payload 'ping-123', got: {unmasked_payload!r}"
            print("[PASS] Fragmented WebSocket frames reassembled and interleaved Ping answered with masked Pong!")
        finally:
            server_sock.close()
            client_sock.close()

        proc2.terminate()
        proc2.wait(timeout=3)

        print("\n[SUCCESS] All tests (Cold Start, Multi-Instance Lock, Failover, Quota, CDP UI, Scratch Cleanup, Desktop Notifications, and WebSocket Fragmentation/Pong) passed!")
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
