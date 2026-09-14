"""
tts_server.py

Локальный TTS-сервер на Silero с поддержкой смешанного русско-английского
текста — держит две модели (ru + en), разбивает реплику на куски по
языку (кириллица/латиница), озвучивает каждый кусок своей моделью и
склеивает результат в один WAV.

Запуск:
    python3 tts_server.py
"""

from flask import Flask, request, send_file
import torch
import numpy as np
import io
import re
import soundfile as sf

app = Flask(__name__)

device = torch.device('cpu')
torch.set_num_threads(4)  # подстрой под реальное число ядер HeroBox

print("Загружаю русскую модель Silero...")
model_ru, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='ru',
    speaker='v4_ru'
)
model_ru.to(device)

print("Загружаю английскую модель Silero...")
model_en, _ = torch.hub.load(
    repo_or_dir='snakers4/silero-models',
    model='silero_tts',
    language='en',
    speaker='v3_en'
)
model_en.to(device)

SPEAKER_RU = 'baya'   # варианты: aidar, baya, kseniya, xenia, eugene, random
SPEAKER_EN = 'en_0'    # варианты: en_0..en_117, random
SAMPLE_RATE = 48000

# Пауза между разноязычными кусками, чтобы не склеивались впритык
PAUSE_SAMPLES = int(0.15 * SAMPLE_RATE)


def split_by_language(text):
    """Разбивает текст на последовательные куски: кириллица+цифры+
    пунктуация в одной группе, латиница — в другой. Цифры и пунктуация
    присоединяются к соседнему языковому куску, чтобы не плодить
    микро-фрагменты (например 'Deftones' отдельно от '2024')."""
    pattern = re.compile(r'[A-Za-z]+(?:[\'\-][A-Za-z]+)*')
    chunks = []
    last_end = 0

    for match in pattern.finditer(text):
        start, end = match.span()
        if start > last_end:
            ru_part = text[last_end:start]
            if ru_part.strip():
                chunks.append(('ru', ru_part))
        chunks.append(('en', match.group()))
        last_end = end

    if last_end < len(text):
        ru_part = text[last_end:]
        if ru_part.strip():
            chunks.append(('ru', ru_part))

    return chunks if chunks else [('ru', text)]


def synthesize_mixed(text):
    """Озвучивает текст, переключаясь между ru/en моделями по кускам,
    возвращает единый numpy-массив с аудио."""
    chunks = split_by_language(text)
    audio_parts = []

    for lang, part in chunks:
        part = part.strip()
        if not part:
            continue
        try:
            if lang == 'en':
                audio = model_en.apply_tts(text=part, speaker=SPEAKER_EN, sample_rate=SAMPLE_RATE)
            else:
                audio = model_ru.apply_tts(text=part, speaker=SPEAKER_RU, sample_rate=SAMPLE_RATE)
            audio_parts.append(audio.numpy())
            audio_parts.append(np.zeros(PAUSE_SAMPLES, dtype=np.float32))
        except Exception as e:
            print(f"[synthesize_mixed] Пропустила кусок '{part}' ({lang}): {e}")

    if not audio_parts:
        return np.zeros(int(0.5 * SAMPLE_RATE), dtype=np.float32)

    return np.concatenate(audio_parts)


@app.route("/synthesize", methods=["POST"])
def synthesize():
    text = request.json.get("text", "")

    audio = synthesize_mixed(text)

    buf = io.BytesIO()
    sf.write(buf, audio, SAMPLE_RATE, format='WAV')
    buf.seek(0)

    return send_file(buf, mimetype="audio/wav")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8003)