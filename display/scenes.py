"""Animated scenes for the 16x16 panel.

The design is deliberately monochrome: one configurable accent color plus a
dimmed version of it on a black background. Every sprite is built from small
2x2 eyes, a 2px mouth, and single-pixel indicators.

The same frames are used by the browser preview and the physical panel.
"""

from __future__ import annotations

import math
import time

from .canvas import BLACK, Canvas, Color

DEFAULT_ACCENT: Color = (0, 200, 255)

# Test patterns are diagnostic and intentionally use real RGB so the color
# order of the panel can be checked. The normal scenes never do.
RED: Color = (255, 40, 40)
GREEN: Color = (0, 255, 120)
BLUE: Color = (0, 80, 255)
WHITE: Color = (255, 255, 255)


def _dim(color: Color, factor: float = 0.35) -> Color:
    factor = max(0.0, min(1.0, factor))
    return (int(color[0] * factor), int(color[1] * factor), int(color[2] * factor))


def _mix(a: Color, b: Color, k: float) -> Color:
    k = max(0.0, min(1.0, k))
    return (
        int(a[0] + (b[0] - a[0]) * k),
        int(a[1] + (b[1] - a[1]) * k),
        int(a[2] + (b[2] - a[2]) * k),
    )


def _face(
    c: Canvas,
    accent: Color,
    blink: bool = False,
    look: tuple[int, int] = (0, 0),
    mouth: float = 0.0,
) -> None:
    """Minimal face: two 2x2 eyes and a 2px mouth."""
    for eye_x in (4, 10):
        x = eye_x + look[0]
        y = 5 + look[1]
        if blink:
            c.hline(x, y + 1, 2, accent)
        else:
            c.rect(x, y, 2, 2, accent)

    if mouth <= 0.05:
        c.hline(7, 10, 2, _dim(accent, 0.45))
    else:
        height = 1 + int(round(mouth * 3))
        c.rect(7, 11 - height, 2, height, accent)


def idle(c: Canvas, t: float, accent: Color) -> None:
    blink = (t % 4.2) < 0.12
    look = ((0, 0), (1, 0), (0, 0), (-1, 0), (0, -1))[int(t / 2.5) % 5]
    _face(c, accent, blink=blink, look=look)


def clock(c: Canvas, t: float, accent: Color) -> None:
    """Two-line clock: hours on top, minutes below."""
    now = time.localtime()
    c.text(f"{now.tm_hour:02d}", 4, 1, accent)
    c.text(f"{now.tm_min:02d}", 4, 9, _dim(accent, 0.4))


