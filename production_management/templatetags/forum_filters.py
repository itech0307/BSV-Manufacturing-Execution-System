import json
from django import template
import markdown
from django.utils.safestring import mark_safe
import os

register = template.Library()

@register.filter
def sub(value, arg):
    return value - arg

@register.filter()
def mark(value):
    extensions = ["nl2br", "fenced_code"]
    return mark_safe(markdown.markdown(value, extensions=extensions))

@register.filter
def first_image(files):
    image_extensions = ['.jpg', '.jpeg', '.png', '.gif', '.bmp']
    for file in files:
        if isinstance(file, dict):
            # file이 딕셔너리인 경우
            file_name = file.get('name', '')
        elif hasattr(file, 'name'):
            # file이 File 객체인 경우
            file_name = file.name
        else:
            # 예상치 못한 형태의 경우, 다음 파일로 넘어갑니다
            continue
        
        _, ext = os.path.splitext(file_name.lower())
        if ext in image_extensions:
            return file
    return None