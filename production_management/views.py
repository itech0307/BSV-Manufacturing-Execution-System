from django.shortcuts import render, get_object_or_404, redirect, resolve_url
from django.http import JsonResponse, HttpResponseNotAllowed
import pandas as pd
from .tasks import ordersheet_upload_celery, dryplan_convert_to_qrcard, dev_order_convert_to_qrcard
from .models import SalesOrder, SalesOrderUploadLog, Development, DevelopmentOrder, DevelopmentComment
import hashlib
from django.utils import timezone
from datetime import timedelta
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.paginator import Paginator
from django.contrib import messages
from .forms import DevelopmentForm, DevelopmentCommentForm
from django.views.decorators.csrf import csrf_exempt
from django.http import HttpResponseForbidden
from django.conf import settings
import json

import boto3
from botocore.exceptions import ClientError
from botocore.config import Config

# Set repository root path in S3 bucket
REPOSITORY_ROOT = 'development/'  # Repository path within the S3 bucket       

# S3 client configuration
s3_config = Config(
    region_name=settings.AWS_S3_REGION_NAME,
    signature_version='s3v4',
    retries={
        'max_attempts': 10,
        'mode': 'standard'
    }
)
s3 = boto3.client('s3', config=s3_config)

def is_production_team(user):
    return user.is_authenticated and user.profile.is_production_team()

@login_required
@user_passes_test(is_production_team)
def order_sheet_upload(request):
    if not request.user.is_authenticated:
        return redirect('common:login')
        
    thirty_days_ago = timezone.now() - timedelta(days=30)
    upload_logs = SalesOrderUploadLog.objects.filter(upload_time__gte=thirty_days_ago).order_by('-upload_time')
    try:
        if request.method == 'POST':
            # Get the file uploaded by the user
            file = request.FILES['importData']

            # Calculate file hash
            file_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)  # Move file pointer back to the beginning
            
            # Convert Excel file to Pandas DataFrame
            df = pd.read_excel(file, na_filter=False, sheet_name='Total received today')            
            # Remove rows with NaN values
            df = df.dropna()
            
            # Convert required columns to strings
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            # Convert DataFrame to JSON
            df_json = df.to_json()
            
            # Optional: Validate order sheet file
            # ordersheet_file_validation(df_json)
            
            # Start Celery task
            order_upload_task = ordersheet_upload_celery.delay(df_json)
            task_id = order_upload_task.task_id

            # Create SalesOrderUploadLog
            SalesOrderUploadLog.objects.create(
                user=request.user,
                file_name=file.name,
                file_hash=file_hash,
                data_count=len(df)
            )
            
            return render(request, 'production_management/order_sheet_upload.html', {'task_id': task_id})

    except Exception as e:
        # Print exception for debugging
        print(f"An error occurred: {e}")
        return JsonResponse({"error": "An error occurred while processing the file."})

    content = {
        'upload_logs': upload_logs,
    }
    return render(request, 'production_management/order_sheet_upload.html', content)

