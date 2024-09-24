# Django가 시작될 때 Celery import
# shared_task 데코레이션이 Celery를 사용
from .celery import app as celery_app
__all__ = ('celery_app',)