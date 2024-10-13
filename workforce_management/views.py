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

# 레포지토리 루트 설정
REPOSITORY_ROOT = 'profile_images/worker/'  # S3 버킷 내의 레포지토리 경로

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
def worker_list(request):
    page = request.GET.get('page', '1')  # 페이지
    kw = request.GET.get('kw', '')  # 검색어
    list = Worker.objects.order_by('join_date')
    if kw:
        list = list.filter(
            Q(worker_code__icontains=kw) |  # Worker 코드 검색
            Q(name__icontains=kw)    # 이름 검색
        ).distinct()
    
    # 프로필 이미지 URL 생성
    for worker in list:
        try:
            worker.profile_image_url = s3.generate_presigned_url(
                'get_object',
                Params={
                    'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
                    'Key': f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
                },
                ExpiresIn=3600  # URL 유효 시간 (초)
            )
        except ClientError as e:
            print(f"S3 URL 생성 오류: {e}")
            worker.profile_image_url = None
    
    paginator = Paginator(list, 10)  # 페이지당 10개씩 보여주기
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

            # 프로필 사진 처리
            if 'profile_image' in request.FILES:
                image = request.FILES['profile_image']
                img = Image.open(image)
                img.thumbnail((400, 400))  # 이미지 크기 조정
                
                # 이미지를 바이트 스트림으로 변환
                buffer = io.BytesIO()
                img.save(buffer, format='JPEG')
                buffer.seek(0)

                # S3에 업로드
                file_name = f'{REPOSITORY_ROOT}{worker.worker_code}.jpg'
                try:
                    s3.upload_fileobj(buffer, settings.AWS_STORAGE_BUCKET_NAME, file_name)
                    # 워커 모델에 이미지 경로 저장
                    worker.profile_image = file_name
                except ClientError as e:
                    # S3 업로드 실패 시 에러 처리
                    print(f"S3 upload error: {e}")
                    # 에러 메시지를 사용자에게 표시하거나 로깅할 수 있습니다.

            worker.save()
            return redirect('workforce_management:worker_list')
        else:
            # Form 데이터가 유효하지 않으면, 에러 메시지와 함께 다시 form을 보여줍니다.
            return render(request, 'workforce_management/worker_register.html', {'form': form})
    else:
        form = WorkerForm()
        return render(request, 'workforce_management/worker_register.html', {'form': form})

@login_required
def worker_detail(request, worker_code):
    if request.method == 'POST':
        # request.body가 비어있는지 확인
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
    
    worker = get_object_or_404(Worker, pk=worker_code)
    
    # 프로필 이미지 URL 생성
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
        print(f"S3 URL 생성 오류: {e}")
        worker.profile_image_url = None
    
    context = {
        'worker': worker
    }
    return render(request, 'workforce_management/worker_detail.html', context)
    
@login_required
def worker_modify(request, worker_code):
    worker = get_object_or_404(Worker, pk=worker_code)
    
    # 관리자 권한을 확인합니다.
    if not request.user.is_superuser:  # 일반적으로 admin 대신 superuser 체크를 사용
        messages.error(request, 'You do not have permission to edit.')
        return redirect('workforce_management:worker_detail', worker_code=worker_code)
    
    if request.method == "POST":
        form = WorkerForm(request.POST, request.FILES, instance=worker)
        if form.is_valid():
            worker = form.save(commit=False)
            worker.save()

            return redirect('workforce_management:worker_detail', worker_code=worker.worker_code)
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
            worker_comment.author = request.user  # author 속성에 로그인 계정 저장
            worker_comment.worker = worker
            worker_comment.save()
            return redirect('{}#comment_{}'.format(
                resolve_url('workforce_management:worker_detail', worker_code=worker_comment.worker.worker_code), worker_comment.id))
    else:
        return HttpResponseNotAllowed('Only POST is possible.')
    context = {'worker': worker, 'form': form}
    return render(request, 'workforce_management/worker_detail.html', context)
