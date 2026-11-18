"""Tiny 16x16 RGB canvas with 3x5 pixel fonts.

The canvas is deliberately dependency-free: a list of RGB tuples. Frames are
sent to WLED as raw row-major RGB bytes.
"""

from __future__ import annotations

WIDTH = 16
HEIGHT = 16

Color = tuple[int, int, int]
BLACK: Color = (0, 0, 0)

# 3x5 uppercase font. Every glyph is exactly 3 columns wide.
FONT_3X5: dict[str, tuple[str, ...]] = {
    " ": ("000", "000", "000", "000", "000"),
    "A": ("010", "101", "111", "101", "101"),
    "B": ("110", "101", "110", "101", "110"),
    "C": ("011", "100", "100", "100", "011"),
    "D": ("110", "101", "101", "101", "110"),
    "E": ("111", "100", "110", "100", "111"),
    "F": ("111", "100", "110", "100", "100"),
    "G": ("011", "100", "101", "101", "011"),
    "H": ("101", "101", "111", "101", "101"),
    "I": ("111", "010", "010", "010", "111"),
    "J": ("001", "001", "001", "101", "010"),
    "K": ("101", "101", "110", "101", "101"),
    "L": ("100", "100", "100", "100", "111"),
    "M": ("101", "111", "111", "101", "101"),
    "N": ("101", "111", "111", "111", "101"),
    "O": ("010", "101", "101", "101", "010"),
    "P": ("110", "101", "110", "100", "100"),
    "Q": ("010", "101", "101", "110", "011"),
    "R": ("110", "101", "110", "101", "101"),
    "S": ("011", "100", "010", "001", "110"),
    "T": ("111", "010", "010", "010", "010"),
    "U": ("101", "101", "101", "101", "111"),
    "V": ("101", "101", "101", "101", "010"),
    "W": ("101", "101", "111", "111", "101"),
    "X": ("101", "101", "010", "101", "101"),
    "Y": ("101", "101", "010", "010", "010"),
    "Z": ("111", "001", "010", "100", "111"),
    "0": ("111", "101", "101", "101", "111"),
    "1": ("010", "110", "010", "010", "111"),
    "2": ("111", "001", "111", "100", "111"),
    "3": ("111", "001", "111", "001", "111"),
    "4": ("101", "101", "111", "001", "001"),
    "5": ("111", "100", "111", "001", "111"),
    "6": ("111", "100", "111", "101", "111"),
    "7": ("111", "001", "001", "001", "001"),
    "8": ("111", "101", "111", "101", "111"),
    "9": ("111", "101", "111", "001", "111"),
    ":": ("000", "010", "000", "010", "000"),
    ".": ("000", "000", "000", "000", "010"),
    "!": ("010", "010", "010", "000", "010"),
    "?": ("111", "001", "011", "000", "010"),
    "-": ("000", "000", "111", "000", "000"),
    "+": ("000", "010", "111", "010", "000"),
    "/": ("001", "001", "010", "100", "100"),
    "=": ("000", "111", "000", "111", "000"),
    "'": ("010", "010", "000", "000", "000"),
}


class Canvas:
    """A mutable 16x16 RGB canvas."""

    def __init__(self, width: int = WIDTH, height: int = HEIGHT):
        self.width = width
        self.height = height
        self.pixels: list[list[Color]] = [[BLACK] * width for _ in range(height)]

    def clear(self, color: Color = BLACK) -> None:
        self.pixels = [[color] * self.width for _ in range(self.height)]

    def set(self, x: int, y: int, color: Color) -> None:
        if 0 <= x < self.width and 0 <= y < self.height:
            self.pixels[y][x] = color

    def get(self, x: int, y: int) -> Color:
        if 0 <= x < self.width and 0 <= y < self.height:
            return self.pixels[y][x]
        return BLACK

    def fill(self, color: Color) -> None:
        self.clear(color)

    def hline(self, x: int, y: int, length: int, color: Color) -> None:
        for i in range(length):
            self.set(x + i, y, color)

    def vline(self, x: int, y: int, length: int, color: Color) -> None:
        for i in range(length):
            self.set(x, y + i, color)

    def rect(self, x: int, y: int, width: int, height: int, color: Color, fill: bool = True) -> None:
        if fill:
            for row in range(y, y + height):
                self.hline(x, row, width, color)
        else:
            self.hline(x, y, width, color)
            self.hline(x, y + height - 1, width, color)
            self.vline(x, y, height, color)
            self.vline(x + width - 1, y, height, color)

    def line(self, x0: int, y0: int, x1: int, y1: int, color: Color) -> None:
        """Bresenham line."""
        dx = abs(x1 - x0)
        sx = 1 if x0 < x1 else -1
        dy = -abs(y1 - y0)
        sy = 1 if y0 < y1 else -1
        err = dx + dy
        while True:
            self.set(x0, y0, color)
            if x0 == x1 and y0 == y1:
                break
            e2 = 2 * err
            if e2 >= dy:
                err += dy
                x0 += sx
            if e2 <= dx:
                err += dx
                y0 += sy

    def text(self, text: str, x: int, y: int, color: Color, spacing: int = 1) -> None:
        for char in text.upper():
            glyph = FONT_3X5.get(char, FONT_3X5[" "])
            for row, bits in enumerate(glyph):
                for col, bit in enumerate(bits):
                    if bit == "1":
                        self.set(x + col, y + row, color)
            x += 3 + spacing

    def text_width(self, text: str, spacing: int = 1) -> int:
        if not text:
            return 0
        return len(text) * 3 + (len(text) - 1) * spacing

    def text_centered(self, text: str, y: int, color: Color, spacing: int = 1) -> None:
        x = max(0, (self.width - self.text_width(text, spacing)) // 2)
        self.text(text, x, y, color, spacing)

    def to_bytes(self, brightness: int = 255) -> bytes:
        """Row-major RGB888 frame, scaled by brightness (0..255)."""
        brightness = max(0, min(255, int(brightness)))
        out = bytearray(self.width * self.height * 3)
        i = 0
        for row in self.pixels:
            for r, g, b in row:
                out[i] = r * brightness // 255
                out[i + 1] = g * brightness // 255
                out[i + 2] = b * brightness // 255
                i += 3
        return bytes(out)
