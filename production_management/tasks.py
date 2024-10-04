import openpyxl
from copy import copy
import pandas as pd
from .models import SalesOrder, ProductionPlan
from datetime import datetime
from django.http import HttpResponse, JsonResponse
from django.conf import settings
from openpyxl.drawing.image import Image
import qrcode
import io
import os

# Celery
from celery import shared_task
# Celery-progress
from celery_progress.backend import ProgressRecorder

import boto3

s3 = boto3.client('s3', region_name=settings.AWS_S3_REGION_NAME)

def get_s3_file(key):
    """S3에서 파일을 가져와 BytesIO 객체로 반환합니다."""
    s3_response = s3.get_object(Bucket=settings.AWS_STORAGE_BUCKET_NAME, Key=key)
    file_content = s3_response['Body'].read()
    return io.BytesIO(file_content)

def index2(request):
    pass

def copy_sheet_attributes(source_sheet, target_sheet):
    if isinstance(source_sheet, openpyxl.worksheet._read_only.ReadOnlyWorksheet):
        return
    target_sheet.sheet_format = copy(source_sheet.sheet_format)
    target_sheet.sheet_properties = copy(source_sheet.sheet_properties)
    target_sheet.merged_cells = copy(source_sheet.merged_cells)
    target_sheet.page_margins = copy(source_sheet.page_margins)
    target_sheet.freeze_panes = copy(source_sheet.freeze_panes)

    # set row dimensions
    # So you cannot copy the row_dimensions attribute. Does not work (because of meta data in the attribute I think). So we copy every row's row_dimensions. That seems to work.
    for rn in range(len(source_sheet.row_dimensions)):
        target_sheet.row_dimensions[rn] = copy(source_sheet.row_dimensions[rn])

    if source_sheet.sheet_format.defaultColWidth is None:
        pass
    else:
        target_sheet.sheet_format.defaultColWidth = copy(source_sheet.sheet_format.defaultColWidth)

    # set specific column width and hidden property
    # we cannot copy the entire column_dimensions attribute so we copy selected attributes
    for key, value in source_sheet.column_dimensions.items():
        target_sheet.column_dimensions[key].min = copy(source_sheet.column_dimensions[key].min)   # Excel actually groups multiple columns under 1 key. Use the min max attribute to also group the columns in the targetSheet
        target_sheet.column_dimensions[key].max = copy(source_sheet.column_dimensions[key].max)  # https://stackoverflow.com/questions/36417278/openpyxl-can-not-read-consecutive-hidden-columns discussed the issue. Note that this is also the case for the width, not onl;y the hidden property
        target_sheet.column_dimensions[key].width = copy(source_sheet.column_dimensions[key].width) # set width for every column
        target_sheet.column_dimensions[key].hidden = copy(source_sheet.column_dimensions[key].hidden)

def copy_cells(source_sheet, target_sheet):
    for r, row in enumerate(source_sheet.iter_rows()):
        for c, cell in enumerate(row):
            source_cell = cell
            if isinstance(source_cell, openpyxl.cell.read_only.EmptyCell):
                continue
            target_cell = target_sheet.cell(column=c+1, row=r+1)

            target_cell._value = source_cell._value
            target_cell.data_type = source_cell.data_type

            if source_cell.has_style:
                target_cell.font = copy(source_cell.font)
                target_cell.border = copy(source_cell.border)
                target_cell.fill = copy(source_cell.fill)
                target_cell.number_format = copy(source_cell.number_format)
                target_cell.protection = copy(source_cell.protection)
                target_cell.alignment = copy(source_cell.alignment)

            if not isinstance(source_cell, openpyxl.cell.ReadOnlyCell) and source_cell.hyperlink:
                target_cell._hyperlink = copy(source_cell.hyperlink)

            if not isinstance(source_cell, openpyxl.cell.ReadOnlyCell) and source_cell.comment:
                target_cell.comment = copy(source_cell.comment)

def copy_sheet(source_sheet, target_sheet):
    copy_cells(source_sheet, target_sheet)  # copy all the cel values and styles
    copy_sheet_attributes(source_sheet, target_sheet)

