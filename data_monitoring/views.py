from django.shortcuts import render, get_object_or_404
from django.views.decorators.csrf import csrf_exempt, csrf_protect
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.utils import timezone
from django.core.paginator import Paginator
import json
from collections import defaultdict
from django.db.models import Q
from .models import (
    DryMix,
    DryLine,
    Delamination,
    Inspection,
    ProductionLot,
    Printing,
    DataMonitoringPrinting,
)
from production_management.models import SalesOrder, ProductionPlan
from workforce_management.models import Worker
from inventory_management.models import RawMaterial, Category
from django.contrib.admin.views.decorators import staff_member_required


from django.utils.dateparse import parse_date
from itertools import chain
import datetime
import pytz
from .tasks import order_convert_to_qrcard

import logging
logger = logging.getLogger('data_monitoring')

from django.core.cache import cache
from django.conf import settings
import hashlib

@csrf_exempt
def input_drymix(request):
    if request.method == "POST":
        # Get the necessary information from the POST data
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        # machine_value = data.get('machine', '')  # The name of the kiosk machine        
        worker_code = data.get('staffNumber', '')  # The employee number of the worker
        logger.info(f"[KIOSK] DRYMIX DATA: {data}")
        # Save the DryMix result to the ProductionPhase model
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    production_plan = ProductionPlan.objects.filter(sales_order=sales_order).order_by('-create_date').first()
                    # Create an instance of the ProductionPhase model
                    production_phase = DryMix(
                        production_plan = production_plan,
                        mixing_information=quantity_data,
                        worker_code=worker_code
                    )
                    production_phase.save()  # Save the instance
                    logger.info(f"[KIOSK] DRYMIX SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    # If the order number does not exist, handle the error  
                    logger.info(f"[KIOSK] DRYMIX ERROR: {order['order_number']}")
            

        return JsonResponse({"status": "success", "message": "Data added successfully"})    
    
    qr_content = request.GET.get('qrContent')

    # Get the list of staff in the DM department from the Worker model
    dm_staff_list = list(Worker.objects.filter(department='DM').values('id', 'worker_code', 'name'))  # id and name

    # Get the unique values of category from the RawMaterial model
    categories = list(Category.objects.values_list('category_name', flat=True).distinct())
    subitems = defaultdict(list)
    for category in categories:
        subitems[category] = list(RawMaterial.objects.filter(category__category_name=category).values_list('material_name', flat=True))

    # Get the latest production record
    latest_phase = DryMix.objects.select_related('production_plan').order_by('-create_date').first()

    # If the QR code content is empty, load the general page
    if not qr_content:
        context = {
            'categories': json.dumps(categories),
            'subitems': json.dumps(subitems),
            'dm_staff_list': json.dumps(dm_staff_list),
            'latest_phase':latest_phase
        }
        return render(request, 'data_monitoring/input_drymix.html', context)

    # If the QR code content is not empty, search by order_number
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] DRYMIX CONNECTED: {qr_content}")
        if qr_content[:3] == "SOV":
            order = SalesOrder.objects.exclude(status=False).get(order_no=qr_content)
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
    except SalesOrder.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_dryline(request):
    machine = request.GET.get('machine', None)    
    
    # When the production volume is entered
    if request.method == "POST":
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')  # machine value 
        
        logger.info(f"[KIOSK] DRYLINE DATA: {data}")
        
        # Save the DryLine result to the ProductionPhase model
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    production_plan = ProductionPlan.objects.filter(sales_order=sales_order).order_by('-create_date').first()
                    
                    # Find the most recent production history
                    production_phase = DryLine.objects.filter(
                            production_plan=production_plan
                    ).order_by('-create_date').first()
                    
                    if production_phase is None or production_phase.pd_lot is not None or production_phase.ag_position is not None: # If the history is not found or the production roll is confirmed, add a new lot
                        production_phase = DryLine.objects.create(
                            production_plan=production_plan,
                            pd_qty=quantity_data,
                            line_no=machine_value,
                            create_date=timezone.now()
                        )
                    elif production_phase is not None and (production_phase.pd_lot is None and production_phase.ag_position is None): # If the production history exists and the roll is not confirmed, update the existing lot
                        production_phase = DryLine.objects.update_or_create(
                            id=production_phase.id, # Update the most recent production lot
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
    
    # Call the QR code information
    qr_content = request.GET.get('qrContent')

    # If the QR code content is empty, load the general page
    if not qr_content:
        context = {}
        return render(request, 'data_monitoring/input_dryline.html', context)

    # If the QR code content is not empty, search by order_number
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
    except SalesOrder.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_rp(request):
    machine = request.GET.get('machine', None)
    if request.method == "POST":
        # Get the necessary information from the POST data
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')  # machine value

        quantity_info = []
        logger.info(f"[KIOSK] RP DATA: {data}")
        
        # Save the RP result to the ProductionPhase model
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    production_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    last_phase = DryLine.objects.filter(production_plan__sales_order=production_order).order_by('-create_date').first()
                    
                    if last_phase:
                        last_phase_plan = last_phase.production_plan
                    else:
                        last_phase_plan = None
                    
                    # Find the most recent production history
                    production_phase = Delamination.objects.filter(
                            production_plan=last_phase_plan
                    ).order_by('-create_date').first()
                    
                    if production_phase is None or production_phase.dlami_lot is not None: # If the history is not found or the production roll is confirmed, add a new lot
                        production_phase = Delamination.objects.create(
                            production_plan=last_phase_plan,
                            dlami_qty=quantity_data,
                            line_no=machine_value,
                            create_date=timezone.now()
                        )
                    elif production_phase is not None and production_phase.dlami_lot is None: # If the production history exists and the roll is not confirmed, update the existing lot
                        production_phase = Delamination.objects.update_or_create(
                            id=production_phase.id, # Update the most recent production lot
                            production_plan=last_phase_plan,
                            defaults={
                                'dlami_qty' : quantity_data,
                                'line_no' : machine_value,
                                'create_date': timezone.now()
                            }
                        )
                    logger.info(f"[KIOSK] RP SAVED: {order['order_number']}")
                except SalesOrder.DoesNotExist:
                    # If the order number does not exist, handle the error
                    logger.info(f"[KIOSK] RP ERROR: {order['order_number']}")
                

        return JsonResponse({"status": "success", "message": "Data added successfully"})    
    
    qr_content = request.GET.get('qrContent')

    # If the QR code content is empty, load the general page
    if not qr_content:
        context = {}
        return render(request, 'data_monitoring/input_rp.html', context)

    # If the QR code content is not empty, search by order_number
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
    except SalesOrder.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_inspection(request):
    if request.method == "POST":
        # Get the necessary information from the POST data
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_data = data.get('quantityInput', [])
        machine_value = data.get('machine', '')
        
        logger.info(f"[KIOSK] INSPECTION DATA: {data}")
        
        # Khởi tạo các biến
        a_qty = 0
        qty_to_printing = 0
        defect = []

        # Xử lý dữ liệu đầu vào
        for item in quantity_data:
            if item.get('Grade') == 'A':
                a_qty = int(item.get('quantity', 0))
            elif item.get('Grade') == 'Printing':
                qty_to_printing = int(item.get('quantity', 0))
            elif item.get('defectCause'):  # Chỉ thêm vào defect nếu là lỗi
                defect.append({
                    'quantity': int(item.get('quantity', 0)),
                    'defectCause': item.get('defectCause')
                    # Do not save nextProcess into JSON anymore
                })
        
        # Save inspection results to the ProductionPhase model
        for order in scanned_orders:
            if order['order_number'][:3] == 'SOV':
                try:
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order['order_number'])
                    last_phase = DryLine.objects.filter(production_plan__sales_order=sales_order).order_by('-create_date').first()
                    
                    if last_phase:
                        last_phase_plan = last_phase.production_plan
                    else:
                        last_phase_plan = None
                    
                    # Create an instance of the ProductionPhase model
                    production_phase = Inspection(
                        sales_order=sales_order,
                        production_plan=last_phase_plan,
                        ins_qty=a_qty,
                        qty_to_printing=qty_to_printing,  # Sử dụng trường qty_to_printing mới
                        line_no=machine_value,
                        ins_information=defect,  # Luôn truyền vào mảng (rỗng hoặc có dữ liệu)
                        create_date=timezone.now()
                    )
                    production_phase.save()
                    logger.info(f"[KIOSK] INSPECTION SAVED: {order['order_number']}, A-GRADE: {a_qty}, TO PRINTING: {qty_to_printing}")
                except SalesOrder.DoesNotExist:
                    logger.info(f"[KIOSK] INSPECTION ERROR: {order['order_number']}")

        return JsonResponse({"status": "success", "message": "Data added successfully"})
    
    qr_content = request.GET.get('qrContent')

    # Get the defect cause
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

    # If the QR code content is empty, load the general page
    if not qr_content:
        context = {'defect_cause':json.dumps(defect_cause)}
        return render(request, 'data_monitoring/input_inspection.html', context)

    # If the QR code content is not empty, search by order_number
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
    except SalesOrder.DoesNotExist:
        data = {
            'status': 'fail',
            'message': 'Order not found'
        }
    return JsonResponse(data)

