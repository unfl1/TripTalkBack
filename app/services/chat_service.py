from kiwipiepy import Kiwi
from sqlmodel import Session, func, select

from app.core.config import ACCOMMODATION_FILE_PATH, TOURIST_FILE_PATH
from app.models.review import Review
from app.schemas.chat import ChatPlaceResult, ChatResponse
from app.services.place_loader import load_places


# 형태소 분석기는 초기화 비용이 있어 모듈 로드 시 한 번만 생성해서 재사용한다.
# (LLM/임베딩 모델과 달리 순수 규칙 기반 분석기라 매 요청마다 돌려도 서버 부담이 크지 않다)
_kiwi = Kiwi()

# 검색어로 의미 없는 일반 의존명사 (필터링 안 하면 거의 모든 장소가 매칭되어버림)
_GENERIC_NOUNS = {"것", "거", "곳", "데", "쪽", "편", "수", "때"}


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


def _tokenize(message: str) -> list[str]:
    """형태소 분석으로 명사만 뽑아 검색어로 사용한다.

    공백 기준 분리 대신 형태소 분석을 쓰는 이유:
    - "강남에서" 같이 조사가 붙은 표현도 "강남"(명사) + "에서"(조사)로 분리되어
      실제 데이터(주소 "강남구" 등)와 정상적으로 매칭된다.
    - "안녕", "높은"처럼 명사가 아닌 감탄사/형용사는 애초에 검색어로 뽑히지 않아
      의도치 않은 매칭(예: "안녕" -> "안녕인사동")이 줄어든다.
    """

    nouns = [
        token.form
        for token in _kiwi.tokenize(message)
        if token.tag in ("NNG", "NNP")
    ]

    return [n for n in nouns if n not in STOPWORDS and n not in _GENERIC_NOUNS]


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

    # 1. 의도 판별: 관광지 / 숙소 / 둘 다
    wants_accommodation = any(keyword in message for keyword in ACCOMMODATION_KEYWORDS)
    wants_tourist = any(keyword in message for keyword in TOURIST_KEYWORDS)
    wants_review = any(keyword in message for keyword in REVIEW_KEYWORDS)

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

    results = [_attach_review_stats(session, place) for place in matched[:10]]

    # 3. 평점/리뷰를 물어본 경우, 리뷰 없는 곳은 뒤로 정렬
    if wants_review:
        results.sort(key=lambda r: (r.avg_rating is None, -(r.avg_rating or 0)))

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
