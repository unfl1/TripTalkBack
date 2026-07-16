import re

from sqlmodel import Session, func, select

from app.core.config import ACCOMMODATION_FILE_PATH, TOURIST_FILE_PATH
from app.models.review import Review
from app.schemas.chat import ChatPlaceResult, ChatResponse
from app.services.place_loader import load_places


# 검색어로 의미 없는 일반 의존명사 (필터링 안 하면 거의 모든 장소가 매칭되어버림)
_GENERIC_NOUNS = {"것", "거", "곳", "데", "쪽", "편", "수", "때"}

# 형태소 분석기 없이 흔한 조사만 뒤에서 잘라내는 단순 규칙.
# (kiwipiepy 대신 사용 - 메모리 사용량 절감이 목적. 복잡한 문장에서는 정확도가 다소 떨어질 수 있음)
_JOSA_PATTERN = re.compile(
    r"(에서는|에서|에게|에는|으로는|으로|에|의|을|를|은|는|이|가|과|와|도)$"
)


# ---------------------------------------------------------------------------
# 키워드 사전
# ---------------------------------------------------------------------------
ACCOMMODATION_KEYWORDS = ["숙소", "호텔", "게스트하우스", "숙박", "묵을", "잘 곳", "잘곳", "펜션"]
TOURIST_KEYWORDS = ["관광지", "관광", "여행지", "가볼만한", "가볼 만한", "볼거리", "명소", "구경"]
REVIEW_KEYWORDS = ["리뷰", "평점", "후기", "별점", "평가"]

# "평점 높은/좋은 순" 정렬을 트리거하는 표현
POSITIVE_RATING_KEYWORDS = ["높은", "좋은", "베스트", "인기", "인기 많은", "잘하는", "핫한"]
# "평점 낮은/안 좋은 순" 정렬을 트리거하는 표현
NEGATIVE_RATING_KEYWORDS = ["낮은", "안 좋은", "안좋은", "별로인", "별로", "나쁜", "안 좋아", "안좋아"]

# 검색 토큰에서 제거할 불용어 (의도 판별용 키워드 + 조사성 표현)
STOPWORDS = set(
    ACCOMMODATION_KEYWORDS
    + TOURIST_KEYWORDS
    + REVIEW_KEYWORDS
    + POSITIVE_RATING_KEYWORDS
    + NEGATIVE_RATING_KEYWORDS
    + [
        "추천", "추천해줘", "해줘", "알려줘", "찾아줘", "찾아", "찾기",
        "검색", "검색해줘", "근처", "주변", "어디", "있어", "있나요",
    ]
)


def _tokenize(message: str) -> list[str]:
    """공백으로 나눈 뒤 흔한 조사만 뒤에서 잘라내 검색어 후보를 만든다.

    형태소 분석기(kiwipiepy) 없이 동작하도록 단순화한 버전.
    "강남에서" -> "강남", "경복궁은" -> "경복궁" 처럼 흔한 케이스는 잡아내지만,
    불규칙 활용이나 복잡한 문장 구조는 완벽히 처리하지 못할 수 있다.
    """

    raw_tokens = re.split(r"\s+", message.strip())

    tokens = []
    for tok in raw_tokens:
        stripped = _JOSA_PATTERN.sub("", tok)
        if stripped and stripped not in STOPWORDS and stripped not in _GENERIC_NOUNS:
            tokens.append(stripped)

    return tokens


def _load_rating_stats(session: Session) -> dict[str, tuple[float | None, int]]:
    """place_id별 평균 평점/리뷰 개수를 한 번의 쿼리로 미리 다 가져온다.

    장소마다 DB 쿼리를 따로 날리면(N+1) 정렬 대상 후보가 많아질수록 느려지기 때문에,
    GROUP BY로 한 번에 집계한 뒤 메모리에서 딕셔너리로 조회하는 방식을 쓴다.
    """

    rows = session.exec(
        select(Review.place_id, func.avg(Review.rating), func.count(Review.id)).group_by(
            Review.place_id
        )
    ).all()

    return {
        place_id: (round(avg_rating, 1) if avg_rating is not None else None, review_count)
        for place_id, avg_rating, review_count in rows
    }


def _to_result(place: dict, rating_stats: dict[str, tuple[float | None, int]]) -> ChatPlaceResult:
    avg_rating, review_count = rating_stats.get(place["contentid"], (None, 0))

    return ChatPlaceResult(
        place_type=place["place_type"],
        contentid=place["contentid"],
        title=place["title"],
        addr1=place["addr1"],
        mapx=place["mapx"],
        mapy=place["mapy"],
        avg_rating=avg_rating,
        review_count=review_count,
    )


def _load_candidates(wants_tourist: bool, wants_accommodation: bool) -> list[dict]:
    candidates: list[dict] = []

    if wants_tourist:
        candidates += [
            {**place, "place_type": "TOURIST"}
            for place in load_places(TOURIST_FILE_PATH)
        ]

    if wants_accommodation:
        candidates += [
            {**place, "place_type": "ACCOMMODATION"}
            for place in load_places(ACCOMMODATION_FILE_PATH)
        ]

    return candidates


def build_chat_response(session: Session, message: str) -> ChatResponse:
    message = message.strip()

    if not message:
        return ChatResponse(
            reply="궁금하신 내용을 입력해 주세요. 예) '강남 숙소 추천', '경복궁 리뷰 어때?'",
        )

    # 1. 의도 판별: 관광지 / 숙소 / 둘 다 + 평점 정렬 방향
    wants_accommodation = any(keyword in message for keyword in ACCOMMODATION_KEYWORDS)
    wants_tourist = any(keyword in message for keyword in TOURIST_KEYWORDS)
    wants_review = any(keyword in message for keyword in REVIEW_KEYWORDS)
    wants_low_rating = any(keyword in message for keyword in NEGATIVE_RATING_KEYWORDS)
    wants_high_rating = any(keyword in message for keyword in POSITIVE_RATING_KEYWORDS)
    wants_rating_sort = wants_review or wants_low_rating or wants_high_rating

    # 둘 다 명시하지 않았다면 둘 다 검색 대상으로 삼는다.
    if not wants_accommodation and not wants_tourist:
        wants_accommodation = True
        wants_tourist = True

    candidates = _load_candidates(wants_tourist, wants_accommodation)

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

    # 3. 평점 붙이기 -> (필요하면) 정렬 -> 그 다음에 상위 10개로 자르기.
    rating_stats = _load_rating_stats(session)
    scored = [_to_result(place, rating_stats) for place in matched]

    if wants_rating_sort and not fallback_used:
        if wants_low_rating:
            scored.sort(key=lambda r: (r.avg_rating is None, r.avg_rating if r.avg_rating is not None else 0))
        else:
            scored.sort(key=lambda r: (r.avg_rating is None, -(r.avg_rating or 0)))

    results = scored[:10]

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
        if wants_rating_sort:
            order = "낮은" if wants_low_rating else "높은"
            reply = f"'{message}'와 관련된 {category} {len(results)}곳을 평점 {order} 순으로 찾았어요."
        else:
            reply = f"'{message}'와 관련된 {category} {len(results)}곳을 찾았어요."

    return ChatResponse(reply=reply, results=results)