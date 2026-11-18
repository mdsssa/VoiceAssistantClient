# ESP32 USB matrix firmware

Minimal firmware for an ESP32 driving a 16x16 WS2812B panel. The panel receives
RGB888 frames over USB serial from `display/server.py`.

## Wiring

```text
mini-PC USB  ---- ESP32 (data + ESP32 power)
5V PSU  +  ---- panel 5V (inject at both ends)
5V PSU  -  ---- panel GND ---- ESP32 GND
ESP32 GPIO16 -- 330R -- 74AHCT125 -- panel DIN
```

The panel must have its own 5 V supply. A USB port cannot power 256 LEDs at a
useful brightness. USB powers the ESP32 and carries data; the panel and the
ESP32 share ground.

If the panel is wired as a snake, set `SERPENTINE 1` in `src/main.cpp`. If your
data pin is not GPIO16, change `LED_PIN`. Color order is GRB; change it in
`FastLED.addLeds<...>` if your panel is RGB.

## Build

PlatformIO:

```bash
cd firmware/esp32_usb_matrix
pio run -t upload
pio device monitor -b 921600
```

Arduino IDE:

1. Install the **FastLED** library.
2. Create a sketch for your ESP32 board and paste `src/main.cpp`.
3. Set the board and port, then upload.

## Protocol

```text
A5 5A | type 0x01 | length (2 bytes, little endian) | 768 RGB bytes | crc8(payload)
```

- Row-major, 16x16, RGB888; 768 bytes per frame.
- CRC-8 polynomial `0x07`, initial value `0`.
- 30 fps over 921600 baud is about 23 KB/s, well within the link budget.
- If no valid frame arrives for 3 seconds, the panel blanks.
- On boot the firmware flashes red, green, and blue to verify power and wiring.

## Power limit

`MAX_CURRENT_MA` is set to 5000 in `src/main.cpp`, which assumes a 5 V 5-10 A
panel supply. If you try to run the panel from a USB port, lower it to the port
limit (for example 900) and keep brightness low; this is not recommended for a
16x16 panel.
