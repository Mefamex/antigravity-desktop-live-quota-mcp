"""
Sıfır Bağımlılıklı Chrome DevTools Protocol (CDP) İstemcisi (src/cdp_client.py)

Neden Standart Kütüphane (`socket`) Kullanıldı?
Harici `websockets` paketi veya sanal ortam (venv) bağımlılığı olmadan, Python'un
yalnızca yerleşik modülleriyle (`socket`, `base64`, `struct`, `urllib.parse`)
RFC-6455 WebSocket el sıkışmasını ve çerçeve (frame) iletimini gerçekleştirir.
Böylece Python sürümü güncellense dahi asla paket kırılması yaşanmaz.
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


def _send_ws_text_frame(sock: socket.socket, text: str) -> None:
    """RFC-6455 istemci maskeli metin çerçevesi (masked text frame) gönderir."""
    payload = text.encode("utf-8")
    length = len(payload)
    mask_key = os.urandom(4)

    header = bytearray()
    header.append(0x81)  # FIN=1, Opcode=1 (Text)

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


def _recv_exact(sock: socket.socket, n: int) -> bytes:
    """Soketten tam olarak `n` bayt okur."""
    buf = bytearray()
    while len(buf) < n:
        chunk = sock.recv(n - len(buf))
        if not chunk:
            raise ConnectionError("WebSocket bağlantısı erken kapandı.")
        buf.extend(chunk)
    return bytes(buf)


def _recv_ws_text_frame(sock: socket.socket) -> str:
    """Sunucudan gelen metin çerçevesini okur (ping/pong çerçevelerini atlar)."""
    while True:
        first_two = _recv_exact(sock, 2)
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
            raise ConnectionError("CDP WebSocket sunucusu bağlantıyı kapattı.")
        if opcode == 0x09:  # Ping -> Pong gönder
            continue
        if opcode == 0x01:  # Text frame
            return payload.decode("utf-8", errors="ignore")


def cdp_evaluate(
    ws_url: str,
    expression: str,
    await_promise: bool = False,
    return_by_value: bool = True,
) -> dict[str, Any]:
    """
    Belirtilen CDP WebSocket URL'sine bağlanır, `Runtime.evaluate` çağrısını
    yapar ve sonucu döndürüp soketi temizce kapatır.
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

        # HTTP 101 yanıt başlığını oku
        resp_header = b""
        while b"\r\n\r\n" not in resp_header:
            chunk = sock.recv(1024)
            if not chunk:
                raise ConnectionError("CDP WebSocket el sıkışması başarısız.")
            resp_header += chunk

        if b"101" not in resp_header.split(b"\r\n", 1)[0]:
            raise ConnectionError("CDP WebSocket 101 Switching Protocols dönmedi.")

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
