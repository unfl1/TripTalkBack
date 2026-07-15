from datetime import datetime

from sqlmodel import Field, SQLModel

from app.models.review import ReviewBase


class ReviewCreate(ReviewBase):
    """리뷰 생성 요청 바디. password 포함."""

    password: str = Field(nullable=False, max_length=100)


class ReviewUpdate(SQLModel):
    """리뷰 수정 요청 바디. password는 필수, 나머지는 선택."""

    password: str

    rating: int | None = Field(default=None, ge=1, le=5)
    review_title: str | None = Field(default=None, max_length=200)
    content: str | None = None


class ReviewDelete(SQLModel):
    """리뷰 삭제 요청 바디."""

    password: str


class ReviewRead(ReviewBase):
    """응답으로 내려줄 스키마. password는 절대 포함하지 않는다."""

    id: int
    created_at: datetime
    updated_at: datetime


class ReviewListResponse(SQLModel):
    """장소 클릭 시 보여줄 리뷰 목록 페이지 응답.

    상단에 평균 평점 / 리뷰 개수, 그 아래 개별 리뷰 목록(제목+별점 등)을 보여준다.
    """

    items: list[ReviewRead]
    avg_rating: float | None = None
    review_count: int = 0
