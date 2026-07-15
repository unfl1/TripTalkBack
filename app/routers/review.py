from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from app.database import get_session
from app.models.review import (
    PlaceType,
    Review,
    ReviewCreate,
    ReviewDelete,
    ReviewRead,
    ReviewUpdate,
)


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

    session.add(review)
    session.commit()
    session.refresh(review)

    return review


@router.get(
    "",
    response_model=list[ReviewRead],
)
def get_reviews(
    place_type: PlaceType | None = None,
    place_id: str | None = None,
    session: Session = Depends(get_session),
):
    query = select(Review)

    if place_type is not None:
        query = query.where(Review.place_type == place_type)

    if place_id is not None:
        query = query.where(Review.place_id == place_id)

    query = query.order_by(Review.created_at.desc())

    reviews = session.exec(query).all()

    return reviews


@router.get(
    "/{review_id}",
    response_model=ReviewRead,
)
def get_review(
    review_id: int,
    session: Session = Depends(get_session),
):
    review = session.get(Review, review_id)

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
    review = session.get(Review, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리뷰를 찾을 수 없습니다.",
        )

    if review.password != review_in.password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비밀번호가 일치하지 않습니다.",
        )

    update_data = review_in.model_dump(
        exclude={"password"},
        exclude_unset=True,
    )

    for key, value in update_data.items():
        setattr(review, key, value)

    review.updated_at = datetime.now()

    session.add(review)
    session.commit()
    session.refresh(review)

    return review


@router.delete(
    "/{review_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
def delete_review(
    review_id: int,
    review_in: ReviewDelete,
    session: Session = Depends(get_session),
):
    review = session.get(Review, review_id)

    if review is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="리뷰를 찾을 수 없습니다.",
        )

    if review.password != review_in.password:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="비밀번호가 일치하지 않습니다.",
        )

    session.delete(review)
    session.commit()

    return None