@csrf_exempt
def input_printing(request):
    machine = request.GET.get('machine', None)
    if request.method == "POST":
        # Lấy dữ liệu POST từ template mới
        data = json.loads(request.body)
        scanned_orders = data.get('scannedOrders', [])
        quantity_input = data.get('quantityInput', '')
        defect_cause = data.get('defectCause', '')
        machine = data.get('machine', '')
        
        logger.info(f"[KIOSK] PRINTING DATA: {scanned_orders}, QUANTITY: {quantity_input}, MACHINE: {machine}")
        
        # Lưu thông tin vào cơ sở dữ liệu
        for qr_item in scanned_orders:
            order_number = qr_item.get('order_number')
            try:
                if int(quantity_input) == 0 and defect_cause:
                    DataMonitoringPrinting.objects.create(
                        order_number=order_number,
                        defect_cause=defect_cause,
                        line_no=machine,
                        create_date=timezone.now(),
                    )
                    logger.info(
                        f"[KIOSK] PRINTING DEFECT SAVED: {order_number} - {defect_cause}"
                    )
                    continue

                if order_number[:3] == 'SOV':
                    sales_order = SalesOrder.objects.exclude(status=False).get(order_no=order_number)
                    last_phase = (
                        DryLine.objects.filter(production_plan__sales_order=sales_order)
                        .order_by('-create_date')
                        .first()
                    )

                    if last_phase:
                        last_phase_plan = last_phase.production_plan
                    else:
                        last_phase_plan = None

                    Printing.objects.create(
                        sales_order=sales_order,
                        production_plan=last_phase_plan,
                        print_qty=int(quantity_input),
                        print_information=None,
                        line_no=machine,
                        create_date=timezone.now(),
                    )

                    logger.info(
                        f"[KIOSK] PRINTING SAVED: {order_number} - QTY: {quantity_input}"
                    )
            except SalesOrder.DoesNotExist:
                logger.info(f"[KIOSK] PRINTING ERROR: {order_number}")
            except ValueError:
                logger.info(f"[KIOSK] PRINTING QUANTITY ERROR: {quantity_input}")

        return JsonResponse({"status": "success", "message": "Data added successfully"})
    
    # Xử lý GET request và quét QR code
    qr_content = request.GET.get('qrContent')

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
        "Base Transparency": "Đốm",
    }

    # Nếu không có QR code, hiển thị trang bình thường
    if not qr_content:
        context = {'defect_cause': json.dumps(defect_cause)}
        return render(request, 'data_monitoring/input_printing.html', context)

    # Nếu có QR code, tìm thông tin đơn hàng
    try:
        qr_content = f"{qr_content.split('!')[2]}-{qr_content.split('!')[3]}"
        logger.info(f"[KIOSK] PRINTING CONNECTED: {qr_content}")
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
    except SalesOrder.DoesNotExist:
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

                    # Perform additional filtering in Python
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

            # Perform additional filtering in Python
            filtered_list = [item for item in initial_list if item.line_no == line]

            # Add aging_position and input_time to each item in filtered_list
            for item in filtered_list:
                # Get the current phase_information list
                item.ag_position = formatted_aging_position
                
                # Save the modified item to the database
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

					# Perform additional filtering in Python
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

			# Perform additional filtering in Python
			filtered_list = [item for item in initial_list if item.line_no == line]
			
			# Process the radio button value based on the ID of each data in 'list'
			selected_values = {}
			for data in request.POST:
				if data.startswith('selection_'):
					data_id = int(data.split('_')[1])
					selected_values[data_id] = request.POST[data]
			
			# Add roll_lot and input_time to each item in filtered_list
			for item in filtered_list:
				# Get the current phase_information list
				if dept == 'DryLine':
					item.pd_lot = lot_no + selected_values[item.id]
				elif dept == 'RP':
					item.dlami_lot = lot_no + selected_values[item.id]
				
				# Save the modified item to the database
				item.save()
            
			ProductionLot.objects.create(lot_no=lot_no)
			
			logger.info(f"[ROLL LOT] SAVED: {lot_no}")

			context = {
				'inside_order_number': inside_order_no,
				'outside_order_number': outside_order_no
			}
		
	return render(request, 'data_monitoring/create_lot_no.html', context)

