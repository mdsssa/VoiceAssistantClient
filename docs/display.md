# 16x16 LED display

Kera renders a 16x16 RGB frame in Python on the mini-PC and sends it to an ESP32.
There are two transports:

| Transport | Firmware | Link | When to use |
|---|---|---|---|
| **USB serial** | `firmware/esp32_usb_matrix` | USB cable, 921600 baud | One cable to the ESP32; no Wi-Fi |
| **WLED / DDP** | WLED | Wi-Fi, UDP 4048 | No custom firmware; WLED web UI |

Both can be active at the same time. The browser preview shows the same frames
regardless of the transport, so scenes can be designed without hardware.

The look is monochrome by design: one configurable accent color on black. Set it
with `DISPLAY_ACCENT` or the color picker in the preview.

## Architecture

```text
assistant (main/wakeword/timer/telegram)
        |
        |  fire-and-forget HTTP events
        v
display.server  (mini-PC, port 8090)
        |
        |  renderer -> 16x16 RGB888 frame
        |
        +--> browser preview (SSE, /events)
        |
        +--> USB serial --> ESP32 --> 16x16 WS2812B panel
        |
        +--> WLED DDP (UDP 4048) --> ESP32 + WLED --> panel
```

## Hardware

This guide assumes a **WS2812B / NeoPixel** 16x16 panel: 5 V, data, ground. A
HUB75 panel needs a different firmware bridge; see the end of this document.

### Bill of materials

| Part | Notes |
|---|---|
| ESP32 dev board | ESP32-WROOM-32 or ESP32-S3; USB for data and flashing |
| 16x16 WS2812B panel | 256 LEDs, 5 V, usually GRB order |
| 5 V power supply | 5-10 A for the panel |
| USB cable | mini-PC to ESP32 |
| 1000 uF capacitor | Across panel 5 V / GND |
| 330-470 ohm resistor | In series with data |
| 74AHCT125 level shifter | 3.3 V ESP32 data to 5 V panel |
| Fuse | 5-10 A on the 5 V feed |
| Diffuser / grid | Optional but recommended |

### Power: USB is not enough for the panel

A WS2812B LED can draw about 60 mA at full white. 256 LEDs is 15.4 A worst case.
USB 2.0 gives 0.5 A, USB 3.0 about 0.9 A, and even a 5 V/3 A USB-C port is
marginal for a bright 16x16 panel.

Use the mini-PC USB port for **the ESP32 and data only**. Power the panel from a
separate 5 V 5-10 A supply, and connect all grounds together. The firmware
limits current to 5000 mA by default; a real 5 V supply with a fuse protects the
panel and wiring.

If you absolutely want a single cable, use a USB-C PD 5 V/3 A source and lower
`MAX_CURRENT_MA` and brightness. Expect dim output and possible port protection
trips; this is not the recommended build.

### Wiring (USB serial)

```text
mini-PC USB  ---- ESP32 (data + ESP32 power)
5V PSU  +  ---- fuse ---- panel 5V (inject at both ends)
5V PSU  -  ---- panel GND ---- ESP32 GND
ESP32 GPIO16 -- 330R -- 74AHCT125 -- panel DIN
1000 uF across panel 5V / GND
```

The ESP32 and panel must share ground. Keep the data wire short and pair it
with ground if possible.

## Option A: USB serial

### Build the firmware

PlatformIO:

```bash
cd firmware/esp32_usb_matrix
pio run -t upload
```

Arduino IDE:

1. Install **FastLED**.
2. Create an ESP32 sketch and paste `firmware/esp32_usb_matrix/src/main.cpp`.
3. Set the board and port, then upload.

Edit `src/main.cpp` if needed:

| Define | Default | Meaning |
|---|---|---|
| `LED_PIN` | 16 | ESP32 data pin |
| `SERPENTINE` | 1 | Panel wiring snakes on odd rows |
| `MAX_CURRENT_MA` | 5000 | FastLED power limit |

The boot sequence flashes red, green, and blue, then blanks until frames arrive.

### Run the display daemon

Install the optional serial dependency if it is not already installed:

```bash
pip install pyserial
```

Find the stable device name:

```bash
ls /dev/serial/by-id/
```

Start the daemon:

```bash
SERIAL_PORT=/dev/serial/by-id/usb-Silicon_Labs_CP2102_USB_to_UART_Bridge_Controller_0001-if00-port0 \
SERIAL_BAUD=921600 \
python -m display.server
```

If the user is not in the `dialout` group on Ubuntu:

```bash
sudo usermod -aG dialout "$USER"
# log out and back in
```

### Protocol

```text
A5 5A | type 0x01 | length (2 bytes, little endian) | 768 RGB bytes | crc8(payload)
```

- Row-major, 16x16, RGB888.
- CRC-8 polynomial `0x07`, initial value `0`.
- 30 fps at 921600 baud is about 23 KB/s.
- If no valid frame arrives for 3 seconds, the panel blanks.
- The firmware maps serpentine rows to the physical panel.

## Option B: WLED over Wi-Fi

1. Flash WLED 0.14 or newer from <https://install.wled.me/>.
2. Join Wi-Fi and open the WLED UI.
3. In **Settings > LED Preferences** set WS2812B, GRB, GPIO16, length 256,
   2D matrix 16x16, serpentine if needed, max current 5000 mA, brightness
   128-180.
4. In **Settings > Sync Interfaces** make sure Realtime/DDP is enabled.
5. Give the ESP32 a static IP or DHCP reservation.
6. Start the daemon with the ESP32 address:

```bash
WLED_HOST=192.168.1.50 python -m display.server
```

Both transports can be used together; set both `SERIAL_PORT` and `WLED_HOST`.

## Preview and test visualization

Run without any transport to use the browser preview only:

