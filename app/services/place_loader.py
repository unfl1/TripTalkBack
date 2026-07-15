import json
from pathlib import Path


def load_places(file_path: Path) -> list[dict]:
    """공공데이터 JSON 파일을 읽어 필수값이 있는 장소만 정제해서 반환한다.

    accommodation / tourist_spot / chat 라우터가 공통으로 사용하던
    '읽기 -> 필수값 필터링 -> 형변환' 로직을 한 곳으로 모은 것.
    """

    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    result: list[dict] = []

    for item in data["items"]:
        contentid = item.get("contentid")
        title = item.get("title")
        addr1 = item.get("addr1")
        mapx = item.get("mapx")
        mapy = item.get("mapy")

        # 필수값 없으면 제외
        if not contentid or not title or not mapx or not mapy:
            continue

        result.append(
            {
                "contentid": str(contentid),
                "title": title,
                "addr1": addr1 or "",
                "mapx": float(mapx),
                "mapy": float(mapy),
            }
        )

    return result
