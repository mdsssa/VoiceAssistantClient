"""Fire-and-forget client used by the assistant.

Events are queued and sent to the display daemon from a background thread, so a
missing or slow display never blocks the voice loop. A short flush on exit makes
sure the final ``idle`` event is not lost when a one-shot voice process quits.
"""

from __future__ import annotations

import atexit
import json
import os
import threading
import time
import urllib.request
from collections import deque

_BASE_URL = os.environ.get("KAIRA_DISPLAY_URL", "http://127.0.0.1:8090").rstrip("/")
_ENABLED = os.environ.get("KAIRA_DISPLAY", "1").strip().lower() not in {"0", "false", "no", "off"}

_queue: deque[tuple[str, dict]] = deque(maxlen=8)
_condition = threading.Condition()
_started = False
_last_state: str | None = None
_last_timer: int | None = None
_last_level = 0.0
_last_level_at = 0.0
_busy = False
_opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def _start() -> None:
    global _started
    if _started or not _ENABLED or not _BASE_URL:
        return
    _started = True
    threading.Thread(target=_worker, name="kaira-display-client", daemon=True).start()


def _post(path: str, payload: dict) -> None:
    if not _ENABLED or not _BASE_URL:
        return
    _start()
    with _condition:
        if path == "/api/state":
            _queue.clear()
        _queue.append((path, payload))
        _condition.notify()


def _worker() -> None:
    global _busy
    while True:
        with _condition:
            while not _queue:
                _condition.wait()
            path, payload = _queue.popleft()
            _busy = True
        request = urllib.request.Request(
            _BASE_URL + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with _opener.open(request, timeout=0.4) as response:
                response.read()
        except Exception:
            # Display is optional: never break the assistant because of it.
            pass
        finally:
            with _condition:
                _busy = False
                _condition.notify_all()


def state(name: str) -> None:
    global _last_state
    name = (name or "idle").lower()
    if name == _last_state:
        return
    _last_state = name
    _post("/api/state", {"state": name})


def level(value: float) -> None:
    global _last_level, _last_level_at
    try:
        value = float(value)
    except (TypeError, ValueError):
        return
    value = max(0.0, min(1.0, value))
    now = time.monotonic()
    if now - _last_level_at < 0.05 and abs(value - _last_level) < 0.02:
        return
    _last_level = value
    _last_level_at = now
    _post("/api/level", {"level": round(value, 3)})


def text(value: str, color: str | None = None) -> None:
    payload: dict = {"text": value}
    if color:
        payload["color"] = color
    _post("/api/text", payload)


def timer(seconds: float) -> None:
    global _last_timer
    value = max(0, int(seconds or 0))
    if value == _last_timer:
        return
    _last_timer = value
    _post("/api/timer", {"seconds": value})


def clear() -> None:
    global _last_state, _last_timer
    _last_state = None
    _last_timer = None
    _post("/api/clear", {})


def flush(timeout: float = 1.0) -> None:
    """Wait for queued events to be sent (used at process exit)."""
    if not _started:
        return
    deadline = time.monotonic() + timeout
    with _condition:
        while (_queue or _busy) and time.monotonic() < deadline:
            _condition.wait(0.02)


atexit.register(flush)
