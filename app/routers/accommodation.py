from fastapi import APIRouter

from app.core.config import ACCOMMODATION_FILE_PATH
from app.schemas.place import PlaceRead
from app.services.place_loader import load_places


router = APIRouter(
    prefix="/api/accommodations",
    tags=["accommodations"],
)


@router.get("", response_model=list[PlaceRead])
def get_accommodations():
    return load_places(ACCOMMODATION_FILE_PATH)
