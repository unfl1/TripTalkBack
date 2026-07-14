import json
from pathlib import Path

from fastapi import APIRouter


router = APIRouter(
    prefix="/api/tourist-spots",
    tags=["tourist-spots"],
)


BASE_DIR = Path(__file__).resolve().parent.parent.parent
TOURIST_FILE_PATH = BASE_DIR / "data" / "서울_관광지.json"


@router.get("")
def get_tourist_spots():
    with TOURIST_FILE_PATH.open("r", encoding="utf-8") as file:
        data = json.load(file)

    result = []

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
                "contentid": contentid,
                "title": title,
                "addr1": addr1,
                "mapx": float(mapx),
                "mapy": float(mapy),
            }
        )

    return result