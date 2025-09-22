#!/bin/bash

# Celery Beat 시작 스크립트
echo "⏰ Celery Beat 시작 중..."

# 프로젝트 루트 디렉토리로 이동
cd "$(dirname "$0")/.."

# Python 경로 설정
export PYTHONPATH="${PYTHONPATH}:$(pwd)/src"

# Celery Beat 실행
celery -A src.scheduler.celery beat \
    --loglevel=info \
    --scheduler=celery.beat:PersistentScheduler
