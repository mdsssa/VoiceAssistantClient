# audio.py — общая озвучка: проигрывание звуков и TTS.
# Используется в main.py (ответы) и timer_watcher.py (сработавшие таймеры).

import os
import platform
import subprocess
import tempfile

import requests

import spotifyConnect


IS_MAC = platform.system() == "Darwin"
TTS_URL = os.environ.get("TTS_URL", "http://localhost:8003/synthesize")


def play_sound(path, blocking=True):
    """mp3 гоняем через mpg123, wav — через aplay; на macOS всё умеет afplay."""
    if IS_MAC:
        cmd = ["afplay", path]
    elif path.endswith(".mp3"):
        cmd = ["mpg123", "-q", path]
    else:
        cmd = ["aplay", "-q", path]
    if blocking:
        subprocess.run(cmd)
    else:
        subprocess.Popen(cmd)


def speak(text):
    """Озвучивает текст, на время ставя музыку на паузу.
    Любая ошибка TTS/плеера логируется и не роняет вызывающий процесс."""
    was_playing = False
    try:
        was_playing = spotifyConnect.pause_music()

        r = requests.post(TTS_URL, json={"text": text})
        if not r.ok or not r.content:
            print(f"[speak] TTS не ответил: {r.status_code}")
            return

        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as f:
            f.write(r.content)
            path = f.name
        try:
            play_sound(path)
        finally:
            os.remove(path)
    except Exception as e:
        print(f"[speak error] {e}")
    finally:
        if was_playing:
            spotifyConnect.resume_music()
