from datetime import datetime

from sqlmodel import Field, SQLModel


class ReviewBase(SQLModel):
    """DB 테이블과 요청/응답 스키마가 공통으로 사용하는 필드."""

    # JSON의 contentid (관광지/숙소 구분 없이 전역에서 고유한 값)
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


class Review(ReviewBase, table=True):
    """실제 DB 테이블. password를 포함해서 저장한다."""

    __tablename__ = "reviews"

    id: int | None = Field(
        default=None,
        primary_key=True,
    )

    # 인증/인가 없이 수정·삭제 권한만 판단하기 위한 값.
    # 요구사항에 따라 암호화 없이 평문 그대로 저장
    password: str = Field(
        nullable=False,
        max_length=100,
    )

    created_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )

    updated_at: datetime = Field(
        default_factory=datetime.now,
        nullable=False,
    )
