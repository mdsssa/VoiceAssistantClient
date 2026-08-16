tools = [
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Получить текущую погоду в указанном городе",
            "parameters": {
                "type": "object",
                "properties": {
                    "city": {"type": "string", "description": "Название города, например Москва, Париж, Токио"}
                },
                "required": ["city"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "play_music",
            "description": "Включить музыку в Spotify по названию трека и/или исполнителя",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string",
                              "description": "Название трека и/или исполнителя, например 'Skryptonite Мразь'"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "pause_music",
            "description": "Поставить текущий трек на паузу",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "resume_music",
            "description": "Продолжить воспроизведение с того места, где остановились",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "skip_track",
            "description": "Переключить на следующий трек",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "previous_music_track",
            "description": "Вернуться к предыдущему треку",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "change_volume",
            "description": "Изменить громкость воспроизведения. Если пользователь просит 'потише'/'погромче' без конкретной цифры, подбери разумное значение сама (например, ±15% от 50)",
            "parameters": {
                "type": "object",
                "properties": {
                    "level": {"type": "integer", "description": "Громкость в процентах, от 0 до 100"}
                },
                "required": ["level"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "seek_track",
            "description": "Перемотать текущий трек на указанную позицию в секундах от начала",
            "parameters": {
                "type": "object",
                "properties": {
                    "seconds": {"type": "integer", "description": "Позиция в треке в секундах, куда перемотать"}
                },
                "required": ["seconds"]
            }
        }
    }
]

WEATHER_CODE_DESCRIPTIONS = {
    0: "ясно",
    1: "преимущественно ясно",
    2: "переменная облачность",
    3: "пасмурно",
    45: "туман",
    48: "изморозь",
    51: "лёгкая морось",
    53: "морось",
    55: "сильная морось",
    56: "лёгкая ледяная морось",
    57: "сильная ледяная морось",
    61: "небольшой дождь",
    63: "дождь",
    65: "сильный дождь",
    66: "лёгкий ледяной дождь",
    67: "сильный ледяной дождь",
    71: "небольшой снег",
    73: "снег",
    75: "сильный снег",
    77: "снежная крупа",
    80: "небольшой ливень",
    81: "ливень",
    82: "сильный ливень",
    85: "небольшой снегопад",
    86: "сильный снегопад",
    95: "гроза",
    96: "гроза с небольшим градом",
    99: "гроза с сильным градом",
}