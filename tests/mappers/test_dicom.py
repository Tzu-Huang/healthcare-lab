import unittest

from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
)
from backend.mappers.dicom import project_mwl_attempt, project_mwl_mapping


class DicomMwlMapperTests(unittest.TestCase):
    def test_attempt_projection_preserves_payload_and_legacy_defaults(self):
        row = {
            "id": 1, "order_record_id": 2, "profile_name": "local", "server_identity": "DCM",
            "mwl_ae_title": "MWL", "scheduled_station_ae_title": "ECG", "local_dcm4chee_order_number": "ORD-2",
            "accession_number": "ACC-2", "requested_procedure_id": "RP-2", "scheduled_procedure_step_id": "SPS-2",
            "study_instance_uid": "1.2.3", "uid_root": "1.2", "request_url": "/mwl", "request_payload_json": '{"b":2}',
            "http_status": 200, "response_body": "ok", "attempt_status": "created", "error_type": "", "error_text": "",
            "attempted_at": "attempted", "completed_at": "completed", "created_at": "created", "updated_at": "updated",
        }

        projected = project_mwl_attempt(row)

        self.assertEqual(projected["requestPayload"], {"b": 2})
        self.assertIsNone(projected["mappingId"])
        self.assertEqual(projected["operationType"], DCM4CHEE_MWL_OPERATION_CREATE)
        self.assertEqual(list(projected), [
            "id", "mappingId", "operationType", "orderRecordId", "profileName", "serverIdentity", "mwlAETitle",
            "scheduledStationAETitle", "localDcm4cheeOrderNumber", "accessionNumber", "requestedProcedureId",
            "scheduledProcedureStepId", "studyInstanceUid", "uidRoot", "requestUrl", "requestPayload", "httpStatus",
            "responseBody", "status", "errorType", "error", "attemptedAt", "completedAt", "createdAt", "updatedAt",
        ])

    def test_mapping_projection_preserves_retry_verification_and_json_fallbacks(self):
        row = {
            "id": 3, "order_record_id": 4, "profile_name": "local", "server_identity": "DCM", "mwl_ae_title": "MWL",
            "scheduled_station_ae_title": "ECG", "local_dcm4chee_order_number": "ORD-4", "patient_id": "P4",
            "issuer_of_patient_id": "LAB", "accession_number": "ACC-4", "requested_procedure_id": "RP-4",
            "scheduled_procedure_step_id": "SPS-4", "study_instance_uid": "1.2.4", "worklist_label": "ECG",
            "uid_root": "1.2", "sync_status": "failed", "last_sync_at": "sync", "retry_count": 2,
            "last_attempt_id": 9, "last_http_status": 500, "last_response_body": "bad", "last_error_type": "http",
            "last_error_text": "failed", "last_error_payload_json": "not-json", "latest_request_payload_json": '{"request":1}',
            "latest_readback_payload_json": '[{"match":true}]', "created_at": "created", "updated_at": "updated",
        }

        projected = project_mwl_mapping(row)

        self.assertEqual(projected["retryCount"], 2)
        self.assertEqual(projected["lastErrorPayload"], {})
        self.assertEqual(projected["latestRequestPayload"], {"request": 1})
        self.assertEqual(projected["latestReadbackPayload"], [{"match": True}])
        self.assertEqual(projected["verification"], {
            "status": DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED, "lastVerifiedAt": "", "method": "",
            "attemptId": None, "query": {}, "match": {}, "errorType": "", "error": "", "errorPayload": {},
        })


if __name__ == "__main__":
    unittest.main()
