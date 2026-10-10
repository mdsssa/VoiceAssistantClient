"""
Wake word «Кэра» на livekit-wakeword (замена Vosk-версии).

После срабатывания микрофон освобождается, запускается main.py --single-turn,
затем детектор создаётся заново и слушает дальше.
"""
import asyncio
import os
import platform
import subprocess

from livekit.wakeword import WakeWordListener, WakeWordModel

MODEL_PATH = os.path.expanduser("~/VoiceAssistantClient/kera.onnx")
THRESHOLD = 0.5   # на тестах было 0.5-0.77; ловит плохо -> 0.35-0.4, ложные -> 0.6
DEBOUNCE = 2.0    # секунды тишины после срабатывания

if platform.system() == "Darwin":
    PYTHON_BIN = "python3"
else:
    PYTHON_BIN = os.path.expanduser("~/VoiceAssistantClient/venv/bin/python3")
MAIN_SCRIPT = os.path.expanduser("~/VoiceAssistantClient/main.py")


async def wait_for_wakeword():
    # Новая модель на каждый цикл, чтобы в буфере не оставалось старого аудио
    model = WakeWordModel(models=[MODEL_PATH])
    async with WakeWordListener(model, threshold=THRESHOLD, debounce=DEBOUNCE) as listener:
        return await listener.wait_for_detection()


async def main():
    print("Жду 'Кэра'...")
    while True:
        detection = await wait_for_wakeword()
        print(f"Finaly Heard! (conf={detection.confidence:.2f})")
        # Микрофон уже свободен (вышли из async with), main.py может его занять
        await asyncio.to_thread(
            subprocess.run, [PYTHON_BIN, MAIN_SCRIPT, "--single-turn"]
        )
        print("Жду 'Кэра'...")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        pass