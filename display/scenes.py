"""Animated scenes for the 16x16 panel.

Everything is drawn in code so the preview and the physical panel always show
the same thing. ``render_frame`` returns one RGB888 frame.
"""

from __future__ import annotations

import math
import time

from .canvas import BLACK, Canvas, Color

CYAN: Color = (0, 200, 255)
CYAN_DIM: Color = (0, 55, 80)
GREEN: Color = (0, 255, 120)
GREEN_DIM: Color = (0, 80, 40)
AMBER: Color = (255, 170, 0)
AMBER_DIM: Color = (70, 45, 0)
ORANGE: Color = (255, 120, 0)
ORANGE_DIM: Color = (70, 30, 0)
RED: Color = (255, 40, 40)
RED_DIM: Color = (70, 0, 0)
PURPLE: Color = (170, 80, 255)
WHITE: Color = (255, 255, 255)
TEAL: Color = (0, 140, 180)


def _face(
    c: Canvas,
    eye_color: Color = CYAN,
    blink: bool = False,
    look: tuple[int, int] = (0, 0),
    mouth: float = 0.0,
    mouth_color: Color = TEAL,
) -> None:
    """Two pixel eyes at rows 5-7 and a mouth at the bottom."""
    for ex in (3, 10):
        if blink:
            c.hline(ex, 6, 3, eye_color)
            continue
        c.rect(ex, 5, 3, 3, eye_color)
        c.set(ex + 1 + look[0], 6 + look[1], BLACK)

    if mouth <= 0.05:
        c.hline(6, 11, 4, mouth_color)
    else:
        height = 1 + int(round(mouth * 3))
        c.rect(6, 12 - height, 4, height, mouth_color)


def idle(c: Canvas, t: float) -> None:
    blink = (t % 4.2) < 0.12
    look = ((0, 0), (1, 0), (0, 0), (-1, 0), (0, -1))[int(t / 2.5) % 5]
    _face(c, blink=blink, look=look)
    # a small breathing dot under the face
    glow = 0.35 + 0.65 * (0.5 + 0.5 * math.sin(t * 2.2))
    c.set(7, 15, _mix(CYAN_DIM, CYAN, glow))
    c.set(8, 15, _mix(CYAN_DIM, CYAN, glow))


def clock(c: Canvas, t: float) -> None:
    """Two-line clock: hours on top, minutes below."""
    now = time.localtime()
    hours = f"{now.tm_hour:02d}"
    minutes = f"{now.tm_min:02d}"
    c.text(hours, 4, 1, CYAN)
    c.text(minutes, 4, 9, CYAN_DIM)
    if int(t * 2) % 2 == 0:
        c.set(1, 5, CYAN_DIM)
        c.set(1, 10, CYAN_DIM)


