
import sounddevice as sd
import queue
import json
import subprocess
import os
import platform
from vosk import Model, KaldiRecognizer


PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")

subprocess.run([PYTHON_BIN, MAIN_SCRIPT, "--single-turn"])
MODEL_PATH = os.path.expanduser("~/vosk-model-ru-full")
SAMPLE_RATE = 16000
WAKE_WORDS = ["кера", "кэра", "керра", "кара", "кира", "ковра", "киря" , "кэро" , "кэйро" , "керри" , "керо", "кэролайн"]


#
# def play_sound(path):
#     if platform.system() == "Darwin":
#         subprocess.run(["afplay", path])
#     else:
#         subprocess.run(["aplay", path])

model = Model(MODEL_PATH)
rec = KaldiRecognizer(model, SAMPLE_RATE)

q = queue.Queue()

def callback(indata, frames, time, status):
    q.put(bytes(indata))

print("Shell started")

with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype='int16',
                        channels=1, callback=callback):
    while True:
        data = q.get()
        if rec.AcceptWaveform(data):
            result = json.loads(rec.Result())
            text = result.get("text", "").lower()
            if any(w in text for w in WAKE_WORDS):
                print("Вызов получен")
                subprocess.run(["python3", os.path.expanduser("./main.py"), "--single-turn"])
                rec.Reset()

