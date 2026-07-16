import random
import re

from sqlmodel import Session, func, select

from app.core.config import ACCOMMODATION_FILE_PATH, TOURIST_FILE_PATH
from app.models.review import Review
from app.schemas.chat import ChatPlaceResult, ChatResponse
from app.services.place_loader import load_places


# 검색어로 의미 없는 일반 의존명사 (필터링 안 하면 거의 모든 장소가 매칭되어버림)
_GENERIC_NOUNS = {"것", "거", "곳", "데", "쪽", "편", "수", "때"}

# 흔한 조사만 뒤에서 잘라내는 단순 규칙 (형태소 분석기 없이 동작).
_JOSA_PATTERN = re.compile(
    r"(에서는|에서|에게|에는|으로는|으로|에|의|을|를|은|는|이|가|과|와|도)$"
)

_HANGUL_PATTERN = re.compile(r"[\uac00-\ud7a3]")


def _is_korean(message: str) -> bool:
    """메시지에 한글이 하나라도 있으면 한국어로, 없으면 영어로 간주한다."""
    return bool(_HANGUL_PATTERN.search(message))


# ---------------------------------------------------------------------------
# 키워드 사전 (한글 + 영어)
# ---------------------------------------------------------------------------
ACCOMMODATION_KEYWORDS_KR = ["숙소", "호텔", "게스트하우스", "숙박", "묵을", "잘 곳", "잘곳", "펜션"]
ACCOMMODATION_KEYWORDS_EN = [
    "hotel", "hotels", "accommodation", "accommodations", "guesthouse",
    "guest house", "stay", "lodging", "place to stay", "room to stay", "hostel",
]
ACCOMMODATION_KEYWORDS = ACCOMMODATION_KEYWORDS_KR + ACCOMMODATION_KEYWORDS_EN

TOURIST_KEYWORDS_KR = ["관광지", "관광", "여행지", "가볼만한", "가볼 만한", "볼거리", "명소", "구경"]
TOURIST_KEYWORDS_EN = [
    "tourist spot", "tourist spots", "tourist", "attraction", "attractions",
    "sightseeing", "places to visit", "things to do", "landmark", "landmarks",
    "spot to visit",
]
TOURIST_KEYWORDS = TOURIST_KEYWORDS_KR + TOURIST_KEYWORDS_EN

REVIEW_KEYWORDS_KR = ["리뷰", "평점", "후기", "별점", "평가"]
REVIEW_KEYWORDS_EN = ["review", "reviews", "rating", "ratings", "rated", "feedback"]
REVIEW_KEYWORDS = REVIEW_KEYWORDS_KR + REVIEW_KEYWORDS_EN

POSITIVE_RATING_KEYWORDS_KR = ["높은", "좋은", "베스트", "인기", "인기 많은", "잘하는", "핫한"]
POSITIVE_RATING_KEYWORDS_EN = ["best", "top", "good", "great", "popular", "highly rated", "high rated"]
POSITIVE_RATING_KEYWORDS = POSITIVE_RATING_KEYWORDS_KR + POSITIVE_RATING_KEYWORDS_EN

NEGATIVE_RATING_KEYWORDS_KR = ["낮은", "안 좋은", "안좋은", "별로인", "별로", "나쁜", "안 좋아", "안좋아"]
NEGATIVE_RATING_KEYWORDS_EN = ["worst", "bad", "low rated", "low rating", "poor"]
NEGATIVE_RATING_KEYWORDS = NEGATIVE_RATING_KEYWORDS_KR + NEGATIVE_RATING_KEYWORDS_EN

# 검색 의도와 무관하게 문장에서 지워도 되는 표현 (동사/조동사류)
_GENERIC_PHRASES_KR = [
    "추천해줘", "추천", "해줘", "알려줘", "찾아줘", "찾아", "찾기",
    "검색해줘", "검색", "근처", "주변", "어디", "있어", "있나요",
]
_GENERIC_PHRASES_EN = [
    "recommend", "suggest", "looking for", "find", "search", "near", "nearby",
    "where", "please", "can you", "could you", "i want", "show me", "tell me",
    "in", "at", "the", "a", "for", "of", "me", "is", "are", "there",
    "can", "i", "you", "do", "does", "to", "on", "with", "any",
]

