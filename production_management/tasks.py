import openpyxl
from copy import copy
import pandas as pd
from production_management.models import SalesOrder
from datetime import datetime

# Celery
from celery import shared_task
# Celery-progress
from celery_progress.backend import ProgressRecorder

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

#@shared_task(bind=True)
def ordersheet_upload_celery(df_json):
    # 작업 진행 상황을 기록하기 위한 객체
    #progress_recorder = ProgressRecorder(self)
    
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
                    'product_type': df['Custom No'][i],
                    'status': True
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
    
        #progress_recorder.set_progress(i + 1, len(df), description="Uploading")