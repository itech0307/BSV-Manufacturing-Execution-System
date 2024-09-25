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

def order_convert_to_qrcard(production_order):
    try:
        # 엑셀 파일로 응답을 생성합니다.
        response = HttpResponse(content_type='application/ms-excel')
        response['Content-Disposition'] = 'attachment; filename="qrcard_.xlsx"'
        
        # JSON 데이터를 pandas DataFrame으로 변환합니다.
        # df = pd.read_json(df_json)
        
        # 새 워크북을 생성하고 기존의 'qrcard.xlsx' 파일을 로드합니다.
        wb = openpyxl.Workbook()
        
        # S3에서 파일 가져오기
        excel_file = get_s3_file('forms/qrcard.xlsx')

        # openpyxl로 워크북 로드
        qrcard = openpyxl.load_workbook(excel_file)
        
        # 각 행에 대해 새 워크시트를 생성하고 데이터를 채웁니다.
        for order in production_order:
            order_no = order.order_no            
            
            ws = wb.create_sheet(str(order_no))
            copy_sheet(qrcard['DRY'], ws)
            # 워크시트에 데이터를 채웁니다.
            
            ws['A3'] = order.customer_name
            ws['F3'] = order.brand
            ws['A4'] = order.item_name
            ws['A5'] = order.color_code
            ws['F5'] = order.pattern
            ws['A6'] = order_no
            ws['G6'] = ''  # Base
            ws['D6'] = order.order_qty  # order qty
            ws['C9'] = order.order_remark  # Remark

            order_no_split = order_no.split('-')
            
            qr_str = f"!BSVPD!{order_no_split[0]}!{order_no_split[1]}!"
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

            qr_img_2 = qrcode.make(qr_str).resize((180, 180))

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