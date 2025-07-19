# Django Celery execution settings

from  __future__  import  absolute_import
import os
from celery import Celery
from django.conf import settings

# Get the environment variables set in the server
import environ
env = environ.Env()
environ.Env.read_env('config/gunicorn.env')

# Django basic settings for the Celery module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', env('DJANGO_SETTINGS_MODULE'))

# The first argument is the module name, the second argument is the message broker
app = Celery('mes', broker='redis://localhost') # celery instance

app.conf.broker_connection_retry_on_startup = True
app.conf.result_backend = 'redis://localhost'
app.conf.task_track_started = True

# Using strings here means that the worker does not configure child process serialization.
# The meaning of -namespace='CELERY' is that all settings related to Celery start with the prefix CELERY_
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load all task modules registered in Django
app.autodiscover_tasks(lambda: settings.INSTALLED_APPS)

@app.task(bind=True)    # Decorator for functions to be executed asynchronously
def debug_task(self):
    print(f'Request: {self.request!r}')