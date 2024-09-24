from django.urls import path
from . import views

app_name = 'production_management'

urlpatterns = [
    path('order_sheet_upload/', views.order_sheet_upload, name='order_sheet_upload'),
    path('dryplan_import/', views.dryplan_import, name='dryplan_import'),
]