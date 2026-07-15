from datetime import datetime

from fastapi import HTTPException, status

from app.models.review import Review
from app.schemas.review import ReviewListResponse, ReviewUpdate


def build_list_response(reviews: list[Review]) -> ReviewListResponse:
    """리뷰 목록으로 평균 평점 / 개수를 계산해 함께 내려준다."""

    review_count = len(reviews)
    avg_rating = (
        round(sum(review.rating for review in reviews) / review_count, 1)
        if review_count > 0
        else None
    )

    return ReviewListResponse(
        items=reviews,
        avg_rating=avg_rating,
        review_count=review_count,
    )


def verify_owner(review: Review, password: str) -> None:
    """수정/삭제 권한(비밀번호)을 확인한다. 인증/인가 대신 사용하는 간이 규칙."""

    if review.password != password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비밀번호가 일치하지 않습니다.",
        )


def apply_update(review: Review, review_in: ReviewUpdate) -> Review:
    update_data = review_in.model_dump(
        exclude={"password"},
        exclude_unset=True,
    )

    for key, value in update_data.items():
        setattr(review, key, value)

    review.updated_at = datetime.now()

    return review
