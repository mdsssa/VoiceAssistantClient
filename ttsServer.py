# tts_server.py
from flask import Flask, request, send_file
import torch
import io
import soundfile as sf

app = Flask(__name__)

device = torch.device('cpu')
torch.set_num_threads(4)  # подстрой под реальное число ядер HeroBox

model, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='ru',
    speaker='v4_ru'
)
model.to(device)

SPEAKER = 'xenia'  # варианты: aidar, baya, kseniya, xenia, eugene, random
SAMPLE_RATE = 48000

@app.route("/synthesize", methods=["POST"])
def synthesize():
    text = request.json.get("text", "")

    audio = model.apply_tts(
        text=text,
        speaker=SPEAKER,
        sample_rate=SAMPLE_RATE
    )

    buf = io.BytesIO()
    sf.write(buf, audio.numpy(), SAMPLE_RATE, format='WAV')
    buf.seek(0)

    return send_file(buf, mimetype="audio/wav")

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)
