from django.urls import path
from . import views

app_name = 'workforce_management'

urlpatterns = [
    path('worker/list/', views.worker_list, name='worker_list'),
    path('worker/register/', views.worker_register, name='worker_register'),
    path('worker/<str:worker_code>/', views.worker_detail, name='worker_detail'),
    path('worker/modify/<str:worker_code>/', views.worker_modify, name='worker_modify'),
    path('worker/comment/create/<str:worker_code>/', views.worker_comment_create, name='worker_comment_create'),
]
