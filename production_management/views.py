from django.shortcuts import render
from django.http import JsonResponse
import pandas as pd
from .tasks import ordersheet_upload_celery, dryplan_convert_to_qrcard
from .models import SalesOrderUploadLog
import hashlib
from django.utils import timezone
from datetime import timedelta

def order_sheet_upload(request):
    thirty_days_ago = timezone.now() - timedelta(days=30)
    upload_logs = SalesOrderUploadLog.objects.filter(upload_time__gte=thirty_days_ago).order_by('-upload_time')
    try:
        if request.method == 'POST':
            # 사용자가 업로드한 파일을 가져옴
            file = request.FILES['importData']

            # 파일 해시 계산
            file_hash = hashlib.sha256(file.read()).hexdigest()
            file.seek(0)  # 파일 포인터를 다시 처음으로 이동
            
            # 엑셀 파일을 Pandas 데이터프레임으로 변환
            df = pd.read_excel(file, na_filter=False, sheet_name='Total received today')            
            # NaN 값을 가진 행 제거
            df = df.dropna()
            
            # 필요한 열만 문자열로 변환
            for col in df.columns:
                df[col] = df[col].astype(str)
            
            # 데이터프레임을 JSON으로 변환
            df_json = df.to_json()
            
            # 주문 파일 검증 (선택적)
            # ordersheet_file_validation(df_json)
            
            # Celery 작업 시작
            order_upload_task = ordersheet_upload_celery.delay(df_json)
            task_id = order_upload_task.task_id

            # SalesOrderUploadLog 생성
            SalesOrderUploadLog.objects.create(
                user=request.user,
                file_name=file.name,
                file_hash=file_hash,
                data_count=len(df)
            )

            context = {
                'upload_logs': upload_logs,
            }
            
            return render(request, 'production_management/order_sheet_upload.html', {'task_id': task_id}, context)

    except Exception as e:
        # 디버깅을 위해 예외를 로그에 출력
        print(f"에러가 발생했습니다: {e}")
        return JsonResponse({"error": "파일 처리 중 에러가 발생했습니다."})

    content = {}
    return render(request, 'production_management/order_sheet_upload.html', content)

def dryplan_import(request):
    if request.method == 'POST':
        try:
            file = request.FILES['importData']
            df = pd.read_excel(file, na_filter=False, sheet_name='plan', header=1)
            
            # 필요한 열만 선택하기
            columns_needed = [
                3, # Order Id
                4, # Seq
                6, # Customer
                11, # Bran
                12, # Item
                13, # Color
                14, # Pattern
                15, # Base
                17, # Order Qty
                36, # Remark
                0, # Line
                2, # Plan Date
                1, # Plan No
                21, # Plan Qty
                16, # Skin/Binder
                24, # RP Qty
                35, # Plan Remark
                7, # OrderType
                ]
            df = df.iloc[:, columns_needed]
            
            # 두 번째 열(order id)이 빈 문자열인 행만 제거
            df = df[df[df.columns[1]] != ""]
           
            df = df.applymap(str)
            df_json = df.to_json()
            response = dryplan_convert_to_qrcard(df_json)
            return response
        except Exception as e:
            return JsonResponse({'error': str(e)})

    return render(request, 'production_management/dryplan_import.html')