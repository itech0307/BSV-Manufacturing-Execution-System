# When Django starts, import Celery
# The shared_task decorator uses Celery
from .celery import app as celery_app
__all__ = ('celery_app',)