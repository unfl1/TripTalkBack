from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.database import get_session
from app.schemas.chat import ChatRequest, ChatResponse
from app.services.chat_service import build_chat_response


router = APIRouter(
    prefix="/api/chat",
    tags=["chat"],
)


@router.post("", response_model=ChatResponse)
def chat(
    request: ChatRequest,
    session: Session = Depends(get_session),
):
    return build_chat_response(session, request.message)
