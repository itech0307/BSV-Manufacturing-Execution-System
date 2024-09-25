from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
import json
from collections import defaultdict
from django.db.models import Q
from .models import DryMix, DryLine, Delamination, Inspection, ProductionLot
from production_management.models import SalesOrder, ProductionPlan
from workforce_management.models import Worker
from inventory_management.models import RawMaterial, Category

from django.utils.dateparse import parse_date
from itertools import chain
import datetime
import pytz
from .tasks import order_convert_to_qrcard

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
                        production_plan = production_plan,
                        mixing_information=quantity_data,
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
    categories = list(Category.objects.values_list('category_name', flat=True).distinct())
    subitems = defaultdict(list)
    for category in categories:
        subitems[category] = list(RawMaterial.objects.filter(category__category_name=category).values_list('material_name', flat=True))

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
            'order_information': {
                'item': order.item_name,
                'pattern': order.pattern,
                'color_code': order.color_code,
                'customer': order.customer_name,
                'order_qty': order.order_qty,
                'order_type': order.order_type,
                'brand': order.brand,
                'qty_unit': order.qty_unit
            },
            'status': 'success',
            'message': 'Order found'
        }
    except order.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_dryline(request):
    machine = request.GET.get('machine', None)    
    
    # 생산량이 입력되었을 때
    if request.method == "POST":
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')  # machine 값 추가
        
        logger.info(f"[KIOSK] DRYLINE DATA: {data}")
        
        # DryLine 결과를 ProductionPhase 모델에 저장
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    production_plan = ProductionPlan.objects.filter(sales_order=sales_order).order_by('-create_date').first()
                    
                    # 가장 최근에 생산된 이력 찾기
                    production_phase = DryLine.objects.filter(
                            production_plan=production_plan
                    ).order_by('-create_date').first()
                    
                    if production_phase is None or production_phase.pd_lot is not None or production_phase.ag_position is not None: # 이력이 없거나 생산 Roll이 확인된 경우, 신규 Lot 추가
                        production_phase = DryLine.objects.create(
                            production_plan=production_plan,
                            pd_qty=quantity_data,
                            line_no=machine_value,
                            create_date=timezone.now()
                        )
                    elif production_phase is not None and (production_phase.pd_lot is None and production_phase.ag_position is None): # 생산된 이력이 있고, Roll이 미확인된 경우, 기존 Lot에 업데이트 
                        production_phase = DryLine.objects.update_or_create(
                            id=production_phase.id, # 가장 최근 생산된 Lot에 업데이트
                            production_plan=production_plan,
                            defaults={
                                'pd_qty' : quantity_data,
                                'line_no' : machine_value,
                                'create_date': timezone.now()
                            }
                        )                    
                    logger.info(f"[KIOSK] DRYLINE SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    logger.info(f"[KIOSK] DRYLINE ERROR: {order['order_number']}")

        return JsonResponse({"status": "success", "message": "Data added successfully"})    
    
    # QR code 정보 호출
    qr_content = request.GET.get('qrContent')

    # QR 코드 내용이 없는 경우, 일반 페이지 로드
    if not qr_content:
        context = {}
        return render(request, 'data_monitoring/input_dryline.html', context)

    # QR 코드 내용이 있는 경우, order_number로 검색
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] DRYLINE CONNECTED: {qr_content}")
        if qr_content[:3] == "SOV":
            order = SalesOrder.objects.exclude(status=False).get(order_no=qr_content)
        data = {
            'order_number': order.order_no,
            'order_information': {
                'item': order.item_name,
                'pattern': order.pattern,
                'color_code': order.color_code,
                'customer': order.customer_name,
                'order_qty': order.order_qty,
                'order_type': order.order_type,
                'brand': order.brand,
                'qty_unit': order.qty_unit
            },
            'status': 'success',
            'message': 'Order found'
        }
    except order.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_rp(request):
    machine = request.GET.get('machine', None)
    if request.method == "POST":
        # POST 데이터에서 필요한 정보 가져오기
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')  # machine 값 추가

        quantity_info = []
        logger.info(f"[KIOSK] RP DATA: {data}")
        
        # RP 결과를 ProductionPhase 모델에 저장
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    production_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    last_phase = DryLine.objects.filter(production_plan__sales_order=production_order).order_by('-create_date').first()
                    
                    if last_phase:
                        last_phase_plan = last_phase.production_plan
                    else:
                        last_phase_plan = None
                    
                    # 가장 최근에 생산된 이력 찾기
                    production_phase = Delamination.objects.filter(
                            production_plan=last_phase_plan
                    ).order_by('-create_date').first()
                    
                    if production_phase is None or production_phase.dlami_lot is not None: # 이력이 없거나 생산 Roll이 확인된 경우, 신규 Lot 추가
                        production_phase = Delamination.objects.create(
                            production_plan=last_phase_plan,
                            dlami_qty=quantity_data,
                            line_no=machine_value,
                            create_date=timezone.now()
                        )
                    elif production_phase is not None and production_phase.dlami_lot is None: # 생산된 이력이 있고, Roll이 미확인된 경우, 기존 Lot에 업데이트 
                        production_phase = Delamination.objects.update_or_create(
                            id=production_phase.id, # 가장 최근 생산된 Lot에 업데이트
                            production_plan=last_phase_plan,
                            defaults={
                                'dlami_qty' : quantity_data,
                                'line_no' : machine_value,
                                'create_date': timezone.now()
                            }
                        )
                    logger.info(f"[KIOSK] RP SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    # 오더 번호가 없는 경우 에러 처리
                    logger.info(f"[KIOSK] RP ERROR: {order['order_number']}")
                

        return JsonResponse({"status": "success", "message": "Data added successfully"})    
    
    qr_content = request.GET.get('qrContent')

    # QR 코드 내용이 없는 경우, 일반 페이지 로드
    if not qr_content:
        context = {}
        return render(request, 'data_monitoring/input_rp.html', context)

    # QR 코드 내용이 있는 경우, order_number로 검색
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] RP CONNECTED: {qr_content}")
        if qr_content[:3] == "SOV":
            order = SalesOrder.objects.exclude(status=False).get(order_no=qr_content)
        data = {
            'order_number': order.order_no,
            'order_information': {
                'item': order.item_name,
                'pattern': order.pattern,
                'color_code': order.color_code,
                'customer': order.customer_name,
                'order_qty': order.order_qty,
                'order_type': order.order_type,
                'brand': order.brand,
                'qty_unit': order.qty_unit
            },
            'status': 'success',
            'message': 'Order found'
        }
    except order.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_inspection(request):
    machine = request.GET.get('machine', None)
    if request.method == "POST":
        # POST 데이터에서 필요한 정보 가져오기
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')  # 키오스크 기기 이름
        logger.info(f"[KIOSK] INSPECTION DATA: {data}")
        
        a_qty = 0
        defect = []
        for item in quantity_data:
            if item.get('Grade') == 'A':
                a_qty = int(item.get('quantity', 0))
            else:
                defect.append({
                    'quantity': int(item.get('quantity', 0)),
                    'defectCause': item.get('defectCause')
                })
        
        # Inspection 결과를 ProductionPhase 모델에 저장
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    last_phase = Inspection.objects.filter(production_plan__sales_order=sales_order).order_by('-create_date').first()
                    
                    if last_phase:
                        last_phase_plan = last_phase.production_plan
                    else:
                        last_phase_plan = None
                    
                    # ProductionPhase 모델 인스턴스 생성
                    production_phase = Inspection(
                        sales_order=sales_order,
                        production_plan=last_phase_plan,
                        ins_qty=a_qty,
                        ins_information=defect,
                        create_date=timezone.now()
                    )
                    production_phase.save()  # 인스턴스 저장
                    logger.info(f"[KIOSK] INSPECTION SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    logger.info(f"[KIOSK] INSPECTION ERROR: {order['order_number']}")

        return JsonResponse({"status": "success", "message": "Data added successfully"})
    
    qr_content = request.GET.get('qrContent')

    # 불량 원인 가져오기
    #defect_cause = Information.objects.filter(name='defect_cause').order_by('-modify_date').first()

    defect_cause = {
        "Shiny": "Bóng",
        "Stain": "Loang Màu",
        "Stock": "Stock",
        "Folding": "Quấn Nhăn",
        "Pinhole": "Lỗ Kim",
        "RP Line": "R/P Xước",
        "Shortage": "Số Lượng Thiếu",
        "RP Overlap": "R/P Nhăn",
        "Wrong Base": "Da Sai",
        "Surface Line": "Xước",
        "Air Expansion": "Phồng Hơi",
        "Contamination": "Dơ",
        "Color Mismatch": "Màu Sai",
        "Fabric Overlap": "Da Nhăn",
        "Base Transparency": "Đốm"
    }

    # QR 코드 내용이 없는 경우, 일반 페이지 로드
    if not qr_content:
        context = {'defect_cause':json.dumps(defect_cause)}
        return render(request, 'data_monitoring/input_inspection.html', context)

    # QR 코드 내용이 있는 경우, order_number로 검색
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] INSPECTION CONNECTED: {qr_content}")
        order = SalesOrder.objects.exclude(status=False).get(order_no=qr_content)
        data = {
            'order_number': order.order_no,
            'order_information': {
                'item': order.item_name,
                'pattern': order.pattern,
                'color_code': order.color_code,
                'customer': order.customer_name,
                'order_qty': order.order_qty,
                'order_type': order.order_type,
                'brand': order.brand,
                'qty_unit': order.qty_unit
            },
            'status': 'success',
            'message': 'Order found'
        }
    except order.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@login_required
