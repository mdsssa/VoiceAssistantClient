"""HTTP API + live preview for the 16x16 display.

Run:
    python -m display.server

Open:
    http://<mini-pc>:8090

Set WLED_HOST to also push frames to a WLED instance over DDP.
"""

from __future__ import annotations

import base64
import json
import os
import time

from flask import Flask, Response, jsonify, request, send_from_directory

from .ddp import DDPSender
from .renderer import Renderer, STATES


def _parse_color(value: str | None, default=(0, 200, 255)):
    if not value:
        return default
    value = value.strip().lstrip("#")
    if len(value) != 6:
        return default
    try:
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return default


def create_app() -> Flask:
    app = Flask(__name__, static_folder="static", static_url_path="/static")

    wled_host = os.environ.get("WLED_HOST", "").strip()
    wled_port = int(os.environ.get("WLED_PORT", "4048"))
    fps = int(os.environ.get("DISPLAY_FPS", "30"))
    ddp = DDPSender(wled_host, port=wled_port) if wled_host else None

    renderer = Renderer(ddp=ddp, fps=fps)
    renderer.start()
    app.config["RENDERER"] = renderer
    app.config["WLED_HOST"] = wled_host

    @app.get("/")
    def index():
        return send_from_directory(app.static_folder, "index.html")

    @app.get("/api/status")
    def status():
        return jsonify(renderer.status())

    @app.post("/api/state")
    def set_state():
        data = request.get_json(silent=True) or {}
        name = str(data.get("state", "")).lower()
        if name not in STATES:
            return jsonify({"ok": False, "error": f"unknown state: {name}"}), 400
        renderer.state.set_state(name)
        return jsonify({"ok": True, "state": name})

    @app.post("/api/level")
    def set_level():
        data = request.get_json(silent=True) or {}
        try:
            value = float(data.get("level", 0))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "level must be a number"}), 400
        renderer.state.set_level(value)
        return jsonify({"ok": True, "level": max(0.0, min(1.0, value))})

    @app.post("/api/text")
    def set_text():
        data = request.get_json(silent=True) or {}
        value = str(data.get("text", ""))
        renderer.state.set_text(value, _parse_color(data.get("color")))
        return jsonify({"ok": True})

    @app.post("/api/timer")
    def set_timer():
        data = request.get_json(silent=True) or {}
        try:
            seconds = int(data.get("seconds", 0))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "seconds must be an integer"}), 400
        renderer.state.set_timer(seconds)
        return jsonify({"ok": True, "seconds": max(0, seconds)})

    @app.post("/api/brightness")
    def set_brightness():
        data = request.get_json(silent=True) or {}
        try:
            value = int(data.get("value", 255))
        except (TypeError, ValueError):
            return jsonify({"ok": False, "error": "value must be an integer"}), 400
        renderer.state.set_brightness(value)
        return jsonify({"ok": True, "brightness": max(0, min(255, value))})

    @app.post("/api/test")
    def test_pattern():
        data = request.get_json(silent=True) or {}
        pattern = str(data.get("pattern", "")).strip().lower()
        renderer.state.set_pattern(pattern)
        return jsonify({"ok": True, "pattern": pattern})

    @app.post("/api/clear")
    def clear():
        renderer.state.reset()
        return jsonify({"ok": True})

    @app.get("/events")
    def events():
        def generate():
            while True:
                frame, meta = renderer.snapshot()
                payload = dict(meta)
                payload["frame"] = base64.b64encode(frame).decode("ascii")
                yield f"data: {json.dumps(payload, separators=(',', ':'))}\n\n"
                time.sleep(1 / 20)

        headers = {
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
        return Response(generate(), mimetype="text/event-stream", headers=headers)

    return app


app = create_app()


def main() -> None:
    host = os.environ.get("DISPLAY_BIND", "0.0.0.0")
    port = int(os.environ.get("DISPLAY_PORT", "8090"))
    wled = app.config.get("WLED_HOST") or ""
    shown_host = host if host not in ("0.0.0.0", "::") else "<mini-pc>"
    print(f"Kera display preview: http://{shown_host}:{port}")
    print(f"WLED DDP target: {wled or 'disabled (preview only)'}")
    app.run(host=host, port=port, threaded=True)


if __name__ == "__main__":
    main()
