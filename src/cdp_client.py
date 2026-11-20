"""
Zero-Dependency Chrome DevTools Protocol (CDP) Client (src/cdp_client.py)

Why the Standard Library (`socket`) Is Used:
Performs the RFC-6455 WebSocket handshake and frame transmission using only
Python's built-in modules (`socket`, `base64`, `struct`, `urllib.parse`), with
no external `websockets` package or virtual environment (venv) dependency.
This ensures packages never break even across Python version upgrades.
"""

from __future__ import annotations

import base64
import json
import os
import socket
import struct
from typing import Any
from urllib.parse import urlparse

import config


def _send_ws_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    """Sends an RFC-6455 client-masked WebSocket frame (FIN=1)."""
    length = len(payload)
    mask_key = os.urandom(4)

    header = bytearray()
    header.append(0x80 | (opcode & 0x0F))

    if length <= 125:
        header.append(0x80 | length)
    elif length <= 65535:
        header.append(0x80 | 126)
        header.extend(struct.pack("!H", length))
    else:
        header.append(0x80 | 127)
        header.extend(struct.pack("!Q", length))

    header.extend(mask_key)
    masked_payload = bytearray(b ^ mask_key[i % 4] for i, b in enumerate(payload))
    sock.sendall(header + masked_payload)


def _send_ws_text_frame(sock: socket.socket, text: str) -> None:
    """Sends an RFC-6455 client-masked text frame."""
    _send_ws_frame(sock, 0x01, text.encode("utf-8"))


def _send_ws_control_frame(sock: socket.socket, opcode: int, payload: bytes = b"") -> None:
    """Sends an RFC-6455 client-masked control frame (e.g., Pong)."""
    _send_ws_frame(sock, opcode, payload)


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Reads exactly `n` bytes from the socket."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("WebSocket connection closed prematurely.")
        buf.extend(chunk)
    return bytes(buf)


def _recv_ws_text_frame(sock: socket.socket) -> str:
    """Reads a (possibly fragmented) text frame from the server and replies to Pings with Pong."""
    fragments = bytearray()
    in_text_message = False

    while True:
        first_two = _recv_exact(sock, 2)
        fin = bool(first_two[0] & 0x80)
        opcode = first_two[0] & 0x0F
        is_masked = bool(first_two[1] & 0x80)
        length = first_two[1] & 0x7F

        if length == 126:
            length = struct.unpack("!H", _recv_exact(sock, 2))[0]
        elif length == 127:
            length = struct.unpack("!Q", _recv_exact(sock, 8))[0]

        mask_key = _recv_exact(sock, 4) if is_masked else b""
        payload = _recv_exact(sock, length)

        if is_masked:
            payload = bytes(b ^ mask_key[i % 4] for i, b in enumerate(payload))

        if opcode == 0x08:  # Connection Close
            raise ConnectionError("CDP WebSocket server closed the connection.")
        if opcode == 0x09:  # Ping -> send Pong
            _send_ws_control_frame(sock, 0x0A, payload)
            continue
        if opcode == 0x0A:  # Pong
            continue
        if opcode == 0x01:  # Text frame (start of single or fragmented message)
            fragments = bytearray(payload)
            in_text_message = True
            if fin:
                return fragments.decode("utf-8", errors="ignore")
            continue
        if opcode == 0x00:  # Continuation frame
            if not in_text_message:
                continue
            fragments.extend(payload)
            if fin:
                return fragments.decode("utf-8", errors="ignore")
            continue


def cdp_evaluate(
    ws_url: str,
    expression: str,
    await_promise: bool = False,
    return_by_value: bool = True,
) -> dict[str, Any]:
    """
    Connects to the specified CDP WebSocket URL, invokes `Runtime.evaluate`,
    returns the result, and cleanly closes the socket.
    """
    parsed = urlparse(ws_url)
    host = parsed.hostname or "127.0.0.1"
    port = parsed.port or 80
    path = parsed.path or "/"
    if parsed.query:
        path = f"{path}?{parsed.query}"

    ws_key = base64.b64encode(os.urandom(16)).decode("ascii")
    handshake = (
        f"GET {path} HTTP/1.1\r\n"
        f"Host: {host}:{port}\r\n"
        f"Upgrade: websocket\r\n"
        f"Connection: Upgrade\r\n"
        f"Sec-WebSocket-Key: {ws_key}\r\n"
        f"Sec-WebSocket-Version: 13\r\n\r\n"
    )

    with socket.create_connection((host, port), timeout=config.NETWORK_TIMEOUT_SEC) as sock:
        sock.sendall(handshake.encode("ascii"))

        # Read HTTP 101 response header
        resp_header = b""
        while b"\r\n\r\n" not in resp_header:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("CDP WebSocket handshake failed.")
            resp_header += chunk

        if b"101" not in resp_header.split(b"\r\n", 1)[0]:
            raise ConnectionError("CDP WebSocket did not return 101 Switching Protocols.")

        req_id = 1
        message = {
            "id": req_id,
            "method": "Runtime.evaluate",
            "params": {
                "expression": expression,
                "awaitPromise": await_promise,
                "returnByValue": return_by_value,
            },
        }
        _send_ws_text_frame(sock, json.dumps(message))

        while True:
            raw_msg = _recv_ws_text_frame(sock)
            data = json.loads(raw_msg)
            if data.get("id") == req_id:
                return data