def parse_date(date_string):
    if not date_string or pd.isna(date_string):
        return None
    
    date_formats = ['%Y-%m-%d %H:%M:%S', '%Y-%m-%d']
    for date_format in date_formats:
        try:
            return datetime.strptime(str(date_string), date_format).date()
        except ValueError:
            continue
    
    return None

@shared_task(bind=True)
def ordersheet_upload_celery(self,df_json):
    try:
        # 작업 진행 상황을 기록하기 위한 객체
        progress_recorder = ProgressRecorder(self)
        
        # JSON을 다시 데이터프레임으로 변환
        df = pd.read_json(df_json)
        
        for i in range(len(df)):
            # Sales order와 Line number가 빈 경우 건너뜀
            if df['Sales order'][i] == "" and df['Line number'][i] == "":
                continue
        
            sales_order = SalesOrder.objects.filter(
                order_no = f"{df['Sales order'][i]}-{(df['Line number'][i])}"
                ).first()
            
            if sales_order:
                # 객체의 order_quantity 필드에서 값을 비교 합니다
                if (int(df['Quantity'][i])) < 0:
                    
                    # order_status 필드 false로 변경
                    sales_order.status = False
                    sales_order.save()  # 변경 사항을 저장합니다.
                
                elif (int(df['Quantity'][i])) > 0:
                    order_data = {
                        'order_id': df['Sales order'][i],
                        'seq_no': int(df['Line number'][i]),
                        'customer_order_no': df['po number'][i],
                        'customer_name': df['Customer Name'][i],
                        'order_type': df['Sales origin'][i],
                        'order_date': parse_date(df['Receipt date'][i]),
                        'rtd': parse_date(df['RTD'][i]),
                        'etd': parse_date(df['ETD'][i]),
                        'brand': df['Brand Name'][i],
                        'item_name': df['Item Name'][i],
                        'color_code': df['Color Code'][i],
                        'color_name': df['Color Name'][i],
                        'pattern': df['TYPE'][i],
                        'spec': df['Spec Name'][i],
                        'order_qty': int(df['Quantity'][i]),
                        'qty_unit': df['Unit'][i],
                        'unit_price': float(df['Ship Unit price'][i]),
                        'currency': df['Currency(Trade)'][i],
                        'order_remark': df['Prod. remark'][i],
                        'model_name': df['Model name'][i],
                        'sample_step': df['Sample Step'][i],
                        'production_location': df['Order To Company'][i],
                        'product_group': df['Prod Group'][i],
                        'product_type': df['Custom No'][i]
                    }
        
                    for key, value in order_data.items():
                        setattr(sales_order, key, value)
                    sales_order.save()
            else:
                if int(df['Quantity'][i]) > 0:
                    order_data = {
                        'order_id': df['Sales order'][i],
                        'seq_no': int(df['Line number'][i]),
                        'customer_order_no': df['po number'][i],
                        'customer_name': df['Customer Name'][i],
                        'order_type': df['Sales origin'][i],
                        'order_date': parse_date(df['Receipt date'][i]),
                        'rtd': parse_date(df['RTD'][i]),
                        'etd': parse_date(df['ETD'][i]),
                        'brand': df['Brand Name'][i],
                        'item_name': df['Item Name'][i],
                        'color_code': df['Color Code'][i],
                        'color_name': df['Color Name'][i],
                        'pattern': df['TYPE'][i],
                        'spec': df['Spec Name'][i],
                        'order_qty': int(df['Quantity'][i]),
                        'qty_unit': df['Unit'][i],
                        'unit_price': float(df['Ship Unit price'][i]),
                        'currency': df['Currency(Trade)'][i],
                        'order_remark': df['Prod. remark'][i],
                        'model_name': df['Model name'][i],
                        'sample_step': df['Sample Step'][i],
                        'production_location': df['Order To Company'][i],
                        'product_group': df['Prod Group'][i],
                        'product_type': df['Custom No'][i]
                    }
                    
                    SalesOrder.objects.create(**order_data)
                else:
                    continue
        
            progress_recorder.set_progress(i + 1, len(df), description="Uploading")
    except Exception as e:
        # 작업 중 에러가 발생한 경우 로그에 출력
        print(f"작업 중 에러가 발생했습니다: {e}")
        # 필요한 예외 처리를 여기에 추가

