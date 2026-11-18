# 16x16 LED display

Kera can show what it is doing on a 16x16 addressable RGB panel. The mini-PC
renders every frame in Python and sends it to **WLED** on an ESP32 over **DDP**
(UDP port 4048). WLED drives the LEDs; there is no custom firmware to maintain.

The same frames are available in a browser preview, so you can design and test
scenes without the panel. The assistant itself only sends small state events
(`listening`, `thinking`, `speaking`, `timer`, ...), and a missing display never
blocks the voice loop.

## Architecture

```text
main.py / wakeword.py / timer_watcher.py / telegrambot.py
        |
        |  fire-and-forget HTTP (display/state, display/level, display/timer)
        v
display.server  (mini-PC, port 8090)
        |  renderer -> 16x16 RGB888 frame
        |
        +--> browser preview (SSE, /events)
        |
        +--> WLED over DDP/UDP 4048
                 |
                 v
         ESP32 + 16x16 WS2812B panel
```

## Hardware

This guide assumes a **WS2812B / NeoPixel** style 16x16 panel: 5 V power, data,
and ground. If your panel has a HUB75 / 64-pin connector, see the note at the
end; the PC side is the same, but the ESP32 bridge is different.

### Bill of materials

| Part | Notes |
|---|---|
| ESP32 dev board | ESP32-WROOM-32 or ESP32-S3; USB for flashing |
| 16x16 WS2812B panel | 256 LEDs, 5 V, common GRB order |
| 5 V power supply | 10 A recommended (see power budget below) |
| 1000 uF capacitor | Across panel 5 V / GND |
| 330-470 ohm resistor | In series with the data line |
| 74AHCT125 level shifter | 3.3 V ESP32 data -> 5 V panel data |
| Fuse | 5-10 A on the 5 V feed |
| Wires | 18-20 AWG for power, short data wire |
| Diffuser / grid | Optional, makes 16x16 pixels look much better |

### Power budget

A WS2812B LED can draw about 60 mA at full white. 256 LEDs is 15.4 A worst case.
Do not plan for that continuously:

- use a 5 V **10 A** supply and enable WLED's automatic brightness limiter;
- set WLED max current to about **5000 mA** and brightness limit to **128**;
- typical animations use 2-4 A; full-white test patterns are the worst case;
- inject 5 V at two corners of the panel and use a common ground everywhere.

Do not power the panel from the ESP32 5 V pin. Power the ESP32 from USB (or a
separate 5 V feed) and the panel from the PSU; connect all grounds together.

### Wiring

```text
5V PSU + ---- fuse ----+------------ panel 5V (inject at both ends)
                       |
                    1000uF
                       |
5V PSU - ----+---------+------------ panel GND ---- ESP32 GND
             |
ESP32 GPIO16 -- 330R -- 74AHCT125 -- panel DIN
ESP32 USB -------------------------- mini-PC (flashing / power)
```

WLED defaults used in this project:

- LED type: WS2812B
- color order: GRB
- data pin: GPIO16 (change in WLED if you wire another pin)
- length: 256
- 2D matrix: 16 x 16
- serpentine: enable if your panel is wired in a snake pattern
- max current: 5000 mA
- brightness limit: 128-180

## WLED setup

1. Flash WLED 0.14 or newer from <https://install.wled.me/> over USB.
2. Connect to the WLED access point, join your Wi-Fi, and open the WLED UI.
3. In **Settings > LED Preferences** set the LED type, GPIO, length, and 2D
   matrix (16x16, serpentine if needed).
4. Set the current limit and brightness limit. Save and reboot.
5. Give the ESP32 a static IP or a DHCP reservation and note the address.
6. In **Settings > Sync Interfaces**, make sure Realtime/DDP is enabled. The PC sends UDP packets to port `4048`.
7. Test the panel with WLED's built-in effects and color patterns first.

The ESP32 and the mini-PC must be on the same network. Allow UDP `4048` from the
mini-PC to the ESP32 if you have a firewall.

## Run the display daemon

On the mini-PC, in the project directory:

```bash
source venv/bin/activate
WLED_HOST=192.168.1.50 python -m display.server
```

Open the preview:

```text
http://<mini-pc>:8090
```

Run without `WLED_HOST` to use only the browser preview:

```bash
python -m display.server
```

> The preview API has no authentication. Run it on a trusted LAN, or bind it to
> `127.0.0.1` with `DISPLAY_BIND=127.0.0.1` if only the mini-PC needs it.

Environment variables:

| Variable | Default | Purpose |
|---|---|---|
| `WLED_HOST` | empty | ESP32 IP; empty means preview only |
| `WLED_PORT` | `4048` | DDP UDP port |
| `DISPLAY_PORT` | `8090` | HTTP preview/API port |
| `DISPLAY_BIND` | `0.0.0.0` | Interface for the preview server |
| `DISPLAY_FPS` | `30` | Render rate and DDP send rate |
| `KAIRA_DISPLAY` | `1` | Set to `0` to disable assistant events |
| `KAIRA_DISPLAY_URL` | `http://127.0.0.1:8090` | Where the assistant sends events |