STOPWORDS = set(
    ACCOMMODATION_KEYWORDS
    + TOURIST_KEYWORDS
    + REVIEW_KEYWORDS
    + POSITIVE_RATING_KEYWORDS
    + NEGATIVE_RATING_KEYWORDS
    + _GENERIC_PHRASES_KR
    + _GENERIC_PHRASES_EN
)

# ---------------------------------------------------------------------------
# 스몰토크 (인사말 / 도움말)
# ---------------------------------------------------------------------------
_GREETING_PATTERNS_KR = ["안녕", "하이", "헬로"]
_GREETING_PATTERNS_EN = ["hello", "hi", "hey"]

_HELP_PATTERNS_KR = ["뭐 할 수 있어", "뭘 할 수 있어", "도움말", "사용법", "어떻게 써", "무엇을 할 수"]
_HELP_PATTERNS_EN = ["what can you do", "help", "how does this work", "how to use", "how do i use"]

_GREETING_REPLIES_KR = [
    "안녕하세요! 서울 여행 계획을 도와드릴게요 🙂",
    "반가워요! 관광지나 숙소 추천이 필요하시면 말씀해 주세요.",
]
_GREETING_REPLIES_EN = [
    "Hello! I can help you plan your trip to Seoul 🙂",
    "Hi there! Ask me about tourist spots or places to stay.",
]

_HELP_REPLY_KR = (
    "저는 이런 걸 도와드릴 수 있어요:\n"
    "1) 관광지/숙소 추천 (예: '강남 숙소 추천해줘', '경복궁 근처 관광지')\n"
    "2) 평점 기준 정렬 (예: '평점 높은 숙소 알려줘', '후기 안 좋은 곳 빼고')\n"
    "3) 특정 장소 리뷰 확인 (예: '경복궁 리뷰 어때?')\n"
    "궁금한 걸 자유롭게 물어보세요!"
)
_HELP_REPLY_EN = (
    "Here's what I can help with:\n"
    "1) Recommending tourist spots or accommodations "
    "(e.g. 'recommend hotels in Gangnam', 'attractions near Gyeongbokgung')\n"
    "2) Sorting by rating (e.g. 'best rated hotels', 'top attractions')\n"
    "3) Checking reviews for a specific place (e.g. 'reviews for Gyeongbokgung')\n"
    "Feel free to ask me anything!"
)


def _match_any(message: str, patterns: list[str]) -> bool:
    lowered = message.lower()
    return any(p.lower() in lowered for p in patterns)


def _has_business_intent(message: str) -> bool:
    """관광지/숙소/리뷰/평점 관련 키워드가 하나라도 있으면 검색 의도가 있다고 판단."""
    return _match_any(
        message,
        ACCOMMODATION_KEYWORDS + TOURIST_KEYWORDS + REVIEW_KEYWORDS
        + POSITIVE_RATING_KEYWORDS + NEGATIVE_RATING_KEYWORDS,
    )


def _smalltalk_reply(message: str, is_korean: bool) -> str | None:
    """인사말/도움말이면 바로 답할 문구를 반환하고, 아니면 None을 반환한다."""

    if _has_business_intent(message):
        return None

    if _match_any(message, _HELP_PATTERNS_KR + _HELP_PATTERNS_EN):
        return _HELP_REPLY_KR if is_korean else _HELP_REPLY_EN

    if _match_any(message, _GREETING_PATTERNS_KR + _GREETING_PATTERNS_EN):
        return random.choice(_GREETING_REPLIES_KR if is_korean else _GREETING_REPLIES_EN)

    return None


# ---------------------------------------------------------------------------
# 지역/장소명 추출
# ---------------------------------------------------------------------------
def _strip_known_phrases_kr(text: str, phrases: list[str]) -> str:
    """한글 의도 표현을 문장에서 지운다 (경계 없이 그냥 substring 제거).

    한글은 "강남숙소"처럼 띄어쓰기 없이 붙는 경우가 흔해서, 단어 경계를
    따지지 않고 문자열 그대로 지워야 "강남"만 깔끔하게 남는다.
    긴 구문부터 먼저 지워야 "가볼 만한"이 "가볼"+"만한"으로 어중간하게
    잘리는 일을 막을 수 있다.
    """

    for phrase in sorted(phrases, key=len, reverse=True):
        text = text.replace(phrase, " ")

    return text


