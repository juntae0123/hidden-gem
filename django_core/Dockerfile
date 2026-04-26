# django_core/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드
COPY . .

# 포트
EXPOSE 8000

# 기본 명령
CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]
