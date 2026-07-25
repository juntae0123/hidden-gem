FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 (psycopg 등 빌드 대비) / System packages
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

# 운영: $PORT 바인딩, --reload 제거, --workers 2
# Korean: 로컬(docker-compose)은 command로 --reload를 덮어쓰고,
#         Railway는 이 CMD로 $PORT에 바인딩한다.
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 2"]