"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include
from django.shortcuts import redirect

def redirect_to_main(request):
    return redirect('common:main')

urlpatterns = [
    path('admin/', admin.site.urls),
    path('common/', include('common.urls')),
    path('inventory_management/', include('inventory_management.urls')),
    path('data_monitoring/', include('data_monitoring.urls')),
    path('production_management/', include('production_management.urls')),
    
    # Celery progress
    path('celery-progress/', include('celery_progress.urls')),

    path('accounts/', include('allauth.urls')),
    path('', redirect_to_main, name='home'),
]