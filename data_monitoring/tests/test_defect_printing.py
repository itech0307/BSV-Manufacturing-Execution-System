import json
from django.test import TestCase
from django.urls import reverse
from data_monitoring.models import DataMonitoringPrinting

class DataMonitoringPrintingTest(TestCase):
    def test_create_defect_record(self):
        payload = {
            "scannedOrders": [{"order_number": "SOV0001-1"}],
            "quantityInput": "0",
            "machine": "L1",
            "defectCause": "Shiny",
        }
        response = self.client.post(
            reverse("data_monitoring:input_printing"),
            data=json.dumps(payload),
            content_type="application/json",
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(DataMonitoringPrinting.objects.count(), 1)
        record = DataMonitoringPrinting.objects.first()
        self.assertEqual(record.order_number, "SOV0001-1")
        self.assertEqual(record.defect_cause, "Shiny")
