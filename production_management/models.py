from django.db import models
from django.utils import timezone
from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.contrib.auth.models import User

# ERP 주문 정보
class SalesOrder(models.Model):
    order_id = models.CharField(max_length=10) # SOV0000000 양식으로 최대 10자리
    seq_no = models.IntegerField()  # 순번
    order_no = models.CharField(max_length=14, unique=True, editable=False) # 주문 번호
    customer_order_no = models.CharField(max_length=100, null=True) # 고객 주문 번호
    customer_name = models.CharField(max_length=50) # 고객사 명
    order_type = models.CharField(max_length=2) # 주문 유형
    order_date = models.DateField() # 주문 일자
    rtd = models.DateField() # 요청 출고일
    etd = models.DateField() # 예정 출고일
    brand = models.CharField(max_length=50) # 브랜드 명
    item_name = models.CharField(max_length=50) # 아이템 이름
    color_code = models.CharField(max_length=50) # 컬러 코드
    pattern = models.CharField(max_length=50) # 패턴
    base_color = models.CharField(max_length=10, null=True) # 베이스 컬러
    spec = models.CharField(max_length=50) # 스펙
    order_qty = models.IntegerField() # 주문 수량
    qty_unit = models.CharField(max_length=10) # 수량 단위
    unit_price = models.FloatField() # 미터 당 가격
    currency = models.CharField(max_length=10) # 통화
    order_remark = models.TextField(null=True) # 주문 비고
    model_name = models.CharField(max_length=100, null=True) # 모델 명
    sample_step = models.CharField(max_length=50, null=True) # 샘플 단계
    production_location = models.CharField(max_length=50) # 생산 위치
    product_group = models.CharField(max_length=10) # 제품 그룹
    product_type = models.CharField(max_length=50) # 제품 유형
    color_name = models.CharField(max_length=50, null=True) # 컬러 명
    status = models.BooleanField(null=True) # 등록 시 null, 출고 완료 시 True, 삭제 시 false
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
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)  # 업로드한 유저
    upload_time = models.DateTimeField(auto_now_add=True)  # 업로드 시간
    file_name = models.CharField(max_length=255)  # 업로드 파일 이름
    file_hash = models.CharField(max_length=64)  # 파일의 해시값 (SHA-256 기준)
    data_count = models.IntegerField()  # 업로드된 데이터 갯수

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
    status = models.BooleanField(null=True)  # 등록 시 null, 완료 시 True, 삭제 시 false
    create_date = models.DateTimeField(default=timezone.now)
    modify_date = models.DateTimeField(auto_now=True)

    def save(self, *args, **kwargs):
        if not self.order_no:
            # 현재 날짜를 'YYMMDD' 형식으로 가져옵니다.
            date_str = self.create_date.strftime('%y%m%d')
            prefix = 'DEV0'
            # 해당 날짜에 생성된 마지막 오더를 찾아서 순서 번호를 증가시킵니다.
            last_order = DevelopmentOrder.objects.filter(order_no__startswith=f'{prefix}{date_str}').order_by('order_no').last()
            if last_order:
                seq_no = int(last_order.order_no.split('-')[-1]) + 1
            else:
                seq_no = 1
            # 새 주문 번호를 생성합니다.
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