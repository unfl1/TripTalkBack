from fastapi import APIRouter

from app.core.config import TOURIST_FILE_PATH
from app.schemas.place import PlaceRead
from app.services.place_loader import load_places


router = APIRouter(
    prefix="/api/tourist-spots",
    tags=["tourist-spots"],
)


@router.get("", response_model=list[PlaceRead])
def get_tourist_spots():
    return load_places(TOURIST_FILE_PATH)
