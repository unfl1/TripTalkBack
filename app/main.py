from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.database import create_db_and_tables
from app.models import Review
from app.routers.accommodation import router as accommodation_router
from app.routers.review import router as review_router
from app.routers.tourist_spot import router as tourist_spot_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()

    yield


app = FastAPI(
    lifespan=lifespan,
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


app.include_router(tourist_spot_router)
app.include_router(accommodation_router)
app.include_router(review_router)


@app.get("/")
def root():
    return {
        "message": "서버가 정상 작동 중입니다."
    }