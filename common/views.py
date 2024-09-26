from django.shortcuts import render, redirect
from django.urls import reverse
from urllib.parse import quote, unquote
from django.contrib.auth import authenticate, login, get_user_model
from .forms import UserRegistrationForm, ProfileForm
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import PasswordChangeForm
from django.contrib import messages
from django.views.decorators.http import require_http_methods
from django.contrib.auth import logout, update_session_auth_hash
from django.contrib.sites.shortcuts import get_current_site
from django.template.loader import render_to_string
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.core.mail import EmailMessage
from .models import Profile
from django.contrib.auth.models import User
from django.conf import settings
from django.utils.translation import gettext as _

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

from datetime import datetime, timezone
from django.http import HttpResponseForbidden
import os

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
def mypage(request):
    if request.method == 'POST':
        form = ProfileForm(request.POST, instance=request.user.profile)
        if form.is_valid():
            form.save()
            messages.success(request, 'Profile updated successfully.')
            return redirect('common:mypage')
    else:
        form = ProfileForm(instance=request.user.profile)
    
    return render(request, 'common/mypage.html', {'form': form})

@login_required
def change_password(request):
    if request.method == 'POST':
        form = PasswordChangeForm(request.user, request.POST)
        if form.is_valid():
            user = form.save()
            update_session_auth_hash(request, user)  # Important!
            messages.success(request, 'Your password was successfully updated!')
            return redirect('common:main')
        else:
            messages.error(request, 'Please correct the error below.')
    else:
        form = PasswordChangeForm(request.user)
    return render(request, 'common/change_password.html', {
        'form': form
    })

# 레포지토리 루트 설정
REPOSITORY_ROOT = 'repository/'  # S3 버킷 내의 레포지토리 경로

# S3 클라이언트 설정
s3_config = Config(
    region_name=settings.AWS_S3_REGION_NAME,
    signature_version='s3v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)
s3 = boto3.client('s3', config=s3_config)

@login_required
def list_files(request):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    path = request.GET.get('path', REPOSITORY_ROOT)

    # 경로가 레포지토리 루트 밖으로 나가지 않도록 보장
    if not path.startswith(REPOSITORY_ROOT):
        path = REPOSITORY_ROOT
    
    # 경로의 끝에 '/'가 없으면 추가
    if path and not path.endswith('/'):
        path += '/'

    try:
        response = s3.list_objects_v2(Bucket=bucket_name, Prefix=path, Delimiter='/')
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})

    files = []
    directories = []

    if 'CommonPrefixes' in response:
        for obj in response['CommonPrefixes']:
            dir_name = obj['Prefix'][len(path):].rstrip('/')
            directories.append({
                'name': dir_name,
                'path': quote(obj['Prefix'])
            })

    if 'Contents' in response:
        for obj in response['Contents']:
            if obj['Key'] != path:  # 현재 디렉토리 자체는 제외
                file_name = obj['Key'][len(path):]
                if not file_name.endswith('/'):  # 디렉토리는 제외
                    # 파일에 대한 임시 URL 생성
                    url = s3.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': obj['Key']},
                                                    ExpiresIn=3600,  # URL의 유효 시간을 1시간으로 설정
                                                    )
                    files.append({
                        'name': file_name,
                        'path': quote(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': url
                    })

    # Parent Directory 경로 계산
    parent_directory = os.path.dirname(path.rstrip('/'))
    if parent_directory.endswith('/'):
        parent_directory = parent_directory[:-1]
    
    # 레포지토리 루트에 있을 때는 parent_directory를 None으로 설정
    if parent_directory + REPOSITORY_ROOT == REPOSITORY_ROOT:
        parent_directory = None
    else:
        # parent_directory가 비어있지 않도록 보장
        parent_directory = parent_directory if parent_directory else REPOSITORY_ROOT

    # 현재 경로를 부분으로 나누기
    current_path_parts = []
    if path.startswith(REPOSITORY_ROOT):
        relative_path = path[len(REPOSITORY_ROOT):].strip('/')
        if relative_path:
            current_path_parts = relative_path.split('/')
    
    # 각 경로 부분에 대한 전체 경로 생성
    breadcrumbs = []
    cumulative_path = REPOSITORY_ROOT
    for part in current_path_parts:
        cumulative_path += part + '/'
        breadcrumbs.append({
            'name': part,
            'path': quote(cumulative_path)
        })

    context = {
        'files': files,
        'directories': directories,
        'current_path': path,
        'breadcrumbs': breadcrumbs,
        'parent_directory': parent_directory,
        'repository_root': REPOSITORY_ROOT,
        'is_superuser': request.user.is_superuser,  # 슈퍼유저 여부 추가
    }

    return render(request, 'common/file_browser.html', context)

@login_required
def upload_file(request):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        path = request.POST.get('path', REPOSITORY_ROOT)
        
        # 경로가 레포지토리 루트 밖으로 나가지 않도록 보장
        if not path.startswith(REPOSITORY_ROOT):
            path = REPOSITORY_ROOT
        
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
        
    # 현재 경로를 유지하면서 리다이렉트
    return redirect(f"{reverse('common:list_files')}?path={quote(path)}")

@login_required
def delete_file(request, file_path):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # 파일 경로가 레포지토리 루트 밖에 있으면 삭제를 허용하지 않음
    if not file_path.startswith(REPOSITORY_ROOT):
        return HttpResponseForbidden("You don't have permission to delete this file.")
    
    try:
        # 파일 메타데이터를 가져와 업로더 확인
        response = s3.head_object(Bucket=bucket_name, Key=file_path)
        uploader = response['Metadata'].get('uploader')
        
        if uploader != request.user.username:
            return HttpResponseForbidden("You don't have permission to delete this file.")
        
        s3.delete_object(Bucket=bucket_name, Key=file_path)
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})
    
    # 삭제 후 현재 디렉토리로 리다이렉트
    current_dir = os.path.dirname(file_path)
    return redirect(f"{reverse('common:list_files')}?path={current_dir}")

@login_required
def create_folder(request):
    if request.method == 'POST':
        folder_name = request.POST.get('folder_name')
        current_path = request.POST.get('current_path', REPOSITORY_ROOT)
        
        if not current_path.endswith('/'):
            current_path += '/'
        
        new_folder_path = f"{current_path}{folder_name}/"
        
        # S3에 빈 객체를 생성하여 폴더를 시뮬레이션합니다
        try:
            s3.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=new_folder_path)
        except ClientError as e:
            return render(request, 'common/error.html', {'error': str(e)})
        
    return redirect('common:list_files')