import sounddevice as sd
import queue
import json
import subprocess
import os
from vosk import Model, KaldiRecognizer

MODEL_PATH = os.path.expanduser("~/vosk-model-small-ru-0.22")
SAMPLE_RATE = 16000
WAKE_WORDS = ["кера", "кэра", "керра", "кара", "кира", "ковра", "киря", "кэро", "кэйро", "керри", "керо", "кэролайн"]

# Путь к интерпретатору внутри venv — обязательно, иначе subprocess не увидит
# установленные туда зависимости (requests, sounddevice, vosk и т.д.)
PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")

model = Model(MODEL_PATH)

# Grammar ограничивает распознавание заданным списком слов вместо полного
# словаря — резко снижает нагрузку на CPU и повышает точность именно на
# нестандартных словах типа "Кэра", раз модели не нужно перебирать весь
# словарь, а только сравнивать с коротким списком.
grammar = json.dumps(WAKE_WORDS + ["[unk]"], ensure_ascii=False)
rec = KaldiRecognizer(model, SAMPLE_RATE, grammar)

q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

print("👂 Слушаю фоном... скажи 'Кэра'")
with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=8000, dtype='int16',
                        channels=1, callback=callback):
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "").lower()
            if any(w in text for w in WAKE_WORDS):
                print("✨ Услышала имя!")
                subprocess.run([PYTHON_BIN, MAIN_SCRIPT, "--single-turn"])
                rec.Reset()