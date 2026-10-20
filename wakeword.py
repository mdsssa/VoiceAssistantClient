import asyncio
import os
import platform
import subprocess
from collections import deque

import numpy as np
import onnxruntime as ort
from livekit.wakeword import WakeWordModel

MODEL_PATH = os.path.expanduser("~/VoiceAssistantClient/kera.onnx")
MODEL_NAME = "kera"    
THRESHOLD = 0.35             
DEBOUNCE = 2.0               

LINUX_MIC = os.environ.get("KERA_MIC", "default")
FRAME_SAMPLES = 1280         # 80 мс при 16 кГц, как в WakeWordListener
FRAME_BYTES = FRAME_SAMPLES * 2
CHUNK_FRAMES = 25            
PREDICT_EVERY = 4            
GATE_RMS = 700               

IS_MAC = platform.system() == "Darwin"
if IS_MAC:
    PYTHON_BIN = "python3"
else:
    PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")


def make_model() -> WakeWordModel:
    so = ort.SessionOptions()
    so.intra_op_num_threads = 1
    so.inter_op_num_threads = 1
    return WakeWordModel(models=[MODEL_PATH], sess_options=so)



def wait_for_wakeword_linux() -> float:
    model = make_model()
    cmd = ["arecord", "-q", "-D", LINUX_MIC, "-f", "S16_LE",
           "-r", "16000", "-c", "1", "-t", "raw"]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
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
            rms_hist.append(float(np.sqrt(np.mean(frame.astype(np.float32) ** 2))))
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


if __name__ == "__main__":
    try:
        if IS_MAC:
            asyncio.run(main_mac())
        else:
            main_linux()
    except KeyboardInterrupt:
        pass