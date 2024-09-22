from django.urls import path
from . import views

app_name = 'common'

urlpatterns = [
    path('main/', views.main_page, name='main'),
    path('login/', views.login_view, name='login'),
    path('register/', views.register, name='register'),
]