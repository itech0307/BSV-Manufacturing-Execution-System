from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
from django.utils import timezone
import json
from collections import defaultdict
from django.db.models import Q
from .models import DryMix, DryLine, Delamination, Inspection
from production_management.models import SalesOrder, ProductionPlan
from workforce_management.models import Worker
from inventory_management.models import RawMaterial

from django.utils.dateparse import parse_date
from itertools import chain

import pytz

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

def order_search(request):
    order_and_status = []
    count = 0
    order_numbers = []
    if request.method == 'POST':
        # request.body가 비어있는지 확인
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
        
        # JSON 데이터 파싱
        try:
            data = json.loads(request.body)
            action = data.get('action')
            if action == 'add_to_my_list':
                my_list = data.get('my_list')
                content = data.get('content')
                sales_order = SalesOrder.objects.exclude(status=False).get(order_no=my_list)
                
            #elif action == 'download_to_qrcard':
            #    order_numbers = data.get('order_numbers').split(',')
            #    sales_orders = SalesOrder.objects.exclude(status=False).filter(order_number__in=order_numbers)
            #    response = order_convert_to_qrcard(sales_orders)
                
            #    return response
        except:
            pass
        
        order_number = request.POST.get('order_number', '')
        order_number = order_number.replace(' ', '')
        order_number = order_number.replace('	', '')
        
        order_numbers = request.POST.get('order_numbers', '')
        
        if order_numbers:
            order_numbers = order_numbers.split(',')
            order_list = SalesOrder.objects.exclude(status=False).filter(order_no__in=order_numbers)
        else:
            order_list = SalesOrder.objects.exclude(status=False).filter(order_no__icontains=order_number)
    
        status = []
       
        # Order Number 마다 생산 진행 이력을 검색하기
        for order in order_list:
            process = []
            
            # 여러 모델에서 sales_order로 검색
            production_phases = list(chain(
                ProductionPlan.objects.filter(sales_order=order),
                DryMix.objects.filter(sales_order=order),
                DryLine.objects.filter(sales_order=order),
                Delamination.objects.filter(sales_order=order),
                Inspection.objects.filter(sales_order=order)
            ))
            
            bal_qty = int(order.order_qty)
            agrade_qty, delami_qty, pd_qty = 0, 0, 0
            sub_pd_qty = 0
            defect, chemical = {}, {}
            
            latest_process = latest_create_date = latest_machine = None
            
            if production_phases:
                for production_phase in production_phases:
                    create_date = production_phase.create_date.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if isinstance(production_phase, ProductionPlan):
                        phase_info = production_phase.pd_information
                        if production_phase.item_group == 'Dry':
                            
                            phase_info.update({
                                'process':'DryPlan',
                                'create_date': create_date,
                                'machine':production_phase.pd_line,
                                'plan_qty':production_phase.plan_qty,
                                'plan_date': production_phase.plan_date.strftime('%Y-%m-%d'),
                                })
                            process.append(phase_info)
                    
                    elif isinstance(production_phase, DryMix):
                        phase_info = production_phase.mix_information

                        for info in phase_info: # json 형식의 phase_information 의 정보 확인
                            if info.get('item', ''):
                                chemical[info.get('item')] = str(info.get('quantity')) + info.get('unit')
                        
                        process.append({
                            'process': 'DryMix',
                            'chemical':chemical,
                            'machine': '',
                            'create_date':create_date
                        })
                    
                    elif isinstance(production_phase, DryLine):
                        phase_info = production_phase.pd_information

                        process.append({
                            'process': 'DryLine',
                            'pd_qty': production_phase.pd_qty,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })
                    
                    elif isinstance(production_phase, Delamination):
                        phase_info = production_phase.delamination_information

                        process.append({
                            'process' : 'RP',
                            'delami_qty': production_phase.delamination_qty,
                            'create_date': create_date,
                            'machine': production_phase.line_no
                        })
                    
                    elif isinstance(production_phase, Inspection):
                        phase_info = production_phase.inspection_information
                        
                        sub_pd_qty = 0
                       
                        for info in phase_info:
                            defect[info.get('defectCause')] = info.get('quantity')
                        
                        agrade_qty = production_phase.inspection_qty
                        bal_qty = bal_qty - agrade_qty
                        
                        process.append({
                            'process' : 'Inspection',
                            'agrade_qty': agrade_qty,
                            'defect': defect,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })

            # create_date를 기준으로 프로세스 리스트 정렬
            process = sorted(process, key=lambda x: x['create_date'])

            # process 리스트에서 가장 최근의 process 이름과 create_date 찾기
            for proc in process:
                if not latest_create_date or proc['create_date'] > latest_create_date:
                    latest_create_date = proc['create_date']
                    latest_process = proc['process']
                    latest_machine = proc['machine']
            

            status.append(
                {
                    'bal_qty':bal_qty,
                    'line_shortage': sub_pd_qty - bal_qty,
                    'process':process,
                    'latest_process': latest_process,
                    'latest_create_date': latest_create_date,
                    'latest_machine' : latest_machine
                }
            )
        
        order_and_status = zip(order_list, status)
        count = len(order_list)

    context = {
        'order_and_status': order_and_status,
        'count': count
    }
    return render(request, 'data_monitoring/order_search.html', context)