@csrf_exempt
def order_search(request):
    order_and_status = []
    count = 0
    order_numbers = []
    if request.method == 'POST':
        # Check if request.body is empty
        if not request.body:
            return JsonResponse({'error': 'Empty request body'}, status=400)
        
        # Parse JSON data
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
       
        # Search for the production history of each Order Number
        for order in order_list:
            process = []
            
            # Search in multiple models for sales_order
            production_phases = sorted(chain(
                ProductionPlan.objects.filter(sales_order=order),
                DryMix.objects.filter(production_plan__sales_order=order),
                DryLine.objects.filter(production_plan__sales_order=order),
                Delamination.objects.filter(production_plan__sales_order=order),
                Inspection.objects.filter(Q(production_plan__sales_order=order) | Q(sales_order=order)),
                Printing.objects.filter(Q(production_plan__sales_order=order) | Q(sales_order=order))
            ), key=lambda x: x.create_date)
            
            bal_qty = int(order.order_qty)
            
            agrade_qty, delami_qty, pd_qty = 0, 0, 0
            sub_pd_qty = 0
            defect, chemical = {}, {}
            
            # Find the latest process name and create_date in the process list
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

                        for info in phase_info: # Check the information of phase_information in json format
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
                        
                        # Lưu số lượng chuyển qua Printing nếu có
                        if production_phase.qty_to_printing:
                            qty_to_printing = production_phase.qty_to_printing
                        
                        process.append({
                            'process' : 'Inspection',
                            'agrade_qty': agrade_qty,
                            'defect': defect,
                            'machine': production_phase.line_no,
                            'create_date': create_date,
                            'qty_to_printing': production_phase.qty_to_printing
                        })

                    elif isinstance(production_phase, Printing):
                        phase_info = production_phase.print_information
                        process.append({
                            'process': 'Printing',
                            'print_qty': production_phase.print_qty,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })

            # Sort the process list based on create_date
            process = sorted(process, key=lambda x: x['create_date'])

            # Find the latest process name and create_date in the process list
            for proc in process:
                if not latest_create_date or proc['create_date'] > latest_create_date:
                    latest_create_date = proc['create_date']
                    latest_process = proc['process']
                    latest_machine = proc['machine']
            
            # Kiểm tra xem có bản ghi Printing nào sau bản ghi Inspection cuối cùng không
            latest_inspection = None
            latest_printing = None
            for proc in reversed(process):
                if proc['process'] == 'Inspection' and not latest_inspection:
                    latest_inspection = proc
                elif proc['process'] == 'Printing' and not latest_printing:
                    latest_printing = proc
                if latest_inspection and latest_printing:
                    break

            # Khởi tạo status với cấu trúc đúng
            status_data = {
                'bal_qty': bal_qty,
                'line_shortage': sub_pd_qty - bal_qty,
                'process': process,
                'latest_process': latest_process,
                'latest_create_date': latest_create_date,
                'latest_machine': latest_machine,
                'qty_to_printing': None  # Mặc định là None
            }

            # Chỉ set qty_to_printing nếu bản ghi Inspection cuối cùng không có bản ghi Printing sau nó
            if latest_inspection:
                inspection_date = latest_inspection.get('create_date')
                printing_date = latest_printing.get('create_date') if latest_printing else None
                
                # Nếu không có bản ghi Printing hoặc Inspection mới hơn Printing
                if not printing_date or (inspection_date and inspection_date > printing_date):
                    status_data['qty_to_printing'] = latest_inspection.get('qty_to_printing')

            status.append(status_data)
        
        order_and_status = zip(order_list, status)
        count = len(order_list)

    context = {
        'order_and_status': order_and_status,
        'count': count
    }
    return render(request, 'data_monitoring/order_search.html', context)

