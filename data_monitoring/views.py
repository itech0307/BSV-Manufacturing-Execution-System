from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
import json
from collections import defaultdict
from django.db.models import Q
from .models import DryMix
from production_management.models import SalesOrder, ProductionPlan
from workforce_management.models import Worker
from inventory_management.models import RawMaterial

import logging
logger = logging.getLogger('data_monitoring')

@csrf_exempt
def input_drymix(request):
    if request.method == "POST":
        # POST 데이터에서 필요한 정보 가져오기
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        # machine_value = data.get('machine', '')  # 키오스크 기기 이름        
        worker_code = data.get('staffNumber', '')  # 작업자 직원번호
        logger.info(f"[KIOSK] DRYMIX DATA: {data}")
        # DryMix 결과를 ProductionPhase 모델에 저장
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    production_plan = ProductionPlan.objects.filter(sales_order=sales_order).order_by('-create_date').first()
                    # ProductionPhase 모델 인스턴스 생성
                    production_phase = DryMix(
                        sales_order=sales_order,
                        production_plan = production_plan,
                        mix_information=quantity_data,
                        worker_code=worker_code
                    )
                    production_phase.save()  # 인스턴스 저장
                    logger.info(f"[KIOSK] DRYMIX SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    # 오더 번호가 없는 경우 에러 처리
                    logger.info(f"[KIOSK] DRYMIX ERROR: {order['order_number']}")
            

        return JsonResponse({"status": "success", "message": "Data added successfully"})    
    
    qr_content = request.GET.get('qrContent')

    # Worker 모델에서 'DM' 부서의 직원 목록 가져오기
    dm_staff_list = list(Worker.objects.filter(department='DM').values('id', 'worker_code', 'name'))  # id와 name을 가져옵니다.

    # RawMaterial 모델에서 category의 고유한 값들을 가져옵니다.
    categories = list(RawMaterial.objects.values_list('category', flat=True).distinct())
    subitems = defaultdict(list)

    for category in categories:
        subitems[category] = list(RawMaterial.objects.filter(category=category).values_list('material_name', flat=True))

    # 가장 최근 입력한 생산 기록 호출
    latest_phase = DryMix.objects.select_related('production_plan').order_by('-create_date').first()

    # QR 코드 내용이 없는 경우, 일반 페이지 로드
    if not qr_content:
        context = {
            'categories': json.dumps(categories),
            'subitems': json.dumps(subitems),
            'dm_staff_list': json.dumps(dm_staff_list),
            'latest_phase':latest_phase
        }
        return render(request, 'data_monitoring/input_drymix.html', context)

    # QR 코드 내용이 있는 경우, order_number로 검색
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] DRYMIX CONNECTED: {qr_content}")
        if qr_content[:3] == "SOV":
            order = SalesOrder.objects.exclude(status=False).get(order_no=qr_content, status=None)
        #order = ProductionOrder.objects.filter(order_number=qr_content).latest('create_date')
        data = {
            'order_number': order.order_no,
            'order_information': order.order_information,
            'status': 'success',
            'message': 'Order found'
        }
    except order.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)
