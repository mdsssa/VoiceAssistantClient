"""Kera 16x16 display.

The assistant imports this package and calls ``state``/``level``/``timer``.
The display daemon renders frames, serves a live browser preview, and sends
DDP packets to WLED.
"""

from .client import clear, flush, level, state, text, timer

__all__ = ["state", "level", "text", "timer", "clear", "flush"]
