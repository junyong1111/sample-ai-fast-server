# celery_app/celery.py
import os
from celery import Celery

# 혹은 별도의 설정 파일을 사용할 수 있습니다.
os.environ.setdefault('src/scheduler/config.py', 'src.config.setting')

# 'celery_app'은 현재 모듈의 이름을 나타냅니다.
app = Celery('scheduler')

# 'scheduler/config.py' 네임스페이스를 사용하여 설정을 로드합니다.
# CELERY_로 시작하는 모든 설정 키를 자동으로 가져옵니다.
app.config_from_object('src.scheduler.config', namespace='CELERY')

# src/scheduler/tasks/ 디렉터리 하위의 모든 tasks.py 파일을 자동으로 찾아서 로드합니다.
app.autodiscover_tasks()

# 태스크 수동 등록 (autodiscover가 작동하지 않는 경우를 대비)
try:
    from src.scheduler.tasks import simple_chart_analysis
    print("✅ 간단한 태스크 모듈 로드 성공")
except ImportError as e:
    print(f"❌ 태스크 모듈 로드 실패: {e}")

# 간단한 Celery Worker - 데이터베이스 풀 초기화 제거

@app.task(bind=True)
def debug_task(self):
    print(f'Request: {self.request!r}')