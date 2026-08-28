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

# 정적 파일 수집 (빌드 시점에 1회 — 런타임 지연 방지)
# Korean: DB 연결 없이 실행되도록 더미 SECRET_KEY 사용
RUN DJANGO_SECRET_KEY=build-only-dummy DJANGO_DEBUG=True \
    python manage.py collectstatic --noinput || echo "collectstatic skipped"

# 포트 / Port
EXPOSE 8000

CMD ["sh", "-c", "python manage.py migrate --noinput && gunicorn config.wsgi:application --bind 0.0.0.0:${PORT:-8000} --workers 2 --access-logfile - --error-logfile -"]