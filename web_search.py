from ddgs import DDGS


def web_search(query: str, max_results: int = 4) -> str:
    """Возвращает короткую сводку результатов поиска в виде текста для модели."""
    try:
        results = DDGS().text(
            query,
            region="ru-ru",
            safesearch="moderate",
            max_results=max_results,
        )
    except Exception as e:  # DDG нестабилен: лимиты, таймауты, смена вёрстки
        return f"Поиск не удался: {e}"

    if not results:
        return "Ничего не найдено."

    lines = []
    for i, r in enumerate(results, 1):
        title = (r.get("title") or "").strip()
        body = (r.get("body") or "").strip()
        if len(body) > 300:
            body = body[:300].rsplit(" ", 1)[0] + "…"
        lines.append(f"{i}. {title}: {body}")
    return "\n".join(lines)




if __name__ == "__main__":
    import sys

    print(web_search(" ".join(sys.argv[1:]) or "test"))