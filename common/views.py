from django.shortcuts import render

import logging
logger = logging.getLogger('common')

def main_page(request):
    logger.info('main_page')
    return render(request, 'common/main.html')