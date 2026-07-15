from pathlib import Path

# app/core/config.py -> app/core -> app -> 프로젝트 루트
BASE_DIR = Path(__file__).resolve().parent.parent.parent

DATA_DIR = BASE_DIR / "data"

TOURIST_FILE_PATH = DATA_DIR / "서울_관광지.json"
ACCOMMODATION_FILE_PATH = DATA_DIR / "서울_숙박.json"

DATABASE_PATH = BASE_DIR / "localhub.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

CORS_ALLOW_ORIGINS = ["*"]
