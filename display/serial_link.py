"""USB serial frame transport for the ESP32 firmware.

The ESP32 receives 16x16 RGB888 frames over its USB serial port. Each packet is:

    A5 5A | type (1) | length (2, little endian) | payload | crc8(payload)

The firmware in ``firmware/esp32_usb_matrix`` implements the same protocol.
``pyserial`` is only needed when ``SERIAL_PORT`` is configured.
"""

from __future__ import annotations

MAGIC = b"\xA5\x5A"
FRAME_TYPE = 0x01
FRAME_BYTES = 16 * 16 * 3


def crc8(data: bytes) -> int:
    crc = 0
    for byte in data:
        crc ^= byte
        for _ in range(8):
            if crc & 0x80:
                crc = ((crc << 1) ^ 0x07) & 0xFF
            else:
                crc = (crc << 1) & 0xFF
    return crc


def encode_frame(frame: bytes) -> bytes:
    if len(frame) != FRAME_BYTES:
        raise ValueError(f"expected {FRAME_BYTES} bytes, got {len(frame)}")
    header = MAGIC + bytes((FRAME_TYPE,)) + len(frame).to_bytes(2, "little")
    return header + frame + bytes((crc8(frame),))


class SerialLink:
    def __init__(self, port: str, baud: int = 921600):
        try:
            import serial
        except ImportError as exc:  # pragma: no cover
            raise RuntimeError("pyserial is required for USB serial: pip install pyserial") from exc

        self._serial_module = serial
        self.port = port
        self.baud = int(baud)
        self._serial = None
        self.sent = 0
        self.errors = 0

    def _ensure_open(self) -> None:
        if self._serial is None:
            self._serial = self._serial_module.Serial(
                self.port,
                self.baud,
                timeout=0,
                write_timeout=0.05,
            )

    def send(self, frame: bytes) -> None:
        packet = encode_frame(frame)
        try:
            self._ensure_open()
            self._serial.write(packet)
            self.sent += 1
        except Exception:
            self.errors += 1
            try:
                if self._serial is not None:
                    self._serial.close()
            except Exception:
                pass
            self._serial = None
            raise

    def close(self) -> None:
        if self._serial is not None:
            try:
                self._serial.close()
            finally:
                self._serial = None
