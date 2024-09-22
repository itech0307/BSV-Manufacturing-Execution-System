from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login
from .forms import UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth import logout

import logging
logger = logging.getLogger('common')

@login_required
def main_page(request):
    logger.info('main_page')
    return render(request, 'common/mes.html')

def login_view(request):
    if request.user.is_authenticated:
        return redirect('common:main')  # 이미 로그인한 사용자는 메인 페이지로 리다이렉트
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('common:main')  # 로그인 후 메인 페이지로 리다이렉트
        else:
            error_message = "Invalid username or password."
            return render(request, 'common/login.html', {'error_message': error_message})
    return render(request, 'common/login.html')

@require_http_methods(["GET", "POST"])
def logout_view(request):
    logout(request)
    messages.success(request, "Successfully logged out.")
    return redirect('common:main')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.set_password(form.cleaned_data['password'])
            user.is_active = False
            user.save()

            return render(request, 'common/registration_done.html')
    else:
        form = UserRegistrationForm()
    return render(request, 'common/register.html', {'form': form})