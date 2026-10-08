
import json
import os
import time
from datetime import datetime, timedelta

TIMERS_FILE = os.path.expanduser("~/VoiceAssistantClient/.timers.json")


def _load():
    if not os.path.exists(TIMERS_FILE):
        return []
    try:
        with open(TIMERS_FILE) as f:
            return json.load(f)
    except (json.JSONDecodeError, FileNotFoundError):
        return []


def _save(timers):
    with open(TIMERS_FILE, "w") as f:
        json.dump(timers, f, ensure_ascii=False)


def set_timer(minutes):
    """Ставит таймер на N минут от текущего момента."""
    try:
        minutes = float(minutes)
        target = datetime.now() + timedelta(minutes=minutes)
        timers = _load()
        timers.append({
            "type": "timer",
            "target": target.isoformat(),
            "label": f"Таймер на {minutes:g} минут"
        })
        _save(timers)
        result = f"Поставила таймер на {minutes:g} минут"
        print(result)
        return result
    except Exception as e:
        print(f"[set_timer error] {e}")
        return f"Не получилось поставить таймер: {e}"


def set_alarm(time_str):
    """Ставит будильник на конкретное время (формат HH:MM), на ближайшее
    наступление этого времени — сегодня, если ещё не прошло, иначе завтра."""
    try:
        hour, minute = map(int, time_str.split(":"))
        now = datetime.now()
        target = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if target <= now:
            target += timedelta(days=1)

        timers = _load()
        timers.append({
            "type": "alarm",
            "target": target.isoformat(),
            "label": f"Будильник на {time_str}"
        })
        _save(timers)
        result = f"Поставила будильник на {time_str}"
        print(result)
        return result
    except Exception as e:
        print(f"[set_alarm error] {e}")
        return f"Не получилось поставить будильник: {e}"


def cancel_all_timers(*_args, **_kwargs):
    """Отменяет все активные таймеры и будильники."""
    _save([])
    result = "Отменила все таймеры и будильники"
    print(result)
    return result


def list_timers(*_args, **_kwargs):
    """Озвучивает список активных таймеров/будильников."""
    timers = _load()
    if not timers:
        return "Активных таймеров и будильников нет"
    parts = [t["label"] for t in timers]
    return "Активные: " + ", ".join(parts)