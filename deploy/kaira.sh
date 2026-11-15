#!/usr/bin/env bash
# kaira.sh — проверка и перезапуск systemd-сервисов Кэры на сервере.
# Сам по себе ничего не меняет: check только читает, restart перезапускает юниты.
#
#   bash deploy/kaira.sh check              проверить файлы, .env, зависимости, порты, юниты
#   bash deploy/kaira.sh status             только состояние сервисов
#   bash deploy/kaira.sh restart            перезапустить 5 сервисов (librespot не трогает)
#   bash deploy/kaira.sh restart tgbot      перезапустить конкретный юнит
#   bash deploy/kaira.sh logs [unit]        смотреть лог (по умолчанию kaira-wakeword)

set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNITS=(kaira-stt kaira-tts kaira-timers kaira-wakeword tgbot)
OPTIONAL_UNITS=(librespot)
fail=0

ok()      { printf '  ✅ %s\n' "$*"; }
bad()     { printf '  ❌ %s\n' "$*"; fail=1; }
warn()    { printf '  ⚠️  %s\n' "$*"; }
section() { printf '\n%s\n' "$*"; }

usage() {
  cat <<'TXT'
Использование: bash deploy/kaira.sh <команда>

  check          проверить файлы, .env, Python-зависимости, порты и юниты
  status         показать состояние сервисов
  restart [u]    перезапустить все сервисы или один указанный
  logs [u]       смотреть journal (по умолчанию kaira-wakeword)
TXT
}

# --- выбираем python проекта ---
PY=""
for candidate in "$ROOT/venv/bin/python3" "$ROOT/.venv/bin/python3"; do
  if [ -x "$candidate" ]; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then PY="$(command -v python3 || true)"; fi

# --- выбираем systemd: user-юниты приоритетнее системных ---
CTL=()
if command -v systemctl >/dev/null 2>&1; then
  if [ -z "${XDG_RUNTIME_DIR:-}" ] && [ -d "/run/user/$(id -u)" ]; then
    export XDG_RUNTIME_DIR="/run/user/$(id -u)"
  fi
  if systemctl --user list-unit-files --no-legend >/dev/null 2>&1 \
     && systemctl --user list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -qx 'kaira-stt.service'; then
    CTL=(systemctl --user)
  elif systemctl list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -qx 'kaira-stt.service'; then
    CTL=(systemctl)
  fi
fi

