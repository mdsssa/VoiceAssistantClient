import sounddevice as sd
import soundfile as sf
import requests
import numpy as np
import subprocess
import tempfile
import os
import json
import argparse

import spotifyConnect
from spotifyConnect import (
    play_music,
    pause_music,
    resume_music,
    skip_track,
    previous_music_track,
    change_volume,
    seek_track,
)
from tools import tools
from weather import get_weather
from spotifyConnect import whats_playing, like_current_track


AVAILABLE_FUNCTIONS = {
    "get_weather": get_weather,
    "play_music": play_music,
    "pause_music": pause_music,
    "resume_music": resume_music,
    "skip_track": skip_track,
    "previous_music_track": previous_music_track,
    "change_volume": change_volume,
    "seek_track": seek_track,
    "whats_playing" : whats_playing,
    "like_current_track" : like_current_track,
}

SERVER = "100.70.125.15"
STT_URL = f"http://{SERVER}:8001/transcribe"
LLM_URL = f"http://{SERVER}:8002/v1/chat/completions"
TTS_URL = f"http://{SERVER}:8003/synthesize"

SAMPLE_RATE = 16000

# SOUND_LISTENING_START = "/System/Library/Sounds/Pop.aiff"
# SOUND_LISTENING_END = "/System/Library/Sounds/Tink.aiff"
SOUND_LISTENING_START = "./sounds/readyToListenV2.mp3"
SOUND_LISTENING_END = "./sounds/listeningEndV2.mp3"
# SOUND_READY = "/System/Library/Sounds/Glass.aiff"

# Сколько последних сообщений (без учёта system) держим в контексте.
# Не даёт истории расти бесконечно и тащить за собой мусор/галлюцинации.
HISTORY_LIMIT = 12

WEATHER_CODE_DESCRIPTIONS = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    56: "лёгкая ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "лёгкий ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "небольшой ливень",
    81: "ливень",
    82: "сильный ливень",
    85: "небольшой снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с небольшим градом",
    99: "гроза с сильным градом",
}


def play_sound(path, blocking=True):
    cmd = ["mpg123", "-q", path]
    if blocking:
        subprocess.run(cmd)
    else:
        subprocess.Popen(cmd)


SYSTEM_PROMPT = (
    "Тебя зовут Кэра. Ты дружелюбный голосовой помощник. "
    "Отвечай кратко и естественно на  ТОЛЬКО НА РУССКОМ!! НЕЛЬЗЯ ГОВОРИТЬ НА КИТАЙСКОМ!!!!!!!. "
    "Для погоды, музыки и управления плеером используй доступные функции —"
     "Если пользователь просит следующий/другой/новый трек — используй skip_track. "
"Если просит предыдущий/прошлый/назад — используй previous_music_track. "
"При неясной формулировке про переключение трека по умолчанию считай, что это skip_track."
    "никогда не отвечай текстом вместо вызова функции и не придумывай данные."
"Если спрашивают, что сейчас играет — используй whats_playing. "
"Если просят добавить текущий трек в избранное/лайкнуть — используй like_current_track. "
)

def record_until_silence(threshold=800, silence_duration=2, max_duration=15):
    """Пишет звук, пока не наступит тишина после того, как человек начал говорить.
    На время записи ставит Spotify на паузу, чтобы музыка не забивала микрофон
    и не триггерила VAD как "пользователь говорит"."""
    was_playing = pause_music()  # см. модификацию pause_music ниже — возвращает, было ли что играть

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
    with open(path, 'rb') as f:
        r = requests.post(STT_URL, files={'file': f})
    os.remove(path)
    text = r.json().get("text", "").replace("[музыка]", "")
    print(text)
    return text


def trim_history(history):
    """Оставляет system-сообщение + последние HISTORY_LIMIT сообщений."""
    system = history[0]
    rest = history[1:]
    if len(rest) > HISTORY_LIMIT:
        rest = rest[-HISTORY_LIMIT:]
    return [system] + rest


def ask_llm(text, history):
    history.append({"role": "user", "content": text})
    history[:] = trim_history(history)

    r = requests.post(LLM_URL, json={
        "messages": history,
        "tools": tools,
        "max_tokens": 300
    })
    message = r.json()["choices"][0]["message"]

    if message.get("tool_calls"):
        history.append(message)
        for call in message["tool_calls"]:
            fn_name = call["function"]["name"]
            fn_args = json.loads(call["function"]["arguments"])

            try:
                result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
            except Exception as e:
                result = f"Ошибка при вызове {fn_name}: {e}"

            history.append({
                "role": "tool",
                "tool_call_id": call["id"],
                "content": result
            })

        r2 = requests.post(LLM_URL, json={
            "messages": history,
            "tools": tools,
            "tool_choice": "required",
            "max_tokens": 150
            # "temperature": 0.1
        })
        final_message = r2.json()["choices"][0]["message"]
        reply = final_message.get("content") or ""

        history.append({"role": "assistant", "content": reply})
        print(final_message)
        return reply.replace("Celsius" , "")
    else:
        reply = message.get("content") or ""
        history.append({"role": "assistant", "content": reply})
        print(message)
        return reply.replace("Celsius" , "")


def speak(text):
    spotifyConnect.change_volume("30")
    r = requests.post(TTS_URL, json={"text": text})
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(r.content)
        path = f.name
    subprocess.run(["aplay", "-q", path])
    os.remove(path)
    spotifyConnect.change_volume("100")


def one_exchange(history):
    audio = record_until_silence()
    if audio is None:
        return False

    play_sound(SOUND_LISTENING_END)
    text = transcribe(audio)
    if not text.strip():
        return False

    reply = ask_llm(text, history)

    # play_sound(SOUND_READY)
    speak(reply)
    return True


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--single-turn", action="store_true")
    args = parser.parse_args()

    # История живёт только в рамках текущего процесса — никакого файла на
    # диске. Перезапустил скрипт — контекст чистый, старые галлюцинации
    # и отладочный мусор с прошлых сессий никуда не тащатся.
    history = [{"role": "system", "content": SYSTEM_PROMPT}]

    if args.single_turn:
        one_exchange(history)
        return

    print("=== Кэра готова. Ctrl+C для выхода ===")
    try:
        while True:
            input("Нажми Enter чтобы начать говорить...")
            one_exchange(history)
    except KeyboardInterrupt:
        print("\nПока!")


if __name__ == "__main__":
    main()