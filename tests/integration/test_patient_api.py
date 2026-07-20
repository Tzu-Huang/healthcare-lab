import unittest

from ._case_support import *

class PatientApiTests(ApiCaseSupport):
    """Focused assertion owner for PatientApiTests."""

    def test_patient_api_allocates_blank_mrn_and_rejects_duplicate(self):
        payload = {
            "mrn": "",
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }

        created = self.client.post("/api/patients", json=payload)

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["summary"]["mrn"], "MRN-000001")
        self.assertIn("PID|1||MRN-000001^^^HEALTHCARE_LAB^MR", item["payload"])

        duplicate = self.client.post("/api/patients", json={**payload, "mrn": "MRN-000001"})

        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("Patient MRN MRN-000001 already exists", duplicate.get_json()["error"])
        self.assertEqual(len(self.client.get("/api/patients").get_json()["items"]), 1)

    def test_integration_patient_lists_filter_to_their_own_protocol(self):
        store = self.dependencies
        patients = {
            mode: store.patient_repository.create_patient_record(
                {
                    "mode": mode,
                    "mrn": f"MRN-{mode.upper()}",
                    "firstName": mode,
                    "lastName": "Patient",
                    "dob": "19850412",
                    "sex": "F",
                }
            )
            for mode in ("hl7-v2", "fhir", "gdt", "dicom")
        }
        store.patient_fhir.create_patient_fhir_workflow_record(patients["fhir"])

        oie = self.client.get("/api/oie/workbench").get_json()["patients"]
        oie_local = self.client.get("/api/oie/local-adt-patients").get_json()["items"]
        gdt = self.client.get("/api/gdt/workbench").get_json()["patients"]
        medplum = self.client.get("/api/fhir/inventory").get_json()["patients"]
        dcm4chee = self.client.get("/api/patients?protocolVersion=DICOM").get_json()["items"]

        self.assertEqual([item["id"] for item in oie], [patients["hl7-v2"]["id"]])
        self.assertEqual([item["id"] for item in oie_local], [patients["hl7-v2"]["id"]])
        self.assertEqual([item["id"] for item in gdt], [patients["gdt"]["id"]])
        self.assertEqual([item["localSourceId"] for item in medplum], [str(patients["fhir"]["id"])])
        self.assertEqual([item["id"] for item in dcm4chee], [patients["dicom"]["id"]])

    def test_patient_api_creates_fhir_local_patient_without_medplum_base(self):
        self.set_medplum_base_url("")

        response = self.client.post(
            "/api/patients",
            json={
                "mode": "fhir",
                "mrn": "MRN-FHIR-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "FHIR R4")
        self.assertEqual(item["messageType"], "Patient")
        self.assertIn('"resourceType": "Patient"', item["payload"])
        self.assertEqual(item["fhir"]["sync"]["status"], "Sync failed")
        self.assertIn("base URL", item["fhir"]["sync"]["error"])


if __name__ == "__main__":
    unittest.main()