has_unit() {
  [ ${#CTL[@]} -gt 0 ] || return 1
  "${CTL[@]}" list-unit-files --no-legend 2>/dev/null | awk '{print $1}' | grep -qx "$1.service"
}

env_value() {
  [ -f "$ROOT/.env" ] || return 1
  grep -E "^[[:space:]]*$1[[:space:]]*=" "$ROOT/.env" 2>/dev/null \
    | tail -1 | cut -d= -f2- | sed 's/[[:space:]]*#.*$//' \
    | sed 's/^[[:space:]]*//; s/[[:space:]]*$//'
}

check_files() {
  section "Файлы проекта: $ROOT"
  local f
  for f in main.py wakeword.py timer_watcher.py telegrambot.py sstServer.py ttsServer.py \
           audio.py prompts.py tools.py spotifyConnect.py kera.onnx \
           sounds/readyToListenV2.mp3 sounds/listeningEndV2.mp3; do
    if [ -e "$ROOT/$f" ]; then ok "$f"; else bad "нет $f"; fi
  done
}

check_env() {
  section ".env"
  if [ ! -f "$ROOT/.env" ]; then
    bad "нет .env — ассистент не запустится"
    return
  fi
  ok ".env на месте"

  local k
  for k in CLIENT_ID CLIENT_SECRET SPOTIFY_TARGET_DEVICE BOT_TOKEN CHAT_ID; do
    if [ -n "$(env_value "$k")" ]; then ok "$k задан"; else bad "$k не задан"; fi
  done

  local provider
  provider="$(env_value LLM_PROVIDER)"
  provider="${provider:-local}"
  if [ "$provider" = "groq" ]; then
    if [ -n "$(env_value GROQ_API_KEY)" ]; then
      ok "LLM_PROVIDER=groq, GROQ_API_KEY задан"
    else
      bad "LLM_PROVIDER=groq, но GROQ_API_KEY пуст"
    fi
  else
    ok "LLM_PROVIDER=$provider (Groq-ключ не нужен)"
    if [ -n "$(env_value LOCAL_LLM_URL)" ]; then
      ok "LOCAL_LLM_URL задан"
    else
      warn "LOCAL_LLM_URL не задан — будет http://localhost:8002/..."
    fi
  fi

  if [ -f "$HOME/.spotify_token_cache.json" ]; then
    ok "Spotify-токен на месте"
  else
    warn "нет ~/.spotify_token_cache.json — нужен python spotifyConnect.py --auth"
  fi
}

check_python() {
  section "Python-зависимости"
  if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    bad "не найден python ($PY)"
    return
  fi
  ok "интерпретатор: $PY"
  "$PY" -c 'import sys; print("  ℹ️  python", sys.version.split()[0])'

  local m
  for m in requests dotenv numpy sounddevice soundfile ddgs telebot onnxruntime livekit.wakeword flask; do
    if "$PY" -c "import $m" >/dev/null 2>&1; then ok "$m"; else bad "$m"; fi
  done
  for m in faster_whisper torch; do
    if "$PY" -c "import $m" >/dev/null 2>&1; then ok "$m"; else bad "$m (нужен kaira-stt/kaira-tts)"; fi
  done
}

check_ports() {
  section "Порты"
  if ! command -v ss >/dev/null 2>&1 && ! command -v lsof >/dev/null 2>&1; then
    warn "нет ss/lsof — порты не проверить"
    return
  fi
  local p unit
  for p in 8001 8003; do
    unit=$([ "$p" = 8001 ] && echo kaira-stt || echo kaira-tts)
    if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE "[:.]$p[[:space:]]"; then
      ok ":$p слушается ($unit)"
    elif command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      ok ":$p слушается ($unit)"
    else
      bad ":$p не слушается ($unit)"
    fi
  done
}

check_services() {
  section "systemd"
  if [ ${#CTL[@]} -eq 0 ]; then
    warn "юниты kaira-* не найдены (ни systemctl --user, ни systemctl)"
    warn "запусти из сессии пользователя или проверь: systemctl --user list-units"
    return
  fi
  ok "контекст: ${CTL[*]}"

  local u state exec_line wd user dead arg
  for u in "${UNITS[@]}" "${OPTIONAL_UNITS[@]}"; do
    if ! has_unit "$u"; then
      warn "нет юнита $u"
      continue
    fi

    state=$("${CTL[@]}" is-active "$u" 2>/dev/null || true)
    if [ "$state" = "active" ]; then ok "$u active"; else bad "$u: ${state:-unknown}"; fi

    exec_line=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^ExecStart=' || true)
    if [ -n "$exec_line" ]; then
      exec_line="${exec_line#ExecStart=}"
      exec_line="${exec_line#-}"
      exec_line="${exec_line//%h/$HOME}"
      printf '       ExecStart: %s\n' "$(printf '%s' "$exec_line" | cut -c1-150)"
      for dead in debug.py t_info.py interruptible_speak.py justtest.py; do
        case "$exec_line" in
          *"$dead"*) bad "$u всё ещё ссылается на удалённый $dead" ;;
        esac
      done
      for arg in $exec_line; do
        case "$arg" in
          "~/"*) arg="$HOME/${arg#~/}" ;;
        esac
        case "$arg" in
          *.py)
            if [ ! -f "$arg" ] && [ ! -f "$ROOT/$arg" ]; then
              bad "$u: нет файла $arg"
            fi
            ;;
        esac
      done
    fi

    wd=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^WorkingDirectory=' | cut -d= -f2-)
    wd="${wd#-}"
    wd="${wd//%h/$HOME}"
    if [ -n "$wd" ] && [ ! -d "$wd" ]; then
      bad "$u: WorkingDirectory не существует: $wd"
    fi

    user=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^User=' | cut -d= -f2-)
    if [ "$user" = "root" ]; then
      warn "$u работает от root — звук и микрофон могут быть недоступны"
    fi
  done
}

check_audio() {
  section "Аудио"
  if command -v arecord >/dev/null 2>&1; then
    if arecord -l 2>/dev/null | grep -q '^card'; then
      ok "микрофон виден (arecord -l)"
    else
      warn "arecord не видит микрофонов"
    fi
  else
    warn "нет arecord (установи alsa-utils)"
  fi

  if command -v aplay >/dev/null 2>&1; then
    if aplay -l 2>/dev/null | grep -q '^card'; then
      ok "аудиовыход виден (aplay -l)"
    else
      warn "aplay не видит аудиовыходов"
    fi
  else
    warn "нет aplay (установи alsa-utils)"
  fi

  if command -v mpg123 >/dev/null 2>&1; then
    ok "mpg123 на месте"
  else
    bad "нет mpg123 — не проиграются sounds/*.mp3"
  fi

  if command -v pactl >/dev/null 2>&1; then
    if pactl info >/dev/null 2>&1; then
      ok "PulseAudio/PipeWire доступен"
    else
      warn "pactl не подключается (проверь user-сессию/XDG_RUNTIME_DIR)"
    fi
  fi

  if [ -n "${KERA_MIC:-}" ]; then
    ok "KERA_MIC=$KERA_MIC"
  else
    warn "KERA_MIC не задан в текущем shell — wakeword возьмёт default"
  fi
}

check_timers_file() {
  section "Таймеры"
  if [ ! -f "$ROOT/.timers.json" ]; then
    ok ".timers.json ещё нет — создастся сам"
    return
  fi
  if "$PY" -c "import json,sys; json.load(open(sys.argv[1]))" "$ROOT/.timers.json" >/dev/null 2>&1; then
    ok ".timers.json валиден"
  else
    bad ".timers.json битый — timer_watcher будет его игнорировать"
  fi
}

summary() {
  echo
  if [ "$fail" -eq 0 ]; then
    echo "Итог: всё зелёное ✅"
  else
    echo "Итог: есть проблемы ❌ — см. выше"
  fi
}

restart_units() {
  if [ ${#CTL[@]} -eq 0 ]; then
    echo "systemd-юниты kaira-* не найдены — нечего перезапускать"
    exit 1
  fi

  local list=("$@")
  if [ ${#list[@]} -eq 0 ]; then
    list=(kaira-stt kaira-tts tgbot kaira-timers kaira-wakeword)
  fi

  local u state
  for u in "${list[@]}"; do
    if ! has_unit "$u"; then
      warn "нет юнита $u"
      continue
    fi
    if "${CTL[@]}" restart "$u" 2>/dev/null; then
      ok "restart $u"
    else
      bad "restart $u"
    fi
  done

  sleep 2
  section "Состояние после рестарта"
  for u in "${list[@]}"; do
    has_unit "$u" || continue
    state=$("${CTL[@]}" is-active "$u" 2>/dev/null || true)
    if [ "$state" = "active" ]; then ok "$u active"; else bad "$u: ${state:-unknown}"; fi
  done
}

logs_cmd() {
  local unit="${1:-kaira-wakeword}"
  if [ ${#CTL[@]} -eq 0 ]; then
    echo "systemd-юниты kaira-* не найдены"
    exit 1
  fi
  if ! has_unit "$unit"; then
    echo "нет юнита $unit"
    exit 1
  fi
  if [ "${CTL[0]}" = "systemctl" ] && [ "${CTL[1]:-}" = "--user" ]; then
    journalctl --user -u "$unit" -f -n 100
  else
    journalctl -u "$unit" -f -n 100
  fi
}

cmd="${1:-check}"
case "$cmd" in
  check)
    check_files
    check_env
    check_python
    check_ports
    check_services
    check_audio
    check_timers_file
    summary
    exit "$fail"
    ;;
  status)
    check_services
    summary
    exit "$fail"
    ;;
  restart)
    shift
    restart_units "$@"
    summary
    exit "$fail"
    ;;
  logs)
    shift
    logs_cmd "$@"
    ;;
  help|-h|--help)
    usage
    ;;
  *)
    echo "Неизвестная команда: $cmd"
    usage
    exit 2
    ;;
esac
