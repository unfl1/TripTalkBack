import json
import re
from pathlib import Path

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlmodel import Session, func, select

from app.database import get_session
from app.models.review import Review


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


BASE_DIR = Path(__file__).resolve().parent.parent.parent
TOURIST_FILE_PATH = BASE_DIR / "data" / "서울_관광지.json"
ACCOMMODATION_FILE_PATH = BASE_DIR / "data" / "서울_숙박.json"


# ---------------------------------------------------------------------------
# 요청/응답 스키마
# ---------------------------------------------------------------------------
class ChatRequest(BaseModel):
    message: str


class ChatPlaceResult(BaseModel):
    place_type: str  # "TOURIST" | "ACCOMMODATION"
    contentid: str
    title: str
    addr1: str
    mapx: float
    mapy: float
    avg_rating: float | None = None
    review_count: int = 0


class ChatResponse(BaseModel):
    reply: str
    results: list[ChatPlaceResult] = []


# ---------------------------------------------------------------------------
# 키워드 사전
# ---------------------------------------------------------------------------
ACCOMMODATION_KEYWORDS = ["숙소", "호텔", "게스트하우스", "숙박", "묵을", "잘 곳", "잘곳", "펜션"]
TOURIST_KEYWORDS = ["관광지", "관광", "여행지", "가볼만한", "가볼 만한", "볼거리", "명소", "구경"]
REVIEW_KEYWORDS = ["리뷰", "평점", "후기", "별점", "평가"]

# 검색 토큰에서 제거할 불용어 (의도 판별용 키워드 + 조사성 표현)
STOPWORDS = set(
    ACCOMMODATION_KEYWORDS
    + TOURIST_KEYWORDS
    + REVIEW_KEYWORDS
    + ["추천", "추천해줘", "해줘", "알려줘", "찾아줘", "근처", "어디", "있어", "있나요", "좋은"]
)


def _load_places(file_path: Path, place_type: str) -> list[dict]:
    with file_path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    places = []

    for item in data["items"]:
        contentid = item.get("contentid")
        title = item.get("title")
        addr1 = item.get("addr1")
        mapx = item.get("mapx")
        mapy = item.get("mapy")

        # 필수값 없으면 제외 (다른 라우터와 동일한 규칙)
        if not contentid or not title or not mapx or not mapy:
            continue

        places.append(
            {
                "place_type": place_type,
                "contentid": str(contentid),
                "title": title,
                "addr1": addr1 or "",
                "mapx": float(mapx),
                "mapy": float(mapy),
            }
        )

    return places


def _tokenize(message: str) -> list[str]:
    raw_tokens = re.split(r"\s+", message.strip())
    tokens = [t for t in raw_tokens if t and t not in STOPWORDS]
    return tokens


def _attach_review_stats(session: Session, place: dict) -> ChatPlaceResult:
    avg_rating, review_count = session.exec(
        select(func.avg(Review.rating), func.count(Review.id)).where(
            Review.place_id == place["contentid"]
        )
    ).one()

    return ChatPlaceResult(
        place_type=place["place_type"],
        contentid=place["contentid"],
        title=place["title"],
        addr1=place["addr1"],
        mapx=place["mapx"],
        mapy=place["mapy"],
        avg_rating=round(avg_rating, 1) if avg_rating is not None else None,
        review_count=review_count or 0,
    )


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
):
    message = request.message.strip()

    if not message:
        return ChatResponse(
            reply="궁금하신 내용을 입력해 주세요. 예) '강남 숙소 추천', '경복궁 리뷰 어때?'",
        )

    # 1. 의도 판별: 관광지 / 숙소 / 둘 다
    wants_accommodation = any(keyword in message for keyword in ACCOMMODATION_KEYWORDS)
    wants_tourist = any(keyword in message for keyword in TOURIST_KEYWORDS)
    wants_review = any(keyword in message for keyword in REVIEW_KEYWORDS)

    # 둘 다 명시하지 않았다면 둘 다 검색 대상으로 삼는다.
    if not wants_accommodation and not wants_tourist:
        wants_accommodation = True
        wants_tourist = True

    candidates: list[dict] = []

    if wants_tourist:
        candidates += _load_places(TOURIST_FILE_PATH, "TOURIST")

    if wants_accommodation:
        candidates += _load_places(ACCOMMODATION_FILE_PATH, "ACCOMMODATION")

    # 2. 지역명/장소명 키워드로 필터링 (제목 또는 주소에 토큰이 포함되면 매칭)
    tokens = _tokenize(message)

    matched = [
        place
        for place in candidates
        if not tokens
        or any(token in f"{place['title']} {place['addr1']}" for token in tokens)
    ]

    # 매칭된 게 없으면 상위 일부라도 보여준다 (완전히 빈 응답 방지).
    fallback_used = False
    if not matched:
        matched = candidates[:5]
        fallback_used = True

    results = [_attach_review_stats(session, place) for place in matched[:10]]

    # 3. 평점/리뷰를 물어본 경우, 리뷰 없는 곳은 뒤로 정렬
    if wants_review:
        results.sort(
            key=lambda r: (r.avg_rating is None, -(r.avg_rating or 0)),
        )

    # 4. 응답 문구
    if not results:
        reply = f"'{message}'에 대한 검색 결과를 찾지 못했어요. 다른 키워드로 다시 물어봐 주세요."
    elif fallback_used:
        reply = (
            f"'{message}'와 정확히 일치하는 곳은 찾지 못했지만, "
            f"참고할 만한 장소 {len(results)}곳을 보여드릴게요."
        )
    else:
        category = (
            "숙소" if wants_accommodation and not wants_tourist
            else "관광지" if wants_tourist and not wants_accommodation
            else "장소"
        )
        reply = f"'{message}'와 관련된 {category} {len(results)}곳을 찾았어요."

    return ChatResponse(reply=reply, results=results)