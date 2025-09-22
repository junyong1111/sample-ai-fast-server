"""
Celery 설정
Redis 브로커와 비트 스케줄러 설정
"""

import os

# Redis 설정
CELERY_BROKER_URL = os.getenv('CELERY_BROKER_URL', 'redis://localhost:6379/0')
CELERY_RESULT_BACKEND = os.getenv('CELERY_RESULT_BACKEND', 'redis://localhost:6379/0')

# 직렬화 설정
CELERY_TASK_SERIALIZER = 'json'
CELERY_ACCEPT_CONTENT = ['json']
CELERY_RESULT_SERIALIZER = 'json'

# 시간대 설정
CELERY_TIMEZONE = 'UTC'

# 태스크 설정
CELERY_TASK_TIME_LIMIT = 600  # 10분
CELERY_TASK_SOFT_TIME_LIMIT = 480  # 8분

# Beat 스케줄러 설정
CELERY_BEAT_SCHEDULER = 'celery.beat:PersistentScheduler'

# Beat 스케줄 정의 - 배치 처리 방식
CELERY_BEAT_SCHEDULE = {
    # 상위 20개 코인 차트 분석 (5분마다)
    'top-20-chart-analysis': {
        'task': 'scheduler.tasks.chart_analysis.analyze_top_20_coins',
        'schedule': 300.0,  # 5분마다 실행
        'args': ('minutes:60', 200, 'binance')
    },
    # 상위 20개 코인 리스크 분석 (1시간마다)
    'top-20-risk-analysis': {
        'task': 'scheduler.tasks.risk_analysis.analyze_top_20_risk',
        'schedule': 3600.0,  # 1시간마다 실행
        'args': ()
    },
}