@login_required
@user_passes_test(is_production_team)
def dryplan_import(request):
    if not request.user.is_authenticated:
        return redirect('common:login')
        
    if request.method == 'POST':
        if not request.user.profile.is_production_team():
            return HttpResponseForbidden("You don't have permission to import dry plans.")
            
        # Check CSRF token
        if not request.POST.get('csrfmiddlewaretoken'):
            return HttpResponseForbidden('CSRF verification failed')
            
        try:
            file = request.FILES['importData']
            df = pd.read_excel(file, na_filter=False, sheet_name='plan', header=1)

            # Columns to get
            columns_needed = [
                3,  # Order Id
                4,  # Seq
                6,  # Customer
                11, # Brand
                12, # Item
                13, # Color
                14, # Pattern
                15, # Base
                17, # Order Qty
                36, # Remark
                0,  # Line
                2,  # Plan Date
                1,  # Plan No
                21, # Plan Qty
                16, # Skin/Binder
                24, # RP Qty
                35, # Plan Remark
                7,  # OrderType
            ]
            df = df.iloc[:, columns_needed]

            # Remove rows with empty Order Id
            df = df[df[df.columns[1]] != ""]

            # Convert data to string
            df = df.applymap(str)

            valid_orders = []
            invalid_orders = []  # Save rows and order numbers that do not exist

            for index, row in df.iterrows():
                order_no = f"{row.iloc[0]}-{row.iloc[1]}"  # Order Id + Seq
                if SalesOrder.objects.filter(order_no=order_no).exists():
                    valid_orders.append(row.to_dict())  # Save to valid list
                else:
                    invalid_orders.append({'row': index + 2, 'order_no': order_no})

            # Create QR for valid orders if any
            if valid_orders:
                df_valid = pd.DataFrame(valid_orders)
                df_json = df_valid.to_json()
                response = dryplan_convert_to_qrcard(df_json)
                
                if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                    import base64
                    
                    # Encode binary content to base64
                    file_content = base64.b64encode(response.content).decode('utf-8')
                    filename = response['Content-Disposition'].split('filename=')[1].strip('"')
                    
                    # Return response with encoded content
                    return JsonResponse({
                        'file_content': file_content,
                        'filename': filename,
                        'content_type': response['Content-Type'],
                        'invalid_orders': invalid_orders
                    })
                return response

            # If there are only invalid orders
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'invalid_orders': invalid_orders})
            return render(request, 'production_management/dryplan_import.html', {
                'invalid_orders': invalid_orders
            })

        except Exception as e:
            if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
                return JsonResponse({'error': str(e)})
            return JsonResponse({'error': str(e)})

    return render(request, 'production_management/dryplan_import.html')

@login_required
def development_list(request):
    kw = request.GET.get('kw', '')
    field = request.GET.get('field', 'title')
    page = request.GET.get('page', '1')

    if field == 'dev_no':
        development_list = Development.objects.filter(id__icontains=kw)
    elif field == 'purpose':
        development_list = Development.objects.filter(purpose__icontains=kw)
    elif field == 'title':
        development_list = Development.objects.filter(title__icontains=kw)
    elif field == 'developer':
        development_list = Development.objects.filter(developer__username__icontains=kw)
    else:
        development_list = Development.objects.all()

    # Sort by id in descending order
    development_list = development_list.order_by('-id')

    paginator = Paginator(development_list, 10)  # Show 10 per page
    page_obj = paginator.get_page(page)
    context = {'development_list': page_obj, 'page': page, 'kw': kw, 'field': field}
    return render(request, 'production_management/development.html', context)

DEVELOPMENT_ROOT = 'development/'

@login_required
def development_detail(request, development_id):
    if request.method == 'POST':
        # Check if request.body is empty
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
        
                # Parse JSON data
        try:
            data = json.loads(request.body)
            action = data.get('action')
            if action == 'download_to_qrcard':
                order_numbers = data.get('order_numbers').split(',')
                development = Development.objects.get(id=development_id)
                development_orders = DevelopmentOrder.objects.filter(order_no__in=order_numbers)
                development_and_orders = zip([development] * len(development_orders), development_orders)
                response = dev_order_convert_to_qrcard(development_and_orders)
                
                return response
        except:
            pass
    
    development = get_object_or_404(Development, pk=development_id)
    
    # Get item, color, pattern information from DevelopmentOrder
    orders = DevelopmentOrder.objects.filter(development=development)

    # Get file list
    path = f"{DEVELOPMENT_ROOT}{development_id}/"
    files = []
    try:
        response = s3.list_objects_v2(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Prefix=path, Delimiter='/')
        if 'Contents' in response:
            for obj in response['Contents']:
                if obj['Key'] != path:  # Current directory itself is excluded
                    file_name = obj['Key'][len(path):]
                    url = s3.generate_presigned_url('get_object',
                                                    Params={'Bucket': settings.AWS_STORAGE_BUCKET_NAME, 'Key': obj['Key']},
                                                    ExpiresIn=3600)
                    files.append({
                        'name': file_name,
                        'size': obj['Size'],
                        'last_modified': obj['LastModified'],
                        'url': url
                    })
    except ClientError as e:
        # Error handling (e.g., log recording)
        print(f"Error fetching files: {str(e)}")
    
    context = {
        'development': development,
        'orders': orders,
        'files': files,
    }
    return render(request, 'production_management/development_detail.html', context)

