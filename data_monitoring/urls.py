from django.urls import path
from . import views

app_name = 'data_monitoring'

urlpatterns = [
    path('input_drymix/', views.input_drymix, name='input_drymix'),

    path('order_search/', views.order_search, name='order_search'),
    path('drymix/', views.drymix, name='drymix'),
    path('dryline/', views.dryline, name='dryline'),
]