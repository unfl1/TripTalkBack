import os
from pathlib import Path

from dotenv import load_dotenv

# app/core/config.py -> app/core -> app -> 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# 프로젝트 루트의 .env 파일을 읽어서 os.environ에 반영
load_dotenv(BASE_DIR / ".env")

DATA_DIR = BASE_DIR / "data"

TOURIST_FILE_PATH = DATA_DIR / "서울_관광지.json"
ACCOMMODATION_FILE_PATH = DATA_DIR / "서울_숙박.json"

# .env에 DATABASE_URL이 없으면 기존과 동일하게 로컬 localhub.db를 기본값으로 사용
DEFAULT_DATABASE_URL = f"sqlite:///{BASE_DIR / 'localhub.db'}"
DATABASE_URL = os.getenv("DATABASE_URL", DEFAULT_DATABASE_URL)

CORS_ALLOW_ORIGINS = ["*"]