#!/usr/bin/env bash
# kaira.sh - check and restart Kera's systemd services on the server.
# The script is safe by default: `check` only reads, `restart` only restarts the listed units.
#
#   bash deploy/kaira.sh check              check files, .env, dependencies, ports, and units
#   bash deploy/kaira.sh status             show service status only
#   bash deploy/kaira.sh restart            restart the 5 services (leaves librespot alone)
#   bash deploy/kaira.sh restart tgbot      restart a single unit
#   bash deploy/kaira.sh logs [unit]        follow the journal (default: kaira-wakeword)

set -o pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
UNITS=(kaira-stt kaira-tts kaira-timers kaira-wakeword tgbot)
OPTIONAL_UNITS=(librespot)
fail=0

ok()      { printf '  [ok]   %s\n' "$*"; }
bad()     { printf '  [fail] %s\n' "$*"; fail=1; }
warn()    { printf '  [warn] %s\n' "$*"; }
info()    { printf '  [info] %s\n' "$*"; }
section() { printf '\n%s\n' "$*"; }

usage() {
  cat <<'TXT'
Usage: bash deploy/kaira.sh <command>

  check          check files, .env, Python dependencies, ports, and units
  status         show service status
  restart [u]    restart all services or one specified unit
  logs [u]       follow the journal (default: kaira-wakeword)
TXT
}

# --- project python ---
PY=""
for candidate in "$ROOT/venv/bin/python3" "$ROOT/.venv/bin/python3"; do
  if [ -x "$candidate" ]; then PY="$candidate"; break; fi
done
if [ -z "$PY" ]; then PY="$(command -v python3 || true)"; fi

# --- systemd: prefer user units over system units ---
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
  section "Project files: $ROOT"
  local f
  for f in main.py wakeword.py timer_watcher.py telegrambot.py sstServer.py ttsServer.py \
           audio.py prompts.py tools.py spotifyConnect.py kera.onnx \
           sounds/readyToListenV2.mp3 sounds/listeningEndV2.mp3; do
    if [ -e "$ROOT/$f" ]; then ok "$f"; else bad "missing $f"; fi
  done
}

check_env() {
  section ".env"
  if [ ! -f "$ROOT/.env" ]; then
    bad "missing .env - the assistant will not start"
    return
  fi
  ok ".env found"

  local k
  for k in CLIENT_ID CLIENT_SECRET SPOTIFY_TARGET_DEVICE BOT_TOKEN CHAT_ID; do
    if [ -n "$(env_value "$k")" ]; then ok "$k is set"; else bad "missing $k"; fi
  done

  local provider
  provider="$(env_value LLM_PROVIDER)"
  provider="${provider:-local}"
  if [ "$provider" = "groq" ]; then
    if [ -n "$(env_value GROQ_API_KEY)" ]; then
      ok "LLM_PROVIDER=groq, GROQ_API_KEY is set"
    else
      bad "LLM_PROVIDER=groq but GROQ_API_KEY is empty"
    fi
  else
    ok "LLM_PROVIDER=$provider (Groq key not needed)"
    if [ -n "$(env_value LOCAL_LLM_URL)" ]; then
      ok "LOCAL_LLM_URL is set"
    else
      warn "LOCAL_LLM_URL is not set - defaulting to http://localhost:8002/..."
    fi
  fi

  if [ -f "$HOME/.spotify_token_cache.json" ]; then
    ok "Spotify token found"
  else
    warn "no ~/.spotify_token_cache.json - run python spotifyConnect.py --auth"
  fi
}

check_python() {
  section "Python dependencies"
  if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    bad "python not found ($PY)"
    return
  fi
  ok "interpreter: $PY"
  "$PY" -c 'import sys; print("  [info] python", sys.version.split()[0])'

  local m
  for m in requests dotenv numpy sounddevice soundfile ddgs telebot onnxruntime livekit.wakeword flask; do
    if "$PY" -c "import $m" >/dev/null 2>&1; then ok "$m"; else bad "$m"; fi
  done
  for m in faster_whisper torch; do
    if "$PY" -c "import $m" >/dev/null 2>&1; then ok "$m"; else bad "$m (needed by kaira-stt/kaira-tts)"; fi
  done
}

check_ports() {
  section "Ports"
  if ! command -v ss >/dev/null 2>&1 && ! command -v lsof >/dev/null 2>&1; then
    warn "no ss/lsof - cannot check ports"
    return
  fi
  local p unit
  for p in 8001 8003; do
    unit=$([ "$p" = 8001 ] && echo kaira-stt || echo kaira-tts)
    if command -v ss >/dev/null 2>&1 && ss -ltn 2>/dev/null | grep -qE "[:.]$p[[:space:]]"; then
      ok ":$p is listening ($unit)"
    elif command -v lsof >/dev/null 2>&1 && lsof -nP -iTCP:"$p" -sTCP:LISTEN >/dev/null 2>&1; then
      ok ":$p is listening ($unit)"
    else
      bad ":$p is not listening ($unit)"
    fi
  done
}

