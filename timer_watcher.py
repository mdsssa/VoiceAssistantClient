import time
from datetime import datetime

from audio import speak
from timers import _load, _save


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

    if not fired:
        return

    _save(remaining)
    for t in fired:
        print(f"[timer_watcher] Сработал: {t['label']}")
        if t["type"] == "alarm":
            speak(f"Будильник! Время {datetime.now().strftime('%H:%M')}")
        else:
            speak(t["label"] + ", время вышло")


if __name__ == "__main__":
    print("Слежу за таймерами...")
    try:
        while True:
            try:
                check_timers()
            except Exception as e:
                # битый файл/недоступный TTS не должны убивать watcher
                print(f"[timer_watcher error] {e}")
            time.sleep(1)
    except KeyboardInterrupt:
        pass
