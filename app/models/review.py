from datetime import datetime
from enum import Enum

from sqlmodel import Field, SQLModel


class PlaceType(str, Enum):
    TOURIST = "TOURIST"
    ACCOMMODATION = "ACCOMMODATION"


class Review(SQLModel, table=True):
    __tablename__ = "reviews"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    place_type: PlaceType = Field(
        nullable=False,
        index=True,
    )

    # JSON의 contentid
    place_id: str = Field(
        nullable=False,
        index=True,
    )

    place_title: str = Field(
        nullable=False,
        max_length=200,
    )

    addr1: str = Field(
        nullable=False,
        max_length=300,
    )

    mapx: float = Field(nullable=False)
    mapy: float = Field(nullable=False)

    rating: int = Field(
        nullable=False,
        ge=1,
        le=5,
    )

    review_title: str = Field(
        nullable=False,
        max_length=200,
    )

    content: str = Field(nullable=False)

    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )