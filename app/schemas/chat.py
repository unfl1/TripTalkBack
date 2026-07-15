from pydantic import BaseModel


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
