
import asyncio
import os
import platform
import subprocess
import time

import numpy as np
from livekit.wakeword import WakeWordModel

MODEL_PATH = os.path.expanduser("~/VoiceAssistantClient/kera.onnx")
MODEL_NAME = "kera"          # ключ в scores = имя файла модели без .onnx
THRESHOLD = 0.5              # ловит плохо -> 0.35-0.4, ложные -> 0.6
DEBOUNCE = 2.0               # секунды между срабатываниями

# На сервере звуком управляет PipeWire (он держит USB-микрофон), поэтому читаем
# через "default" -> PipeWire. Нужный микрофон выбирается как источник по
# умолчанию: wpctl set-default <id источника из `wpctl status`>.
# Можно переопределить: export KERA_MIC=...
LINUX_MIC = os.environ.get("KERA_MIC", "default")
FRAME_SAMPLES = 1280         # 80 мс при 16 кГц, как в WakeWordListener
FRAME_BYTES = FRAME_SAMPLES * 2

IS_MAC = platform.system() == "Darwin"
if IS_MAC:
    PYTHON_BIN = "python3"
else:
    PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")


# ---------- Linux: arecord ----------
def wait_for_wakeword_linux() -> float:
    model = WakeWordModel(models=[MODEL_PATH])
    cmd = ["arecord", "-q", "-D", LINUX_MIC, "-f", "S16_LE",
           "-r", "16000", "-c", "1", "-t", "raw"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    last = 0.0
    try:
        while True:
            buf = proc.stdout.read(FRAME_BYTES)
            if len(buf) < FRAME_BYTES:
                err = proc.stderr.read().decode(errors="ignore").strip()
                raise RuntimeError(
                    f"arecord остановился (устройство {LINUX_MIC}): {err or 'нет вывода'}"
                )
            frame = np.frombuffer(buf, dtype=np.int16)
            scores = model.predict(frame)
            conf = float(scores.get(MODEL_NAME, 0.0))
            if conf > THRESHOLD and time.time() - last > DEBOUNCE:
                return conf
    finally:
        proc.terminate()
        proc.wait()


# ---------- macOS: WakeWordListener ----------
async def wait_for_wakeword_mac() -> float:
    from livekit.wakeword import WakeWordListener

    model = WakeWordModel(models=[MODEL_PATH])
    async with WakeWordListener(model, threshold=THRESHOLD, debounce=DEBOUNCE) as listener:
        detection = await listener.wait_for_detection()
        return detection.confidence


def run_main_script():
    subprocess.run([PYTHON_BIN, MAIN_SCRIPT, "--single-turn"])


async def main_mac():
    print("Жду 'Кэра'...")
    while True:
        conf = await wait_for_wakeword_mac()
        print(f"Finaly Heard! (conf={conf:.2f})")
        await asyncio.to_thread(run_main_script)
        print("Жду 'Кэра'...")


def main_linux():
    print(f"Жду 'Кэра'... (микрофон {LINUX_MIC})")
    while True:
        conf = wait_for_wakeword_linux()
        print(f"Finaly Heard! (conf={conf:.2f})")
        run_main_script()
        print("Жду 'Кэра'...")


if __name__ == "__main__":
    try:
        if IS_MAC:
            asyncio.run(main_mac())
        else:
            main_linux()
    except KeyboardInterrupt:
        pass