@login_required
def development_register(request):
    if request.method == 'POST':
        form = DevelopmentForm(request.POST)
        if form.is_valid():
            development = form.save(commit=False)
            development.developer = request.user  # Save login account to developer attribute
            development.content = request.POST['content']

            development.save()

            # Create folder in S3 bucket
            folder_name = f"{REPOSITORY_ROOT}{development.id}/"
            try:
                s3.put_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=folder_name)
            except ClientError as e:
                print(f"Error creating folder: {e}")
            
            item_names = request.POST.getlist('item_name[]')
            color_codes = request.POST.getlist('color_code[]')
            patterns = request.POST.getlist('pattern[]')
            specs = request.POST.getlist('spec[]')
            order_qtys = request.POST.getlist('order_qty[]')
            order_remarks = request.POST.getlist('order_remark[]')
            product_groups = request.POST.getlist('product_group[]')
            
            # Combine information into one array
            combined_info = zip(item_names, color_codes, patterns, specs, order_qtys, order_remarks, product_groups)
            
            for info in combined_info:
                item_name, color_code, pattern, spec, order_qty, order_remark, product_group = info
                order = DevelopmentOrder(
                    development=development,
                    item_name=item_name,
                    color_code=color_code,
                    pattern=pattern,
                    spec=spec,
                    order_qty=order_qty,
                    qty_unit='m',
                    order_remark=order_remark,
                    product_group=product_group
                    )
                order.save()
            
            return redirect('production_management:development_list')
        else:
            # If form data is invalid, show the form again with an error message
            return render(request, 'production_management/development_register.html', {'form': form})
    else:
        form = DevelopmentForm()  # Create empty form for GET request
        return render(request, 'production_management/development_register.html', {'form': form})

@login_required
def development_modify(request, development_id):
    development = get_object_or_404(Development, pk=development_id)
    if request.user != development.developer:
        messages.error(request, 'You do not have permission to edit')
        return redirect('production_management:development_detail', development_id=development.id)
    
    # Initialize orders variable
    orders = DevelopmentOrder.objects.filter(development=development)
    
    if request.method == "POST":
        form = DevelopmentForm(request.POST, instance=development)
        if form.is_valid():
            development = form.save(commit=False)
            development.save()

            # Delete existing orders and save new orders
            DevelopmentOrder.objects.filter(development=development).delete()
            
            items = request.POST.getlist("item_name[]")
            colors = request.POST.getlist("color_code[]")
            patterns = request.POST.getlist("pattern[]")
            order_qtys = request.POST.getlist("order_qty[]")
            specs = request.POST.getlist("spec[]")
            order_remarks = request.POST.getlist("order_remark[]")
            product_groups = request.POST.getlist("product_group[]")
            
            # Combine information into one array
            combined_info = zip(items, colors, patterns, order_qtys, specs, order_remarks, product_groups)
            
            for info in combined_info:
                item_name, color_code, pattern, order_qty, spec, order_remark, product_group = info
                order = DevelopmentOrder(
                    development=development,
                    item_name=item_name,
                    color_code=color_code,
                    pattern=pattern,
                    spec=spec,
                    order_qty=order_qty,
                    qty_unit='m',
                    order_remark=order_remark,
                    product_group=product_group
                    )
                order.save()

            return redirect('production_management:development_detail', development_id=development.id)
    else:
        form = DevelopmentForm(instance=development)
    
    context = {
        'development':development,
        'form': form,
        'orders': orders,
        'purpose': development.purpose,
        'remark': development.content,
    }
    return render(request, 'production_management/development_register.html', context)