def timer(c: Canvas, t: float, seconds: float) -> None:
    seconds = max(0, int(seconds))
    if seconds >= 3600:
        top = min(99, seconds // 3600)
        bottom = (seconds % 3600) // 60
    else:
        top = min(99, seconds // 60)
        bottom = seconds % 60

    c.rect(0, 0, 16, 16, ORANGE_DIM, fill=False)
    c.text(f"{top:02d}", 4, 1, ORANGE)
    c.text(f"{bottom:02d}", 4, 9, ORANGE_DIM)

    # blinking markers on the left edge
    if int(t * 2) % 2 == 0:
        c.set(1, 7, ORANGE)
        c.set(1, 8, ORANGE)


def listening(c: Canvas, t: float, level: float) -> None:
    level = max(0.0, min(1.0, level))
    _face(c, eye_color=CYAN, look=(0, -1))
    for i in range(5):
        wave = 0.5 + 0.5 * abs(math.sin(t * 6 + i * 0.9))
        height = 1 + int(round(3 * min(1.0, level * 0.7 + wave * 0.3)))
        x = i * 3
        for dx in (0, 1):
            for y in range(16 - height, 16):
                c.set(x + dx, y, CYAN if dx == 0 else CYAN_DIM)


def thinking(c: Canvas, t: float) -> None:
    _face(c, eye_color=AMBER, look=(0, -1))
    active = int(t * 4) % 4
    for i in range(3):
        color = AMBER if i == active else AMBER_DIM
        c.set(5 + i * 3, 14, color)
        c.set(5 + i * 3, 15, color)


def speaking(c: Canvas, t: float, level: float) -> None:
    level = max(0.0, min(1.0, level))
    mouth = 0.25 + 0.75 * min(1.0, level * 0.6 + 0.4 * abs(math.sin(t * 7)))
    _face(c, eye_color=GREEN, mouth=mouth, mouth_color=GREEN)
    for side in (0, 15):
        for i in range(3):
            height = 1 + int(round(2 * min(1.0, level + 0.3 * abs(math.sin(t * 8 + i)))))
            for y in range(16 - height, 16):
                c.set(side, y, GREEN_DIM)


def error(c: Canvas, t: float) -> None:
    for ex in (3, 10):
        for i in range(3):
            c.set(ex + i, 5 + i, RED)
            c.set(ex + 2 - i, 5 + i, RED)
    c.hline(6, 12, 4, RED_DIM)
    if int(t * 3) % 2 == 0:
        c.rect(0, 0, 16, 16, RED_DIM, fill=False)


def alarm(c: Canvas, t: float) -> None:
    flash = int(t * 4) % 2 == 0
    if flash:
        c.fill((50, 0, 0))
    c.rect(0, 0, 16, 16, RED if flash else RED_DIM, fill=False)
    c.text_centered("!", 5, WHITE if flash else RED)


def music(c: Canvas, t: float, level: float) -> None:
    level = max(0.0, min(1.0, level))
    for i in range(8):
        wave = abs(math.sin(t * 3 + i * 0.7))
        height = 2 + int(round(11 * min(1.0, level * 0.5 + wave * 0.7)))
        color = _mix(GREEN, PURPLE, i / 7)
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
    name = (name or "").lower()
    if name == "bars":
        colors = (RED, GREEN, (0, 80, 255), WHITE)
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
        for x, y, color in ((0, 0, RED), (15, 0, GREEN), (0, 15, (0, 80, 255)), (15, 15, WHITE)):
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
                c.set(x, y, GREEN_DIM)
    else:
        c.text_centered(name[:5].upper(), 5, WHITE)


def _mix(a: Color, b: Color, k: float) -> Color:
    k = max(0.0, min(1.0, k))
    return (
        int(a[0] + (b[0] - a[0]) * k),
        int(a[1] + (b[1] - a[1]) * k),
        int(a[2] + (b[2] - a[2]) * k),
    )


def render_frame(
    state: str = "idle",
    t: float = 0.0,
    level: float = 0.0,
    text: str = "",
    text_color: Color = CYAN,
    timer_seconds: float = 0,
    brightness: int = 255,
    pattern: str = "",
) -> bytes:
    """Render one frame for the given state."""
    c = Canvas()
    state = (state or "idle").lower()

    if pattern:
        _pattern(c, pattern, t)
    elif text:
        scrolling_text(c, text, t, text_color)
    elif state == "idle":
        if timer_seconds > 0:
            timer(c, t, timer_seconds)
        elif int(t) % 12 < 8:
            idle(c, t)
        else:
            clock(c, t)
    elif state == "listening":
        listening(c, t, level)
    elif state == "thinking":
        thinking(c, t)
    elif state == "speaking":
        speaking(c, t, level)
    elif state == "error":
        error(c, t)
    elif state == "timer":
        timer(c, t, timer_seconds)
    elif state == "alarm":
        alarm(c, t)
    elif state == "music":
        music(c, t, level)
    else:
        idle(c, t)

    return c.to_bytes(brightness)