```bash
python -m display.server
```

Open:

```text
http://<mini-pc>:8090
```

The page shows a 16x16 canvas with the exact frames that go to the panel. It has:

- state buttons: idle, listening, thinking, speaking, error, timer, alarm, music;
- listening/speaking level slider;
- brightness slider;
- accent color picker;
- timer input;
- scrolling text input;
- test patterns: color bars, checkerboard, gradient, corners, snake;
- a demo mode that cycles states.

The preview API has no authentication. Run it on a trusted LAN, or bind it to
`127.0.0.1` with `DISPLAY_BIND=127.0.0.1`.

### Test patterns

Test patterns intentionally use real RGB colors so you can check panel order,
orientation, and dead LEDs. Normal sprites use only the selected accent color.

- `bars`: red, green, blue, white columns;
- `checker`: every-other 2x2 block;
- `gradient`: RGB gradient;
- `corners`: red top-left, green top-right, blue bottom-left, white bottom-right;
- `snake`: a pixel walking the border.

### Accent color

Default is cyan (`#00c8ff`). Change it permanently with:

```bash
DISPLAY_ACCENT=#ff8800 python -m display.server
```

The server also reads the project `.env` file, so `WLED_HOST`, `SERIAL_PORT`, and
`DISPLAY_ACCENT` can live there too.

Or use the color picker in the preview; the change is live and is reflected in
`/api/status`.

Regenerate the still/GIF previews (needs Pillow):

```bash
pip install pillow
python -m display.demo
```

`docs/display-preview.png` and `docs/display-preview.gif` are committed examples.

## API

| Method | Path | Body | What it does |
|---|---|---|---|
| POST | `/api/state` | `{"state":"listening"}` | Set a state |
| POST | `/api/level` | `{"level":0.6}` | Audio level |
| POST | `/api/text` | `{"text":"TIMER 5:00","color":"#00c8ff"}` | Scrolling text; color optional |
| POST | `/api/timer` | `{"seconds":300}` | Countdown shown in idle |
| POST | `/api/brightness` | `{"value":128}` | Frame brightness |
| POST | `/api/accent` | `{"color":"#ff8800"}` | Set the accent color |
| POST | `/api/test` | `{"pattern":"bars"}` | Test pattern |
| POST | `/api/clear` | `{}` | Reset state, text, timer, pattern |
| GET | `/api/status` | - | Live state and transport status |
| GET | `/events` | - | SSE stream with base64 frames |

## Assistant integration

The assistant emits states when the display package is installed:

- `main.py`: `listening` while recording, `thinking` during STT/LLM, `speaking`
  during TTS, `error` on failure;
- `wakeword.py`: `idle` -> `listening` -> `idle`;
- `timer_watcher.py`: countdown in idle, `timer`/`alarm` when a timer fires;
- `telegrambot.py`: `thinking` while handling a message, then `idle`.

The client is fire-and-forget. If the daemon is not running, the assistant
continues normally.

### systemd user unit (USB example)

`~/.config/systemd/user/kaira-display.service`:

```ini
[Unit]
Description=Kera 16x16 display
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
WorkingDirectory=%h/VoiceAssistantClient
ExecStart=%h/VoiceAssistantClient/venv/bin/python -m display.server
Environment=SERIAL_PORT=/dev/serial/by-id/usb-REPLACE-ME-if00-port0
Environment=SERIAL_BAUD=921600
Environment="DISPLAY_ACCENT=#00c8ff"
Environment=PYTHONUNBUFFERED=1
Restart=on-failure
RestartSec=3

[Install]
WantedBy=default.target
```

```bash
systemctl --user daemon-reload
systemctl --user enable --now kaira-display
systemctl --user status kaira-display
```

For WLED, replace `SERIAL_PORT` with `Environment=WLED_HOST=192.168.1.50`.
`deploy/kaira.sh` can restart it explicitly:

```bash
bash deploy/kaira.sh restart kaira-display
```

## Troubleshooting

**USB: nothing on the panel**

- Check `ls /dev/serial/by-id/` and the `SERIAL_PORT` path.
- Check permissions: user in `dialout`, then log out and back in.
- Confirm the firmware boot flash (red/green/blue). If it does not flash, the
  ESP32 is not powered or the pin/board is wrong.
- Check the baud rate: 921600 on both sides.
- The firmware blanks after 3 seconds without valid frames.

**USB: random colors or flicker**

- Check common ground between ESP32 and panel PSU.
- Use the 330 ohm resistor and level shifter.
- Keep the USB cable and data wire away from power wires.
- Do not power the panel from USB; check the 5 V supply and fuse.

**WLED: preview works but the panel is black**

- Check `WLED_HOST`, ping the ESP32, and allow UDP 4048.
- Confirm the 2D matrix is 16x16 and length is 256.
- Test a WLED built-in effect first.

**Wrong colors**

- Set the color order in WLED or in `FastLED.addLeds` (GRB/RGB/BRG).

**Mirrored or scrambled image**

- Toggle `SERPENTINE` in the firmware, or serpentine in WLED.
- Use the `corners` pattern: red must be top-left, green top-right, blue
  bottom-left, white bottom-right.

**Preview does not open**

- Check `http://127.0.0.1:8090/api/status` on the mini-PC.
- Check `DISPLAY_BIND` and the firewall.

## HUB75 panels

WLED and this firmware target WS2812B. A HUB75 panel has a 64-pin connector and
needs a different library (`ESP32-HUB75-MatrixPanel-DMA`). The renderer, preview,
API, and assistant integration stay the same; only the ESP32 bridge changes.

## Notes

- The display is a status display, not a text console. Long messages scroll.
- The preview and the physical panel share one renderer.
- The display daemon is separate from the assistant: restart it without touching
  the voice loop.