@csrf_protect
def aging_room(request):
    context = {}
    now = datetime.datetime.now()

    if request.method == 'POST':
        action = request.POST.get('action')
        
        if action == 'search':
            inside_order_no = "SOV0" + request.POST.get('inside_order_number')
            outside_order_no = "SOV0" + request.POST.get('outside_order_number')

            logger.info(f"[AGING ROOM] ORDER SEARCH: INSIDE {inside_order_no} / OUTSIDE {outside_order_no}")

            inside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
            outside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()

            if inside_product is not None and outside_product is not None:
                if inside_product.line_no == outside_product.line_no:
                    line = inside_product.line_no
                    inside_product_time = inside_product.create_date
                    outside_product_time = outside_product.create_date
                    initial_list = DryLine.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))

                    # Python으로 추가 필터링 수행
                    filtered_list = [item for item in initial_list if item.line_no == line]
                else:
                    filtered_list = None
            else:
                filtered_list = None

            context = {
                'list': filtered_list,
                'inside_order_number': inside_order_no,
                'outside_order_number': outside_order_no,
                'now': now
            }

        elif action == 'register':
            aging_position = request.POST.get('aging_position')
            formatted_aging_position = aging_position.replace(" ", "").upper()
            inside_order_no = request.POST.get('inside_order_number')
            outside_order_no = request.POST.get('outside_order_number')

            inside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
            outside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()

            line = inside_product.line_no
            inside_product_time = inside_product.create_date
            outside_product_time = outside_product.create_date
            initial_list = DryLine.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))

            # Python으로 추가 필터링 수행
            filtered_list = [item for item in initial_list if item.line_no == line]

            # filtered_list의 각 항목에 aging_position과 input_time 추가
            for item in filtered_list:
                # 현재의 phase_information 리스트를 가져옴
                item.ag_position = formatted_aging_position
                
                # 변경된 항목을 데이터베이스에 저장
                item.save()

            context = {
                'inside_order_number': inside_order_no,
                'outside_order_number': outside_order_no
            }
        
    return render(request, 'data_monitoring/aging_room.html', context)

