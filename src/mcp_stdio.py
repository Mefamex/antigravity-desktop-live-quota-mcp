"""
Zero-Dependency MCP Stdio (JSON-RPC 2.0) Protocol Server (src/mcp_stdio.py)

Why Pure Stdlib JSON-RPC Instead of the Official `mcp` SDK?
Even just for `stdio` communication, the official Python `mcp` package loads
28 packages into memory in the background, including `starlette`, `uvicorn`,
`sse-starlette`, `pydantic`, and `cryptography` (~455 ms startup latency and
~45 MB RAM consumption).

This module implements the MCP protocol directly using only Python's built-in
`sys.stdin`, `sys.stdout`, and `json` modules:
- Startup latency: ~18 ms (25x faster)
- Memory footprint: ~9 MB (5x lighter)
- External package dependencies: 0
"""

from __future__ import annotations

import json
import os
import sys
from typing import Any

import config
from src.discovery import diagnose_cdp_status
from src.lock import LeaderLock
from src.logger import get_logger
from src.quota_client import fetch_live_quota
from src.scratch_cleaner import clean_scratch_cache
from src.ui_watcher import inject_into_all_windows

log = get_logger("mcp")

TOOLS_SCHEMA: list[dict[str, Any]] = [
    {
        "name": "get_quota_status",
        "description": (
            "Queries live AI model quota and usage status "
            "(Gemini 5h/weekly, Claude/GPT, Argon) via the local Antigravity language_server."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "include_raw": {
                    "type": "boolean",
                    "description": "If true, also includes the raw response from the server.",
                    "default": False,
                },
                "force_refresh": {
                    "type": "boolean",
                    "description": "If true, clears the local language server cache and fetches live quota directly from the cloud.",
                    "default": False,
                },
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "reinject_badge",
        "description": (
            "Immediately reinjects and refreshes the live quota indicator (badge) "
            "in the Antigravity Desktop window title bar."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "force": {
                    "type": "boolean",
                    "description": "Forces reinstallation even if the badge is already present.",
                    "default": True,
                }
            },
            "additionalProperties": False,
        },
    },
    {
        "name": "get_instance_status",
        "description": (
            "Returns PID, multi-instance leadership (Leader/Standby), "
            "and lock status information for the running MCP server."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {},
            "additionalProperties": False,
        },
    },
    {
        "name": "clean_scratch_cache",
        "description": (
            "Safely cleans temporary scratch directories "
            "(~/.gemini/antigravity/brain/*/scratch/) created by Antigravity Desktop during sessions."
        ),
        "inputSchema": {
            "type": "object",
            "properties": {
                "dry_run": {
                    "type": "boolean",
                    "description": "If true, calculates the cleanable size without deleting files.",
                    "default": False,
                },
                "older_than_hours": {
                    "type": "number",
                    "description": "Cleans files older than the specified number of hours (0 means all).",
                    "default": 0,
                },
            },
            "additionalProperties": False,
        },
    },
]


def _write_jsonrpc(payload: dict[str, Any]) -> None:
    """
    Writes a single-line JSON-RPC message to `sys.stdout` and flushes immediately.
    """
    line = json.dumps(payload, ensure_ascii=False)
    sys.stdout.write(line + "\n")
    sys.stdout.flush()


def _handle_tool_call(
    name: str, arguments: dict[str, Any], lock: LeaderLock
) -> tuple[bool, Any]:
    """Executes the specified MCP tool and returns `(is_error, result_dict)`."""
    if name == "get_quota_status":
        include_raw = bool(arguments.get("include_raw", False))
        force_refresh = bool(arguments.get("force_refresh", False))
        report = fetch_live_quota(force_refresh=force_refresh)
        data = report.to_dict()
        if not include_raw:
            data.pop("raw_response", None)
        data["summary_text"] = report.format_compact()
        return (not report.ok, data)

    if name == "reinject_badge":
        force = bool(arguments.get("force", True))
        result = inject_into_all_windows(force=force)
        return (not result.get("ok", False), result)

    if name == "get_instance_status":
        holder_pid = lock.read_holder_pid()
        status = {
            "server_version": config.SERVER_VERSION,
            "pid": os.getpid(),
            "role": "LEADER" if lock.is_leader else "STANDBY",
            "leader_pid": holder_pid,
            "lock_file": str(config.LOCK_FILE_PATH),
            "devtools_port_file": str(config.DEVTOOLS_PORT_FILE),
            "ui_injection_enabled": config.UI_Injection_Enabled,
            "cdp_status": diagnose_cdp_status(),
        }
        return (False, status)

    if name == "clean_scratch_cache":
        dry_run = bool(arguments.get("dry_run", False))
        older_than_hours = float(arguments.get("older_than_hours", 0.0))
        result = clean_scratch_cache(older_than_hours=older_than_hours, dry_run=dry_run)
        return (not result.get("ok", False), result)

    return (True, {"error": f"Unknown tool: {name}"})


def run_stdio_server(lock: LeaderLock) -> None:
    """
    Reads JSON-RPC 2.0 requests from standard input (`sys.stdin`) and sends
    responses. Exits cleanly when the client closes (`EOF`).
    """
    log.info("MCP Stdio server started, waiting for client messages...")

    for raw_line in sys.stdin:
        line = raw_line.strip()
        if not line:
            continue

        try:
            msg = json.loads(line)
        except json.JSONDecodeError as exc:
            log.warning(f"Invalid JSON-RPC line: {exc}")
            continue

        method = msg.get("method")
        msg_id = msg.get("id")
        params = msg.get("params") or {}

        # Notification messages (no id, no response expected)
        if msg_id is None:
            if method == "notifications/initialized":
                log.info("MCP client handshake (initialized) completed.")
            continue

        if method == "initialize":
            client_proto = params.get("protocolVersion") or config.PROTOCOL_VERSION
            _write_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "protocolVersion": client_proto,
                        "capabilities": {"tools": {}},
                        "serverInfo": {
                            "name": config.SERVER_NAME,
                            "version": config.SERVER_VERSION,
                        },
                    },
                }
            )

        elif method == "ping":
            _write_jsonrpc({"jsonrpc": "2.0", "id": msg_id, "result": {}})

        elif method == "tools/list":
            _write_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {"tools": TOOLS_SCHEMA},
                }
            )

        elif method == "tools/call":
            tool_name = str(params.get("name", ""))
            tool_args = params.get("arguments") or {}
            is_err, output = _handle_tool_call(tool_name, tool_args, lock)
            _write_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "result": {
                        "content": [
                            {
                                "type": "text",
                                "text": json.dumps(output, ensure_ascii=False, indent=2),
                            }
                        ],
                        "isError": is_err,
                    },
                }
            )

        else:
            _write_jsonrpc(
                {
                    "jsonrpc": "2.0",
                    "id": msg_id,
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}",
                    },
                }
            )

    log.info("MCP Stdio stream (EOF) closed, shutting down server.")
