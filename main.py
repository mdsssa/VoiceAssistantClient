import argparse
import json
import os
import tempfile

import numpy as np
import requests
import sounddevice as sd
import soundfile as sf
from dotenv import load_dotenv

from audio import play_sound, speak
import display
from prompts import VOICE_PROMPT
from recipes import search_and_send_recipe
from spotifyConnect import (
    play_music,
    pause_music,
    resume_music,
    skip_track,
    previous_music_track,
    change_volume,
    seek_track,
    start_my_wave,
    whats_playing,
    like_current_track,
)
from timers import set_timer, set_alarm, cancel_all_timers, list_timers
from tools import tools
from weather import get_weather
from web_search import web_search


load_dotenv()

AVAILABLE_FUNCTIONS = {
    "get_weather": get_weather,
    "play_music": play_music,
    "pause_music": pause_music,
    "resume_music": resume_music,
    "skip_track": skip_track,
    "previous_music_track": previous_music_track,
    "change_volume": change_volume,
    "seek_track": seek_track,
    "whats_playing": whats_playing,
    "like_current_track": like_current_track,
    "start_my_wave": start_my_wave,
    "search_and_send_recipe": search_and_send_recipe,
    "set_timer": set_timer,
    "set_alarm": set_alarm,
    "cancel_all_timers": cancel_all_timers,
    "list_timers": list_timers,
    "web_search": web_search,
}

SERVER = "localhost"
STT_URL = f"http://{SERVER}:8001/transcribe"
SAMPLE_RATE = 16000


LLM_PROVIDER = os.environ.get("LLM_PROVIDER", "local")
if LLM_PROVIDER == "groq":
    LLM_URL = "https://api.groq.com/openai/v1/chat/completions"
    LLM_MODEL = "openai/gpt-oss-20b"
    LLM_HEADERS = {"Authorization": f"Bearer {os.environ['GROQ_API_KEY']}"}
else:
    LLM_URL = os.environ.get("LOCAL_LLM_URL", f"http://{SERVER}:8002/v1/chat/completions")
    LLM_MODEL = None
    LLM_HEADERS = {}


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
SOUND_LISTENING_START = os.path.join(BASE_DIR, "sounds", "readyToListenV2.mp3")
SOUND_LISTENING_END = os.path.join(BASE_DIR, "sounds", "listeningEndV2.mp3")

# Сколько последних сообщений (без учёта system) держим в контексте.
# Не даёт истории расти бесконечно и тащить за собой мусор/галлюцинации.
HISTORY_LIMIT = 30


def record_until_silence(threshold=800, silence_duration=1.5, max_duration=15):
    """Пишет звук, пока не наступит тишина после того, как человек начал говорить.
    На время записи ставит Spotify на паузу, чтобы музыка не забивала микрофон
    и не триггерила VAD как "пользователь говорит"."""
    display.state("listening")
    was_playing = pause_music()

    frames = []
    chunk_size = 1024
    silence_chunks = 0
    silence_limit = int(SAMPLE_RATE / chunk_size * silence_duration)
    max_chunks = int(SAMPLE_RATE / chunk_size * max_duration)
    started_speaking = False

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    stream.start()
    play_sound(SOUND_LISTENING_START, blocking=False)

    try:
        for _ in range(max_chunks):
            data, _ = stream.read(chunk_size)
            frames.append(data.copy())
            volume = np.abs(data).mean()
            display.level(min(1.0, volume / 8000.0))

            if volume > threshold:
                started_speaking = True
                silence_chunks = 0
            elif started_speaking:
                silence_chunks += 1
                if silence_chunks > silence_limit:
                    break
    finally:
        stream.stop()
        stream.close()
        if was_playing:
            resume_music()

    if not started_speaking:
        return None

    return np.concatenate(frames, axis=0)


def transcribe(audio) -> str:
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        sf.write(f.name, audio, SAMPLE_RATE)
        path = f.name
    try:
        with open(path, 'rb') as f:
            r = requests.post(STT_URL, files={'file': f})
        text = r.json().get("text", "")
    finally:
        os.remove(path)
    print(text)
    return text


def trim_history(history):
    """Оставляет system-сообщение + последние HISTORY_LIMIT сообщений."""
    system = history[0]
    rest = history[1:]
    if len(rest) > HISTORY_LIMIT:
        rest = rest[-HISTORY_LIMIT:]
    return [system] + rest


def _build_payload(messages, max_tokens) -> dict:
    payload = {
        "messages": messages,
        "tools": tools,
        "temperature": 0.1,
        "max_tokens": max_tokens,
    }
    if LLM_MODEL:
        payload["model"] = LLM_MODEL
    return payload


def _chat(messages, max_tokens) -> dict:
    """Один запрос к LLM. Всегда возвращает message, даже если ответ странный."""
    r = requests.post(LLM_URL, headers=LLM_HEADERS, json=_build_payload(messages, max_tokens))
    print(f"DEBUG LLM raw response: {r.status_code} {r.text}")
    try:
        data = r.json()
    except ValueError:
        return {"content": "Произошла неизвестная ошибка"}
    if data.get("choices"):
        return data["choices"][0]["message"]
    return data.get("message") or {"content": "Произошла неизвестная ошибка"}


def ask_llm(text, history) -> str:
    history.append({"role": "user", "content": text})
    history[:] = trim_history(history)

    message = _chat(history, 300)
    if message.get("tool_calls"):
        history.append(message)
        for call in message["tool_calls"]:
            fn_name = call["function"]["name"]
            try:
                fn_args = json.loads(call["function"]["arguments"] or "{}")
                result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
            except Exception as e:
                result = f"Ошибка при вызове {fn_name}: {e}"
            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": str(result),
            })

        message = _chat(history, 150)

    reply = (message.get("content") or "").replace("Celsius", "")
    history.append({"role": "assistant", "content": reply})
    print(message)
    return reply


def one_exchange(history):
    try:
        audio = record_until_silence()
        if audio is None:
            display.state("idle")
            return

        display.state("thinking")
        play_sound(SOUND_LISTENING_END)
        text = transcribe(audio)
        if not text.strip():
            display.state("idle")
            return

        reply = ask_llm(text, history)
        display.state("speaking")
        speak(reply)
        display.state("idle")
    except Exception as e:
        print(f"[voice error] {e}")
        display.state("error")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-turn", action="store_true")
    args = parser.parse_args()

    history = [{"role": "system", "content": VOICE_PROMPT}]

    if args.single_turn:
        one_exchange(history)
        return

    print("Кэра готова.")
    try:
        while True:
            input("Нажми Enter чтобы начать говорить...")
            one_exchange(history)
    except KeyboardInterrupt:
        print("\nПока!")


if __name__ == "__main__":
    main()
