# 🎙 Кэра — голосовой ассистент

[![Python](https://img.shields.io/badge/python-3.10%2B-3776AB?logo=python&logoColor=white)](https://www.python.org/)
[![Platform](https://img.shields.io/badge/platform-Linux%20%7C%20macOS-2e3440?logo=linux&logoColor=white)](#-быстрый-старт)
[![STT](https://img.shields.io/badge/STT-faster--whisper-0ea5e9)](https://github.com/SYSTRAN/faster-whisper)
[![TTS](https://img.shields.io/badge/TTS-Silero%20ru%2Fen-ea580c)](https://github.com/snakers4/silero-models)
[![LLM](https://img.shields.io/badge/LLM-Groq%20%7C%20local-8b5cf6)](#-архитектура)

**Кэра (Кэролайн)** — локальный русскоязычный голосовой помощник: слушает wake-word,
записывает реплику по VAD, распознаёт речь, думает через LLM с function calling и отвечает
голосом. Умеет управлять Spotify, ставить таймеры и будильники, узнавать погоду, искать
в интернете и присылать рецепты в Telegram.

> A local Russian-speaking voice assistant:
> wake word → VAD → faster-whisper → LLM with tool calling → Silero TTS.

```text
— Кэра, включи мою волну
— Включаю волну от избранного
```

Репозиторий — **клиент**. STT, TTS и (опционально) LLM поднимаются отдельными процессами,
поэтому требования к микрофону и к серверам не смешиваются.

---

## ✨ Возможности

- 🎯 **Wake-word «Кэра»** — ONNX-модель `kera.onnx`, на Linux через `arecord`, на macOS через `livekit.wakeword`.
- 🎤 **Запись по VAD** — пишет до паузы в речи и ставит Spotify на паузу, чтобы музыка не триггерила микрофон.
- 🧠 **LLM с инструментами** — Groq API или любой локальный OpenAI-совместимый сервер.
- 🎵 **Spotify** — play/pause, следующий/предыдущий трек, громкость, перемотка, лайк, «моя волна».
- ⏰ **Таймеры и будильники** — хранятся в `.timers.json`, озвучиваются отдельным watcher-процессом.
- 🌤 **Погода** — Open-Meteo, по умолчанию Томск.
- 🔎 **Веб-поиск** — DuckDuckGo, когда знаний модели не хватает.
- 🍳 **Рецепты** — находит страницу с рецептом и отправляет её в Telegram.
- 💬 **Telegram-бот** — тот же LLM и те же инструменты, но в чате.
- 🗣 **Смешанный ru/en TTS** — текст режется по языку, и Silero переключает модели на английских вставках.

---

## 🧠 Архитектура

```text
        ┌──────────────┐
        │  wakeword.py │  ONNX «Кэра» (Linux: arecord / macOS: livekit)
        └──────┬───────┘
               │ запускает main.py --single-turn
               ▼
🎙 микрофон ─► VAD ─► main.py ──HTTP──► sstServer.py :8001 (faster-whisper, ru)
                        │
                        ├──► LLM (Groq API или local :8002)
                        │        ▲
                        │        │ tools.py — JSON-схемы функций
                        │        │
                        │   function calling
                        │        ├── spotifyConnect.py ──► Spotify Web API
                        │        ├── weather.py        ──► Open-Meteo
                        │        ├── web_search.py     ──► DuckDuckGo
                        │        ├── recipes.py        ──► Telegram
                        │        └── timers.py         ──► .timers.json
                        │
                        └──HTTP──► ttsServer.py :8003 (Silero ru+en) ──► 🔊
```

Отдельные процессы:

| Процесс | Порт | Зачем |
|---|---|---|
| `sstServer.py` | `8001` | Распознавание речи (faster-whisper `small`, `int8`, язык `ru`) |
| LLM | `8002` | Локальная модель (если `LLM_PROVIDER=local`) |
| `ttsServer.py` | `8003` | Синтез речи (Silero `v4_ru` + `v3_en`) |
| `timer_watcher.py` | — | Следит за таймерами и озвучивает срабатывания |
| `telegrambot.py` | — | Чат-бот на том же LLM |

---

## 📁 Структура

| Файл | Роль |
|---|---|
| [main.py](main.py) | Голосовой цикл: запись, STT, LLM с tool calls, TTS |
| [wakeword.py](wakeword.py) | Wake-word «Кэра»; `--debug` печатает score модели (Linux) |
| [audio.py](audio.py) | `play_sound()` и `speak()` — общее аудио для всех процессов |
| [prompts.py](prompts.py) | Системные промпты: голос и Telegram, общие правила инструментов |
| [tools.py](tools.py) | JSON-схемы функций для LLM + расшифровка кодов погоды |
| [spotifyConnect.py](spotifyConnect.py) | OAuth, обновление токена, Spotify Web API |
| [weather.py](weather.py) | Погода через Open-Meteo |
| [web_search.py](web_search.py) | Поиск через DuckDuckGo |
| [recipes.py](recipes.py) | Поиск рецепта и отправка в Telegram |
| [timers.py](timers.py) | Хранение таймеров и будильников |
| [timer_watcher.py](timer_watcher.py) | Озвучка сработавших таймеров |
| [telegrambot.py](telegrambot.py) | Telegram-бот |
| [sstServer.py](sstServer.py) | Flask + faster-whisper, `:8001` |
| [ttsServer.py](ttsServer.py) | Flask + Silero, `:8003` |
| [testmic.py](testmic.py) | Показывает уровень микрофона — удобно подбирать порог VAD |
| [sort_downloads.py](sort_downloads.py) | Отдельная утилита сортировки `~/Downloads`, к ассистенту не относится |

---

## 🚀 Быстрый старт

### 1. Зависимости

Нужен Python **3.10+**.

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

Системные пакеты (Linux):

```bash
# mp3-звуки и запись/воспроизведение wav
sudo apt install mpg123 alsa-utils
```

На macOS дополнительно ничего не нужно — используется встроенный `afplay`.

Для Spotify понадобится **Spotify Connect-устройство** (например, `librespot`), имя которого
указывается в `SPOTIFY_TARGET_DEVICE`.

### 2. `.env`

Создай в корне проекта файл `.env` (он в `.gitignore`):

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

# --- Telegram (бот и отправка рецептов) ---
BOT_TOKEN=123456:ABC-DEF...
CHAT_ID=-1001234567890
```

| Переменная | Обязательна | Назначение |
|---|---|---|
| `CLIENT_ID`, `CLIENT_SECRET` | да | приложение Spotify |
| `REDIRECT_URI` | да | callback для OAuth, по умолчанию `http://127.0.0.1:8888/callback` |
| `SPOTIFY_TARGET_DEVICE` | для Spotify | часть имени устройства в Spotify Connect |
| `LLM_PROVIDER` | нет | `groq` или `local` (по умолчанию `local`) |
| `GROQ_API_KEY` | для Groq | ключ API |
| `LOCAL_LLM_URL` | нет | по умолчанию `http://localhost:8002/v1/chat/completions` |
| `BOT_TOKEN`, `CHAT_ID` | для Telegram | бот и чат для сообщений |
| `TTS_URL` | нет | по умолчанию `http://localhost:8003/synthesize` |
| `KERA_MIC` | нет | ALSA-устройство для `arecord`, по умолчанию `default` |

> ⚠️ Ключи из `.env` не коммитятся. Если файл уже попадал в git — перевыпусти токены.

### 3. Spotify — авторизация один раз

```bash
python spotifyConnect.py --auth      # откроет браузер, токен ляжет в ~/.spotify_token_cache.json
python spotifyConnect.py --devices   # проверить, что целевое устройство видно
```

Токен обновляется автоматически; `scope`: playback state/modify + library read/modify.

---

## ▶️ Запуск

Каждый пункт — в своём терминале.

```bash
# 1. Распознавание речи
python sstServer.py                  # :8001

# 2. Синтез речи
python ttsServer.py                  # :8003

# 3. LLM
#    - Groq: LLM_PROVIDER=groq в .env, отдельный процесс не нужен
#    - local: подними свой OpenAI-совместимый сервер на :8002

# 4. Голосовой ассистент
python wakeword.py                   # всегда слушает «Кэра»
python main.py                       # Enter → говоришь
python main.py --single-turn         # одна реплика (так запускает wakeword)

# 5. Telegram-бот
python telegrambot.py

# 6. Таймеры и будильники
python timer_watcher.py
```

Если STT/TTS/LLM живут на другой машине, поменяй `STT_URL` в [main.py](main.py),
`TTS_URL` в окружении или `LOCAL_LLM_URL` в `.env`.

---

## 🎧 Spotify: что доступно

| Команда | Функция |
|---|---|
| «включи …» | `play_music` — поиск трека и запуск альбома с нужной позиции |
| «поставь на паузу» / «продолжи» | `pause_music` / `resume_music` |
| «следующий» / «предыдущий» | `skip_track` / `previous_music_track` |
| «громче» / «тише» / «громкость 40» | `change_volume` (системная громкость: `pactl` / `osascript`) |
| «перемотай на минуту» | `seek_track` |
| «что играет?» | `whats_playing` |
| «лайкни» | `like_current_track` |
| «включи мою волну» | `start_my_wave` — Liked Songs с первого лайкнутого трека и дальше |

Логика «следующий/предыдущий» описана в системном промпте — при неясной формулировке
по умолчанию считается `skip_track`.

---

## 🗣 Голос и TTS

- Ответы короткие, без эмодзи, все цифры проговариваются словами — это задано в [prompts.py](prompts.py).
- Silero держит две модели: русскую и английскую. Текст режется по языку, куски склеиваются
  с небольшой паузой, поэтому «Deftones» звучит по-английски, а остальное — по-русски.
- `sounds/readyToListenV2.mp3` — звук начала записи, `sounds/listeningEndV2.mp3` — конца.

---

## 🧩 Как добавить свою команду

1. Напиши функцию в подходящем модуле — она должна вернуть строку для модели.
2. Импортируй её в [main.py](main.py) и добавь в `AVAILABLE_FUNCTIONS`.
3. Опиши схему через `_tool(...)` в [tools.py](tools.py): имя, описание и параметры.
4. Если нужно, добавь правило в `TOOL_RULES` в [prompts.py](prompts.py), чтобы модель
   понимала, когда функцию вызывать.

Пример:

```python
# tools.py
_tool("say_hello", "Поздороваться с пользователем",
      name=("string", "Имя, к которому обращаемся"))
```

---

## 🩺 Диагностика

```bash
python testmic.py                    # уровень микрофона, подобрать threshold в main.py
python wakeword.py --debug           # score модели и rms (только Linux, нужен arecord)
python spotifyConnect.py --devices   # список Spotify Connect-устройств
python web_search.py "курс биткоина" # проверить поиск отдельно
```

Частые причины «ничего не слышит»:

- микрофон занят другим процессом (`arecord -l` / `KERA_MIC`);
- порог VAD слишком высокий — смотри `testmic.py` и `record_until_silence(threshold=...)`;
- wake-word не срабатывает — проверь `THRESHOLD` и `GATE_RMS` в [wakeword.py](wakeword.py).

---

## 📌 Заметки

- Все пути теперь считаются от каталога проекта: `sounds/`, `kera.onnx`, `.timers.json`.
- На macOS для звука используется `afplay`, на Linux — `mpg123` для mp3 и `aplay` для wav.
- `.timers.json` создаётся автоматически и не коммитится.
- `requirements.txt` без жёстких пинов: удобно ставить свежие версии, но при желании
  зафиксируй их под своё окружение.
- `sort_downloads.py` — самостоятельная утилита, к голосовому ассистенту отношения не имеет.
