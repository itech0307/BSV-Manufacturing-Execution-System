from django.urls import path
from . import views

app_name = 'inventory_management'

urlpatterns = [
    path('raw_materials/', views.view_raw_materials, name='view_raw_materials'),
    path('add_category/', views.add_category, name='add_category'),
    path('add_supplier/', views.add_supplier, name='add_supplier'),
    path('add_rawmaterial/', views.add_rawmaterial, name='add_rawmaterial'),
]