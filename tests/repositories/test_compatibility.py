import unittest

from ._case_support import *

class CompatibilityStoreTests(StoreCaseSupport):
    """Focused assertion owner for CompatibilityStoreTests."""

    def test_oie_settings_profile_migration_preserves_existing_workflow_records(self):
        patient = self.store.create_patient_record(self.patient_payload(mrn="MRN-LEGACY-001"))
        order = self.store.create_order_record({"patientRecordId": patient["id"]})
        result = self.store.record_oie_result(
            "MSH|legacy",
            {
                "messageControlId": "LEGACY-RESULT-1",
                "messageType": "ORU^R01",
                "patientMrn": "MRN-LEGACY-001",
                "placerOrderNumber": order["localOrderNumber"],
                "fillerOrderNumber": "",
            },
        )
        with self.store.connect() as connection:
            connection.execute("DROP TABLE oie_managed_channel_mappings")
            connection.execute("DROP TABLE oie_settings_profiles")

        reopened = DemoStore(self.store.path)

        self.assertEqual(reopened.get_patient_record(patient["id"])["id"], patient["id"])
        self.assertEqual(reopened.get_order_record(order["id"])["id"], order["id"])
        self.assertEqual(reopened.list_oie_results()[0]["id"], result["id"])
        self.assertEqual(
            reopened.get_oie_settings_profile()["managementApi"]["username"],
            "admin",
        )


if __name__ == "__main__":
    unittest.main()
