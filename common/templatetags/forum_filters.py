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
            # If the file is a dictionary
            file_name = file.get('name', '')
        elif hasattr(file, 'name'):
            # If the file is a File object
            file_name = file.name
        else:
            # If the file is an unexpected form, skip to the next file
            continue
        
        _, ext = os.path.splitext(file_name.lower())
        if ext in image_extensions:
            return file
    return None