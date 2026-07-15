from pydantic import BaseModel


class PlaceRead(BaseModel):
    """관광지 / 숙소 목록 응답 스키마."""

    contentid: str
    title: str
    addr1: str
    mapx: float
    mapy: float
