from pydantic import BaseModel


class PlaceRead(BaseModel):
    """관광지 / 숙소 목록 응답 스키마."""

    contentid: str
    title: str
    addr1: str
    mapx: float
    mapy: float


class PlaceSearchResult(PlaceRead):
    """장소 검색(정확히 일치) 결과 스키마. 관광지/숙소를 구분하기 위해 place_type 추가."""

    place_type: str  # "TOURIST" | "ACCOMMODATION"