import asyncio
import os
import platform
import subprocess
import sys
import time
from collections import deque

import numpy as np
import onnxruntime as ort
from livekit.wakeword import WakeWordModel

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(BASE_DIR, "kera.onnx")
MODEL_NAME = "kera"
THRESHOLD = 0.35
DEBOUNCE = 2.0

LINUX_MIC = os.environ.get("KERA_MIC", "default")
FRAME_SAMPLES = 1280         # 80 мс при 16 кГц, как в WakeWordListener
FRAME_BYTES = FRAME_SAMPLES * 2
CHUNK_FRAMES = 25            # ~2 секунды аудио в одном окне
PREDICT_EVERY = 4            # предсказание не чаще, чем раз в 4 окна
GATE_RMS = 700               # ниже этого уровня считаем, что в комнате тишина

IS_MAC = platform.system() == "Darwin"
MAIN_SCRIPT = os.path.join(BASE_DIR, "main.py")
# main.py запускаем тем же питоном, что и wakeword, но на Linux у проекта
# обычно есть свой venv — предпочитаем его, как было и раньше.
VENV_PYTHON = os.path.join(BASE_DIR, "venv", "bin", "python3")
PYTHON_BIN = sys.executable if IS_MAC or not os.path.exists(VENV_PYTHON) else VENV_PYTHON


def make_model() -> WakeWordModel:
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    return WakeWordModel(models=[MODEL_PATH], sess_options=so)


def _arecord_cmd():
    return ["arecord", "-q", "-D", LINUX_MIC, "-f", "S16_LE",
            "-r", "16000", "-c", "1", "-t", "raw"]


def _rms(frame):
    return float(np.sqrt(np.mean(frame.astype(np.float32) ** 2)))


def wait_for_wakeword_linux() -> float:
    model = make_model()
    proc = subprocess.Popen(_arecord_cmd(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    frames = deque(maxlen=CHUNK_FRAMES)
    rms_hist = deque(maxlen=CHUNK_FRAMES)
    step = 0
    try:
        while True:
            buf = proc.stdout.read(FRAME_BYTES)
            if len(buf) < FRAME_BYTES:
                err = proc.stderr.read().decode(errors="ignore").strip()
                raise RuntimeError(
                    f"arecord остановился (устройство {LINUX_MIC}): {err or 'нет вывода'}"
                )
            frame = np.frombuffer(buf, dtype=np.int16)
            frames.append(frame)
            rms_hist.append(_rms(frame))
            if len(frames) < CHUNK_FRAMES:
                continue  # копим первые 2 секунды
            step += 1
            if step % PREDICT_EVERY:
                continue
            if GATE_RMS and max(rms_hist) < GATE_RMS:
                continue  # тишина, модель не трогаем
            scores = model.predict(np.concatenate(list(frames)))
            conf = float(scores.get(MODEL_NAME, 0.0))
            if conf >= THRESHOLD:
                return conf
    finally:
        proc.terminate()
        proc.wait()


# ---------- macOS: WakeWordListener ----------
async def wait_for_wakeword_mac() -> float:
    from livekit.wakeword import WakeWordListener

    model = make_model()
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


def debug_scores():
    """Печатает score модели и rms — чтобы подобрать THRESHOLD и GATE_RMS.
    Работает только на Linux: читает микрофон через arecord."""
    model = make_model()
    proc = subprocess.Popen(_arecord_cmd(), stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    frames = deque(maxlen=CHUNK_FRAMES)
    best = 0.0
    rms_max = 0.0
    t0 = time.time()
    try:
        while True:
            buf = proc.stdout.read(FRAME_BYTES)
            if len(buf) < FRAME_BYTES:
                print("arecord остановился")
                return
            frame = np.frombuffer(buf, dtype=np.int16)
            rms_max = max(rms_max, _rms(frame))
            frames.append(frame)
            if len(frames) < CHUNK_FRAMES:
                continue
            scores = model.predict(np.concatenate(list(frames)))
            best = max(best, max((float(v) for v in scores.values()), default=0.0))
            if time.time() - t0 >= 0.5:
                print(f"rms_max={rms_max:7.0f}  score_max={best:.3f}  scores={scores}")
                best, rms_max, t0 = 0.0, 0.0, time.time()
    finally:
        proc.terminate()
        proc.wait()


if __name__ == "__main__":
    try:
        if "--debug" in sys.argv:
            if IS_MAC:
                print("Режим --debug работает только на Linux: нужен arecord.")
            else:
                debug_scores()
        elif IS_MAC:
            asyncio.run(main_mac())
        else:
            main_linux()
    except KeyboardInterrupt:
        pass
