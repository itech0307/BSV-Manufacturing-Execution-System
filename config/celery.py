# Django Celery 실행 세팅

from  __future__  import  absolute_import
import os
from celery import Celery
from django.conf import settings

# 서버 내에 설정해 둔 환경변수 가져오기
import environ
env = environ.Env()
environ.Env.read_env('config/gunicorn.env')

# Celery 모듈을 위한 Django 기본세팅
os.environ.setdefault('DJANGO_SETTINGS_MODULE', env('DJANGO_SETTINGS_MODULE'))

# 첫번째 인자는 모듈 이름, 두번째 인자는 messege broker
app = Celery('mes', broker='redis://localhost') # celery instance

app.conf.broker_connection_retry_on_startup = True
app.conf.result_backend = 'redis://localhost'
app.conf.task_track_started = True

# 여기서 문자열을 사용하는것은 작업자가가 자식 프로세스 직렬화 구성을 하지 않는것을 의미합니다.
# -namespace='CELERY' 의 의미는 셀러리와 관련된 모든 설정은 CELERY_ 라는 prefix로 시작함을 의미
app.config_from_object('django.conf:settings', namespace='CELERY')

# Django 에 등록된 모든 task 모듈을 로드
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)    # 비동기로 실행할 함수에 데코레이터
def debug_task(self):
    print(f'Request: {self.request!r}')