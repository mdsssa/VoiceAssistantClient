# Kera - Voice Assistant

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-2e3440?logo=linux&logoColor=white)](#quick-start)
[![STT](https://img.shields.io/badge/STT-faster--whisper-0ea5e9)](https://github.com/SYSTRAN/faster-whisper)
[![TTS](https://img.shields.io/badge/TTS-Silero%20ru%2Fen-ea580c)](https://github.com/snakers4/silero-models)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20local-8b5cf6)](#architecture)

**Kera (Caroline)** is a local Russian-speaking voice assistant: it listens for a wake word,
records a phrase using VAD, transcribes speech, thinks with an LLM that can call tools, and
replies with synthesized speech. It can control Spotify, set timers and alarms, report the
weather, search the web, and send recipes to Telegram.

```text
User:  Kera, start my wave
Kera:  Starting your wave from Liked Songs
```

> Kera speaks Russian. The dialogue above is translated for readability.

This repository contains the **client**. STT, TTS, and (optionally) the LLM run as separate
processes, so microphone dependencies and server dependencies do not get mixed together.

---

## Features

- **Wake word "Kera"** - ONNX model `kera.onnx`; `arecord` on Linux, `livekit.wakeword` on macOS.
- **VAD recording** - records until silence and pauses Spotify so music does not trigger the microphone.
- **LLM with tools** - Groq API or any local OpenAI-compatible server.
- **Spotify** - play/pause, next/previous track, volume, seek, like, "my wave".
- **Timers and alarms** - stored in `.timers.json` and announced by a separate watcher process.
- **Weather** - Open-Meteo, Tomsk by default.
- **Web search** - DuckDuckGo when the model needs fresh information.
- **Recipes** - finds a recipe page and sends it to Telegram.
- **Telegram bot** - the same LLM and tools, but in a chat.
- **Mixed ru/en TTS** - text is split by language and Silero switches models for English inserts.

---

## Architecture

```text
        +--------------+
        |  wakeword.py |  ONNX "Kera" (Linux: arecord / macOS: livekit)
        +------+-------+
               | launches main.py --single-turn
               v
microphone --> VAD --> main.py --HTTP--> sstServer.py :8001 (faster-whisper, ru)
                        |
                        +--> LLM (Groq API or local :8002)
                        |        ^
                        |        | tools.py - JSON function schemas
                        |        |
                        |   function calling
                        |        +--> spotifyConnect.py --> Spotify Web API
                        |        +--> weather.py        --> Open-Meteo
                        |        +--> web_search.py     --> DuckDuckGo
                        |        +--> recipes.py        --> Telegram
                        |        +--> timers.py         --> .timers.json
                        |
                        +--HTTP--> ttsServer.py :8003 (Silero ru+en) --> speaker
```

Separate processes:

| Process | Port | Purpose |
|---|---|---|
| `sstServer.py` | `8001` | Speech recognition (faster-whisper `small`, `int8`, language `ru`) |
| LLM | `8002` | Local model when `LLM_PROVIDER=local` |
| `ttsServer.py` | `8003` | Speech synthesis (Silero `v4_ru` + `v3_en`) |
| `timer_watcher.py` | - | Watches timers and announces them |
| `telegrambot.py` | - | Chat bot using the same LLM |

---

## Project structure

| File | Purpose |
|---|---|
| [main.py](main.py) | Voice loop: recording, STT, LLM with tool calls, TTS |
| [wakeword.py](wakeword.py) | Wake word "Kera"; `--debug` prints model scores (Linux) |
| [audio.py](audio.py) | `play_sound()` and `speak()` shared by all processes |
| [prompts.py](prompts.py) | System prompts for voice and Telegram plus shared tool rules |
| [tools.py](tools.py) | JSON function schemas for the LLM and weather code descriptions |
| [spotifyConnect.py](spotifyConnect.py) | OAuth, token refresh, Spotify Web API |
| [weather.py](weather.py) | Weather via Open-Meteo |
| [web_search.py](web_search.py) | Search via DuckDuckGo |
| [recipes.py](recipes.py) | Recipe search and Telegram delivery |
| [timers.py](timers.py) | Timer and alarm storage |
| [timer_watcher.py](timer_watcher.py) | Announces expired timers and alarms |
| [telegrambot.py](telegrambot.py) | Telegram bot |
| [sstServer.py](sstServer.py) | Flask + faster-whisper, `:8001` |
| [ttsServer.py](ttsServer.py) | Flask + Silero, `:8003` |
| [testmic.py](testmic.py) | Prints microphone level - useful for tuning the VAD threshold |
| [deploy/kaira.sh](deploy/kaira.sh) | Checks and restarts systemd services on the server |
| [sort_downloads.py](sort_downloads.py) | Standalone `~/Downloads` cleanup utility, unrelated to the assistant |

---

## Quick start

### 1. Dependencies

Python **3.10+** is required.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

System packages (Linux):

```bash
# mp3 sounds and wav playback/recording
sudo apt install mpg123 alsa-utils
```

On macOS nothing extra is needed - the built-in `afplay` is used.

Spotify requires a **Spotify Connect device** (for example, `librespot`). Its name is set in
`SPOTIFY_TARGET_DEVICE`.

### 2. `.env`

Create a `.env` file in the project root (it is gitignored):

```dotenv
# --- Spotify ---
CLIENT_ID=your_client_id
CLIENT_SECRET=your_client_secret
REDIRECT_URI=http://127.0.0.1:8888/callback
SPOTIFY_TARGET_DEVICE=HeroBox

# --- LLM ---
# groq | local
LLM_PROVIDER=groq
GROQ_API_KEY=your_groq_key
LOCAL_LLM_URL=http://localhost:8002/v1/chat/completions

# --- Telegram (bot and recipe delivery) ---
BOT_TOKEN=123456:ABC-DEF...
CHAT_ID=-1001234567890
```

| Variable | Required | Purpose |
|---|---|---|
| `CLIENT_ID`, `CLIENT_SECRET` | yes | Spotify application credentials |
| `REDIRECT_URI` | yes | OAuth callback, defaults to `http://127.0.0.1:8888/callback` |
| `SPOTIFY_TARGET_DEVICE` | for Spotify | Part of the Spotify Connect device name |
| `LLM_PROVIDER` | no | `groq` or `local` (default is `local`) |
| `GROQ_API_KEY` | for Groq | API key |
| `LOCAL_LLM_URL` | no | Defaults to `http://localhost:8002/v1/chat/completions` |
| `BOT_TOKEN`, `CHAT_ID` | for Telegram | Bot token and target chat |
| `TTS_URL` | no | Defaults to `http://localhost:8003/synthesize` |
| `KERA_MIC` | no | ALSA device for `arecord`, defaults to `default` |

> **Note:** never commit `.env`. If the file has ever been pushed to git, rotate the tokens.

### 3. Spotify authorization (once)

```bash
python spotifyConnect.py --auth      # opens the browser; token is stored in ~/.spotify_token_cache.json
python spotifyConnect.py --devices   # verifies that the target device is visible
```

The token is refreshed automatically. Scope: playback state/modify and library read/modify.

---

## Running

Run each item in its own terminal.

```bash
# 1. Speech recognition
python sstServer.py                  # :8001

# 2. Speech synthesis
python ttsServer.py                  # :8003

# 3. LLM
#    - Groq: set LLM_PROVIDER=groq in .env, no separate process needed
#    - local: run your own OpenAI-compatible server on :8002

# 4. Voice assistant
python wakeword.py                   # always listening for "Kera"
python main.py                       # press Enter to talk
python main.py --single-turn         # one phrase (this is how wakeword starts it)

# 5. Telegram bot
python telegrambot.py

# 6. Timers and alarms
python timer_watcher.py
```

If STT, TTS, or the LLM run on another machine, change `STT_URL` in [main.py](main.py),
`TTS_URL` in the environment, or `LOCAL_LLM_URL` in `.env`.

---

## systemd on the server

Services: `kaira-stt`, `kaira-tts`, `kaira-timers`, `kaira-wakeword`, `tgbot`, plus a separate
`librespot` (left untouched). Entry points have not changed, so the unit files do not need to be
edited: after `git pull`, restart the services. There are no new pip dependencies, so
`pip install` is not required after an update.

```bash
bash deploy/kaira.sh check             # read-only: files, .env, dependencies, ports, units
bash deploy/kaira.sh restart           # restarts 5 services, leaves librespot alone
bash deploy/kaira.sh restart tgbot     # restarts a single service
bash deploy/kaira.sh logs kaira-wakeword
```

The script detects whether the units are user units (`systemctl --user`) or system units
(`systemctl`) and prints the `ExecStart` line for each service. If `check` reports a problem,
send its output plus `systemctl --user cat kaira-wakeword` so it can be fixed.

---

## Spotify commands

| Command | Function |
|---|---|
| "play ..." | `play_music` - searches for a track and starts the album at that track |
| "pause" / "resume" | `pause_music` / `resume_music` |
| "next" / "previous" | `skip_track` / `previous_music_track` |
| "louder" / "quieter" / "volume 40" | `change_volume` (system volume: `pactl` / `osascript`) |
| "seek to 1:00" | `seek_track` |
| "what is playing?" | `whats_playing` |
| "like this" | `like_current_track` |
| "start my wave" | `start_my_wave` - Liked Songs from the first liked track onward |

The "next/previous" behavior is described in the system prompt; when the request is ambiguous,
`skip_track` is used by default.

---

## Voice and TTS

- Replies are short, without emoji, and all numbers are spelled out as words. This is configured
  in [prompts.py](prompts.py).
- Silero keeps two models, Russian and English. The text is split by language, and the chunks are
  joined with a short pause, so "Deftones" is pronounced in English while the rest is Russian.
- `sounds/readyToListenV2.mp3` is the recording start sound and `sounds/listeningEndV2.mp3` is
  the end sound.

---

## Adding a command

1. Write a function in a suitable module. It must return a string for the model.
2. Import it in [main.py](main.py) and add it to `AVAILABLE_FUNCTIONS`.
3. Describe the schema with `_tool(...)` in [tools.py](tools.py): name, description, and parameters.
4. If needed, add a rule to `TOOL_RULES` in [prompts.py](prompts.py) so the model knows when to call it.

Example:

```python
# tools.py
_tool("say_hello", "Greet the user",
      name=("string", "Name to address"))
```

---

## Diagnostics

```bash
python testmic.py                    # microphone level, useful for tuning threshold in main.py
python wakeword.py --debug           # model score and rms (Linux only, requires arecord)
python spotifyConnect.py --devices   # list Spotify Connect devices
python web_search.py "bitcoin price" # test web search separately
```

Common reasons for "it does not hear me":

- the microphone is busy (`arecord -l` / `KERA_MIC`);
- the VAD threshold is too high - check `testmic.py` and `record_until_silence(threshold=...)`;
- the wake word does not trigger - check `THRESHOLD` and `GATE_RMS` in [wakeword.py](wakeword.py).

---

## Notes

- All paths are resolved from the project directory: `sounds/`, `kera.onnx`, `.timers.json`.
- On macOS audio is played with `afplay`; on Linux `mpg123` is used for mp3 and `aplay` for wav.
- `.timers.json` is created automatically and is not committed.
- `requirements.txt` has no hard pins: this makes fresh installs easy, but you can pin versions
  for your own environment.
- `sort_downloads.py` is a standalone utility and has nothing to do with the voice assistant.
