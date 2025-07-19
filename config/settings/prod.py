from .base import *
import os
import environ

ALLOWED_HOSTS = ['18.139.97.72', 'bsv-mes.com']
DEBUG = False

AWS_STORAGE_BUCKET_NAME = 'bsv-mes-prod-bucket'
AWS_S3_CUSTOM_DOMAIN = 'bsv-mes-prod-bucket.s3.ap-southeast-1.amazonaws.com'
AWS_S3_REGION_NAME = 'ap-southeast-1'

env = environ.Env()
environ.Env.read_env(BASE_DIR / '.env')

TIME_ZONE = 'Asia/Ho_Chi_Minh'  # Apply the Vietnam Ho Chi Minh time
USE_I18N = True
USE_L10N = True
USE_TZ = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql_psycopg2',
        'NAME': env('DB_NAME'),
        'USER': env('DB_USER'),
        'PASSWORD': env('DB_PASSWORD'),
        'HOST': env('DB_HOST'),
        'PORT': '5432',
    }
}