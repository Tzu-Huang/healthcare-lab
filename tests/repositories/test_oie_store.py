import unittest

from ._case_support import *

class OieStoreTests(StoreCaseSupport):
    """Focused assertion owner for OieStoreTests."""

    def test_order_send_result_persists_ack_and_transport_error(self):
        patient = self.store.create_patient_record(
            {
                "mrn": "MRN-A04-002",
                "firstName": "Jordan",
                "lastName": "Case",
                "dob": "19770102",
                "sex": "M",
            }
        )
        order = self.store.create_order_record({"patientRecordId": patient["id"]})

        accepted = self.store.update_order_send_result(
            order["id"],
            order_status="Accepted",
            ack_code="AA",
            ack_control_id="ORM1",
            ack_text="OK",
            ack_payload="MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8\rMSA|AA|ORM1|OK",
        )
        self.assertEqual(accepted["ack"]["code"], "AA")
        self.assertEqual(accepted["status"], "Accepted")

        failed = self.store.update_order_send_result(
            order["id"],
            order_status="Transport error",
            transport_error="connection refused",
        )
        self.assertEqual(failed["status"], "Transport error")
        self.assertEqual(failed["transportError"], "connection refused")


if __name__ == "__main__":
    unittest.main()
