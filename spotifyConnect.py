import requests
import json
import os
import time
import webbrowser
import base64
import http.server
import urllib.parse
import subprocess
import os
from dotenv import load_dotenv
import platform


load_dotenv()

CLIENT_ID = os.environ["CLIENT_ID"]
CLIENT_SECRET = os.environ["CLIENT_SECRET"]
REDIRECT_URI = os.environ.get("REDIRECT_URI")
TARGET_DEVICE_NAME = os.environ.get("SPOTIFY_TARGET_DEVICE")
# Должен ТОЧНО совпадать с тем, что вписан в настройках приложения на
# dashboard (Redirect URIs). Локальный редирект для однократной ручной
# авторизации на этой же машине.

SCOPES =  "user-read-playback-state user-modify-playback-state user-library-modify"

TOKEN_FILE = os.path.expanduser("~/.spotify_token_cache.json")

AUTH_URL = "https://accounts.spotify.com/authorize"
TOKEN_URL = "https://accounts.spotify.com/api/token"
API_BASE = "https://api.spotify.com/v1"


# ==== Часть 1: первичная авторизация (запускается один раз руками) ====

class _CallbackHandler(http.server.BaseHTTPRequestHandler):
    """Ловит редирект от Spotify с authorization code."""
    code = None

    def do_GET(self):
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _CallbackHandler.code = params.get("code", [None])[0]
        self.send_response(200)
        self.send_header("Content-type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write("Готово, можно закрывать вкладку.".encode("utf-8"))


def _get_authorization_code():
    params = {
        "client_id": CLIENT_ID,
        "response_type": "code",
        "redirect_uri": REDIRECT_URI,
        "scope": SCOPES,
    }
    url = f"{AUTH_URL}?{urllib.parse.urlencode(params)}"
    print(f"Открываю браузер для авторизации:\n{url}")
    webbrowser.open(url)

    server = http.server.HTTPServer(("127.0.0.1", 8888), _CallbackHandler)
    server.handle_request()  # блокируется, пока не придёт один запрос
    return _CallbackHandler.code


def _exchange_code_for_token(code):
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth_header}"},
        data={
            "grant_type": "authorization_code",
            "code": code,
            "redirect_uri": REDIRECT_URI,
        },
    )
    r.raise_for_status()
    return r.json()


def run_initial_auth():
    """Запускать один раз вручную: python3 spotify_control.py --auth"""
    code = _get_authorization_code()
    if not code:
        print("Не получили authorization code, что-то пошло не так.")
        return
    token_data = _exchange_code_for_token(code)
    token_data["obtained_at"] = time.time()
    with open(TOKEN_FILE, "w") as f:
        json.dump(token_data, f)
    print(f"Готово! Токен сохранён в {TOKEN_FILE}")


# ==== Часть 2: авто-обновление токена (используется на каждый вызов) ====

def _load_token_cache():
    if not os.path.exists(TOKEN_FILE):
        raise RuntimeError(
            "Нет сохранённого токена. Сначала запусти: python3 spotify_control.py --auth"
        )
    with open(TOKEN_FILE) as f:
        return json.load(f)


def _refresh_access_token(refresh_token):
    auth_header = base64.b64encode(f"{CLIENT_ID}:{CLIENT_SECRET}".encode()).decode()
    r = requests.post(
        TOKEN_URL,
        headers={"Authorization": f"Basic {auth_header}"},
        data={
            "grant_type": "refresh_token",
            "refresh_token": refresh_token,
        },
    )
    r.raise_for_status()
    return r.json()


def get_access_token():
    """
    Возвращает валидный access_token, сама обновляя его по refresh_token,
    если он истёк (access_token живёт всего час).
    """
    cache = _load_token_cache()
    expires_at = cache["obtained_at"] + cache["expires_in"]

    if time.time() < expires_at - 60:  # запас в 60 секунд
        return cache["access_token"]

    new_data = _refresh_access_token(cache["refresh_token"])
    # refresh_token иногда не возвращается повторно — берём старый, если нет нового
    new_data.setdefault("refresh_token", cache["refresh_token"])
    new_data["obtained_at"] = time.time()

    with open(TOKEN_FILE, "w") as f:
        json.dump(new_data, f)

    return new_data["access_token"]


# ==== Часть 3: сами команды к Web API ====

def _auth_headers():
    return {"Authorization": f"Bearer {get_access_token()}"}


def get_devices():
    """Список доступных Spotify Connect устройств (телефон, HeroBox и т.д.)"""
    r = requests.get(f"{API_BASE}/me/player/devices", headers=_auth_headers())
    r.raise_for_status()
    return r.json()["devices"]


def find_device_id(name_substring):
    """Находит device_id по части имени устройства (например, 'HeroBox')."""
    devices = get_devices()
    for d in devices:
        if name_substring.lower() in d["name"].lower():
            return d["id"]
    return None

