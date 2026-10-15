
import os
import subprocess
import sys
import time
from importlib.metadata import version

import numpy as np
from livekit.wakeword import WakeWordModel

MODEL_PATH = os.path.expanduser("~/VoiceAssistantClient/kera.onnx")
MIC = os.environ.get("KERA_MIC", "default")
USE_FLOAT = len(sys.argv) > 1 and sys.argv[1] == "float"
FRAME = 1280  # 80 мс

print("livekit-wakeword", version("livekit-wakeword"), "| формат:", "float32" if USE_FLOAT else "int16")
print("model size:", os.path.getsize(MODEL_PATH), "байт | микрофон:", MIC)

model = WakeWordModel(models=[MODEL_PATH])
proc = subprocess.Popen(
    ["arecord", "-q", "-D", MIC, "-f", "S16_LE", "-r", "16000", "-c", "1", "-t", "raw"],
    stdout=subprocess.PIPE,
)

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
        data = frame.astype(np.float32) / 32768.0 if USE_FLOAT else frame
        scores = model.predict(data)
        try:
            top = max(float(v) for v in scores.values())
            shown = {k: round(float(v), 3) for k, v in scores.items()}
        except Exception:
            top, shown = 0.0, scores
        best = max(best, top)
        if time.time() - t0 >= 0.5:
            print(f"rms_max={rms_max:7.0f}  score_max={best:.3f}  scores={shown}")
            best, rms_max, t0 = 0.0, 0.0, time.time()
except KeyboardInterrupt:
    pass
finally:
    proc.terminate()