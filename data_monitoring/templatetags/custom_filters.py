import json
from datetime import datetime, date
from django import template
from django.utils.html import mark_safe
import pytz

register = template.Library()

@register.filter(name='get_item')
def get_item(value, arg):
    try:
        return value[arg]
    except IndexError:
        return None

@register.filter(name='get_key')
def get_key(value, arg):
    if isinstance(value, dict):
        return value.get(arg)
    return None

@register.filter(name='get_slice')
def get_slice(value, arg):
    if value is None:
        return ''
    return value[arg:]

@register.filter
def sum_pd_qty(data_list):
    return sum(int(data.phase_information[0].get('quantity')) for data in data_list)

@register.filter
def sum_defect_quantities(phase_information):
    total_loss_qty = 0
    for entry in phase_information:
        if 'defectCause' in entry:
            try:
                total_loss_qty += int(entry.get('quantity', 0))
            except ValueError:
                continue
    return total_loss_qty

@register.filter
def json_script(value, element_id):
    json_str = json.dumps(value)
    return mark_safe(f'<script id="{element_id}" type="application/json">{json_str}</script>')

def json_serializable(value):
    """
    객체를 JSON으로 직렬화할 수 있는 문자열로 변환합니다.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ''
    return value

@register.filter(name='json_str')
def json_str(value):
    """
    JSON 직렬화 필터.
    """
    try:
        json_str = json.dumps(value, default=json_serializable)
        return json_str
    except (TypeError, ValueError):
        return ''

@register.filter(name='zip_count')
def zip_count(value):
    zip_count = len(list(value))
    return zip_count

@register.filter(name='elapsed_time')
def elapsed_time(value):
    """주어진 datetime 객체와 현재 시간 사이의 경과 시간을 'Xd Xh ago' 형식으로 반환합니다."""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value  # 처리할 수 없는 형식이면 그대로 반환
        
    if isinstance(value, datetime):
        # 현재 시간
        now = datetime.now()
        
        elapsed_time = now - value
        days = elapsed_time.days
        hours = elapsed_time.seconds // 3600
        minutes = (elapsed_time.seconds % 3600) // 60

        if days > 0:
            return f"{days}d {hours}h ago"
        elif hours > 0:
            return f"{hours}h {minutes}m ago"
        else:
            return f"{minutes}m ago"
    
    return value

@register.filter(name='d_day')
def d_day(value):
    """주어진 날짜와 오늘 사이의 D-day를 계산하여 반환합니다."""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()  # 문자열을 날짜 객체로 변환
        except ValueError:
            return value  # 날짜 형식이 잘못된 경우 그대로 반환

    if isinstance(value, date):
        today = date.today()  # 현재 날짜 (date 객체)
        
        delta = value - today  # 날짜 차이 계산
        days = delta.days      # 일수 추출
        
        if days == 0:
            return "D-day"
        elif days > 0:
            return f"D-{days}"
        else:
            return f"D+{-days}"
    
    return value