from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session

from app import crud
from app.database import get_session
from app.models.review import Review
from app.schemas.review import (
    ReviewCreate,
    ReviewDelete,
    ReviewListResponse,
    ReviewRead,
    ReviewUpdate,
)
from app.services import review_service


router = APIRouter(
    prefix="/api/reviews",
    tags=["reviews"],
)


@router.post(
    "",
    response_model=ReviewRead,
    status_code=status.HTTP_201_CREATED,
)
def create_review(
    review_in: ReviewCreate,
    session: Session = Depends(get_session),
):
    review = Review.model_validate(review_in)

    return crud.review.create_review(session, review)


@router.get(
    "",
    response_model=ReviewListResponse,
)
def get_reviews(
    place_id: str | None = None,
    session: Session = Depends(get_session),
):
    reviews = crud.review.get_reviews(session, place_id=place_id)

    return review_service.build_list_response(reviews)


@router.get(
    "/{review_id}",
    response_model=ReviewRead,
)
def get_review(
    review_id: int,
    session: Session = Depends(get_session),
):
    review = crud.review.get_review(session, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리뷰를 찾을 수 없습니다.",
        )

    return review


@router.patch(
    "/{review_id}",
    response_model=ReviewRead,
)
def update_review(
    review_id: int,
    review_in: ReviewUpdate,
    session: Session = Depends(get_session),
):
    review = crud.review.get_review(session, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리뷰를 찾을 수 없습니다.",
        )

    review_service.verify_owner(review, review_in.password)

    review = review_service.apply_update(review, review_in)

    return crud.review.save_review(session, review)


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_review(
    review_id: int,
    review_in: ReviewDelete,
    session: Session = Depends(get_session),
):
    review = crud.review.get_review(session, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리뷰를 찾을 수 없습니다.",
        )

    review_service.verify_owner(review, review_in.password)

    crud.review.delete_review(session, review)

    return None
