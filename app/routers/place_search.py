from fastapi import APIRouter, Query

from app.schemas.place import PlaceSearchResult
from app.services.place_search import search_places_exact


router = APIRouter(
    prefix="/api/places",
    tags=["places"],
)


@router.get("/search", response_model=list[PlaceSearchResult])
def search_places(q: str = Query(..., min_length=1, description="검색할 장소명 (정확히 일치하는 것만 반환)")):
    return search_places_exact(q)