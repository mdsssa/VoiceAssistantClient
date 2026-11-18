"""Minimal DDP (Distributed Display Protocol) sender for WLED.

WLED listens for DDP on UDP port 4048 by default. A single UDP packet holds the
whole 16x16 RGB888 frame (768 bytes), so one packet per frame is enough.
"""

from __future__ import annotations

import socket

DDP_PORT = 4048


class DDPSender:
    def __init__(self, host: str, port: int = DDP_PORT, width: int = 16, height: int = 16):
        self.host = host
        self.port = port
        self.width = width
        self.height = height
        self.sequence = 0
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.sent = 0
        self.errors = 0

    def send(self, frame: bytes) -> None:
        expected = self.width * self.height * 3
        if len(frame) != expected:
            raise ValueError(f"expected {expected} bytes, got {len(frame)}")

        header = bytes(
            (
                0x41,                 # version 1, push
                self.sequence & 0x0F, # sequence
                0x01,                 # RGB, 8 bits per channel
                0x01,                 # destination id
            )
        ) + (0).to_bytes(4, "big") + len(frame).to_bytes(2, "big")

        try:
            self.sock.sendto(header + frame, (self.host, self.port))
            self.sent += 1
        except OSError:
            self.errors += 1
            raise

        self.sequence = (self.sequence + 1) & 0x0F
