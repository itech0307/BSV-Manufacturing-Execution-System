from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('main/', views.main_page, name='main'),

    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('register/', views.register, name='register'),
    path('activate/<uidb64>/<token>/', views.activate, name='activate'),
    
    path('mypage/', views.mypage, name='mypage'),
    path('change-password/', views.change_password, name='change_password'),

    path('file_browser/', views.list_files, name='list_files'),
    path('file_browser/upload/', views.upload_file, name='upload_file'),
    path('file_browser/delete/<path:file_path>/', views.delete_file, name='delete_file'),
    path('file_browser/create_folder/', views.create_folder, name='create_folder'),
]