import time
import os
import subprocess
import platform
import requests
from datetime import datetime
from timers import TIMERS_FILE, _load, _save
import spotifyConnect

TTS_URL = "http://localhost:8003/synthesize"


def play_sound(path, blocking=True):
    cmd = ["mpg123", "-q", path] if platform.system() != "Darwin" else ["afplay", path]
    if blocking:
        subprocess.run(cmd)
    else:
        subprocess.Popen(cmd)


def speak(text):
    was_playing = spotifyConnect.duck_pause()
    r = requests.post(TTS_URL, json={"text": text})
    path = "/tmp/timer_announce.wav"
    with open(path, "wb") as f:
        f.write(r.content)
    subprocess.run(["aplay", "-q", path] if platform.system() != "Darwin" else ["afplay", path])
    os.remove(path)
    if was_playing:
        spotifyConnect.resume_music()


def check_timers():
    timers = _load()
    now = datetime.now()
    remaining = []
    fired = []

    for t in timers:
        target = datetime.fromisoformat(t["target"])
        if now >= target:
            fired.append(t)
        else:
            remaining.append(t)

    if fired:
        _save(remaining)
        for t in fired:
            print(f"[timer_watcher] Сработал: {t['label']}")
            if t["type"] == "alarm":
                speak(f"Будильник! Время {datetime.now().strftime('%H:%M')}")
            else:
                speak(t["label"] + ", время вышло")


if __name__ == "__main__":
    print("Слежу за таймерами...")
    while True:
        time.sleep(1)
        check_timers()