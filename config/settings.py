# Logging configuration
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {process:d} {thread:d} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': 'logs/celery/celery.log',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'production_management.tasks': {
            'handlers': ['file'],
            'level': 'INFO',
            'propagate': True,
        },
    },
} 