def _strip_known_phrases_en(text: str, phrases: list[str]) -> str:
    """영어 의도 표현을 문장에서 지운다 (단어 경계 기준으로만 제거).

    "at", "a", "in" 같은 짧은 단어를 경계 없이 지우면 "rated"의 "at"처럼
    단어 중간이 잘려나가므로, 반드시 완전한 단어 단위로만 매칭한다.
    """

    for phrase in sorted(phrases, key=len, reverse=True):
        pattern = r"\b" + re.escape(phrase) + r"\b"
        text = re.sub(pattern, " ", text, flags=re.IGNORECASE)

    return text


# ---------------------------------------------------------------------------
# 지역명 로마자 표기 매핑 (영어로 물어봐도 실제 한글 데이터와 매칭되도록)
# ---------------------------------------------------------------------------
_DISTRICT_ROMANIZATION = {
    # 서울 25개 구
    "gangnam": "강남", "gangdong": "강동", "gangbuk": "강북", "gangseo": "강서",
    "gwanak": "관악", "gwangjin": "광진", "guro": "구로", "geumcheon": "금천",
    "nowon": "노원", "dobong": "도봉", "dongdaemun": "동대문", "dongjak": "동작",
    "mapo": "마포", "seodaemun": "서대문", "seocho": "서초", "seongdong": "성동",
    "seongbuk": "성북", "songpa": "송파", "yangcheon": "양천", "yeongdeungpo": "영등포",
    "yongsan": "용산", "eunpyeong": "은평", "jongno": "종로", "junggu": "중구",
    "jungnang": "중랑",
    # 자주 찾는 동네/명소 이름
    "itaewon": "이태원", "hongdae": "홍대", "hongik": "홍대", "myeongdong": "명동",
    "insadong": "인사동", "apgujeong": "압구정", "yeouido": "여의도",
    "gyeongbokgung": "경복궁", "sinchon": "신촌", "jamsil": "잠실",
    "konkuk": "건대", "seongsu": "성수", "seoul": "서울",
}


def _romanize_lookup(token: str) -> str | None:
    """영어 로마자 지역명 토큰을 대응하는 한글 지역명으로 바꿔준다.

    데이터(addr1, title)가 전부 한글이라, "gangnam" 같은 영어 토큰은 그대로는
    절대 매칭될 수 없다. 흔한 서울 지역명 정도는 매핑 테이블로 다리를 놓는다.
    """
    return _DISTRICT_ROMANIZATION.get(token.lower())


def _tokenize(message: str) -> list[str]:
    """의도 표현을 제거하고 남는 부분에서 지역/장소명 후보를 뽑는다.

    형태소 분석기 없이 동작하도록 단순화한 버전이라 완벽하지 않지만,
    "강남에서", "강남 숙소", "강남숙소"(붙여쓰기) 처럼 흔한 케이스들을 처리한다.
    """

    remainder = _strip_known_phrases_kr(
        message,
        ACCOMMODATION_KEYWORDS_KR + TOURIST_KEYWORDS_KR + REVIEW_KEYWORDS_KR
        + POSITIVE_RATING_KEYWORDS_KR + NEGATIVE_RATING_KEYWORDS_KR
        + _GENERIC_PHRASES_KR,
    )
    remainder = _strip_known_phrases_en(
        remainder,
        ACCOMMODATION_KEYWORDS_EN + TOURIST_KEYWORDS_EN + REVIEW_KEYWORDS_EN
        + POSITIVE_RATING_KEYWORDS_EN + NEGATIVE_RATING_KEYWORDS_EN
        + _GENERIC_PHRASES_EN,
    )

    raw_tokens = re.split(r"[\s,.!?]+", remainder.strip())

    tokens = []
    for tok in raw_tokens:
        if not tok:
            continue
        stripped = _JOSA_PATTERN.sub("", tok)
        if not stripped or stripped in STOPWORDS or stripped in _GENERIC_NOUNS:
            continue

        # "gangnam" 같은 영어 지역명이면 매칭 가능한 한글 지역명으로 바꿔치기.
        romanized = _romanize_lookup(stripped)
        tokens.append(romanized if romanized else stripped)

    return tokens


def _load_rating_stats(session: Session) -> dict[str, tuple[float | None, int]]:
    """place_id별 평균 평점/리뷰 개수를 한 번의 쿼리로 미리 다 가져온다."""

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


