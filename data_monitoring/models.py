from django.db import models
from django.utils import timezone
from production_management.models import SalesOrder, ProductionPlan
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
    sales_order = models.ForeignKey(SalesOrder, null=True, on_delete=models.CASCADE)
    production_plan = models.ForeignKey(ProductionPlan, null=True, on_delete=models.CASCADE)
    ins_qty = models.IntegerField()
    ins_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)
    qty_to_printing = models.IntegerField(null=True, blank=True)
    position = models.CharField(max_length=50, null=True, blank=True)
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    def __str__(self):
        return f"{self.production_plan.sales_order.order_no}-{self.production_plan.plan_date}"

class Printing(models.Model):
    sales_order = models.ForeignKey(SalesOrder, null=True, on_delete=models.CASCADE)
    production_plan = models.ForeignKey(ProductionPlan, null=True, on_delete=models.CASCADE)
    print_qty = models.IntegerField()
    print_information = models.JSONField(null=True)
    line_no = models.CharField(max_length=10)
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
        
        # Find missing numbers in lot_no from ProductionLot model
        existing_lots = ProductionLot.objects.filter(lot_no__startswith=today)
        
        existing_counts = sorted(
            int(lot.lot_no.split('-')[-1][:-1]) if lot.lot_no.split('-')[-1][-1] in 'AB'
            else int(lot.lot_no.split('-')[-1])
            for lot in existing_lots
            if '-' in lot.lot_no
        )
        
        count = 1
        for existing_count in existing_counts:
            if existing_count != count:
                break
            count += 1
        
        new_lot_no = f"{today}-{count}"
        return new_lot_no