def dryplan_convert_to_qrcard(df_json):
    try:
        # 엑셀 파일로 응답을 생성합니다.
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="qrcard_.xlsx"'
        
        # JSON 데이터를 pandas DataFrame으로 변환합니다.
        df = pd.read_json(df_json)
        
        # 새 워크북을 생성하고 기존의 'qrcard.xlsx' 파일을 로드합니다.
        wb = openpyxl.Workbook()
        
        # S3에서 파일 가져오기
        excel_file = get_s3_file('forms/qrcard.xlsx')

        # openpyxl로 워크북 로드
        qrcard = openpyxl.load_workbook(excel_file)
        
        # 각 행에 대해 새 워크시트를 생성하고 데이터를 채웁니다.
        for i in range(len(df)):
            ws = wb.create_sheet(str(i+1))
            copy_sheet(qrcard['DRY'], ws)
            # 워크시트에 데이터를 채웁니다.
            row_data = df.iloc[i]  # 데이터 프레임에서 한 행의 데이터를 미리 불러옴
            try:
                sales_order = SalesOrder.objects.exclude(status=False).get(order_no=f"{row_data.iloc[0]}-{row_data.iloc[1]}")
                if '/' in str(row_data.iloc[14]):
                    skin_resin, binder_resin = str(row_data.iloc[14]).split('/')
                else:
                    skin_resin, binder_resin = '', ''
                
                pd_information = {
                    "base": f"{row_data.iloc[7]}",
                    "skin_resin": skin_resin,
                    "binder_resin": binder_resin,
                    "rp_qty": f"{row_data.iloc[15]}",
                    "plan_remark": f"{row_data.iloc[16]}"
                }
                
                # ProductionPlan 모델 인스턴스 생성 또는 업데이트
                production_plan, created = ProductionPlan.objects.update_or_create(
                    sales_order=sales_order,
                    plan_date=row_data.iloc[11][:10],
                    defaults={
                        'plan_no': f"{row_data.iloc[12]}",
                        'plan_qty': int(row_data.iloc[13]),
                        'pd_line': f"{row_data.iloc[10]}",
                        'item_group': 'Dry',
                        'pd_information': pd_information
                    }
                )
            except:
                pass

            ws['A3'] = row_data.iloc[2]  # customer
            ws['F3'] = row_data.iloc[3]  # brand
            ws['A4'] = row_data.iloc[4]  # item
            ws['A5'] = row_data.iloc[5]  # color
            ws['F5'] = row_data.iloc[6]  # pattern
            ws['A6'] = f"{row_data.iloc[0]}-{row_data.iloc[1]}"   # order number
            ws['G6'] = row_data.iloc[7]  # Base
            ws['D6'] = row_data[8]  # order qty
            ws['C9'] = row_data.iloc[9]  # Remark
            ws['C11'] = row_data.iloc[16]  # Plan Remark

            ws['A17'] = f'D{row_data.iloc[10]}-{row_data.iloc[12]}'  # Line
            ws['F17'] = row_data.iloc[11][5:10]  # plan date
            ws['G7'] = f"Plan Qty: {row_data.iloc[13]} M"  # plan qty
            ws['A7'] = row_data.iloc[17]  # order type
            
            qr_str = f"!BSVPD!{row_data.iloc[0]}!{row_data.iloc[1]}!"
            qr_img = qrcode.make(qr_str).resize((160, 160))
            
            # QR 코드 이미지를 BytesIO 스트림에 저장합니다.
            img_stream = io.BytesIO()
            qr_img.save(img_stream, format='PNG')
            
            # 스트림 위치를 처음으로 돌립니다.
            img_stream.seek(0)
            
            # openpyxl 이미지 객체를 생성합니다.
            qr_img_openpyxl = Image(img_stream)
            
            # 워크시트에 QR 코드 이미지를 추가합니다.
            ws.add_image(qr_img_openpyxl, "G22")

            qr_img_2 = qrcode.make(qr_str).resize((160, 160))

            # QR 코드 이미지를 BytesIO 스트림에 저장합니다.
            img_stream_2 = io.BytesIO()
            qr_img_2.save(img_stream_2, format='PNG')
            
            # 스트림 위치를 처음으로 돌립니다.
            img_stream_2.seek(0)
            
            # openpyxl 이미지 객체를 생성합니다.
            qr_img_openpyxl_2 = Image(img_stream_2)
            
            # 워크시트에 QR 코드 이미지를 추가합니다.
            ws.add_image(qr_img_openpyxl_2, "A22")
        
        # 워크북을 저장하고 응답을 반환합니다.
        del wb['Sheet']
        wb.save(response)
        return response
    
    except Exception as e:
        # 에러가 발생하면 JSON 형식으로 에러 메시지를 반환합니다.
        return JsonResponse({'error': str(e)})