def whats_playing(*_args, **_kwargs):
    """Говорит, какой трек сейчас играет."""
    try:
        track = get_current_track()
        if not track:
            return "Сейчас ничего не играет"
        result = f"Сейчас играет: {track['name']}"
        print(result)
        return result
    except Exception as e:
        print(f"[whats_playing error] {e}")
        return f"Не получилось узнать, что играет: {e}"


def like_current_track(*_args, **_kwargs):
    try:
        track = get_current_track()
        if not track:
            return "Сейчас ничего не играет, нечего добавлять в избранное"
        save_track(track["uri"])  # было track["id"]
        result = f"Добавила в избранное: {track['name']}"
        print(result)
        return result
    except Exception as e:
        print(f"[like_current_track error] {e}")
        return f"Не получилось добавить в избранное: {e}"


def search_track(query):
    """Ищет трек, возвращает его uri и читаемое название или None."""
    r = requests.get(
        f"{API_BASE}/search",
        headers=_auth_headers(),
        params={"q": query, "type": "track", "limit": 1},
    )
    r.raise_for_status()
    items = r.json()["tracks"]["items"]
    if not items:
        return None
    track = items[0]
    artists = ", ".join(a["name"] for a in track["artists"])
    return {
        "uri": track["uri"],
        "name": f"{artists} — {track['name']}",
    }


