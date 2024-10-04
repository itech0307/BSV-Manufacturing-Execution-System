from django.urls import path
from . import views

app_name = 'production_management'

urlpatterns = [
    path('order_sheet_upload/', views.order_sheet_upload, name='order_sheet_upload'),
    path('dryplan_import/', views.dryplan_import, name='dryplan_import'),

    path('development_list/', views.development_list, name='development_list'),
    path('development_register/', views.development_register, name='development_register'),

    path('development_detail/<int:development_id>/', views.development_detail, name='development_detail'),
    path('development/modify/<int:development_id>/', views.development_modify, name='development_modify'),
    path('development/delete/<int:development_id>/', views.development_delete, name='development_delete'),

    path('development/<int:development_id>/upload/', views.upload_file, name='upload_file'),
    path('development/<int:development_id>/download/<str:file_name>/', views.download_file, name='download_file'),
    path('development/<int:development_id>/files/', views.list_files, name='list_files'),

    path('development_comment/create/<int:development_id>/', views.development_comment_create, name='development_comment_create'),
    path('development_comment/modify/<int:development_comment_id>/', views.development_comment_modify, name='development_comment_modify'),
    path('development_comment/delete/<int:development_comment_id>/', views.development_comment_delete, name='development_comment_delete'),
    path('development/update_status/<int:development_id>/', views.update_status, name='update_status'),

]