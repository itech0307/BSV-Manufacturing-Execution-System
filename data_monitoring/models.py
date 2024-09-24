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
    lot_number = models.CharField(max_length=20, unique=True)
    create_date = models.DateTimeField(default=timezone.now)

    @classmethod
    def generate_roll_lot(cls):
        today = datetime.now().strftime('%m%d')
        three_days_ago = datetime.now() - timedelta(days=3)
        
        # 'DryLine'와 'RP'의 phase 검색
        production_phases = list(chain(
                DryLine.objects.filter(),
                Delamination.objects.filter()
            ))
        
        roll_lots = set()
        
        for phase in production_phases:
            if isinstance(phase, DryLine):
                roll_lots.add(phase.pd_lot)
            elif isinstance(phase, Delamination):
                roll_lots.add(phase.dlami_lot)
        
        existing_counts = sorted(
            int(roll_lot.split('-')[-1][:-1]) if roll_lot.split('-')[-1][-1] in 'AB'
            else int(roll_lot.split('-')[-1])
            for roll_lot in roll_lots 
            if '-' in roll_lot
        )
        
        count = 1
        for existing_count in existing_counts:
            if existing_count != count:
                break
            count += 1
        
        new_lot_number = f"{today}-{count}"
        cls.objects.create(lot_number=new_lot_number)
        return new_lot_number