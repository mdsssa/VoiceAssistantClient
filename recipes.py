import os
import requests
from ddgs import DDGS
from t_info import bot_token , chat_id

TG_BOT_TOKEN = bot_token
TG_CHAT_ID = chat_id


def search_and_send_recipe(query: str) -> str:
    search_query = f"{query} пошаговый рецепт с фото"

    try:
        with DDGS() as ddgs:
            results = list(ddgs.text(search_query, max_results=15))

            if not results:
                return "Я ничего не нашла. Попробуй сформулировать запрос иначе."

            best_res = None

            bad_domains = [
                'pinterest', 'instagram', 'youtube', 'tiktok', 'facebook',
                'vk.com', 'ok.ru', 'twitter', 'x.com', 'reddit' , 'vk.ru'
            ]

            # Слова-маркеры мусорных страниц
            bad_title_words = ['подборка', 'топ-', '10 ', '20 ', '30 ', 'идей', 'каталог', 'все рецепты', 'блюда из',
                               'главная']
            bad_url_words = ['catalog', 'podborka', 'collection', 'tags', 'category', 'recipe-book']

            # Извлекаем ключевые слова из запроса для проверки релевантности
            # Убираем стоп-слова
            stop_words = ['рецепт', 'рецепты', 'пошаговый', 'с', 'фото', 'приготовить', 'как']
            query_words = [word.lower() for word in query.split() if word.lower() not in stop_words]

            for res in results:
                url = res.get('href', '').lower()
                title = res.get('title', '').lower()
                body = res.get('body', '').lower()

                # 1. Блокируем соцсети и мусорные домены
                if any(domain in url for domain in bad_domains):
                    continue

                # 2. Отсекаем мусор по заголовку
                if any(bad in title for bad in bad_title_words):
                    continue

                # 3. Отсекаем мусор по URL
                if any(bad in url for bad in bad_url_words):
                    continue

                # 4. ПРОВЕРКА РЕЛЕВАНТНОСТИ: хотя бы одно ключевое слово из запроса должно быть в title или body
                # Это чтобы не присылало болоньезе на запрос "паста с креветками"
                is_relevant = any(word in title or word in body for word in query_words)
                if not is_relevant:
                    continue

                # 5. Проверяем, что это страница рецепта
                if 'recept' in url or 'recipe' in url or 'retsept' in url:
                    best_res = res
                    break

            if not best_res:
                best_res = results[0]

            tg_message = (
                f"{best_res['title']}\n\n"
                f"Описание:\n{best_res['body']}\n\n"
                f"[Открыть полный рецепт с шагами]({best_res['href']})"
            )

        # Отправка в Telegram
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": tg_message,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False
        }
        response = requests.post(url, json=payload)
        response.raise_for_status()

        return "Я нашла рецепт и отправила его тебе в Телеграм."

    except Exception as e:
        return f"Ошибка при поиске или отправке: {e}"
