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
        
        # Find missing numbers by searching lot_no in the ProductionLot model
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

class Scanner(models.Model):
    hostname = models.CharField(max_length=60, unique=True)
    department = models.CharField(max_length=40, db_index=True)
    user_name = models.CharField(max_length=20, null=True, blank=True)
    ip_lan = models.GenericIPAddressField(null=True, blank=True)
    ip_tailscale = models.GenericIPAddressField(null=True, blank=True)

    is_active = models.BooleanField(default=True)   # Show/hide on MES
    last_seen = models.DateTimeField(null=True, blank=True, db_index=True)

    class Meta:
        ordering = ['department', 'hostname']

    # Dynamic online/offline status
    @property
    def online_status(self):
        if not self.last_seen:
            return "UNKNOWN"
        delta = timezone.now() - self.last_seen
        return "ONLINE" if delta.total_seconds() < 120 else "OFFLINE"

    def __str__(self):
        return f"{self.hostname} ({self.department})"

class ColorSwatch(models.Model):
    """Model to store color swatch information"""
    epc = models.CharField('EPC Code', max_length=200, unique=True, db_index=True)
    stt = models.IntegerField('STT')
    type = models.CharField('Loại (MG/SP)', max_length=2, choices=[('MG', 'Main'), ('SP', 'Sample')])
    customer = models.CharField('Khách hàng', max_length=200)
    item = models.CharField('Sản phẩm', max_length=200)
    color = models.CharField('Màu', max_length=50)
    pattern = models.CharField('Mẫu', max_length=100)
    base_color = models.CharField('Màu Base', max_length=100, null=True, blank=True)
    created_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(null=True, auto_now=True)

    last_location = models.CharField('Last Location', max_length=200, null=True, blank=True)
    class Meta:
        indexes = [
            models.Index(fields=['epc']),
        ]
        ordering = ['stt']

    def __str__(self):
        return f"{self.stt}_{self.type} - {self.customer} - {self.item} - {self.color} - {self.pattern}"

class ColorSwatchMovement(models.Model):
    """Model to store the history of color swatch movement"""

    color_swatch = models.ForeignKey(ColorSwatch, on_delete=models.CASCADE, related_name='movements')
    line_no = models.CharField('Line No', max_length=60, null=True, blank=True)
    created_date = models.DateTimeField('Received Time')
    created_by = models.CharField('Created By', max_length=20, null=True, blank=True)

    class Meta:
        ordering = ['-created_date']
        indexes = [
            models.Index(fields=['color_swatch', '-created_date']),
        ]

    def __str__(self):
        return f"{self.color_swatch} - {self.line_no} - {self.created_date}"

    @classmethod
    def cleanup_old_records(cls, days=15):
        """Delete old records but keep the latest movement for each swatch"""
        import logging
        from django.db import transaction
        logger = logging.getLogger(__name__)
        
        try:
            cutoff_date = timezone.now() - timedelta(days=days)
            
            with transaction.atomic():
                # Get all swatches that have movements older than cutoff_date
                swatches_with_old_movements = cls.objects.filter(
                    created_date__lt=cutoff_date
                ).values_list('color_swatch_id', flat=True).distinct()
                
                total_deleted = 0
                
                for swatch_id in swatches_with_old_movements:
                    # Get the latest movement for this swatch
                    latest_movement = cls.objects.filter(
                        color_swatch_id=swatch_id
                    ).order_by('-created_date').first()
                    
                    if latest_movement:
                        # Delete all movements for this swatch except the latest one
                        deleted_count, _ = cls.objects.filter(
                            color_swatch_id=swatch_id,
                            created_date__lt=cutoff_date
                        ).exclude(id=latest_movement.id).delete()
                        
                        total_deleted += deleted_count
                
                logger.info(f"Cleanup completed: Deleted {total_deleted} old ColorSwatchMovement records, keeping latest movement for each swatch")
                return total_deleted
                
        except Exception as e:
            logger.error(f"Error during cleanup_old_records: {str(e)}")
            return 0 