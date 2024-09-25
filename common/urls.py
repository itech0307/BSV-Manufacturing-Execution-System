from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('main/', views.main_page, name='main'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),

    path('file_browser/', views.list_files, name='list_files'),
    path('upload/', views.upload_file, name='upload_file'),
    path('delete/<int:file_id>/', views.delete_file, name='delete_file'),
]