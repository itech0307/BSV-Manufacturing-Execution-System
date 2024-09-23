from django.shortcuts import render

from django.http import JsonResponse
from django.shortcuts import render
import pandas as pd
from .tasks import ordersheet_upload_celery

def order_sheet_upload(request):
    if request.method == 'POST':
        # 사용자가 업로드한 파일을 가져옴
        file = request.FILES['importData']
        
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
        
        return render(request, 'production_management/order_sheet_upload.html', {'task_id': task_id})

    content = {}
    return render(request, 'production_management/order_sheet_upload.html', content)