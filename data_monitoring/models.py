from django.db import models
from django.utils import timezone
from production_management.models import ProductionPlan
from itertools import chain
from datetime import datetime, timedelta

class DryMix(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    mixing_information = models.JSONField(null=True)
    worker_code = models.CharField(max_length=10)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"

class WetMix(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    mixing_information = models.JSONField(null=True)
    worker_code = models.CharField(max_length=10)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"
    
class DryLine(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    pd_qty = models.IntegerField()
    pd_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)
    ag_position = models.CharField(max_length=50, null=True)
    pd_lot = models.CharField(max_length=50, null=True)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"

class WetLine(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    pd_qty = models.IntegerField()
    pd_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)
    pd_lot = models.CharField(max_length=50, null=True)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"
    
class Delamination(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    dlami_qty = models.IntegerField()
    dlami_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)
    dlami_lot = models.CharField(max_length=50, null=True)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"

class Inspection(models.Model):
    production_plan = models.ForeignKey(ProductionPlan, on_delete=models.CASCADE)
    ins_qty = models.IntegerField()
    ins_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)    
    position = models.CharField(max_length=50)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"

class ProductionLot(models.Model):
    lot_no = models.CharField(max_length=20, unique=True)
    create_date = models.DateTimeField(default=timezone.now)

    @classmethod
    def generate_lot(cls):
        today = datetime.now().strftime('%m%d')
        three_days_ago = datetime.now() - timedelta(days=3)
        
        # 'DryLine'와 'RP'의 phase 검색
        production_phases = list(chain(
                DryLine.objects.filter(),
                Delamination.objects.filter()
            ))
        
        lots_set = set()
        
        for phase in production_phases:
            if isinstance(phase, DryLine):
                lot_no = phase.pd_lot
            elif isinstance(phase, Delamination):
                lot_no = phase.dlami_lot
            
            if lot_no.split('-')[-1][-1:] in 'AB':
                lot_no = lot_no[:-1]
            else:
                lot_no = lot_no
            if today in lot_no:
                lots_set.add(lot_no)
        
        # 현재 lot_no의 숫자를 추출
        existing_counts = sorted(
            int(lot_no.split('-')[-1][:-1]) if lot_no.split('-')[-1][-1] in 'AB'
            else int(lot_no.split('-')[-1])
            for lot_no in lots_set 
            if '-' in lot_no
        )
        
        # 누락된 숫자 찾기
        count = 1
        for existing_count in existing_counts:
            if existing_count != count:
                break
            count += 1
        
        new_lot_no = f"{today}-{count}"
        cls.objects.create(lot_no=new_lot_no)
        return new_lot_no