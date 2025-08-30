FROM python:3.12-slim

WORKDIR /app

# 시스템 의존성 + 한글 폰트
RUN apt-get update && apt-get install -y --no-install-recommends \
      curl ca-certificates wget gnupg \
      fonts-noto-cjk \
    && rm -rf /var/lib/apt/lists/*

# Playwright 설치 (크로미움 포함 의존성 자동 설치)
RUN pip install --no-cache-dir --upgrade pip \
 && pip install --no-cache-dir "playwright>=1.46" fastapi "uvicorn[standard]>=0.26" pydantic requests \
 && python -m playwright install --with-deps chromium

# setup.py 기반 앱 설치
COPY setup.py /app/
COPY src /app/src
# README가 있으면 복사
# COPY README.md /app/
RUN pip install --no-cache-dir .

EXPOSE 8000
CMD ["uvicorn","src.app.main:app","--host","0.0.0.0","--port","8000"]