def dev_order_convert_to_qrcard(development_and_orders):
    try:
        # 엑셀 파일로 응답을 생성합니다.
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="dev_qrcard_.xlsx"'
        
        # JSON 데이터를 pandas DataFrame으로 변환합니다.
        # df = pd.read_json(df_json)
        
        # 새 워크북을 생성하고 기존의 'qrcard.xlsx' 파일을 로드합니다.
        wb = openpyxl.Workbook()
        
        # S3에서 파일 가져오기
        excel_file = get_s3_file('forms/qrcard.xlsx')

        # openpyxl로 워크북 로드
        qrcard = openpyxl.load_workbook(excel_file)
        
        # 각 행에 대해 새 워크시트를 생성하고 데이터를 채웁니다.
        for development, order in development_and_orders:
            order_no = order.order_no
            order_info = order.order_information
            ws = wb.create_sheet(str(order_no))
            copy_sheet(qrcard['DEV'], ws)
            # 워크시트에 데이터를 채웁니다.
            
            ws['A3'] = str(development.category)
            #ws['F3'] = str(development.deadline)[2:]
            ws['A4'] = order_info['item']
            ws['A5'] = order_info['color']
            ws['F5'] = order_info['pattern']
            ws['A6'] = str(order_no)
            ws['G6'] = order_info['base']  # Base
            ws['A7'] = order_info['skin_resin']  # Base
            ws['G7'] = order_info['binder_resin']  # Base
            ws['D6'] = order_info['order_qty']  # order qty
            ws['C9'] = str(development.title)  # subject
            ws['C10'] = str(development.purpose)  # purpose
            ws['C11'] = str(development.content)  # Remark

            order_no.split('-')
            
            qr_str = f"!BSVPD!{order_no.split('-')[0]}!{order_no.split('-')[1]}!"
            qr_img = qrcode.make(qr_str).resize((160, 160))
            
            # QR 코드 이미지를 BytesIO 스트림에 저장합니다.
            img_stream = io.BytesIO()
            qr_img.save(img_stream, format='PNG')
            
            # 스트림 위치를 처음으로 돌립니다.
            img_stream.seek(0)
            
            # openpyxl 이미지 객체를 생성합니다.
            qr_img_openpyxl = Image(img_stream)
            
            # 워크시트에 QR 코드 이미지를 추가합니다.
            ws.add_image(qr_img_openpyxl, "G22")

            qr_img_2 = qrcode.make(qr_str).resize((160, 160))

            # QR 코드 이미지를 BytesIO 스트림에 저장합니다.
            img_stream_2 = io.BytesIO()
            qr_img_2.save(img_stream_2, format='PNG')
            
            # 스트림 위치를 처음으로 돌립니다.
            img_stream_2.seek(0)
            
            # openpyxl 이미지 객체를 생성합니다.
            qr_img_openpyxl_2 = Image(img_stream_2)
            
            # 워크시트에 QR 코드 이미지를 추가합니다.
            ws.add_image(qr_img_openpyxl_2, "A22")
        
        # 워크북을 저장하고 응답을 반환합니다.
        del wb['Sheet']
        wb.save(response)
        return response
    
    except Exception as e:
        # 에러가 발생하면 JSON 형식으로 에러 메시지를 반환합니다.
        return JsonResponse({'error': str(e)})