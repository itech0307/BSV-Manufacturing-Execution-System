from django.db import migrations, models
import django.utils.timezone

class Migration(migrations.Migration):

    dependencies = [
        ('data_monitoring', '0007_printing'),
        ('data_monitoring', '0007_remove_inspection_next_step_and_more'),
    ]

    operations = [
        migrations.CreateModel(
            name='DataMonitoringPrinting',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('order_number', models.CharField(max_length=20)),
                ('defect_cause', models.CharField(max_length=100)),
                ('line_no', models.CharField(max_length=10)),
                ('create_date', models.DateTimeField(default=django.utils.timezone.now)),
            ],
        ),
    ]