def play_track_uri(uri, device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.put(
        f"{API_BASE}/me/player/play",
        headers=_auth_headers(),
        params=params,
        json={"uris": [uri]},
    )
    # 204 No Content — нормальный ответ на успешный play
    if r.status_code not in (200, 204):
        r.raise_for_status()


def pause(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.put(f"{API_BASE}/me/player/pause", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def next_track(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.post(f"{API_BASE}/me/player/next", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def get_current_track():
    """Возвращает информацию о текущем играющем треке (или None, если ничего не играет)."""
    r = requests.get(f"{API_BASE}/me/player/currently-playing", headers=_auth_headers())
    if r.status_code == 204 or not r.content:
        return None
    r.raise_for_status()
    data = r.json()
    item = data.get("item")
    if not item:
        return None
    artists = ", ".join(a["name"] for a in item["artists"])
    return {
        "id": item["id"],
        "uri": item["uri"],
        "name": f"{artists} — {item['name']}",
        "is_playing": data.get("is_playing", False),
    }


def save_track(track_uri):
    """Добавляет трек в 'Your Music' (Liked Songs) через актуальный
    универсальный эндпоинт библиотеки."""
    r = requests.put(
        f"{API_BASE}/me/library",
        headers=_auth_headers(),
        params={"uris": track_uri},
    )
    if r.status_code not in (200, 204):
        print(f"[save_track] {r.status_code}: {r.text}")
        r.raise_for_status()



def search_track(query):
    """Ищет трек, возвращает его uri, читаемое название и uri альбома
    (для запуска с реальной очередью, чтобы next/previous работали)."""
    r = requests.get(
        f"{API_BASE}/search",
        headers=_auth_headers(),
        params={"q": query, "type": "track", "limit": 1},
    )
    r.raise_for_status()
    items = r.json()["tracks"]["items"]
    if not items:
        return None
    track = items[0]
    artists = ", ".join(a["name"] for a in track["artists"])
    return {
        "uri": track["uri"],
        "name": f"{artists} — {track['name']}",
        "album_uri": track["album"]["uri"],
    }


def play_context_uri(context_uri, offset_uri, device_id=None):
    """Запускает воспроизведение контекста (альбом/плейлист) с конкретного
    трека — так у Spotify появляется реальная очередь, и next/previous
    начинают осмысленно работать."""
    params = {"device_id": device_id} if device_id else {}
    r = requests.put(
        f"{API_BASE}/me/player/play",
        headers=_auth_headers(),
        params=params,
        json={"context_uri": context_uri, "offset": {"uri": offset_uri}},
    )
    if r.status_code not in (200, 204):
        print(f"[play_context_uri] {r.status_code}: {r.text}")
        r.raise_for_status()

def pause(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.put(f"{API_BASE}/me/player/pause", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def resume(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.put(f"{API_BASE}/me/player/play", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def next_track(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.post(f"{API_BASE}/me/player/next", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def previous_track(device_id=None):
    params = {"device_id": device_id} if device_id else {}
    r = requests.post(f"{API_BASE}/me/player/previous", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def set_volume(percent, device_id=None):
    """percent: 0-100"""
    params = {"volume_percent": max(0, min(100, int(percent)))}
    if device_id:
        params["device_id"] = device_id
    r = requests.put(f"{API_BASE}/me/player/volume", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()


def seek(position_ms, device_id=None):
    """Перемотка на конкретную позицию в треке, в миллисекундах."""
    params = {"position_ms": max(0, int(position_ms))}
    if device_id:
        params["device_id"] = device_id
    r = requests.put(f"{API_BASE}/me/player/seek", headers=_auth_headers(), params=params)
    if r.status_code not in (200, 204):
        r.raise_for_status()



def play_music(query):
    try:
        track = search_track(query)
        if not track:
            return f"Не нашла трек по запросу: {query}"

        device_id = find_device_id(TARGET_DEVICE_NAME)
        if not device_id:
            return (
                f"Не вижу устройство '{TARGET_DEVICE_NAME}' в списке Spotify Connect. "
                "Проверь, что librespot запущен."
            )

        play_context_uri(track["album_uri"], track["uri"], device_id=device_id)
        result = f"Включаю: {track['name']}"
        print(result)
        return result
    except Exception as e:
        print(f"[play_music error] {e}")
        return f"Не получилось включить музыку: {e}"


def _resolve_device_or_message():
    """
    Общий хелпер для остальных команд плеера: находит device_id целевого
    устройства или возвращает (None, сообщение_об_ошибке).
    """
    device_id = find_device_id(TARGET_DEVICE_NAME)
    if not device_id:
        return None, (
            f"Не вижу устройство '{TARGET_DEVICE_NAME}' в списке Spotify Connect. "
            "Проверь, что librespot запущен."
        )
    return device_id, None


def pause_music(*_args, **_kwargs):
    """Ставит воспроизведение на паузу. Возвращает True, если что-то
    реально было поставлено на паузу (было is_playing=True), иначе False —
    это нужно вызывающему коду, чтобы знать, стоит ли потом резюмить."""
    try:
        r = requests.get(f"{API_BASE}/me/player", headers=_auth_headers())
        if r.status_code == 204 or not r.json().get("is_playing"):
            return False  # нечего было ставить на паузу

        device_id, err = _resolve_device_or_message()
        if err:
            return False
        pause(device_id=device_id)
        print("Поставила на паузу")
        return True
    except Exception as e:
        print(f"[pause_music error] {e}")
        return False


def resume_music(*_args, **_kwargs):
    """Продолжает воспроизведение с того же места."""
    try:
        device_id, err = _resolve_device_or_message()
        if err:
            return err
        resume(device_id=device_id)
        result = "Продолжаю"
        print(result)
        return result
    except Exception as e:
        print(f"[resume_music error] {e}")
        return f"Не получилось продолжить воспроизведение: {e}"


def skip_track(*_args, **_kwargs):
    """Переключает на следующий трек."""
    try:
        device_id, err = _resolve_device_or_message()
        if err:
            return err
        next_track(device_id=device_id)
        result = "Переключаю на следующий трек"
        print(result)
        return result
    except Exception as e:
        print(f"[skip_track error] {e}")
        return f"Не получилось переключить трек: {e}"


def previous_music_track(*_args, **_kwargs):
    """Возвращает на предыдущий трек."""
    try:
        device_id, err = _resolve_device_or_message()
        if err:
            return err
        previous_track(device_id=device_id)
        result = "Включаю предыдущий трек"
        print(result)
        return result
    except Exception as e:
        print(f"[previous_music_track error] {e}")
        return f"Не получилось включить предыдущий трек: {e}"


# def change_volume(level):
#     try:
#         device_id, err = _resolve_device_or_message()
#         if err:
#             return err
#         level = max(0, min(100, int(level)))
#         set_volume(level, device_id=device_id)
#         result = f"Ставлю громкость на {level}%"
#         print(result)
#         return result
#     except Exception as e:
#         print(f"[change_volume error] {e}")
#         return f"Не получилось изменить громкость: {e}"


def change_volume(level):
    try:
        level = max(0, min(100, int(level)))
        if platform.system() == "Darwin":
            subprocess.run(["osascript", "-e", f"set volume output volume {level}"])
        else:
            subprocess.run(["pactl", "set-sink-volume", "@DEFAULT_SINK@", f"{level}%"], check=True)
        result = f"Ставлю громкость на {level}%"
        print(result)
        return result
    except Exception as e:
        print(f"[change_volume error] {e}")
        return f"Не получилось изменить громкость: {e}"



def seek_track(seconds):
    """
    seconds: позиция в треке в секундах, куда перемотать (например,
    "перемотай на минуту" -> 60).
    """
    try:
        device_id, err = _resolve_device_or_message()
        if err:
            return err
        position_ms = max(0, int(seconds)) * 1000
        seek(position_ms, device_id=device_id)
        result = f"Перематываю на {seconds} секунд"
        print(result)
        return result
    except Exception as e:
        print(f"[seek_track error] {e}")
        return f"Не получилось перемотать трек: {e}"


if __name__ == "__main__":
    import sys

    if "--auth" in sys.argv:
        run_initial_auth()
    else:
        print("Использование: python3 spotify_control.py --auth")
