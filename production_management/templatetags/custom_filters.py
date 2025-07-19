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
    try:
        return sum(int(data.pd_qty) for data in data_list)
    except AttributeError:
        return sum(int(data.dlami_qty) for data in data_list)

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
    Convert an object to a string that can be serialized to JSON.
    """
    if isinstance(value, datetime):
        return value.isoformat()
    if value is None:
        return ''
    return value

@register.filter(name='json_str')
def json_str(value):
    """
    JSON serialization filter.
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
    """Return the elapsed time between the given datetime object and the current time in the format 'Xd Xh ago'."""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, '%Y-%m-%d %H:%M:%S')
        except ValueError:
            return value  # If the format cannot be processed, return it as is
        
    if isinstance(value, datetime):
        # Current time
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
    """Calculate the D-day between the given date and today and return it."""
    if isinstance(value, str):
        try:
            value = datetime.strptime(value, "%Y-%m-%d").date()  # Convert the string to a date object
        except ValueError:
            return value  # If the date format is incorrect, return it as is

    if isinstance(value, date):
        today = date.today()  # Current date (date object)
        
        delta = value - today  # Calculate the date difference
        days = delta.days      # Extract the number of days
        
        if days == 0:
            return "D-day"
        elif days > 0:
            return f"D-{days}"
        else:
            return f"D+{-days}"
    
    return value

@register.filter
def custom_date_format(value):
    if value:
        return value.strftime("%-m-%d")
    return ""