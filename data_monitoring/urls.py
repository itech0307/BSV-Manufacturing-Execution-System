from django.urls import path
from . import views

app_name = 'data_monitoring'

urlpatterns = [
    path('drymix/', views.input_drymix, name='input_drymix')
]