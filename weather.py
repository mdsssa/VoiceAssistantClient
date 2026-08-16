import requests
from tools import WEATHER_CODE_DESCRIPTIONS


def describe_weather_code(code):
    return WEATHER_CODE_DESCRIPTIONS.get(code, "неизвестные погодные условия")


def get_weather(city):
    try:
        geo = requests.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "ru"}
        ).json()
        if not geo.get("results"):
            return f"Не нашла город {city}"
        loc = geo["results"][0]
        lat, lon = loc["latitude"], loc["longitude"]
        found_name = loc.get("name", city)

        # current_weather не даёт ни ощущаемой температуры, ни кода погоды
        # в удобном виде без него самого — берём через "current" с явным
        # списком полей.
        forecast = requests.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,apparent_temperature,weather_code",
            }
        ).json()["current"]

        temp = round(forecast["temperature_2m"])
        feels_like = round(forecast["apparent_temperature"])
        condition = describe_weather_code(forecast["weather_code"])

        result = (
            f"В городе {found_name} сейчас {condition}, {temp} градусов, "
            f"а по ощущениям {feels_like} градусов"
        )
        print(result)
        return result
    except Exception as e:
        print(f"[get_weather error] {e}")
        return f"Не получилось узнать погоду: {e}"