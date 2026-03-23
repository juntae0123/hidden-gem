import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

# 1. .env 파일의 환경 변수를 읽어옵니다.
load_dotenv()

# 2. 환경 변수에서 DB 접속 정보를 가져옵니다.
# .env에 DATABASE_URL이 없으면 에러를 발생시켜 보안 사고를 방지합니다.
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL")

if not SQLALCHEMY_DATABASE_URL:
    raise ValueError("❌ .env 파일에 'DATABASE_URL' 설정이 없습니다. 확인해주세요!")

# 3. SQLAlchemy 엔진 생성
engine = create_engine(SQLALCHEMY_DATABASE_URL)

# 4. DB 세션 생성 설정
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# 5. 모델 클래스들의 베이스가 되는 클래스
Base = declarative_base()

# DB 세션 의존성 주입을 위한 함수 (FastAPI에서 사용 예정)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()