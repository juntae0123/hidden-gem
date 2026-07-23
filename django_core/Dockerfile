# django_core/Dockerfile
FROM python:3.12-slim

WORKDIR /app

# 시스템 패키지 / System packages
RUN apt-get update && apt-get install -y \
    libpq-dev \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Python 패키지 / Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 소스 코드 / Source code
COPY . .

# 포트 (로컬 개발 기준, 운영은 $PORT 사용) / Port
EXPOSE 8000

# 기본 명령 — 운영: gunicorn, $PORT 미지정 시 8000
# Korean: 로컬(docker-compose)은 command로 runserver를 덮어쓰고,
#         Railway는 이 CMD를 그대로 사용해 $PORT에 바인딩한다.
CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile - --error-logfile -"]