check_services() {
  section "systemd"
  if [ ${#CTL[@]} -eq 0 ]; then
    warn "kaira-* units not found (neither systemctl --user nor systemctl)"
    warn "run this from the user's session or check: systemctl --user list-units"
    return
  fi
  ok "context: ${CTL[*]}"

  local u state exec_line wd user dead arg
  for u in "${UNITS[@]}" "${OPTIONAL_UNITS[@]}"; do
    if ! has_unit "$u"; then
      warn "no unit $u"
      continue
    fi

    state=$("${CTL[@]}" is-active "$u" 2>/dev/null || true)
    if [ "$state" = "active" ]; then ok "$u active"; else bad "$u: ${state:-unknown}"; fi

    exec_line=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^ExecStart=' || true)
    if [ -n "$exec_line" ]; then
      exec_line="${exec_line#ExecStart=}"
      exec_line="${exec_line#-}"
      exec_line="${exec_line//%h/$HOME}"
      printf '         ExecStart: %s\n' "$(printf '%s' "$exec_line" | cut -c1-150)"
      for dead in debug.py t_info.py interruptible_speak.py justtest.py; do
        case "$exec_line" in
          *"$dead"*) bad "$u still references removed $dead" ;;
        esac
      done
      for arg in $exec_line; do
        case "$arg" in
          "~/"*) arg="$HOME/${arg#~/}" ;;
        esac
        case "$arg" in
          *.py)
            if [ ! -f "$arg" ] && [ ! -f "$ROOT/$arg" ]; then
              bad "$u: missing file $arg"
            fi
            ;;
        esac
      done
    fi

    wd=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^WorkingDirectory=' | cut -d= -f2-)
    wd="${wd#-}"
    wd="${wd//%h/$HOME}"
    if [ -n "$wd" ] && [ ! -d "$wd" ]; then
      bad "$u: WorkingDirectory does not exist: $wd"
    fi

    user=$("${CTL[@]}" cat "$u" 2>/dev/null | grep -m1 '^User=' | cut -d= -f2-)
    if [ "$user" = "root" ]; then
      warn "$u runs as root - audio and microphone may be unavailable"
    fi
  done
}

check_audio() {
  section "Audio"
  if command -v arecord >/dev/null 2>&1; then
    if arecord -l 2>/dev/null | grep -q '^card'; then
      ok "microphone detected (arecord -l)"
    else
      warn "arecord finds no microphones"
    fi
  else
    warn "no arecord (install alsa-utils)"
  fi

  if command -v aplay >/dev/null 2>&1; then
    if aplay -l 2>/dev/null | grep -q '^card'; then
      ok "audio output detected (aplay -l)"
    else
      warn "aplay finds no audio outputs"
    fi
  else
    warn "no aplay (install alsa-utils)"
  fi

  if command -v mpg123 >/dev/null 2>&1; then
    ok "mpg123 found"
  else
    bad "no mpg123 - sounds/*.mp3 will not play"
  fi

  if command -v pactl >/dev/null 2>&1; then
    if pactl info >/dev/null 2>&1; then
      ok "PulseAudio/PipeWire is reachable"
    else
      warn "pactl cannot connect (check the user session/XDG_RUNTIME_DIR)"
    fi
  fi

  if [ -n "${KERA_MIC:-}" ]; then
    ok "KERA_MIC=$KERA_MIC"
  else
    warn "KERA_MIC is not set in this shell - wakeword will use default"
  fi
}

check_timers_file() {
  section "Timers"
  if [ ! -f "$ROOT/.timers.json" ]; then
    ok ".timers.json does not exist yet - it will be created automatically"
    return
  fi
  if [ -z "$PY" ] || [ ! -x "$PY" ]; then
    warn "no python - cannot validate .timers.json"
    return
  fi
  if "$PY" -c "import json,sys; json.load(open(sys.argv[1]))" "$ROOT/.timers.json" >/dev/null 2>&1; then
    ok ".timers.json is valid"
  else
    bad ".timers.json is broken - timer_watcher will ignore it"
  fi
}

summary() {
  echo
  if [ "$fail" -eq 0 ]; then
    echo "Result: all checks passed"
  else
    echo "Result: problems found - see above"
  fi
}

restart_units() {
  if [ ${#CTL[@]} -eq 0 ]; then
    echo "kaira-* systemd units not found - nothing to restart"
    exit 1
  fi

  local list=("$@")
  if [ ${#list[@]} -eq 0 ]; then
    list=(kaira-stt kaira-tts tgbot kaira-timers kaira-wakeword)
  fi

  local u state
  for u in "${list[@]}"; do
    if ! has_unit "$u"; then
      warn "no unit $u"
      continue
    fi
    if "${CTL[@]}" restart "$u" 2>/dev/null; then
      ok "restart $u"
    else
      bad "failed to restart $u"
    fi
  done

  sleep 2
  section "State after restart"
  for u in "${list[@]}"; do
    has_unit "$u" || continue
    state=$("${CTL[@]}" is-active "$u" 2>/dev/null || true)
    if [ "$state" = "active" ]; then ok "$u active"; else bad "$u: ${state:-unknown}"; fi
  done
}

logs_cmd() {
  local unit="${1:-kaira-wakeword}"
  if [ ${#CTL[@]} -eq 0 ]; then
    echo "kaira-* systemd units not found"
    exit 1
  fi
  if ! has_unit "$unit"; then
    echo "no unit $unit"
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
    echo "Unknown command: $cmd"
    usage
    exit 2
    ;;
esac
