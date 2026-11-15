import sounddevice as sd
import numpy as np

SAMPLE_RATE = 16000
chunk_size = 1024

stream = sd.InputStream(samplerate=SAMPLE_RATE, channels=1, dtype='int16')
stream.start()

try:
    while True:
        data, _ = stream.read(chunk_size)
        volume = np.abs(data).mean()
        print(f"Level: {volume:.0f}")
except KeyboardInterrupt:
    pass
finally:
    stream.stop()
    stream.close()