def timer(c: Canvas, t: float, seconds: float, accent: Color) -> None:
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        top = min(99, seconds // 3600)
        bottom = (seconds % 3600) // 60
    else:
        top = min(99, seconds // 60)
        bottom = seconds % 60

    c.rect(0, 0, 16, 16, _dim(accent, 0.25), fill=False)
    c.text(f"{top:02d}", 4, 1, accent)
    c.text(f"{bottom:02d}", 4, 9, _dim(accent, 0.45))


def listening(c: Canvas, t: float, level: float, accent: Color) -> None:
    level = max(0.0, min(1.0, level))
    _face(c, accent, look=(0, -1))
    for i in range(4):
        wave = 0.5 + 0.5 * abs(math.sin(t * 6 + i * 0.9))
        height = 1 + int(round(2 * min(1.0, level * 0.7 + wave * 0.3)))
        x = 2 + i * 4
        for y in range(16 - height, 16):
            c.set(x, y, accent)


def thinking(c: Canvas, t: float, accent: Color) -> None:
    _face(c, accent, look=(0, -1))
    active = int(t * 4) % 4
    for i in range(3):
        color = accent if i == active else _dim(accent, 0.3)
        c.set(5 + i * 3, 14, color)


def speaking(c: Canvas, t: float, level: float, accent: Color) -> None:
    level = max(0.0, min(1.0, level))
    mouth = 0.25 + 0.75 * min(1.0, level * 0.6 + 0.4 * abs(math.sin(t * 7)))
    _face(c, accent, mouth=mouth)


def error(c: Canvas, t: float, accent: Color) -> None:
    # 3x3 X eyes, slightly larger than the normal 2x2 eyes.
    for eye_x in (3, 10):
        for i in range(3):
            c.set(eye_x + i, 4 + i, accent)
            c.set(eye_x + 2 - i, 4 + i, accent)
    c.hline(7, 11, 2, _dim(accent, 0.4))


def alarm(c: Canvas, t: float, accent: Color) -> None:
    flash = int(t * 4) % 2 == 0
    if flash:
        c.fill(_dim(accent, 0.12))
    c.rect(0, 0, 16, 16, accent if flash else _dim(accent, 0.35), fill=False)
    c.text_centered("!", 5, accent)


def music(c: Canvas, t: float, level: float, accent: Color) -> None:
    level = max(0.0, min(1.0, level))
    for i in range(8):
        wave = abs(math.sin(t * 3 + i * 0.7))
        height = 2 + int(round(11 * min(1.0, level * 0.5 + wave * 0.7)))
        color = _mix(accent, _dim(accent, 0.2), i / 7)
        x = i * 2
        for y in range(16 - height, 16):
            c.set(x, y, color)
            c.set(x + 1, y, color)


def scrolling_text(c: Canvas, text: str, t: float, color: Color) -> None:
    width = c.text_width(text)
    if width <= c.width:
        c.text_centered(text, 5, color)
        return
    offset = int(t * 14) % (width + c.width)
    c.text(text, c.width - offset, 5, color)


def _pattern(c: Canvas, name: str, t: float) -> None:
    """Diagnostic patterns. These keep RGB colors on purpose."""
    name = (name or "").lower()
    if name == "bars":
        colors = (RED, GREEN, BLUE, WHITE)
        for i, color in enumerate(colors):
            c.rect(i * 4, 0, 4, 16, color)
    elif name == "checker":
        for y in range(16):
            for x in range(16):
                if (x // 2 + y // 2) % 2 == 0:
                    c.set(x, y, WHITE)
    elif name == "gradient":
        for y in range(16):
            for x in range(16):
                c.set(x, y, (x * 17, y * 17, 255 - x * 12))
    elif name == "corners":
        c.rect(0, 0, 16, 16, (0, 0, 30), fill=True)
        for x, y, color in ((0, 0, RED), (15, 0, GREEN), (0, 15, BLUE), (15, 15, WHITE)):
            c.rect(x - 1 if x else 0, y - 1 if y else 0, 2, 2, color)
        step = int(t * 4) % 16
        c.set(step, 8, WHITE)
    elif name == "snake":
        border = [(x, 0) for x in range(16)] + [(15, y) for y in range(1, 16)]
        border += [(x, 15) for x in range(14, -1, -1)] + [(0, y) for y in range(14, 0, -1)]
        idx = int(t * 8) % len(border)
        for i, (x, y) in enumerate(border):
            if i == idx:
                c.set(x, y, GREEN)
            elif i < idx:
                c.set(x, y, _dim(GREEN, 0.3))
    else:
        c.text_centered(name[:5].upper(), 5, WHITE)


def render_frame(
    state: str = "idle",
    t: float = 0.0,
    level: float = 0.0,
    text: str = "",
    text_color: Color | None = None,
    timer_seconds: float = 0,
    brightness: int = 255,
    pattern: str = "",
    accent: Color = DEFAULT_ACCENT,
) -> bytes:
    """Render one frame for the given state."""
    c = Canvas()
    state = (state or "idle").lower()
    text_color = text_color or accent

    if pattern:
        _pattern(c, pattern, t)
    elif text:
        scrolling_text(c, text, t, text_color)
    elif state == "idle":
        if timer_seconds > 0:
            timer(c, t, timer_seconds, accent)
        elif int(t) % 12 < 8:
            idle(c, t, accent)
        else:
            clock(c, t, accent)
    elif state == "listening":
        listening(c, t, level, accent)
    elif state == "thinking":
        thinking(c, t, accent)
    elif state == "speaking":
        speaking(c, t, level, accent)
    elif state == "error":
        error(c, t, accent)
    elif state == "timer":
        timer(c, t, timer_seconds, accent)
    elif state == "alarm":
        alarm(c, t, accent)
    elif state == "music":
        music(c, t, level, accent)
    else:
        idle(c, t, accent)

    return c.to_bytes(brightness)
