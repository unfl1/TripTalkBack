from app.core.config import ACCOMMODATION_FILE_PATH, TOURIST_FILE_PATH
from app.services.place_loader import load_places


def search_places_exact(query: str) -> list[dict]:
    """관광지 + 숙소를 통틀어, title이 검색어와 '정확히' 일치하는 장소만 반환한다.

    부분 일치/유사 검색은 하지 않는다 (앞뒤 공백만 정리하고 완전히 같은 문자열인지 비교).
    """

    query = query.strip()

    if not query:
        return []

    results: list[dict] = []

    for place in load_places(TOURIST_FILE_PATH):
        if place["title"] == query:
            results.append({**place, "place_type": "TOURIST"})

    for place in load_places(ACCOMMODATION_FILE_PATH):
        if place["title"] == query:
            results.append({**place, "place_type": "ACCOMMODATION"})

    return results