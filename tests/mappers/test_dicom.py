import unittest

from backend.domain.statuses import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
)
from backend.mappers.dicom import (
    project_mwl_attempt,
    project_mwl_mapping,
    project_result_record,
    project_result_snapshot,
)


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

    def test_result_projection_preserves_reconciliation_artifact_and_generation(self):
        columns = [
            "id", "result_key", "patient_record_id", "order_record_id", "mapping_id", "profile_name",
            "server_identity", "source_ae_title", "study_instance_uid", "series_instance_uid", "sop_instance_uid",
            "accession_number", "patient_id", "issuer_of_patient_id", "requested_procedure_id",
            "scheduled_procedure_step_id", "modality", "study_datetime", "series_datetime", "instance_datetime",
            "viewer_url", "study_retrieve_url", "series_retrieve_url", "instance_retrieve_url",
            "reconciliation_status", "match_method", "match_strength", "query_url", "query_payload_json",
            "diagnostic_payload_json", "raw_metadata_json", "refresh_generation", "first_seen_at",
            "last_refreshed_at", "created_at", "updated_at",
        ]
        row = {column: f"value-{column}" for column in columns}
        row.update({
            "id": 7, "patient_record_id": 8, "order_record_id": 9, "mapping_id": 10,
            "query_payload_json": '{"query":true}', "diagnostic_payload_json": '{"reason":"matched"}',
            "raw_metadata_json": '{"source":"qido","type":"instance","artifact":{"mime":"application/pdf"}}',
            "refresh_generation": "generation-2",
        })

        projected = project_result_record(row)

        self.assertEqual(projected["reconciliationStatus"], "value-reconciliation_status")
        self.assertEqual(projected["queryPayload"], {"query": True})
        self.assertEqual(projected["diagnostic"], {"reason": "matched"})
        self.assertEqual(projected["source"], "qido")
        self.assertEqual(projected["sourceType"], "instance")
        self.assertEqual(projected["artifact"], {"mime": "application/pdf"})
        self.assertEqual(projected["refreshGeneration"], "generation-2")

    def test_refresh_snapshot_projection_preserves_list_and_rejects_invalid_shapes(self):
        self.assertEqual(project_result_snapshot('[{"id":2},{"id":1}]'), [{"id": 2}, {"id": 1}])
        self.assertEqual(project_result_snapshot('{"id":1}'), [])
        self.assertEqual(project_result_snapshot("not-json"), [])


if __name__ == "__main__":
    unittest.main()
