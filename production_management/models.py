from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth.models import User

# ERP Order Information
class SalesOrder(models.Model):
    order_id = models.CharField(max_length=10) # SOV0000000 format, max 10 digits
    seq_no = models.IntegerField()  # Sequence number
    order_no = models.CharField(max_length=14, unique=True, editable=False) # Order number
    customer_order_no = models.CharField(max_length=100, null=True) # Customer order number
    customer_name = models.CharField(max_length=50) # Customer name
    order_type = models.CharField(max_length=2) # Order type
    order_date = models.DateField() # Order date
    rtd = models.DateField() # Requested delivery date
    etd = models.DateField() # Estimated delivery date
    brand = models.CharField(max_length=50) # Brand name
    item_name = models.CharField(max_length=50) # Item name
    color_code = models.CharField(max_length=50) # Color code
    pattern = models.CharField(max_length=50) # Pattern
    base_color = models.CharField(max_length=10, null=True) # Base color
    spec = models.CharField(max_length=50) # Spec
    order_qty = models.IntegerField() # Order quantity
    qty_unit = models.CharField(max_length=10) # Quantity unit
    unit_price = models.FloatField() # Unit price
    currency = models.CharField(max_length=10) # Currency
    order_remark = models.TextField(null=True) # Order remark
    model_name = models.CharField(max_length=100, null=True) # Model name
    sample_step = models.CharField(max_length=50, null=True) # Sample step
    production_location = models.CharField(max_length=50) # Production location
    product_group = models.CharField(max_length=10) # Product group
    product_type = models.CharField(max_length=50) # Product type   
    color_name = models.CharField(max_length=50, null=True) # Color name
    status = models.BooleanField(null=True) # Status, null when registered, True when shipped, False when deleted
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_no:
            self.order_no = f"{self.order_id}-{self.seq_no}"
        try:
            super().save(*args, **kwargs)
        except IntegrityError:
            raise ValidationError(f"Order number '{self.order_no}' already exists.")

    def __str__(self):
        return self.order_no

class SalesOrderUploadLog(models.Model):
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # Uploaded user
    upload_time = models.DateTimeField(auto_now_add=True)  # Upload time
    file_name = models.CharField(max_length=255)  # Uploaded file name
    file_hash = models.CharField(max_length=64)  # File hash (SHA-256)
    data_count = models.IntegerField()  # Uploaded data count

    def __str__(self):
        return f"{self.file_name} - {self.upload_time}"

class ProductionPlan(models.Model):
    sales_order = models.ForeignKey(SalesOrder, on_delete=models.CASCADE)
    plan_date = models.DateField()
    plan_no = models.CharField(max_length=10, null=True)
    plan_qty = models.IntegerField()
    pd_line = models.CharField(max_length=10)
    item_group = models.CharField(max_length=10)
    pd_information = models.JSONField()
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.sales_order.order_no}-{self.plan_date}"

class Development(models.Model):
    developer = models.ForeignKey(User, on_delete=models.CASCADE)
    title = models.CharField(max_length=100)
    purpose = models.CharField(max_length=200)
    category = models.CharField(max_length=50)
    deadline = models.DateField(null=True)
    content = models.TextField()
    status = models.CharField(
        max_length=10,
        choices=[('Progress', 'Progress'), ('Complete', 'Complete')],
        default='Progress'
    )
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.title
    
class DevelopmentOrder(models.Model):
    development = models.ForeignKey(Development, on_delete=models.CASCADE)
    order_no = models.CharField(max_length=14, unique=True, editable=False)
    item_name = models.CharField(max_length=50)
    color_code = models.CharField(max_length=50)
    pattern = models.CharField(max_length=50)
    base_color = models.CharField(max_length=10, null=True)
    spec = models.CharField(max_length=50)
    order_qty = models.IntegerField()
    qty_unit = models.CharField(max_length=10)
    order_remark = models.TextField(null=True)
    product_group = models.CharField(max_length=10)
    status = models.BooleanField(null=True)  # Status, null when registered, True when completed, False when deleted
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_no:
            # Get current date in 'YYMMDD' format
            date_str = self.create_date.strftime('%y%m%d')
            prefix = 'DEV0'

            # Find the last order number in the transaction and create a new number
            last_order = DevelopmentOrder.objects.filter(order_no__startswith=f'{prefix}{date_str}').order_by('order_no').last()
            if last_order:
                seq_no = int(last_order.order_no.split('-')[-1]) + 1
            else:
                seq_no = 1
            
            while True:
                new_order_no = f'{prefix}{date_str}-{seq_no}'
                if not DevelopmentOrder.objects.filter(order_no=new_order_no).exists():
                    self.order_no = new_order_no
                    break
                seq_no += 1
            
            # Create a new order number
            self.order_no = f'{prefix}{date_str}-{seq_no}'
        super(DevelopmentOrder, self).save(*args, **kwargs)

    def __str__(self):
        return self.order_no

class DevelopmentComment(models.Model):
    development = models.ForeignKey(Development, related_name='development_comment_set', on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)