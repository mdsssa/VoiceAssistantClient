"""
stt_server.py

Локальный STT-сервер на faster-whisper — совместим с существующим
клиентским кодом (main.py), который шлёт multipart file на /transcribe
и ждёт {"text": "..."}.

Запуск:
    python3 stt_server.py
"""

from flask import Flask, request, jsonify
from faster_whisper import WhisperModel
import tempfile
import os

app = Flask(__name__)

# "small" — разумный баланс скорости/качества для N-series CPU.
# Если будет слишком медленно — попробуй "base".
model = WhisperModel("small", device="cpu", compute_type="int8")


@app.route("/transcribe", methods=["POST"])
def transcribe():
    f = request.files["file"]
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
        f.save(tmp.name)
        path = tmp.name

    try:
        segments, _ = model.transcribe(path, language="ru")
        text = " ".join(s.text for s in segments).strip()
    finally:
        os.remove(path)

    return jsonify({"text": text})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8001)