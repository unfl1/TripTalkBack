from sqlmodel import Session, select

from app.models.review import Review


def create_review(session: Session, review: Review) -> Review:
    session.add(review)
    session.commit()
    session.refresh(review)

    return review


def get_review(session: Session, review_id: int) -> Review | None:
    return session.get(Review, review_id)


def get_reviews(session: Session, place_id: str | None = None) -> list[Review]:
    query = select(Review)

    if place_id is not None:
        query = query.where(Review.place_id == place_id)

    query = query.order_by(Review.created_at.desc())

    return session.exec(query).all()


def save_review(session: Session, review: Review) -> Review:
    session.add(review)
    session.commit()
    session.refresh(review)

    return review


def delete_review(session: Session, review: Review) -> None:
    session.delete(review)
    session.commit()
