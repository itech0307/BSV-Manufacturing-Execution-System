from django.shortcuts import render, get_object_or_404, redirect, resolve_url
from django.utils import timezone
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.http import HttpResponseNotAllowed, JsonResponse
from django.core.paginator import Paginator
from django.db.models import Q
from .models import Worker, WorkerComment
from .forms import WorkerForm, WorkerCommentForm

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
    
    context = {
        'worker': worker
    }
    return render(request, 'workforce_management/worker_detail.html', context)
    
@login_required
def worker_modify(request, worker_code):
    worker = get_object_or_404(Worker, worker_code=worker_code)
    
    # 관리자 권한을 확인합니다.
    if not request.user.is_superuser:  # 일반적으로 admin 대신 superuser 체크를 사용
        messages.error(request, 'You do not have permission to edit.')
        return redirect('workforce_management:worker_detail', worker_code=worker_code)
    
    if request.method == "POST":
        form = WorkerForm(request.POST, request.FILES, instance=worker)
        if form.is_valid():
            worker = form.save(commit=False)
            worker.save()

            return redirect('workforce_management:worker_detail', worker_code=worker_code)
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