@login_required
@csrf_protect
def create_lot_no(request):
	context = {}
	now = datetime.datetime.now()

	if request.method == 'POST':
		action = request.POST.get('action')
		
		if action == 'search':
			lot_no = ProductionLot.generate_lot()
			inside_order_no = "SOV0" + request.POST.get('inside_order_number')
			outside_order_no = "SOV0" + request.POST.get('outside_order_number')

			logger.info(f"[ROLL LOT] ORDER SEARCH: INSIDE {inside_order_no} / OUTSIDE {outside_order_no}")
			
			inside_product_list = list(chain(
				DryLine.objects.filter(production_plan__sales_order__order_no=inside_order_no),
				Delamination.objects.filter(production_plan__sales_order__order_no=inside_order_no)
			))
			inside_product = sorted(inside_product_list, key=lambda x: x.create_date, reverse=True)[0] if inside_product_list else None

			outside_product_list = list(chain(
				DryLine.objects.filter(production_plan__sales_order__order_no=outside_order_no),
				Delamination.objects.filter(production_plan__sales_order__order_no=outside_order_no)
			))
			outside_product = sorted(outside_product_list, key=lambda x: x.create_date, reverse=True)[0] if outside_product_list else None
			
			if inside_product and inside_product.line_no[:5] == 'bsvdl':
				inside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
				outside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()
				dept = 'DryLine'
			elif inside_product and inside_product.line_no[:5] == 'bsvrp':
				inside_product = Delamination.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
				outside_product = Delamination.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()
				dept = "RP"
			else:
				dept = ""

			if inside_product is not None and outside_product is not None:
				if inside_product.line_no == outside_product.line_no:
					line = inside_product.line_no
					inside_product_time = inside_product.create_date
					outside_product_time = outside_product.create_date

					if dept == 'DryLine':
						initial_list = DryLine.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))
					elif dept == 'RP':
						initial_list = Delamination.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))

					# Python으로 추가 필터링 수행
					filtered_list = [item for item in initial_list if item.line_no == line]
				else:
					filtered_list = None
			else:
				filtered_list = None

			context = {
				'list': filtered_list,
				'dept':dept,
				'inside_order_number': inside_order_no,
				'outside_order_number': outside_order_no,
				'roll_lot':lot_no
			}

		elif action == 'register':
			lot_no = request.POST.get('roll_lot')
			dept = request.POST.get('dept')
			inside_order_no = request.POST.get('inside_order_number')
			outside_order_no = request.POST.get('outside_order_number')

			if dept == 'DryLine':
				inside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
				outside_product = DryLine.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()
			elif dept == 'RP':
				inside_product = Delamination.objects.filter(Q(production_plan__sales_order__order_no=inside_order_no)).order_by('-create_date').first()
				outside_product = Delamination.objects.filter(Q(production_plan__sales_order__order_no=outside_order_no)).order_by('-create_date').first()

			line = inside_product.line_no
			inside_product_time = inside_product.create_date
			outside_product_time = outside_product.create_date
			if dept == 'DryLine':
				initial_list = DryLine.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))
			elif dept == 'RP':
				initial_list = Delamination.objects.filter(Q(create_date__gte=inside_product_time) & Q(create_date__lte=outside_product_time))

			# Python으로 추가 필터링 수행
			filtered_list = [item for item in initial_list if item.line_no == line]
			
			# 'list'에 있는 각 데이터의 ID를 기반으로 라디오 버튼 값을 처리
			selected_values = {}
			for data in request.POST:
				if data.startswith('selection_'):
					data_id = int(data.split('_')[1])
					selected_values[data_id] = request.POST[data]
			
			# filtered_list의 각 항목에 roll_lot input_time 추가
			for item in filtered_list:
				# 현재의 phase_information 리스트를 가져옴
				if dept == 'DryLine':
					item.pd_lot = lot_no + selected_values[item.id]
				elif dept == 'RP':
					item.dlami_lot = lot_no + selected_values[item.id]
				
				# 변경된 항목을 데이터베이스에 저장
				item.save()
            
			ProductionLot.objects.create(lot_no=lot_no)
			
			logger.info(f"[ROLL LOT] SAVED: {lot_no}")

			context = {
				'inside_order_number': inside_order_no,
				'outside_order_number': outside_order_no
			}
		
	return render(request, 'data_monitoring/create_lot_no.html', context)

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
                
            elif action == 'download_to_qrcard':
                order_numbers = data.get('order_numbers').split(',')
                sales_orders = SalesOrder.objects.exclude(status=False).filter(order_no__in=order_numbers)
                response = order_convert_to_qrcard(sales_orders)
                
                return response
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
                DryMix.objects.filter(production_plan__sales_order=order),
                DryLine.objects.filter(production_plan__sales_order=order),
                Delamination.objects.filter(production_plan__sales_order=order),
                Inspection.objects.filter(production_plan__sales_order=order)
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
                        phase_info = production_phase.mixing_information

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

                        sub_pd_qty = sub_pd_qty + production_phase.pd_qty

                        process.append({
                            'process': 'DryLine',
                            'pd_qty': production_phase.pd_qty,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })
                    
                    elif isinstance(production_phase, Delamination):
                        phase_info = production_phase.dlami_information

                        process.append({
                            'process' : 'RP',
                            'delami_qty': production_phase.dlami_qty,
                            'create_date': create_date,
                            'machine': production_phase.line_no
                        })
                    
                    elif isinstance(production_phase, Inspection):
                        phase_info = production_phase.ins_information
                        
                        sub_pd_qty = 0
                       
                        for info in phase_info:
                            defect[info.get('defectCause')] = info.get('quantity')
                        
                        agrade_qty = production_phase.ins_qty
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

