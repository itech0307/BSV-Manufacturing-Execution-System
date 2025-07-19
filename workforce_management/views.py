from django.shortcuts import render, get_object_or_404, redirect, resolve_url
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseNotAllowed, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Worker, WorkerComment
from .forms import WorkerForm, WorkerCommentForm
from django.conf import settings

from PIL import Image
import io
from botocore.exceptions import ClientError

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# Set the repository root
REPOSITORY_ROOT = 'profile_images/worker/'  # The repository path in the S3 bucket

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
def worker_list(request):
    page = request.GET.get('page', '1')  # Page
    kw = request.GET.get('kw', '')  # Search keyword
    list = Worker.objects.order_by('join_date')
    if kw:
        list = list.filter(
            Q(worker_code__icontains=kw) |  # Search by worker code
            Q(name__icontains=kw)    # Search by name
        ).distinct()
    
    # Create the profile image URL
    for worker in list:
        try:
            worker.profile_image_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
                },
                ExpiresIn=3600  # URL validity time (seconds)
            )
        except ClientError as e:
            print(f"S3 URL creation error: {e}")
            worker.profile_image_url = None
    
    paginator = Paginator(list, 10)  # Show 10 per page
    page_obj = paginator.get_page(page)
    context = {'list': page_obj, 'page': page, 'kw': kw}
    return render(request, 'workforce_management/worker_list.html', context)

@login_required
def worker_register(request):
    if request.method == 'POST':
        form = WorkerForm(request.POST, request.FILES)
        if form.is_valid():
            worker = form.save(commit=False)
            worker.worker_code = request.POST['worker_code']
            worker.name = request.POST['name']
            worker.phone_number = request.POST['phone_number']
            worker.department = request.POST['department']
            worker.position = request.POST['position']
            worker.join_date = request.POST['join_date']

            # Process the profile picture
            if 'profile_image' in request.FILES:
                image = request.FILES['profile_image']
                img = Image.open(image)
                img.thumbnail((400, 400))  # Adjust the image size
                
                # Convert the image to a byte stream
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                buffer.seek(0)

                # Upload to S3
                file_name = f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
                try:
                    s3.upload_fileobj(buffer, settings.AWS_STORAGE_BUCKET_NAME, file_name)
                    # Save the image path to the worker model
                    worker.profile_image = file_name
                except ClientError as e:
                    # Handle the error when the S3 upload fails
                    print(f"S3 upload error: {e}")
                    # You can display the error message to the user or log it.

            worker.save()
            return redirect('workforce_management:worker_list')
        else:
            # If the form data is invalid, display the error message and the form again.
            return render(request, 'workforce_management/worker_register.html', {'form': form})
    else:
        form = WorkerForm()
        return render(request, 'workforce_management/worker_register.html', {'form': form})

@login_required
def worker_detail(request, worker_id):
    if request.method == 'POST':
        # Check if request.body is empty
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
    
    worker = get_object_or_404(Worker, pk=worker_id)
    
    # Create the profile image URL
    try:
        worker.profile_image_url = s3.generate_presigned_url(
            'get_object',
            Params={
                'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                'Key': f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
            },
            ExpiresIn=3600
        )
    except ClientError as e:
        print(f"S3 URL creation error: {e}")
        worker.profile_image_url = None
    
    context = {
        'worker': worker
    }
    return render(request, 'workforce_management/worker_detail.html', context)
    
@login_required
def worker_modify(request, worker_id):
    worker = get_object_or_404(Worker, pk=worker_id)
    
    # Check if the user has admin privileges
    if not request.user.is_superuser:  # Check if the user has admin privileges
        messages.error(request, 'You do not have permission to edit.')
        return redirect('workforce_management:worker_detail', worker_id=worker_id)
    
    if request.method == "POST":
        form = WorkerForm(request.POST, request.FILES, instance=worker)
        if form.is_valid():
            worker = form.save(commit=False)
            
            # Process the profile picture
            if 'profile_image' in request.FILES:
                image = request.FILES['profile_image']
                img = Image.open(image)
                img.thumbnail((400, 400))
                
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                buffer.seek(0)

                file_name = f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
                try:
                    s3.upload_fileobj(buffer, settings.AWS_STORAGE_BUCKET_NAME, file_name)
                    worker.profile_image = file_name
                except ClientError as e:
                    print(f"S3 upload error: {e}")
                    messages.error(request, 'Profile image upload error.')
            
            worker.save()
            return redirect('workforce_management:worker_detail', worker_id=worker.id)
    else:
        form = WorkerForm(instance=worker)
    
    context = {
        'worker':worker,
        'form': form
    }
    return render(request, 'workforce_management/worker_register.html', context)

@login_required
def worker_comment_create(request, worker_code):
    worker = get_object_or_404(Worker, pk=worker_code)
    if request.method == "POST":
        form = WorkerCommentForm(request.POST)
        if form.is_valid():
            worker_comment = form.save(commit=False)
            worker_comment.author = request.user  # Save the login account to the author attribute
            worker_comment.worker = worker
            worker_comment.save()
            return redirect('{}#comment_{}'.format(
                resolve_url('workforce_management:worker_detail', worker_code=worker_comment.worker.worker_code), worker_comment.id))
    else:
        return HttpResponseNotAllowed('Only POST is possible.')
    context = {'worker': worker, 'form': form}
    return render(request, 'workforce_management/worker_detail.html', context)
