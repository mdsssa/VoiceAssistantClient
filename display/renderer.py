"""Display state machine and the render loop."""

from __future__ import annotations

import threading
import time

from . import scenes
from .canvas import Color
from .scenes import DEFAULT_ACCENT

STATES = {"idle", "listening", "thinking", "speaking", "error", "timer", "alarm", "music"}


class DisplayState:
    """Thread-safe state shared by the HTTP API and the render thread."""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self.state = "idle"
        self.level = 0.0
        self.brightness = 255
        self.accent: Color = DEFAULT_ACCENT
        self.text = ""
        self.text_color: Color | None = None
        self.pattern = ""
        self._text_until = 0.0
        self._pattern_until = 0.0
        self._timer_end = 0.0
        self._timer_total = 0
        self.last_event = time.monotonic()

    def set_state(self, name: str) -> None:
        name = (name or "idle").lower()
        if name not in STATES:
            raise ValueError(f"unknown state: {name}")
        with self._lock:
            self.state = name
            self.last_event = time.monotonic()

    def set_level(self, value: float) -> None:
        with self._lock:
            self.level = max(0.0, min(1.0, float(value)))
            self.last_event = time.monotonic()

    def set_brightness(self, value: int) -> None:
        with self._lock:
            self.brightness = max(0, min(255, int(value)))
            self.last_event = time.monotonic()

    def set_accent(self, color: Color) -> None:
        with self._lock:
            self.accent = tuple(max(0, min(255, int(c))) for c in color)
            self.last_event = time.monotonic()

    def set_text(self, text: str, color: Color | None = None, ttl: float = 10.0) -> None:
        with self._lock:
            self.text = (text or "").strip()[:64]
            self.text_color = color
            self._text_until = time.monotonic() + ttl if self.text else 0.0
            self.last_event = time.monotonic()

    def set_pattern(self, pattern: str, ttl: float = 8.0) -> None:
        with self._lock:
            self.pattern = (pattern or "").strip().lower()
            self._pattern_until = time.monotonic() + ttl if self.pattern else 0.0
            self.last_event = time.monotonic()

    def set_timer(self, seconds: float) -> None:
        with self._lock:
            seconds = max(0, int(seconds))
            self._timer_total = seconds
            self._timer_end = time.monotonic() + seconds if seconds else 0.0
            self.last_event = time.monotonic()

    def timer_seconds(self) -> int:
        with self._lock:
            if not self._timer_end:
                return 0
            return max(0, int(round(self._timer_end - time.monotonic())))

    def snapshot(self) -> dict:
        now = time.monotonic()
        with self._lock:
            if self.text and now > self._text_until:
                self.text = ""
            if self.pattern and now > self._pattern_until:
                self.pattern = ""

            # If the assistant dies mid-turn, do not freeze on "thinking".
            if self.state in {"listening", "thinking", "speaking"} and now - self.last_event > 45:
                self.state = "idle"
                self.level = 0.0
            if self.state in {"error", "alarm"} and now - self.last_event > 90:
                self.state = "idle"

            return {
                "state": self.state,
                "level": round(self.level, 3),
                "brightness": self.brightness,
                "accent": self.accent,
                "text": self.text,
                "text_color": self.text_color,
                "pattern": self.pattern,
                "timer": self.timer_seconds(),
            }

    def reset(self) -> None:
        with self._lock:
            self.state = "idle"
            self.level = 0.0
            self.text = ""
            self.text_color = None
            self.pattern = ""
            self._text_until = 0.0
            self._pattern_until = 0.0
            self._timer_end = 0.0
            self._timer_total = 0
            self.last_event = time.monotonic()


class Renderer:
    """Renders frames at a fixed rate and pushes them to configured links."""

    def __init__(self, ddp=None, serial_link=None, fps: int = 30) -> None:
        self.state = DisplayState()
        self.ddp = ddp
        self.serial_link = serial_link
        self.fps = max(1, min(60, int(fps)))
        self._lock = threading.Lock()
        self._frame = bytes(16 * 16 * 3)
        self._meta: dict = {
            "state": "idle",
            "level": 0.0,
            "brightness": 255,
            "accent": DEFAULT_ACCENT,
            "timer": 0,
            "pattern": "",
            "fps": 0,
            "wled": ddp is not None,
            "serial": serial_link is not None,
        }
        self._running = False
        self._thread: threading.Thread | None = None
        self._frames = 0
        self._fps = 0.0
        self._send_errors = 0

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._running = True
        self._thread = threading.Thread(target=self._loop, name="kera-display", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._running = False
        if self._thread:
            self._thread.join(timeout=1.0)

    def snapshot(self) -> tuple[bytes, dict]:
        with self._lock:
            meta = dict(self._meta)
            return self._frame, meta

    def status(self) -> dict:
        """Live state for the status endpoint (not the last rendered frame)."""
        meta = self.state.snapshot()
        with self._lock:
            meta.update(
                {
                    "fps": round(self._fps, 1),
                    "wled": self.ddp is not None,
                    "serial": self.serial_link is not None,
                    "frames": self._frames,
                    "ddp_errors": getattr(self.ddp, "errors", 0) if self.ddp else 0,
                    "serial_errors": getattr(self.serial_link, "errors", 0) if self.serial_link else 0,
                    "send_errors": self._send_errors,
                }
            )
        return meta

    def _loop(self) -> None:
        started = time.monotonic()
        fps_started = started
        fps_frames = 0
        while self._running:
            frame_started = time.monotonic()
            t = frame_started - started
            meta = self.state.snapshot()
            try:
                frame = scenes.render_frame(
                    state=meta["state"],
                    t=t,
                    level=meta["level"],
                    text=meta["text"],
                    text_color=meta["text_color"],
                    timer_seconds=meta["timer"],
                    brightness=meta["brightness"],
                    pattern=meta["pattern"],
                    accent=meta["accent"],
                )
            except Exception as e:  # a broken scene should not kill the panel
                print(f"[display] render error: {e}")
                frame = bytes(16 * 16 * 3)

            for link in (self.ddp, self.serial_link):
                if link is None:
                    continue
                try:
                    link.send(frame)
                except Exception:
                    self._send_errors += 1

            with self._lock:
                self._frame = frame
                self._frames += 1
                fps_frames += 1
                elapsed = frame_started - fps_started
                if elapsed >= 1.0:
                    self._fps = fps_frames / elapsed
                    fps_started = frame_started
                    fps_frames = 0
                self._meta = {
                    "state": meta["state"],
                    "level": meta["level"],
                    "brightness": meta["brightness"],
                    "accent": meta["accent"],
                    "timer": meta["timer"],
                    "pattern": meta["pattern"],
                    "fps": round(self._fps, 1),
                    "wled": self.ddp is not None,
                    "serial": self.serial_link is not None,
                    "frames": self._frames,
                    "ddp_errors": getattr(self.ddp, "errors", 0) if self.ddp else 0,
                    "serial_errors": getattr(self.serial_link, "errors", 0) if self.serial_link else 0,
                    "send_errors": self._send_errors,
                }

            sleep_for = 1.0 / self.fps - (time.monotonic() - frame_started)
            if sleep_for > 0:
                time.sleep(sleep_for)
