import sounddevice as sd
import queue
import json
import subprocess
import os
from vosk import Model, KaldiRecognizer
import platform


MODEL_PATH = os.path.expanduser("~/vosk-model-small-ru-0.22")
SAMPLE_RATE = 16000
WAKE_WORDS = ["кера", "кэра", "керра", "кэролайн" , ]
def load_common_words(path):
    with open(path, encoding="utf-8") as f:
        return f.read().split()

COMMON_WORDS = load_common_words(os.path.expanduser("~/VoiceAssistantClient/common_words_ru.txt"))

if platform.system() == "Darwin":
    PYTHON_BIN = "python3"
    MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")
else:
    PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
    MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")

model = Model(MODEL_PATH)


grammar = json.dumps(WAKE_WORDS + COMMON_WORDS + ["[unk]"], ensure_ascii=False)
rec = KaldiRecognizer(model, SAMPLE_RATE, grammar)

q = queue.Queue()
rec.SetWords(True)  # включает вывод confidence по каждому слову
def callback(indata, frames, time, status):
    q.put(bytes(indata))

print("👂 Слушаю фоном... скажи 'Кэра'")
with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                        channels=1, callback=callback):
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            words = result.get("result", [])
            text = result.get("text", "").lower()

            if words:
                # Средняя уверенность по всем распознанным словам в этой фразе
                avg_conf = sum(w.get("conf", 0) for w in words) / len(words)
            else:
                avg_conf = 0

            print(f"heard: '{text}' conf: {avg_conf:.2f}")


            if any(w in text for w in WAKE_WORDS) and avg_conf > 0.5:
                print(f"✨ Услышала имя! (conf={avg_conf:.2f})")
                subprocess.run([PYTHON_BIN, MAIN_SCRIPT, "--single-turn"])
                rec.Reset()
                while not q.empty():
                    q.get_nowait()