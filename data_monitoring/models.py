from django.db import models
from django.utils import timezone
from production_management.models import ProductionPlan

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