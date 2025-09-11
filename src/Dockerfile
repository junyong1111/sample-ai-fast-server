# syntax=docker/dockerfile:1.7
FROM python:3.12-slim AS base
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1
WORKDIR /app

# 1) OS deps
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl ca-certificates wget gnupg build-essential fonts-noto-cjk \
  && rm -rf /var/lib/apt/lists/*

# 2) 의존성 파일만 먼저 복사 → 의존성 레이어 캐시 보존
COPY requirements.txt /app/requirements.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# 3) (무거움) playwright 설치는 의존성 레이어 뒤에
RUN python -m playwright install --with-deps chromium
# 필요 없다면 아예 이미지에 넣지 말고:
# RUN PLAYWRIGHT_SKIP_BROWSER_DOWNLOAD=1 pip install playwright

# 4) 앱 소스는 마지막에 복사 → 소스 변경 시 이 레이어만 무효
COPY setup.py /app/
COPY src /app/src

# 5) 패키지 등록만 (의존성 재설치 X)
RUN pip install --no-cache-dir --no-deps .

EXPOSE 8000
CMD ["uvicorn","src.app.main:app","--host","0.0.0.0","--port","8000"]