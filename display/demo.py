"""Render preview images/GIFs of the display scenes.

This is a development helper and needs Pillow (``pip install pillow``). The
runtime daemon does not depend on Pillow.

Run:
    python -m display.demo
"""

from __future__ import annotations

from pathlib import Path

from . import scenes

try:
    from PIL import Image, ImageDraw
except ImportError as exc:  # pragma: no cover
    raise SystemExit("display.demo needs Pillow: pip install pillow") from exc

SCALE = 16
FRAME = 16

# name, animation time, level, timer seconds, text, pattern
SHOTS = [
    ("Idle face", "idle", 0.6, 0.0, 0, "", ""),
    ("Clock", "idle", 9.0, 0.0, 0, "", ""),
    ("Listening", "listening", 1.2, 0.55, 0, "", ""),
    ("Thinking", "thinking", 1.0, 0.0, 0, "", ""),
    ("Speaking", "speaking", 1.1, 0.7, 0, "", ""),
    ("Timer", "timer", 1.0, 0.0, 125, "", ""),
    ("Error", "error", 1.0, 0.0, 0, "", ""),
    ("Alarm", "alarm", 1.0, 0.0, 0, "", ""),
    ("Music", "music", 1.0, 0.6, 0, "", ""),
    ("Bars", "idle", 0.0, 0.0, 0, "", "bars"),
]


def _image(state: str, t: float, level: float, timer: int, text: str, pattern: str) -> Image.Image:
    frame = scenes.render_frame(
        state=state,
        t=t,
        level=level,
        text=text,
        timer_seconds=timer,
        pattern=pattern,
    )
    return Image.frombytes("RGB", (FRAME, FRAME), frame).resize(
        (FRAME * SCALE, FRAME * SCALE), Image.Resampling.NEAREST
    )


def contact_sheet(path: Path | str = "docs/display-preview.png") -> Path:
    cols = 5
    rows = 2
    label_height = 22
    cell = FRAME * SCALE
    sheet = Image.new("RGB", (cols * cell, rows * (cell + label_height)), (8, 11, 18))
    draw = ImageDraw.Draw(sheet)

    for index, (label, state, t, level, timer, text, pattern) in enumerate(SHOTS):
        image = _image(state, t, level, timer, text, pattern)
        x = (index % cols) * cell
        y = (index // cols) * (cell + label_height)
        sheet.paste(image, (x, y))
        draw.text((x + 6, y + cell + 5), label, fill=(216, 228, 245))

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(target)
    return target


def animated_gif(path: Path | str = "docs/display-preview.gif", fps: int = 12) -> Path:
    sequence = [
        ("idle", 0.0, 0.0, 0, ""),
        ("listening", 0.0, 0.55, 0, ""),
        ("thinking", 0.0, 0.0, 0, ""),
        ("speaking", 0.0, 0.7, 0, ""),
        ("timer", 0.0, 0.0, 125, ""),
        ("alarm", 0.0, 0.0, 0, ""),
    ]
    frames = []
    for state, _, level, timer, text in sequence:
        for frame_index in range(fps * 2):
            t = frame_index / fps
            image = _image(state, t, level, timer, text, "")
            frames.append(image.convert("P", palette=Image.ADAPTIVE, colors=64))

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(
        target,
        save_all=True,
        append_images=frames[1:],
        duration=int(1000 / fps),
        loop=0,
        optimize=True,
        disposal=2,
    )
    return target


def main() -> None:
    sheet = contact_sheet()
    gif = animated_gif()
    print(f"wrote {sheet}")
    print(f"wrote {gif}")


if __name__ == "__main__":
    main()