@login_required
def dryplan(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # Initialize the list to store search results

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = ProductionPlan.objects.filter(Q(item_group="Dry")&Q(sales_order__order_no__in=order_numbers)).select_related('sales_order').order_by('-create_date')

        else:
            # Receive the POST request to search for OrderNo
            order_no = request.POST.get('order_no', '')  # Get the OrderNo input from the form
            item = request.POST.get('item', '')  # Get the Item input
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # Combine OrderNo and Item to search for data
            query = Q(item_group="Dry")
            if order_no:
                query &= Q(sales_order__order_no__icontains=order_no)
            if item:
                query &= Q(sales_order__item_name__icontains=item)
            if color_code:
                query &= Q(sales_order__color_code__icontains=color_code)
            if pattern:
                query &= Q(sales_order__pattern__icontains=pattern)
            
            if customer:
                query &= Q(sales_order__customer_name__icontains=customer)
            
            if order_type:
                query &= Q(sales_order__order_type__icontains=order_type)
            
            if start_date_str and end_date_str:
                start_date = parse_date(start_date_str)
                end_date = parse_date(end_date_str)
                if start_date and end_date:
                    start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                    end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                    query &= Q(create_date__range=(start_of_day, end_of_day))

            list = ProductionPlan.objects.filter(query).select_related('sales_order').order_by('-create_date')
    else:
        # In the case of GET request, display the DryLine data for the past 3 days
        list = ProductionPlan.objects.filter(
            item_group="Dry", create_date__range=(_3daysago, now)
        ).select_related('sales_order').order_by('-create_date')

    context = {'list': list,
               'today': today,  # Add today's date to the context
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/dryplan.html', context)

@login_required
def drymix(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # Initialize the list to store search results

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = DryMix.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # Receive the POST request to search for OrderNo
            order_no = request.POST.get('order_no', '')  # Get the OrderNo input from the form
            item = request.POST.get('item', '')  # Get the Item input
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # Combine OrderNo and Item to search for data
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
        # In the case of GET request, display the DryLine data for the past 14 days
        list = DryMix.objects.filter(
            create_date__range=(_3daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    context = {'list': list,
               'today': today,  # Add today's date to the context
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/drymix.html', context)

@login_required
def dryline(request):
    # Lấy thời gian hiện tại
    now = datetime.datetime.now()
    # Tính thời điểm bắt đầu của ngày hiện tại
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    # Tính thời điểm kết thúc của ngày hiện tại
    today_end = now.replace(hour=23, minute=59, second=59, microsecond=999999)
    # Tính thời điểm 3 ngày trước
    _3daysago = today_start - datetime.timedelta(days=3)
    # Tính thời điểm 30 ngày trước cho tìm kiếm
    _30daysago = today_start - datetime.timedelta(days=30)
    
    status_plan = []
    order_numbers = []
    list = []
    list_and_plan = []  # Initialize the list to store search results

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = DryLine.objects.filter(
                Q(production_plan__sales_order__order_no__in=order_numbers)
            ).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # Receive the POST request to search for OrderNo
            order_no = request.POST.get('order_no', '')  # Get the OrderNo input from the form
            item = request.POST.get('item', '')  # Get the Item input
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # Combine OrderNo and Item to search for data
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
                try:
                    start_date = parse_date(start_date_str)
                    end_date = parse_date(end_date_str)
                    if start_date and end_date:
                        # Đảm bảo lấy đủ dữ liệu từ đầu ngày start_date đến cuối ngày end_date
                        start_of_day = datetime.datetime.combine(start_date, datetime.time.min)
                        end_of_day = datetime.datetime.combine(end_date, datetime.time.max)
                        query &= Q(create_date__range=(start_of_day, end_of_day))
                except ValueError:
                    pass  # Xử lý khi parse date thất bại

            list = DryLine.objects.filter(query).select_related('production_plan__sales_order').order_by('-create_date')
    else:
        # In the case of GET request, display the DryLine data for the past 3 days
        list = DryLine.objects.filter(
            create_date__range=(_3daysago, today_end)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    context = {
        'list': list,
        'today': now.date(),
        '30daysago': _30daysago.date()
    }
    return render(request, 'data_monitoring/dryline.html', context)

@login_required
def delamination(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _7daysago = now+datetime.timedelta(days=-7)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # Initialize the list to store search results

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = Delamination.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # Receive the POST request to search for OrderNo
            order_no = request.POST.get('order_no', '')  # Get the OrderNo input from the form
            item = request.POST.get('item', '')  # Get the Item input
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # Combine OrderNo and Item to search for data
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
        # In the case of GET request, display the DryLine data for the past 14 days
        list = Delamination.objects.filter(
            create_date__range=(_7daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')

    context = {'list': list,
               'today': today,  # Add today's date to the context
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/delamination.html', context)

@login_required
def inspection(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_numbers = []
    list = []  # Initialize the list to store search results

    if request.method == 'POST':
        order_numbers = request.POST.get('order_numbers', '')
        if order_numbers:
            order_numbers = order_numbers.split(',')
            list = Inspection.objects.filter(Q(production_plan__sales_order__order_no__in=order_numbers)).select_related('production_plan__sales_order').order_by('-create_date')
        else:
            # Receive the POST request to search for OrderNo
            order_no = request.POST.get('order_no', '')  # Get the OrderNo input from the form
            item = request.POST.get('item', '')  # Get the Item input
            color_code = request.POST.get('color_code', '')
            pattern = request.POST.get('pattern', '')
            start_date_str = request.POST.get('start_date', '')
            end_date_str = request.POST.get('end_date', '')
            customer = request.POST.get('customer', '')
            order_type = request.POST.get('order_type', '')

            # Combine OrderNo and Item to search for data
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
        # In the case of GET request, display the DryLine data for the past 3 days
        list = Inspection.objects.filter(
            create_date__range=(_3daysago, now)
        ).select_related('production_plan__sales_order').order_by('-create_date')
    
    # Calculate the sum of quantity for the DryLine phase
    list_and_quantity = []
    
    for inspection in list:
        sales_order = inspection.sales_order
        production_plan = inspection.production_plan
        
        # Search for the entire production history for the corresponding plan_id
        phases = Inspection.objects.filter(
            production_plan__sales_order=sales_order,
            production_plan=production_plan
        ).order_by('create_date')

        # Sum the quantity values
        dryline_phases = DryLine.objects.filter(
            production_plan=production_plan
        ).order_by('create_date').first()

        if dryline_phases:
            quantity = dryline_phases.pd_qty
        else:
            quantity = 0                   

        # Save the list and quantity values together
        list_and_quantity.append((inspection, quantity))

    context = {'list': list_and_quantity,
               'today': today,  # Add today's date to the context
               '30daysago':_30daysago
               }
    return render(request, 'data_monitoring/inspection.html', context)


@staff_member_required
def debug_export_counts(request):
    # Get the orders from DryLine with line_no 'bsvdl03', 'bsvdl04'
    direct_orders = DryLine.objects.filter(
        line_no__in=['bsvdl03', 'bsvdl04']
    ).values_list('production_plan__sales_order', flat=True).distinct()
    direct_count = len(direct_orders)
    
    # Get the orders from Delamination
    delamination_orders = Delamination.objects.values_list('production_plan__sales_order', flat=True).distinct()
    delamination_count = len(delamination_orders)
    
    # Combine the two lists above
    production_orders = list(set(chain(direct_orders, delamination_orders)))
    combined_count = len(production_orders)
    
    # Orders that have passed Inspection
    inspection_orders = Inspection.objects.values_list('sales_order', flat=True).distinct()
    inspection_count = len(inspection_orders)
    
    # Only get orders that are ready for Inspection but not yet inspected
    order_list = SalesOrder.objects.filter(id__in=production_orders).exclude(id__in=inspection_orders)
    final_count = order_list.count()
    
    return JsonResponse({
        'direct_count': direct_count,
        'delamination_count': delamination_count,
        'combined_unique_count': combined_count,
        'inspection_count': inspection_count,
        'final_count': final_count
    })

@login_required
def inspection_waitlist(request):
    page = request.GET.get('page', '1')
    
    # Create cache key based on parameters
    cache_params = f"export_page_{page}"
    cache_key = f"order_export:{hashlib.md5(cache_params.encode()).hexdigest()}"
    
    # Check if there is data in the cache
    cached_data = cache.get(cache_key)
    if cached_data:
        return render(request, 'data_monitoring/inspection_waitlist.html', cached_data)
    
    # Use efficient raw query
    raw_query = """
    WITH dryline_plans AS (
        SELECT dl.production_plan_id, dl.line_no
        FROM data_monitoring_dryline dl
        WHERE dl.create_date >= '2025-01-01'
    ),
    delamination_plans AS (
        SELECT d.production_plan_id
        FROM data_monitoring_delamination d
    ),
    inspected_orders AS (
        SELECT i.sales_order_id
        FROM data_monitoring_inspection i
    ),
    plans_with_order AS (
        SELECT p.id AS production_plan_id, p.sales_order_id
        FROM production_management_productionplan p
    )
    SELECT DISTINCT s.id, s.etd
    FROM production_management_salesorder s
    JOIN plans_with_order pwo ON pwo.sales_order_id = s.id
    JOIN dryline_plans dl ON dl.production_plan_id = pwo.production_plan_id
    LEFT JOIN delamination_plans d ON d.production_plan_id = pwo.production_plan_id
    LEFT JOIN inspected_orders i ON i.sales_order_id = s.id
    WHERE (
        (
            dl.line_no IN ('bsvdl01', 'bsvdl02') 
            AND d.production_plan_id IS NOT NULL
        )
        OR (
            dl.line_no IN ('bsvdl03', 'bsvdl04')
        )
    )
    AND i.sales_order_id IS NULL
    LIMIT 5000;
    """
    
    # Cache the list of IDs
    all_order_ids_cache_key = "export_all_order_ids"
    all_order_ids = cache.get(all_order_ids_cache_key)
    
    if not all_order_ids:
        from django.db import connection
        with connection.cursor() as cursor:
            cursor.execute(raw_query)
            all_order_ids = [row[0] for row in cursor.fetchall()]
        
        cache.set(all_order_ids_cache_key, all_order_ids, 300)
    
    # Pagination - reduce the number of items per page to avoid heavy data
    paginator = Paginator(all_order_ids, 20)
    page_obj = paginator.get_page(page)
    current_page_ids = page_obj.object_list
    
    # Get order information
    current_orders = list(SalesOrder.objects.filter(id__in=current_page_ids).order_by('-etd'))
    
    # Sort orders by id
    id_to_order = {order.id: order for order in current_orders}
    current_orders = [id_to_order[id] for id in current_page_ids if id in id_to_order]
    
    # Process status
    status = []
    
    for order in current_orders:
        # Cache key for order status
        order_status_key = f"order_status:{order.id}"
        order_status = cache.get(order_status_key)
        
        if not order_status:
            # Calculate status if not in cache
            process = []
            
            # Find production phases
            production_phases = sorted(chain(
                ProductionPlan.objects.filter(sales_order=order),
                DryMix.objects.filter(production_plan__sales_order=order),
                DryLine.objects.filter(production_plan__sales_order=order),
                Delamination.objects.filter(production_plan__sales_order=order),
                Inspection.objects.filter(Q(production_plan__sales_order=order) | Q(sales_order=order)),
                Printing.objects.filter(Q(production_plan__sales_order=order) | Q(sales_order=order))
            ), key=lambda x: x.create_date)
            
            bal_qty = int(order.order_qty)
            agrade_qty, delami_qty, pd_qty = 0, 0, 0
            sub_pd_qty = 0
            defect, chemical = {}, {}
            
            # Khởi tạo status_data với giá trị mặc định
            status_data = {
                'bal_qty': bal_qty,
                'line_shortage': 0,
                'process': [],
                'latest_process': None,
                'latest_create_date': None,
                'latest_machine': None,
                'qty_to_printing': None
            }
            
            # Find the latest process name and create_date in the process list
            latest_process = latest_create_date = latest_machine = None

            if production_phases:
                for production_phase in production_phases:
                    create_date = production_phase.create_date.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if isinstance(production_phase, ProductionPlan):
                        phase_info = production_phase.pd_information
                        if production_phase.item_group == 'Dry':
                            phase_info = {
                                'process': 'DryPlan',
                                'create_date': create_date,
                                'machine': production_phase.pd_line,
                                'plan_qty': production_phase.plan_qty,
                                'plan_date': production_phase.plan_date.strftime('%Y-%m-%d')
                            }
                            process.append(phase_info)
                    
                    elif isinstance(production_phase, DryMix):
                        phase_info = production_phase.mixing_information
                        for info in phase_info:
                            if info.get('item', ''):
                                chemical[info.get('item')] = str(info.get('quantity')) + info.get('unit')
                        process.append({
                            'process': 'DryMix',
                            'chemical': chemical,
                            'machine': '',
                            'create_date': create_date
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
                            'process': 'RP',
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
                            'process': 'Inspection',
                            'agrade_qty': agrade_qty,
                            'defect': defect,
                            'machine': production_phase.line_no,
                            'create_date': create_date,
                            'qty_to_printing': production_phase.qty_to_printing
                        })

                    elif isinstance(production_phase, Printing):
                        phase_info = production_phase.print_information
                        process.append({
                            'process': 'Printing',
                            'print_qty': production_phase.print_qty,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })
                
                # Sort by time
                process = sorted(process, key=lambda x: x['create_date'])
                
                # Find the latest phase
                for proc in process:
                    if not latest_create_date or proc['create_date'] > latest_create_date:
                        latest_create_date = proc['create_date']
                        latest_process = proc['process']
                        latest_machine = proc['machine']
            
            # Khởi tạo status với cấu trúc đúng
            status_data = {
                'bal_qty': bal_qty,
                'line_shortage': sub_pd_qty - bal_qty,
                'process': process,
                'latest_process': latest_process,
                'latest_create_date': latest_create_date,
                'latest_machine': latest_machine
            }

            cache.set(order_status_key, status_data, 3600)  # cache 1 hour
        else:
            status_data = order_status
        
        # Ensure to add order_status to the list
        status.append(status_data)
    
    # Create a list of combined order and status
    order_and_status = list(zip(current_orders, status))
    
    # Sort order_and_status by latest_create_date (descending - newest at the top)
    order_and_status = sorted(
        order_and_status, 
        key=lambda x: x[1].get('latest_create_date') or '1900-01-01 00:00:00',
        reverse=True
    )
    
    context = {
        'order_and_status': order_and_status,
        'page_obj': page_obj,
        'total_pages': paginator.num_pages,
        'total_orders': len(all_order_ids)
    }
    
    # Cache the result
    cache.set(cache_key, context, 300)
    
    return render(request, 'data_monitoring/inspection_waitlist.html', context)

@login_required
def printing_waitlist(request):
    today = datetime.date.today()
    now = datetime.datetime.now()
    _3daysago = now+datetime.timedelta(days=-3)
    _30daysago = today - datetime.timedelta(days=30)
    order_and_status = []
    count = 0

    # Lấy tất cả các đơn hàng có Inspection gần nhất với qty_to_printing > 0
    inspections = Inspection.objects.filter(
        qty_to_printing__gt=0
    ).select_related('production_plan__sales_order', 'sales_order').order_by('-create_date')

    # Lọc ra các đơn hàng chưa có bản ghi Printing sau bản ghi Inspection cuối cùng
    for inspection in inspections:
        sales_order = inspection.sales_order or inspection.production_plan.sales_order
        
        # Kiểm tra xem có bản ghi Printing nào sau bản ghi Inspection này không
        latest_printing = Printing.objects.filter(
            Q(production_plan__sales_order=sales_order) | Q(sales_order=sales_order),
            create_date__gt=inspection.create_date
        ).exists()
        
        if not latest_printing:
            process = []
            
            # Search in multiple models for sales_order
            production_phases = sorted(chain(
                ProductionPlan.objects.filter(sales_order=sales_order),
                DryMix.objects.filter(production_plan__sales_order=sales_order),
                DryLine.objects.filter(production_plan__sales_order=sales_order),
                Delamination.objects.filter(production_plan__sales_order=sales_order),
                Inspection.objects.filter(Q(production_plan__sales_order=sales_order) | Q(sales_order=sales_order)),
                Printing.objects.filter(Q(production_plan__sales_order=sales_order) | Q(sales_order=sales_order))
            ), key=lambda x: x.create_date)
            
            bal_qty = int(sales_order.order_qty)
            
            agrade_qty, delami_qty, pd_qty = 0, 0, 0
            sub_pd_qty = 0
            defect, chemical = {}, {}
            
            # Find the latest process name and create_date in the process list
            latest_process = latest_create_date = latest_machine = None

            if production_phases:
                for production_phase in production_phases:
                    create_date = production_phase.create_date.astimezone(pytz.timezone('Asia/Ho_Chi_Minh')).strftime('%Y-%m-%d %H:%M:%S')
                    
                    if isinstance(production_phase, ProductionPlan):
                        phase_info = production_phase.pd_information
                        if production_phase.item_group == 'Dry':
                            phase_info = {
                                'process': 'DryPlan',
                                'create_date': create_date,
                                'machine': production_phase.pd_line,
                                'plan_qty': production_phase.plan_qty,
                                'plan_date': production_phase.plan_date.strftime('%Y-%m-%d')
                            }
                            process.append(phase_info)
                    
                    elif isinstance(production_phase, DryMix):
                        phase_info = production_phase.mixing_information
                        for info in phase_info:
                            if info.get('item', ''):
                                chemical[info.get('item')] = str(info.get('quantity')) + info.get('unit')
                        process.append({
                            'process': 'DryMix',
                            'chemical': chemical,
                            'machine': '',
                            'create_date': create_date
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
                            'process': 'RP',
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
                            'process': 'Inspection',
                            'agrade_qty': agrade_qty,
                            'defect': defect,
                            'machine': production_phase.line_no,
                            'create_date': create_date,
                            'qty_to_printing': production_phase.qty_to_printing
                        })

                    elif isinstance(production_phase, Printing):
                        phase_info = production_phase.print_information
                        process.append({
                            'process': 'Printing',
                            'print_qty': production_phase.print_qty,
                            'machine': production_phase.line_no,
                            'create_date': create_date
                        })
                
                # Sort by time
                process = sorted(process, key=lambda x: x['create_date'])
                
                # Find the latest phase
                for proc in process:
                    if not latest_create_date or proc['create_date'] > latest_create_date:
                        latest_create_date = proc['create_date']
                        latest_process = proc['process']
                        latest_machine = proc['machine']
            
            # Khởi tạo status với cấu trúc đúng
            status_data = {
                'bal_qty': bal_qty,
                'line_shortage': sub_pd_qty - bal_qty,
                'process': process,
                'latest_process': latest_process,
                'latest_create_date': latest_create_date,
                'latest_machine': latest_machine,
                'qty_to_printing': inspection.qty_to_printing
            }

            order_and_status.append((sales_order, status_data))
            count += 1

    context = {
        'order_and_status': order_and_status,
        'count': count,
        'today': today,
        '30daysago': _30daysago
    }
    return render(request, 'data_monitoring/printing_list.html', context)