# ---------------------------------------------------------------------------
# 응답 문구 (다양화 + 이중 언어)
# ---------------------------------------------------------------------------
def _empty_message_reply(is_korean: bool) -> str:
    if is_korean:
        return "궁금하신 내용을 입력해 주세요. 예) '강남 숙소 추천', '경복궁 리뷰 어때?'"
    return "Please tell me what you're looking for. e.g. 'recommend hotels in Gangnam', 'reviews for Gyeongbokgung'"


def _no_result_reply(message: str, is_korean: bool) -> str:
    if is_korean:
        options = [
            f"'{message}'에 대한 검색 결과를 찾지 못했어요. 다른 키워드로 다시 물어봐 주세요.",
            f"음, '{message}'와 딱 맞는 곳을 못 찾았어요. 지역명이나 표현을 바꿔서 다시 시도해 볼까요?",
        ]
    else:
        options = [
            f"I couldn't find results for '{message}'. Try a different keyword or area name.",
            f"Hmm, nothing matched '{message}'. Could you try rephrasing or naming a district?",
        ]
    return random.choice(options)


def _fallback_reply(message: str, count: int, is_korean: bool) -> str:
    if is_korean:
        options = [
            f"'{message}'와 정확히 일치하는 곳은 찾지 못했지만, 참고할 만한 장소 {count}곳을 보여드릴게요.",
            f"딱 맞는 결과는 없었지만, 비슷하게 참고하실 만한 {count}곳을 추려봤어요.",
        ]
    else:
        options = [
            f"I couldn't find an exact match for '{message}', but here are {count} places you might like.",
            f"No exact match, but here are {count} suggestions that might still be useful.",
        ]
    return random.choice(options)


def _result_reply(
    message: str,
    count: int,
    category_kr: str,
    category_en: str,
    wants_rating_sort: bool,
    wants_low_rating: bool,
    is_korean: bool,
) -> str:
    if is_korean:
        if wants_rating_sort:
            order = "낮은" if wants_low_rating else "높은"
            options = [
                f"'{message}'와 관련된 {category_kr} {count}곳을 평점 {order} 순으로 찾았어요.",
                f"평점 {order} 순으로 {category_kr} {count}곳을 정리했어요.",
            ]
        else:
            options = [
                f"'{message}'와 관련된 {category_kr} {count}곳을 찾았어요.",
                f"{category_kr} {count}곳을 찾아왔어요. 살펴보세요!",
            ]
    else:
        if wants_rating_sort:
            order = "lowest" if wants_low_rating else "highest"
            options = [
                f"Found {count} {category_en} related to '{message}', sorted by {order} rating.",
                f"Here are {count} {category_en} sorted by {order} rating.",
            ]
        else:
            options = [
                f"Found {count} {category_en} related to '{message}'.",
                f"Here are {count} {category_en} you might like!",
            ]

    return random.choice(options)


def build_chat_response(session: Session, message: str) -> ChatResponse:
    message = message.strip()
    is_korean = _is_korean(message) if message else True

    if not message:
        return ChatResponse(reply=_empty_message_reply(is_korean))

    # 0. 스몰토크(인사말/도움말)면 검색 없이 바로 답한다.
    smalltalk = _smalltalk_reply(message, is_korean)
    if smalltalk is not None:
        return ChatResponse(reply=smalltalk)

    # 1. 의도 판별: 관광지 / 숙소 / 둘 다 + 평점 정렬 방향
    wants_accommodation = _match_any(message, ACCOMMODATION_KEYWORDS)
    wants_tourist = _match_any(message, TOURIST_KEYWORDS)
    wants_review = _match_any(message, REVIEW_KEYWORDS)
    wants_low_rating = _match_any(message, NEGATIVE_RATING_KEYWORDS)
    wants_high_rating = _match_any(message, POSITIVE_RATING_KEYWORDS)
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
        reply = _no_result_reply(message, is_korean)
    elif fallback_used:
        reply = _fallback_reply(message, len(results), is_korean)
    else:
        category_kr = (
            "숙소" if wants_accommodation and not wants_tourist
            else "관광지" if wants_tourist and not wants_accommodation
            else "장소"
        )
        category_en = (
            "accommodations" if wants_accommodation and not wants_tourist
            else "tourist spots" if wants_tourist and not wants_accommodation
            else "places"
        )
        reply = _result_reply(
            message, len(results), category_kr, category_en,
            wants_rating_sort, wants_low_rating, is_korean,
        )

    return ChatResponse(reply=reply, results=results)