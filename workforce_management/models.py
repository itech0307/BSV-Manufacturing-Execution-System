from django.db import models

class Worker(models.Model):
    DEPARTMENT_CHOICES = [
        ('BL', 'Boiler'),
        ('BF', 'Buffing'),
        ('RC', 'Recovery'),
        ('DL1', 'Dry Line1'),
        ('DL2', 'Dry Line2'),
        ('DL3', 'Dry Line3'),
        ('DL4', 'Dry Line4'),
        ('DM', 'Dry Mixing'),
        ('EB', 'Embossing'),
        ('ES', 'Environment and Safety'),
        ('INS', 'Inspection'),
        ('MT', 'Maintance'),
        ('PT', 'Printing'),
        ('PO', 'Production Office'),
        ('QC', 'Quality Control'),
        ('RP', 'Release Paper'),
        ('SM', 'Semi-Material'),
        ('SP', 'Shipment'),
        ('ST', 'Stock'),
        ('WL', 'Wet Line'),
        ('WM', 'Wet Mixing')
    ]

    POSITION_CHOICES = [
        ('GW', 'General Worker'),
        ('VTL', 'Vice Team Leader'),
        ('TL', 'Team Leader')
    ]

    worker_code = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    position = models.CharField(
        max_length=3,
        choices=POSITION_CHOICES,
        default='GW',
    )
    phone_number = models.CharField(max_length=100, null=True, blank=True)
    department = models.CharField(
        max_length=4,
        choices=DEPARTMENT_CHOICES,
        default='PO',
    )
    join_date = models.DateField()
    status = models.BooleanField(null=True) # 등록 시 null, 삭제 시 false

    def __str__(self):
        return f"{self.worker_code}-{self.name}"