def drymix(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # 검색 결과를 저장할 리스트를 초기화합니다.

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = DryMix.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # POST 요청을 받아 OrderNo를 검색합니다.
            order_no = request.POST.get('order_no', '')  # 폼에서 입력한 OrderNo를 가져옵니다.
            item = request.POST.get('item', '')  # Item 입력값을 받습니다.
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # OrderNo와 Item을 조합하여 데이터를 검색합니다.
            query = Q()
            if order_no:
                query &= Q(production_plan__sales_order__order_no__icontains=order_no)
            if item:
                query &= Q(production_plan__sales_order__item_name__icontains=item)
            if color_code:
                query &= Q(production_plan__sales_order__color_code__icontains=color_code)
            if pattern:
                query &= Q(production_plan__sales_order__pattern__icontains=pattern)
            
            if customer:
                query &= Q(production_plan__sales_order__customer_name__icontains=customer)
            
            if order_type:
                query &= Q(production_plan__sales_order__order_type__icontains=order_type)
            
            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                    query &= Q(create_date__range=(start_of_day, end_of_day))

            list = DryMix.objects.filter(query).select_related('production_plan__sales_order').order_by('-create_date')
    else:
        # GET 요청의 경우, 최근 14일 동안의 DryLine 데이터를 표시합니다.
        list = DryMix.objects.filter(
            create_date__range=(_3daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    context = {'list': list,
               'today': today,  # 오늘 날짜를 컨텍스트에 추가
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/drymix.html', context)

def dryline(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    status_plan = []
    order_numbers = []
    list = []
    list_and_plan = []  # 검색 결과를 저장할 리스트를 초기화

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = DryLine.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')

        else:
            # POST 요청을 받아 OrderNo를 검색합니다.
            order_no = request.POST.get('order_no', '')  # 폼에서 입력한 OrderNo를 가져옵니다.
            item = request.POST.get('item', '')  # Item 입력값을 받습니다.
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # OrderNo와 Item을 조합하여 데이터를 검색합니다.
            query = Q()
            if order_no:
                query &= Q(production_plan__sales_order__order_no__icontains=order_no)
            if item:
                query &= Q(production_plan__sales_order__item_name__icontains=item)
            if color_code:
                query &= Q(production_plan__sales_order__color_code__icontains=color_code)
            if pattern:
                query &= Q(production_plan__sales_order__pattern__icontains=pattern)
            
            if customer:
                query &= Q(production_plan__sales_order__customer_name__icontains=customer)
            
            if order_type:
                query &= Q(production_plan__sales_order__order_type__icontains=order_type)
            
            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                    query &= Q(create_date__range=(start_of_day, end_of_day))

            list = DryLine.objects.filter(query).select_related('production_plan__sales_order').order_by('-create_date')
    else:
        # GET 요청의 경우, 최근 3일 동안의 DryLine 데이터를 표시합니다.
        list = DryLine.objects.filter(
            create_date__range=(_3daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    # ProductionPlan 서브쿼리를 생성하여 각 ProductionPhase와 관련된 최신 ProductionPlan을 가져옵니다.
    #latest_plan_subquery = ProductionPlan.objects.filter(
    #    production_order=OuterRef('production_order')
    #).order_by('-create_date').values('plan_information__plan_qty')[:1]

    # ProductionPhase와 관련된 최신 ProductionPlan의 plan_qty를 annotate하여 가져옵니다.
    #list_and_plan = list.annotate(
    #    latest_plan_qty=Subquery(latest_plan_subquery)
    #).order_by('-create_date')

    context = {'list': list,
               'today': today,  # 오늘 날짜를 컨텍스트에 추가
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/dryline.html', context)

def delamination(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _7daysago = now+datetime.timedelta(days=-7)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # 검색 결과를 저장할 리스트를 초기화합니다.

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = Delamination.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # POST 요청을 받아 OrderNo를 검색합니다.
            order_no = request.POST.get('order_no', '')  # 폼에서 입력한 OrderNo를 가져옵니다.
            item = request.POST.get('item', '')  # Item 입력값을 받습니다.
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # OrderNo와 Item을 조합하여 데이터를 검색합니다.
            query = Q()
            if order_no:
                query &= Q(production_plan__sales_order__order_no__icontains=order_no)
            if item:
                query &= Q(production_plan__sales_order__item_name__icontains=item)
            if color_code:
                query &= Q(production_plan__sales_order__color_code__icontains=color_code)
            if pattern:
                query &= Q(production_plan__sales_order__pattern__icontains=pattern)
            
            if customer:
                query &= Q(production_plan__sales_order__customer_name__icontains=customer)
            
            if order_type:
                query &= Q(production_plan__sales_order__order_type__icontains=order_type)
            
            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                    query &= Q(create_date__range=(start_of_day, end_of_day))

            list = Delamination.objects.filter(query).select_related('production_plan__sales_order').order_by('-create_date')
    else:
        # GET 요청의 경우, 최근 14일 동안의 DryLine 데이터를 표시합니다.
        list = Delamination.objects.filter(
            create_date__range=(_7daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    context = {'list': list,
               'today': today,  # 오늘 날짜를 컨텍스트에 추가
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/delamination.html', context)

def inspection(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # 검색 결과를 저장할 리스트를 초기화합니다.

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = Inspection.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # POST 요청을 받아 OrderNo를 검색합니다.
            order_no = request.POST.get('order_no', '')  # 폼에서 입력한 OrderNo를 가져옵니다.
            item = request.POST.get('item', '')  # Item 입력값을 받습니다.
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # OrderNo와 Item을 조합하여 데이터를 검색합니다.
            query = Q()
            if order_no:
                query &= Q(production_plan__sales_order__order_no__icontains=order_no)
            if item:
                query &= Q(production_plan__sales_order__item_name__icontains=item)
            if color_code:
                query &= Q(production_plan__sales_order__color_code__icontains=color_code)
            if pattern:
                query &= Q(production_plan__sales_order__pattern__icontains=pattern)
            
            if customer:
                query &= Q(production_plan__sales_order__customer_name__icontains=customer)
            
            if order_type:
                query &= Q(production_plan__sales_order__order_type__icontains=order_type)
            
            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                    query &= Q(create_date__range=(start_of_day, end_of_day))

            list = Inspection.objects.filter(query).select_related('production_plan__sales_order').order_by('-create_date')
    else:
        # GET 요청의 경우, 최근 3일 동안의 DryLine 데이터를 표시합니다.
        list = Inspection.objects.filter(
            create_date__range=(_3daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')
    
    # DryLine 단계의 quantity 합계 계산
    list_and_quantity = []
    for inspection in list:
        sales_order = inspection.sales_order
        production_plan = inspection.production_plan
        
        # 해당 plan_id 로 전체 공정 내역 조회
        phases = Inspection.objects.filter(
            production_plan__sales_order=sales_order,
            production_plan=production_plan
        ).order_by('create_date')

        # quantity 값을 합산합니다.
        quantity = 0
        for phase in phases:
            phase_info_list = phase.ins_information  # JSON 리스트
            # 리스트 내부의 각 항목에서 'quantity' 값을 추출하여 합산합니다.
            
            for item in phase_info_list:
                if phase_info_list[-1].get("roll_lot", ""):
                    quantity_str = item.get('quantity')
                
                    if quantity_str:
                        try:
                            # 문자열을 숫자로 변환
                            quantity = int(quantity_str)
                            break
                        except (ValueError, TypeError):
                            # 변환에 실패하면 기본값 0을 사용
                            quantity = 0                        

        # 리스트와 quantity 값을 함께 저장합니다.
        list_and_quantity.append((inspection, quantity))

    context = {'list': list_and_quantity,
               'today': today,  # 오늘 날짜를 컨텍스트에 추가
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/inspection.html', context)