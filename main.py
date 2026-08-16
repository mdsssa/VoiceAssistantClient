import sounddevice as sd
import soundfile as sf
import requests
import numpy as np
import subprocess
import tempfile
import os
import json
import argparse

SERVER = "100.70.125.15"
STT_URL = f"http://{SERVER}:8001/transcribe"
LLM_URL = f"http://{SERVER}:8002/v1/chat/completions"
TTS_URL = f"http://{SERVER}:8003/synthesize"

SAMPLE_RATE = 16000

# SOUND_LISTENING_START = "/System/Library/Sounds/Pop.aiff"
# SOUND_LISTENING_END = "/System/Library/Sounds/Tink.aiff"
SOUND_LISTENING_START = "./sounds/listeningStartV1.mp3"
SOUND_LISTENING_END = "./sounds/listeningStopV1.mp3"
SOUND_READY = "/System/Library/Sounds/Glass.aiff"

# Сколько последних сообщений (без учёта system) держим в контексте.
# Не даёт истории расти бесконечно и тащить за собой мусор/галлюцинации.
HISTORY_LIMIT = 12


def play_sound(path, blocking=True):
    if blocking:
        subprocess.run(["afplay", path])
    else:
        subprocess.Popen(["afplay", path])


SYSTEM_PROMPT = (
    "Тебя зовут Кэра (Кэролайн). Ты дружелюбный голосовой помощник. "
    "Отвечай кратко, естественно, на русском языке, как в живом разговоре. "
    "Если пользователь спрашивает про погоду, используй функцию get_weather с названием города, которое он назвал. "
    "Никогда не придумывай данные о погоде сама — если функция недоступна или вернула ошибку, честно скажи об этом."
)

tools = [{
    "type": "function",
    "function": {
        "name": "get_weather",
        "description": "Получить текущую погоду в указанном городе",
        "parameters": {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "Название города, например Москва, Париж, Токио"}
            },
            "required": ["city"]
        }
    }
}]


def get_weather(city):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "ru"}
        ).json()
        if not geo.get("results"):
            return f"Не нашла город {city}"
        loc = geo["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        found_name = loc.get("name", city)

        weather = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True}
        ).json()["current_weather"]

        temp = round(weather["temperature"])
        wind = weather["windspeed"]

        result = f"В городе {found_name} сейчас {temp} градусов, скорость ветра {wind} километров в час"
        print(result)
        return result
    except Exception as e:
        print(f"[get_weather error] {e}")
        return f"Не получилось узнать погоду: {e}"


AVAILABLE_FUNCTIONS = {"get_weather": get_weather}


def record_until_silence(threshold=800, silence_duration=1.2, max_duration=15):
    """Пишет звук, пока не наступит тишина после того, как человек начал говорить."""
    frames = []
    chunk_size = 1024
    silence_chunks = 0
    silence_limit = int(SAMPLE_RATE / chunk_size * silence_duration)
    max_chunks = int(SAMPLE_RATE / chunk_size * max_duration)
    started_speaking = False

    stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
    stream.start()
    # Сигнал играем ПОСЛЕ старта стрима и неблокирующе — иначе первый слог речи
    # теряется, пока проигрывается звук / инициализируется стрим.
    play_sound(SOUND_LISTENING_START, blocking=False)

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

    stream.stop()
    stream.close()

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
            "max_tokens": 300
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
    r = requests.post(TTS_URL, json={"text": text})
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
        f.write(r.content)
        path = f.name
    subprocess.run(["afplay", path])
    os.remove(path)


def one_exchange(history):
    audio = record_until_silence()
    if audio is None:
        return False

    play_sound(SOUND_LISTENING_END)
    text = transcribe(audio)
    if not text.strip():
        return False

    reply = ask_llm(text, history)

    play_sound(SOUND_READY)
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