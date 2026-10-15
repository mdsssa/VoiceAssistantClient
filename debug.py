
import os
import subprocess
import time
from collections import deque
from importlib.metadata import version

import numpy as np
from livekit.wakeword import WakeWordModel

MODEL_PATH = os.path.expanduser("~/VoiceAssistantClient/kera.onnx")
MIC = os.environ.get("KERA_MIC", "default")
FRAME = 1280        # 80 мс
CHUNK_FRAMES = 25   # окно 2 с, как в WakeWordListener

print("livekit-wakeword", version("livekit-wakeword"))
print("model size:", os.path.getsize(MODEL_PATH), "байт | микрофон:", MIC)

model = WakeWordModel(models=[MODEL_PATH])
proc = subprocess.Popen(
    ["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
    stdout=subprocess.PIPE,
)

frames = deque(maxlen=CHUNK_FRAMES)
best = 0.0
rms_max = 0.0
t0 = time.time()
try:
    while True:
        buf = proc.stdout.read(FRAME * 2)
        if len(buf) < FRAME * 2:
            print("arecord остановился")
            break
        frame = np.frombuffer(buf, dtype=np.int16)
        rms_max = max(rms_max, float(np.sqrt(np.mean(frame.astype(np.float64) ** 2))))
        frames.append(frame)
        if len(frames) < CHUNK_FRAMES:
            continue
        scores = model.predict(np.concatenate(list(frames)))
        try:
            best = max(best, max(float(v) for v in scores.values()))
        except Exception:
            pass
        if time.time() - t0 >= 0.5:
            print(f"rms_max={rms_max:7.0f}  score_max={best:.3f}  scores={scores}")
            best, rms_max, t0 = 0.0, 0.0, time.time()
except KeyboardInterrupt:
    pass
finally:
    proc.terminate()