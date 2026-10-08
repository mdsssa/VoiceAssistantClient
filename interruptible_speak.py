# interruptible_speak.py — замена обычного subprocess.run на проигрывание
# с возможностью прервать его голосовой командой "стоп"

import subprocess
import threading
import queue
import json
import sounddevice as sd
from vosk import Model, KaldiRecognizer
import os

STOP_WORDS = ["стоп", "стой", "хватит", "замолчи"]
SAMPLE_RATE = 16000
MODEL_PATH = os.path.expanduser("~/vosk-model-small-ru-0.22")

_model = Model(MODEL_PATH)


def play_interruptible(path):
    """Проигрывает аудиофайл, параллельно слушая микрофон на 'стоп'.
    Если услышала — сразу обрывает воспроизведение."""
    stop_flag = threading.Event()
    q = queue.Queue()

    def mic_callback(indata, frames, time, status):
        q.put(bytes(indata))

    def listen_for_stop():
        rec = KaldiRecognizer(_model, SAMPLE_RATE, json.dumps(STOP_WORDS + ["[unk]"], ensure_ascii=False))
        with sd.RawInputStream(samplerate=SAMPLE_RATE, blocksize=4000, dtype='int16',
                                channels=1, callback=mic_callback):
            while not stop_flag.is_set():
                try:
                    data = q.get(timeout=0.2)
                except queue.Empty:
                    continue
                if rec.AcceptWaveform(data):
                    result = json.loads(rec.Result())
                    text = result.get("text", "").lower()
                    if any(w in text for w in STOP_WORDS):
                        stop_flag.set()

    listener = threading.Thread(target=listen_for_stop, daemon=True)
    listener.start()

    proc = subprocess.Popen(["aplay", "-q", path])

    while proc.poll() is None:
        if stop_flag.wait(timeout=0.1):
            proc.terminate()
            print("🛑 Прервано голосом")
            break

    stop_flag.set()
    listener.join(timeout=1)