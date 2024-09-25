from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, get_user_model
from .forms import UserRegistrationForm
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth import logout
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from .models import Profile
from django.contrib.auth.models import User
from django.conf import settings
import boto3
from botocore.exceptions import ClientError
from datetime import datetime, timezone
from django.http import HttpResponseForbidden

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
    #messages.success(request, "Successfully logged out.")
    return redirect('common:main')

def register(request):
    if request.method == 'POST':
        form = UserRegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.save()
            mail_subject = 'Activate your account.'
            message = render_to_string('common/account_activation_email.html', {
                'user': user,
                'domain': settings.base.DOMAIN,
                'uid': urlsafe_base64_encode(force_bytes(user.pk)),
                'token': user.profile.activation_token,
            })
            to_email = form.cleaned_data.get('email')
            email = EmailMessage(
                mail_subject, message, to=[to_email]
            )
            email.send()
            return render(request, 'common/registration_done.html')
    else:
        form = UserRegistrationForm()
    return render(request, 'common/register.html', {'form': form})

def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        User = get_user_model()
        user = User.objects.get(pk=uid)
    except(TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None
    if user is not None and str(user.profile.activation_token) == str(token):
        user.is_active = True
        user.profile.email_confirmed = True
        user.save()
        
        # 사용자를 인증하고 로그인합니다
        authenticated_user = authenticate(username=user.username, password=None)
        if authenticated_user is not None:
            login(request, authenticated_user)
        
        return redirect('common:main')
    else:
        return render(request, 'common/account_activation_invalid.html')

@login_required
def list_files(request):
    s3 = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    path = request.GET.get('path', '')

    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=path, Delimiter='/')
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})

    files = []
    directories = []

    if 'CommonPrefixes' in response:
        for obj in response['CommonPrefixes']:
            dir_name = obj['Prefix'].split('/')[-2]
            directories.append({'name': dir_name, 'path': obj['Prefix']})

    if 'Contents' in response:
        for obj in response['Contents']:
            if not obj['Key'].endswith('/'):
                file_name = obj['Key'].split('/')[-1]
                files.append({
                    'name': file_name,
                    'path': obj['Key'],
                    'size': obj['Size'],
                    'last_modified': obj['LastModified'],
                    'etag': obj['ETag'].strip('"')  # ETag can be used to identify the uploader
                })

    parent_directory = '/'.join(path.split('/')[:-2]) + '/' if path else None

    context = {
        'files': files,
        'directories': directories,
        'current_path': path,
        'parent_directory': parent_directory,
    }

    return render(request, 'common/file_browser.html', context)

@login_required
def upload_file(request):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        s3 = boto3.client('s3')
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        path = request.POST.get('path', '')
        
        try:
            s3.upload_fileobj(
                file, 
                bucket_name, 
                f"{path}{file.name}",
                ExtraArgs={
                    'Metadata': {'uploader': request.user.username}
                }
            )
        except ClientError as e:
            return render(request, 'common/error.html', {'error': str(e)})
        
    return redirect('list_files')

@login_required
def delete_file(request, file_path):
    s3 = boto3.client('s3')
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    try:
        # 파일 메타데이터를 가져와 업로더 확인
        response = s3.head_object(Bucket=bucket_name, Key=file_path)
        uploader = response['Metadata'].get('uploader')
        
        if uploader != request.user.username:
            return HttpResponseForbidden("You don't have permission to delete this file.")
        
        s3.delete_object(Bucket=bucket_name, Key=file_path)
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})
    
    return redirect('common:list_files')