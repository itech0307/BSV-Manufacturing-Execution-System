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
        return redirect('common:main')  # If the user is already logged in, redirect to the main page
    if request.method == 'POST':
        username = request.POST['username']
        password = request.POST['password']
        user = authenticate(request, username=username, password=password)
        if user is not None:
            login(request, user)
            return redirect('common:main')  # After logging in, redirect to the main page
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
        
        # Authenticate the user and log in
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

# Set the repository root
REPOSITORY_ROOT = 'repository/'  # The repository path in the S3 bucket

# Set the S3 client
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

    # Ensure the path does not go outside the repository root
    if not path.startswith(REPOSITORY_ROOT):
        path = REPOSITORY_ROOT
    
    # If the path does not end with '/', add it
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
            if obj['Key'] != path:  # The current directory itself is excluded
                file_name = obj['Key'][len(path):]
                if not file_name.endswith('/'):  # Directories are excluded
                    # Create a temporary URL for the file
                    url = s3.generate_presigned_url('get_object',
                                                    Params={'Bucket': bucket_name, 'Key': obj['Key']},
                                                    ExpiresIn=3600,  # Set the validity time of the URL to 1 hour
                                                    )
                    files.append({
                        'name': file_name,
                        'path': quote(obj['Key']),
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': url
                    })

    # Calculate the parent directory path
    parent_directory = os.path.dirname(path.rstrip('/'))
    if parent_directory.endswith('/'):
        parent_directory = parent_directory[:-1]
    
    # When the parent directory is in the repository root, set parent_directory to None
    if parent_directory + REPOSITORY_ROOT == REPOSITORY_ROOT:
        parent_directory = None
    else:
            # Ensure parent_directory is not empty
        parent_directory = parent_directory if parent_directory else REPOSITORY_ROOT

    # Divide the current path into parts
    current_path_parts = []
    if path.startswith(REPOSITORY_ROOT):
        relative_path = path[len(REPOSITORY_ROOT):].strip('/')
        if relative_path:
            current_path_parts = relative_path.split('/')
    
    # Create the full path for each path part
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
        'is_superuser': request.user.is_superuser,  # Add superuser status
    }

    return render(request, 'common/file_browser.html', context)

@login_required
def upload_file(request):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        bucket_name = settings.AWS_STORAGE_BUCKET_NAME
        path = request.POST.get('path', REPOSITORY_ROOT)
        
        # Ensure the path does not go outside the repository root
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
        
    # Redirect while keeping the current path
    return redirect(f"{reverse('common:list_files')}?path={quote(path)}")

@login_required
def delete_file(request, file_path):
    bucket_name = settings.AWS_STORAGE_BUCKET_NAME
    
    # Do not allow deletion if the file path is outside the repository root
    if not file_path.startswith(REPOSITORY_ROOT):
        return HttpResponseForbidden("You don't have permission to delete this file.")
    
    try:
        # Get the file metadata and check the uploader
        response = s3.head_object(Bucket=bucket_name, Key=file_path)
        uploader = response['Metadata'].get('uploader')
        
        if uploader != request.user.username:
            return HttpResponseForbidden("You don't have permission to delete this file.")
        
        s3.delete_object(Bucket=bucket_name, Key=file_path)
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})
    
    # Redirect to the current directory after deletion
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
        
        # Create an empty object in S3 to simulate a folder
        try:
            s3.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=new_folder_path)
        except ClientError as e:
            return render(request, 'common/error.html', {'error': str(e)})
        
    return redirect('common:list_files')