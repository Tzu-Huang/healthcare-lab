"""FHIR workflow row and boundary presentation."""

from __future__ import annotations

from typing import Any

from backend.domain.fhir_ledger import FHIR_SUPPORTED_RESOURCE_TYPES, json_value, mapping_for_resource_type
from backend.domain.statuses import FHIR_SYNC_STATUS_SYNCED
from backend.mappers.types import RowMapping


def project_workflow_record(row: RowMapping) -> dict[str, Any]:
    resource_type = row["resource_type"]
    return {
        "id": row["id"], "localFhirRecordNumber": row["local_fhir_record_number"],
        "localSourceType": row["local_source_type"], "localSourceId": row["local_source_id"],
        "resourceType": resource_type,
        "identifier": {"system": row["identifier_system"], "value": row["identifier_value"]},
        "resource": json_value(row["resource_json"], {}),
        "dependencies": json_value(row["dependency_json"], []),
        "mapping": mapping_for_resource_type(resource_type) if resource_type in FHIR_SUPPORTED_RESOURCE_TYPES else None,
        "medplum": {"id": row["medplum_resource_id"], "reference": row["medplum_resource_reference"]},
        "sync": {"status": row["sync_status"], "error": row["sync_error"],
                 "operationOutcome": json_value(row["operation_outcome_json"], {}),
                 "lastSyncAt": row["last_sync_at"], "syncStartedAt": row["sync_started_at"]},
        "createdAt": row["created_at"], "updatedAt": row["updated_at"],
        "localOnly": row["sync_status"] != FHIR_SYNC_STATUS_SYNCED,
    }


def project_sync_attempt(row: RowMapping) -> dict[str, Any]:
    return {
        "id": row["id"], "fhirRecordId": row["fhir_record_id"], "method": row["method"],
        "requestUrl": row["request_url"], "requestPayload": json_value(row["request_payload_json"], {}),
        "httpStatus": row["http_status"], "responsePayload": json_value(row["response_payload_json"], {}),
        "operationOutcome": json_value(row["operation_outcome_json"], {}),
        "error": row["error_text"], "attemptedAt": row["attempted_at"],
    }