@login_required
def development_delete(request, development_id):
    development = get_object_or_404(Development, pk=development_id)
    if request.user != development.developer:
        messages.error(request, 'You do not have permission to delete')
        return redirect('production_management:development_detail', development_id=development.id)
    development.delete()
    return redirect('production_management:development_list')

@login_required
def development_comment_create(request, development_id):
    development = get_object_or_404(Development, pk=development_id)
    if request.method == "POST":
        form = DevelopmentCommentForm(request.POST)
        if form.is_valid():
            development_comment = form.save(commit=False)
            development_comment.user = request.user  # Save login account to user attribute
            development_comment.development = development
            
            development_comment.save()
            
            return redirect('{}#comment_{}'.format(
                resolve_url('production_management:development_detail', development_id=development_comment.development.id), development_comment.id))
    else:
        return HttpResponseNotAllowed('Only POST is possible.')
    context = {'development': development, 'form': form}
    return render(request, 'production_management/development_detail.html', context)

@login_required
def development_comment_modify(request, development_comment_id):
    development_comment = get_object_or_404(DevelopmentComment, pk=development_comment_id)
    if request.user != development_comment.user:
        messages.error(request, 'This is not your comment')
        return redirect('production_management:development_detail', development_id=development_comment.development.id)
    if request.method == "POST":
        form = DevelopmentCommentForm(request.POST, instance=development_comment)
        if form.is_valid():
            development_comment = form.save(commit=False)
            
            development_comment.save()
            return redirect('{}#comment_{}'.format(
                resolve_url('production_management:development_detail', development_id=development_comment.development.id), development_comment.id))
    else:
        form = DevelopmentCommentForm(instance=development_comment)
    context = {'development_comment': development_comment, 'form': form}
    return render(request, 'production_management/comment.html', context)

@login_required
def development_comment_delete(request, development_comment_id):
    development_comment = get_object_or_404(DevelopmentComment, pk=development_comment_id)
    if request.user != development_comment.user:
        messages.error(request, 'This is not your comment')
    else:
        development_comment.delete()
    return redirect('production_management:development_detail', development_id=development_comment.development.id)

@csrf_exempt
def update_status(request, development_id):
    if request.method == 'POST':
        try:
            development = Development.objects.get(id=development_id)
            if request.user == development.developer:
                data = json.loads(request.body)
                new_status = data.get('status')
                if new_status in ['Progress', 'Complete']:
                    development.status = new_status
                    development.save()
                    return JsonResponse({'success': True})
                else:
                    return JsonResponse({'success': False, 'error': 'Invalid status'})
            else:
                return JsonResponse({'success': False, 'error': 'Unauthorized'})
        except Development.DoesNotExist:
            return JsonResponse({'success': False, 'error': 'Development not found'})
    return JsonResponse({'success': False, 'error': 'Invalid request method'})

@login_required
def upload_development_file(request, development_id):
    if request.method == 'POST' and request.FILES['file']:
        file = request.FILES['file']
        path = f"{DEVELOPMENT_ROOT}{development_id}/{file.name}"
        
        try:
            s3.upload_fileobj(
                file, 
                settings.AWS_STORAGE_BUCKET_NAME, 
                path,
                ExtraArgs={
                    'Metadata': {'uploader': request.user.username}
                }
            )
        except ClientError as e:
            return render(request, 'common/error.html', {'error': str(e)})
        
    return redirect('production_management:development_detail', development_id=development_id)

@login_required
def delete_development_file(request, development_id, file_name):
    path = f"{DEVELOPMENT_ROOT}{development_id}/{file_name}"
    
    try:
        # Get file metadata to check uploader
        response = s3.head_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=path)
        uploader = response['Metadata'].get('uploader')
        
        if uploader != request.user.username:
            return HttpResponseForbidden("You don't have permission to delete this file.")
        
        s3.delete_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=path)
    except ClientError as e:
        return render(request, 'common/error.html', {'error': str(e)})
    
    return redirect('production_management:development_detail', development_id=development_id)