The preview uses Server-Sent Events and shows exactly what is sent to WLED, so
it is also the test visualization.

## Test patterns

The preview page has buttons for color bars, checkerboard, gradient, corner
markers, and a snake. They are useful for checking:

- panel orientation and serpentine setting;
- color order (GRB vs RGB);
- power and brightness limits;
- that every LED is alive.

The same patterns can be sent from the command line:

```bash
curl -X POST http://127.0.0.1:8090/api/test \
  -H 'Content-Type: application/json' \
  -d '{"pattern":"corners"}'
```

## API

All endpoints are local to the display daemon.

| Method | Path | Body | What it does |
|---|---|---|---|
| POST | `/api/state` | `{"state":"listening"}` | Set `idle`, `listening`, `thinking`, `speaking`, `error`, `timer`, `alarm`, or `music` |
| POST | `/api/level` | `{"level":0.6}` | Audio level for listening/speaking/music |
| POST | `/api/text` | `{"text":"TIMER 5:00","color":"#00c8ff"}` | Scrolling text overlay |
| POST | `/api/timer` | `{"seconds":300}` | Countdown shown in idle |
| POST | `/api/brightness` | `{"value":128}` | Frame brightness, 0-255 |
| POST | `/api/test` | `{"pattern":"bars"}` | Test pattern |
| POST | `/api/clear` | `{}` | Reset state, text, timer, pattern |
| GET | `/api/status` | - | Live state |
| GET | `/events` | - | SSE stream with base64 frames |

## Assistant integration

The assistant already emits states when the display package is installed:

- `wakeword.py`: `idle` -> `listening` on wake -> `idle` after the turn;
- `main.py`: `listening` while recording, `thinking` during STT/LLM, `speaking`
  during TTS, `error` on failure;
- `timer_watcher.py`: countdown in idle, `timer`/`alarm` when a timer fires;
- `telegrambot.py`: `thinking` while handling a message, then `idle`.

The client is fire-and-forget. If the daemon is not running, the assistant
continues normally.

### systemd user unit (optional)

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
Environment=WLED_HOST=192.168.1.50
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

The existing `deploy/kaira.sh` can restart it explicitly:

```bash
bash deploy/kaira.sh restart kaira-display
```

## Preview images

`docs/display-preview.png` is a contact sheet of the scenes.
`docs/display-preview.gif` is a short animation.

Regenerate them (needs Pillow):

```bash
pip install pillow
python -m display.demo
```

## Troubleshooting

**Preview works, panel is black**

- Check `WLED_HOST` and ping the ESP32.
- Check that UDP `4048` is not blocked.
- In WLED, confirm the 2D matrix is 16x16 and the length is 256.
- Try a WLED built-in effect first; if that works, the issue is DDP/network.

**Wrong colors**

- Change color order in WLED (GRB, RGB, BRG).
- WS2812B panels are usually GRB.

**Mirrored or scrambled image**

- Enable or disable serpentine in the WLED 2D matrix settings.
- Check panel orientation (rotate 0/90/180/270).
- Use the `corners` test pattern: red must be top-left, green top-right,
  blue bottom-left, white bottom-right.

**Flicker or random pixels**

- Use the 330-470 ohm data resistor and a level shifter.
- Keep the data wire short and pair it with ground.
- Inject power at both ends of the panel.
- Add the 1000 uF capacitor near the first LED.

**ESP32 reboots when the panel is bright**

- The panel is drawing more current than the supply can deliver.
- Lower WLED max current and brightness limit.
- Use a bigger 5 V supply and thicker power wires.

**Browser preview does not open**

- Check `http://127.0.0.1:8090/api/status` on the mini-PC.
- Check the port and firewall; `DISPLAY_BIND=0.0.0.0` is needed for LAN access.
- If the daemon is down, the assistant is unaffected.

**The display freezes on "thinking"**

- The renderer falls back to idle after 45 seconds without events.
- Check the assistant logs and the daemon log.

## HUB75 panels

WLED does not drive HUB75 panels. If your 16x16 panel has a 64-pin HUB75
connector instead of three wires, you need a different firmware bridge, for
example `ESP32-HUB75-MatrixPanel-DMA`. The renderer, web preview, API, and
assistant integration in `display/` remain the same; only the frame transport
to the panel changes. In that case the ESP32 must receive frames over Wi-Fi or a
serial link and push them to the HUB75 panel.

## Notes

- The panel is a status display, not a text console. The 3x5 font is readable
  but short; long messages scroll.
- The preview and the physical panel share one renderer, so there is no
  "works in the browser but not on the matrix" surprise.
- The display daemon is intentionally separate from the assistant, so you can
  restart it without touching the voice loop.
