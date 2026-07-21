import unittest

from ._case_support import *

class Dcm4cheeStoreTests(StoreCaseSupport):
    """Focused assertion owner for Dcm4cheeStoreTests."""

    def test_dcm4chee_mapping_backfills_from_existing_attempts(self):
        patient = self.dependencies.patient_repository.create_patient_record(
            {
                "mrn": "MRN-300101",
                "firstName": "Avery",
                "middleName": "Lee",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
                "patientClass": "O",
                "assignedLocation": "CARDIOLOGY^ROOM1",
                "attendingProvider": "P123^Rivera^Elena",
                "accountNumber": "",
            }
        )
        profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "mwl": {"aeTitle": "DCM4CHEE", "defaultScheduledStationAETitle": "ECG_AP"},
        }
        order = self.dependencies.order_repository.create_dcm4chee_order_record(
            {"patientRecordId": patient["id"], "requestedAt": "20260708103000"}
        )
        payload = build_dcm4chee_mwl_payload(order, profile)
        attempt = self.dependencies.dcm4chee_mwl_attempt_coordinator.create_dcm4chee_mwl_attempt(
            int(order["id"]),
            profile,
            request_payload=payload,
            attempt_status=DCM4CHEE_MWL_STATUS_CREATED,
            http_status=200,
            response_body='{"created":true}',
        )
        with self.dependencies.database.connect() as connection:
            connection.execute("DELETE FROM local_dcm4chee_mwl_mappings")
            connection.execute("UPDATE local_dcm4chee_mwl_attempts SET mapping_id = NULL")

        reopened = assemble_application_dependencies(self.dependencies.database.path)
        mapping = reopened.dcm4chee_mwl_repository.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
        attempts = reopened.dcm4chee_mwl_repository.list_dcm4chee_mwl_attempts(int(order["id"]))

        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)
        self.assertEqual(mapping["lastAttemptId"], attempt["id"])
        self.assertEqual(mapping["accessionNumber"], "ACC-000001")
        self.assertEqual(mapping["patientId"], "MRN-300101")
        self.assertEqual(attempts[0]["mappingId"], mapping["id"])
        self.assertEqual(self.dependencies.order_repository.list_order_records()[0]["id"], order["id"])

    def test_dcm4chee_patient_sync_mapping_attempt_and_patient_view(self):
        patient = self.dependencies.patient_repository.create_patient_record(
            {
                "mode": "dicom",
                "mrn": "MRN-300102",
                "firstName": "Avery",
                "middleName": "Lee",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "hl7": {
                "host": "dcm4chee",
                "port": 2575,
                "receivingApplication": "DCM4CHEE",
                "receivingFacility": "DCM4CHEE",
                "patientAssigningAuthority": "local-dcm4chee",
            },
        }

        sync = self.dependencies.dcm4chee_patient_sync_repository.upsert_dcm4chee_patient_sync(int(patient["id"]), profile)
        attempt = self.dependencies.dcm4chee_patient_sync_repository.create_dcm4chee_patient_sync_attempt(
            int(patient["id"]),
            profile,
            patient_sync_id=int(sync["id"]),
            operation_type=DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
            request_url="mllp://dcm4chee:2575",
            request_payload="MSH|^~\\&|...",
        )
        updated_attempt = self.dependencies.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
            response_payload="MSH|^~\\&|...\rMSA|AA|ADT1|OK",
            ack={"code": "AA", "controlId": "ADT1", "text": "OK"},
        )
        updated_sync = self.dependencies.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_from_attempt(
            int(sync["id"]),
            updated_attempt,
            sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
        )
        refreshed = self.dependencies.patient_repository.get_patient_record(int(patient["id"]))
        attempts = self.dependencies.dcm4chee_patient_sync_repository.list_dcm4chee_patient_sync_attempts(int(patient["id"]))

        self.assertEqual(sync["status"], DCM4CHEE_PATIENT_SYNC_STATUS_PENDING)
        self.assertEqual(updated_sync["status"], DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED)
        self.assertEqual(updated_sync["patientId"], "MRN-300102")
        self.assertEqual(updated_sync["issuerOfPatientId"], "local-dcm4chee")
        self.assertEqual(updated_sync["ack"]["code"], "AA")
        self.assertFalse(updated_sync["retryable"])
        self.assertEqual(attempts[0]["requestUrl"], "mllp://dcm4chee:2575")
        self.assertEqual(refreshed["dcm4chee"]["patient"]["status"], DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED)

    def test_dcm4chee_patient_sync_failure_is_retryable(self):
        patient = self.dependencies.patient_repository.create_patient_record(
            {
                "mode": "dicom",
                "mrn": "MRN-300103",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        profile = {
            "profileName": "local-dcm4chee",
            "dimse": {"calledAETitle": "DCM4CHEE"},
            "hl7": {
                "host": "dcm4chee",
                "port": 2575,
                "receivingApplication": "DCM4CHEE",
                "receivingFacility": "DCM4CHEE",
                "patientAssigningAuthority": "local-dcm4chee",
            },
        }

        sync = self.dependencies.dcm4chee_patient_sync_repository.upsert_dcm4chee_patient_sync(
            int(patient["id"]),
            profile,
            sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
            increment_retry=True,
        )
        attempt = self.dependencies.dcm4chee_patient_sync_repository.create_dcm4chee_patient_sync_attempt(
            int(patient["id"]),
            profile,
            patient_sync_id=int(sync["id"]),
            attempt_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
            error_type="dcm4chee_hl7_unreachable",
            error_text="connection refused",
        )
        updated_sync = self.dependencies.dcm4chee_patient_sync_repository.update_dcm4chee_patient_sync_from_attempt(
            int(sync["id"]),
            attempt,
            sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
        )

        self.assertEqual(updated_sync["status"], DCM4CHEE_PATIENT_SYNC_STATUS_FAILED)
        self.assertTrue(updated_sync["retryable"])
        self.assertEqual(updated_sync["retryCount"], 1)
        self.assertEqual(updated_sync["lastErrorType"], "dcm4chee_hl7_unreachable")
        self.assertEqual(self.dependencies.patient_repository.get_patient_record(int(patient["id"]))["id"], patient["id"])


if __name__ == "__main__":
    unittest.main()
