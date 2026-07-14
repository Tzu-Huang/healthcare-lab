from __future__ import annotations

import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from flask import Flask, jsonify, request
from werkzeug.middleware.proxy_fix import ProxyFix
try:
    from dotenv import load_dotenv
except ModuleNotFoundError:  # pragma: no cover - optional in minimal test envs
    def load_dotenv(*_args, **_kwargs):
        return False

from backend.config import (
    DCM4CHEE_AUTH_MODES,
    DCM4CHEE_PROFILE_NAME,
    MEDPLUM_DEFAULT_AUTH_GRACE_SECONDS,
    coerce_config_bool,
    coerce_config_int,
    load_application_config,
    normalize_gdt_bridge_success_mode,
    normalize_gdt_filename_profile,
    parse_app_host,
    parse_app_port,
    parse_config_bool,
)
from backend.clients.medplum import (
    MedplumAccessToken,
    MedplumAuthManager,
    derive_medplum_token_url,
    normalize_fhir_base_url,
    request_fhir_json,
    request_fhir_raw,
)
from backend.clients import dcm4chee as dcm4chee_client
from backend.clients import oie as oie_client
from backend.clients.health import (
    DOCKER_COMPOSE_APPLICATION_URLS,
    run_http_smoke,
    run_lab_application_check,
    run_tcp_smoke,
    smoke_step,
)
from backend.api.oie import create_oie_blueprint
from backend.api.lab_servers import create_lab_servers_blueprint
from backend.api.dashboard import create_dashboard_blueprint
from backend.api.dcm4chee import create_dcm4chee_profile_blueprint
from backend.api.patients import create_patients_blueprint
from backend.api.orders import create_orders_blueprint
from backend.api.fhir import create_fhir_blueprint
from backend.api.gdt import create_gdt_blueprint
from backend.api.home import create_home_blueprint
from backend.services.patient_workflow import PatientWorkflowService, sync_patient_to_dcm4chee
from backend.services.order_workflow import (
    OrderWorkflowService,
    dcm4chee_patient_payload_from_mwl_payload,
    ensure_dcm4chee_patient_for_mwl_payload,
    sync_order_to_dcm4chee_mwl,
)
from backend.services.oie_workflow import (
    OieWorkflowService,
    accept_oie_result_payload,
    build_hl7_ack,
    mllp_frame,
    mllp_unframe,
    parse_hl7_ack,
    parse_oru_summary,
)
from backend.services.gdt_workflow import (
    GdtWorkflowService,
    discover_gdt_inbound_candidates,
    gdt_collision_safe_path,
    gdt_file_is_stable,
    gdt_filename_binding_matches,
    gdt_has_supported_exchange_extension,
    gdt_inbound_sort_key,
    gdt_is_internal_or_temp_file,
    gdt_path_status,
    import_gdt_bridge_files,
)
from backend.services.fhir_workflow import (
    FhirWorkflowService,
    first_fhir_bundle_resource,
    medplum_create_resource_url,
    medplum_identifier_search_url,
    medplum_resource_reference,
    medplum_update_resource_url,
    sync_fhir_workflow_record_to_medplum,
)
from backend.domain.errors import UpstreamDcm4cheeError, UpstreamFhirError, ValidationError
from backend.domain.validation import require_http_url
from backend.domain.dicom import validate_dcm4chee_profile
from backend.domain import fhir as fhir_domain
from backend.runtime.gdt_bridge_watcher import GdtBridgeInboundWatcher as RuntimeGdtBridgeInboundWatcher
from backend.runtime.oie_result_listener import OieResultListener as RuntimeOieResultListener
from backend.services.oie_settings import OieSettingsService
from backend.lab_store import (
    DCM4CHEE_MWL_OPERATION_CREATE,
    DCM4CHEE_MWL_OPERATION_VERIFY,
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
    DCM4CHEE_MWL_VERIFICATION_FAILED,
    DCM4CHEE_MWL_VERIFICATION_VERIFIED,
    DCM4CHEE_MWL_OPERATION_READBACK,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    DemoStore,
    LAB_OPERATION_ACTIONS,
    LAB_HEALTH_STATUSES,
    LAB_SERVER_PROTOCOLS,
    LAB_SERVER_TYPES,
    HL7_V2_MSH_SUFFIX,
    FHIR_SYNC_STATUS_FAILED,
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCED,
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    ORDER_STATUS_ACCEPTED,
    ORDER_STATUS_ERROR,
    ORDER_STATUS_REJECTED,
    ORDER_STATUS_TRANSPORT_ERROR,
    OpenEMRProcedureOrderSource,
    SimulatorValidationError,
    ensure_gdt_bridge_dirs,
    parse_openemr_allowed_procedure_codes,
    validate_gdt_bridge_dirs,
)
from backend.lab_operations import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
    LabOperationError,
)
from backend.dashboard_services import (
    LAB_DASHBOARD_SERVICE_GROUPS,
    collect_dashboard_resource_snapshot,
    dashboard_action_for_group,
    dashboard_child_for_group,
    dashboard_health_rank,
    dashboard_operation_services,
    dashboard_servers_for_group,
    dashboard_summary,
    derive_dashboard_group_status,
)

MEDPLUM_INVENTORY_RESOURCE_TYPES = (
    "Patient",
    "ServiceRequest",
    "DiagnosticReport",
    "Observation",
    "DocumentReference",
)
MEDPLUM_READ_RESOURCE_TYPES = MEDPLUM_INVENTORY_RESOURCE_TYPES + ("Binary",)
MEDPLUM_PATIENT_REFERENCE_FIELDS = ("subject", "patient")
PROJECT_ROOT = Path(__file__).resolve().parents[1]

load_dotenv(PROJECT_ROOT / ".env")

# Compatibility exports for existing integrations and test patch seams.
OieResultListener = RuntimeOieResultListener
GdtBridgeInboundWatcher = RuntimeGdtBridgeInboundWatcher
send_hl7_mllp_message = oie_client.send_hl7_mllp_message

def error_response(message: str, status_code: int):
    return jsonify({"success": False, "error": message}), status_code


def dcm4chee_archive_dicomweb_url_from_base(base_url: str, called_ae_title: str) -> str:
    base = str(base_url or "").strip().rstrip("/")
    ae_title = urllib.parse.quote(str(called_ae_title or "DCM4CHEE").strip() or "DCM4CHEE", safe="")
    if not base:
        return f"http://127.0.0.1:8082/dcm4chee-arc/aets/{ae_title}/rs"
    parsed = urllib.parse.urlparse(base)
    if not parsed.scheme or not parsed.netloc:
        return f"http://127.0.0.1:8082/dcm4chee-arc/aets/{ae_title}/rs"
    path_parts = [part for part in parsed.path.split("/") if part]
    if "aets" in path_parts:
        index = path_parts.index("aets")
        if len(path_parts) > index + 1:
            path_parts[index + 1] = ae_title
    archive_path = "/" + "/".join(path_parts)
    return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, archive_path, "", "", "")).rstrip("/")


def dcm4chee_profile_from_config(config: dict[str, Any]) -> dict[str, Any]:
    profile_name = str(config.get("DCM4CHEE_PROFILE_NAME", DCM4CHEE_PROFILE_NAME) or "").strip()
    called_ae_title = str(config.get("DCM4CHEE_CALLED_AE_TITLE", "DCM4CHEE") or "").strip()
    mwl_ae_title = str(config.get("DCM4CHEE_MWL_AE_TITLE", "WORKLIST") or "").strip()
    dicomweb_base_url = str(
        config.get(
            "DCM4CHEE_DICOMWEB_BASE_URL",
            f"http://127.0.0.1:8082/dcm4chee-arc/aets/{mwl_ae_title or 'WORKLIST'}/rs",
        )
        or ""
    ).strip().rstrip("/")
    web_ui_url = str(
        config.get("DCM4CHEE_WEB_UI_URL", "http://127.0.0.1:8082/dcm4chee-arc/ui2") or ""
    ).strip().rstrip("/")
    archive_dicomweb_base_url = dcm4chee_archive_dicomweb_url_from_base(dicomweb_base_url, called_ae_title)
    qido_url = str(config.get("DCM4CHEE_QIDO_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
    wado_url = str(config.get("DCM4CHEE_WADO_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
    stow_url = str(config.get("DCM4CHEE_STOW_RS_URL") or archive_dicomweb_base_url).strip().rstrip("/")
    viewer_url_template = (
        str(config.get("DCM4CHEE_VIEWER_STUDY_URL_TEMPLATE") or "").strip()
        or (f"{web_ui_url}/#/study/{{studyInstanceUid}}" if web_ui_url else "")
    )
    return {
        "profileName": profile_name,
        "displayName": str(config.get("DCM4CHEE_DISPLAY_NAME", "dcm4chee Local Archive") or "").strip(),
        "environmentName": str(config.get("DCM4CHEE_ENVIRONMENT_NAME", "local-docker") or "").strip(),
        "webUiUrl": web_ui_url,
        "dimse": {
            "host": str(config.get("DCM4CHEE_DIMSE_HOST", "127.0.0.1") or "").strip(),
            "port": coerce_config_int(config.get("DCM4CHEE_DIMSE_PORT"), default=11112),
            "calledAETitle": called_ae_title,
            "callingAETitle": str(
                config.get("DCM4CHEE_CALLING_AE_TITLE", "HEALTHCARE_LAB") or ""
            ).strip(),
        },
        "mwl": {
            "aeTitle": mwl_ae_title,
            "defaultScheduledStationAETitle": str(
                config.get("DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE", "ECG_AP") or ""
            ).strip(),
        },
        "hl7": {
            "host": str(config.get("DCM4CHEE_HL7_HOST", "127.0.0.1") or "").strip(),
            "port": coerce_config_int(config.get("DCM4CHEE_HL7_PORT"), default=2575),
            "sendingApplication": str(
                config.get("DCM4CHEE_HL7_SENDING_APPLICATION", "HEALTHCARE_LAB") or ""
            ).strip(),
            "sendingFacility": str(config.get("DCM4CHEE_HL7_SENDING_FACILITY", "LAB_APP") or "").strip(),
            "receivingApplication": str(
                config.get("DCM4CHEE_HL7_RECEIVING_APPLICATION", "DCM4CHEE") or ""
            ).strip(),
            "receivingFacility": str(
                config.get("DCM4CHEE_HL7_RECEIVING_FACILITY", "DCM4CHEE") or ""
            ).strip(),
            "patientAssigningAuthority": str(
                config.get("DCM4CHEE_PATIENT_ASSIGNING_AUTHORITY", profile_name) or ""
            ).strip(),
        },
        "dicomweb": {
            "baseUrl": dicomweb_base_url,
            "qidoRsUrl": qido_url,
            "wadoRsUrl": wado_url,
            "stowRsUrl": stow_url,
        },
        "viewer": {
            "studyUrlTemplate": viewer_url_template,
        },
        "security": {
            "authMode": str(config.get("DCM4CHEE_AUTH_MODE", "none") or "").strip().lower(),
            "tlsEnabled": coerce_config_bool(config.get("DCM4CHEE_TLS_ENABLED"), default=False),
            "tlsVerify": coerce_config_bool(config.get("DCM4CHEE_TLS_VERIFY"), default=True),
            "username": str(config.get("DCM4CHEE_USERNAME", "") or "").strip(),
            "tokenUrl": str(config.get("DCM4CHEE_TOKEN_URL", "") or "").strip(),
            "certificatePath": str(config.get("DCM4CHEE_CERTIFICATE_PATH", "") or "").strip(),
            "privateKeyPath": str(config.get("DCM4CHEE_PRIVATE_KEY_PATH", "") or "").strip(),
            "localLabOnly": str(config.get("DCM4CHEE_AUTH_MODE", "none") or "").strip().lower() == "none",
        },
    }


def current_timestamp() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace(
        "+00:00", "Z"
    )


def hl7_message_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


# Compatibility exports: implementation ownership is in ``backend.clients``.
request_dcm4chee_mwl_create = dcm4chee_client.request_dcm4chee_mwl_create
dcm4chee_archive_rs_base_url = dcm4chee_client.dcm4chee_archive_rs_base_url
request_dcm4chee_patient_search = dcm4chee_client.request_dcm4chee_patient_search
request_dcm4chee_patient_create = dcm4chee_client.request_dcm4chee_patient_create
request_dcm4chee_mwl_readback = dcm4chee_client.request_dcm4chee_mwl_readback
request_dcm4chee_mwl_verification = dcm4chee_client.request_dcm4chee_mwl_verification
request_dcm4chee_qido = dcm4chee_client.request_dcm4chee_qido


def classify_dcm4chee_mwl_verification_error(exc: UpstreamDcm4cheeError) -> str:
    body = str(exc.response_body or "").lower()
    text = str(exc).lower()
    if exc.http_status == 404 and "patient" in body and "exist" in body:
        return "patient_missing"
    if "mwl_rsservice" in body or "no web application" in body:
        return "mwl_endpoint_unsupported"
    if "profile" in text or "baseurl" in text:
        return "mwl_profile_invalid"
    return "dcm4chee_unreachable" if exc.http_status is None else "mwl_query_failed"


def match_dcm4chee_mwl_items(
    store: DemoStore,
    mapping: dict[str, Any],
    response_body: str,
) -> dict[str, Any]:
    expected = {
        "patient_id": str(mapping.get("patientId") or "").strip(),
        "issuer_of_patient_id": str(mapping.get("issuerOfPatientId") or "").strip(),
        "accession_number": str(mapping.get("accessionNumber") or "").strip(),
        "requested_procedure_id": str(mapping.get("requestedProcedureId") or "").strip(),
        "scheduled_procedure_step_id": str(mapping.get("scheduledProcedureStepId") or "").strip(),
        "scheduled_station_ae_title": str(mapping.get("scheduledStationAETitle") or "").strip(),
        "study_instance_uid": str(mapping.get("studyInstanceUid") or "").strip(),
        "worklist_label": str(mapping.get("worklistLabel") or "").strip(),
    }
    datasets = store.dcm4chee_datasets_from_response_body(response_body)
    if not datasets:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_FAILED,
            "errorType": "mwl_empty",
            "error": "dcm4chee MWL query returned no items for the expected identifiers.",
            "match": {},
            "errorPayload": {"expected": expected, "returnedCount": 0},
        }

    candidates: list[dict[str, Any]] = []
    mismatches: list[dict[str, Any]] = []
    for index, dataset in enumerate(datasets):
        found = store.dcm4chee_identifiers_from_dataset(dataset)
        strong_matches = []
        if expected["accession_number"] and found.get("accession_number") == expected["accession_number"]:
            strong_matches.append("accession_number")
        if (
            expected["requested_procedure_id"]
            and expected["scheduled_procedure_step_id"]
            and found.get("requested_procedure_id") == expected["requested_procedure_id"]
            and found.get("scheduled_procedure_step_id") == expected["scheduled_procedure_step_id"]
        ):
            strong_matches.append("requested_procedure_id+scheduled_procedure_step_id")
        conflicts = {
            key: {"expected": expected_value, "actual": found.get(key, "")}
            for key, expected_value in expected.items()
            if expected_value and found.get(key) and found.get(key) != expected_value
            and key
            in {
                "patient_id",
                "issuer_of_patient_id",
                "accession_number",
                "requested_procedure_id",
                "scheduled_procedure_step_id",
                "scheduled_station_ae_title",
            }
        }
        summary = {
            "index": index,
            "identifiers": found,
            "strongMatches": strong_matches,
            "conflicts": conflicts,
        }
        if strong_matches and not conflicts:
            candidates.append(summary)
        else:
            mismatches.append(summary)

    if len(candidates) == 1:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_VERIFIED,
            "errorType": "",
            "error": "",
            "match": {
                **candidates[0],
                "method": "dcm4chee-mwl-rest",
                "expected": expected,
                "returnedCount": len(datasets),
            },
            "errorPayload": {},
        }
    if len(candidates) > 1:
        return {
            "status": DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS,
            "errorType": "mwl_ambiguous",
            "error": "dcm4chee MWL query returned multiple matching items.",
            "match": {},
            "errorPayload": {"expected": expected, "candidates": candidates, "returnedCount": len(datasets)},
        }
    return {
        "status": DCM4CHEE_MWL_VERIFICATION_FAILED,
        "errorType": "mwl_mismatch",
        "error": "dcm4chee MWL query returned items, but none matched the expected order identifiers.",
        "match": {},
        "errorPayload": {"expected": expected, "items": mismatches, "returnedCount": len(datasets)},
    }


def verify_order_dcm4chee_mwl(
    store: DemoStore,
    order: dict[str, Any],
    profile: dict[str, Any],
) -> dict[str, Any]:
    diagnostics = validate_dcm4chee_profile(profile)
    mapping = store.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
    if not mapping:
        raise SimulatorValidationError("dcm4chee MWL mapping is not available for this order.")
    query_criteria = store.dcm4chee_mwl_verification_query_from_mapping(mapping)
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = str(dicomweb.get("baseUrl") or "").strip().rstrip("/")
    request_url = f"{base_url}/mwlitems"
    if query_criteria:
        request_url = f"{request_url}?{urllib.parse.urlencode(query_criteria)}"

    attempt = store.create_dcm4chee_mwl_verification_attempt(
        int(order["id"]),
        mapping,
        request_url=request_url,
        query_criteria=query_criteria,
    )
    method = "dcm4chee-mwl-rest"
    if (
        str(mapping.get("status") or "").strip() == DCM4CHEE_MWL_STATUS_PATIENT_MISSING
        or str(mapping.get("lastErrorType") or "").strip() == "patient_missing"
    ):
        error_text = (
            str(mapping.get("lastError") or "").strip()
            or "dcm4chee patient precondition is missing for this MWL order."
        )
        error_payload = {
            "lastSyncStatus": mapping.get("status") or "",
            "lastHttpStatus": mapping.get("lastHttpStatus"),
            "lastResponseBody": mapping.get("lastResponseBody") or "",
        }
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            http_status=mapping.get("lastHttpStatus"),
            response_body=mapping.get("lastResponseBody") or "",
            error_type="patient_missing",
            error_text=error_text,
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=DCM4CHEE_MWL_VERIFICATION_FAILED,
            method=method,
            query_criteria=query_criteria,
            error_type="patient_missing",
            error_text=error_text,
            error_payload=error_payload,
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}
    if not diagnostics["valid"]:
        error_text = str(diagnostics.get("summary") or "dcm4chee profile is incomplete or invalid.")
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_FAILED,
            error_type="mwl_profile_invalid",
            error_text=error_text,
            response_body=json.dumps(diagnostics, sort_keys=True),
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=DCM4CHEE_MWL_VERIFICATION_FAILED,
            method=method,
            query_criteria=query_criteria,
            error_type="mwl_profile_invalid",
            error_text=error_text,
            error_payload=diagnostics,
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}

    try:
        status, response_body, actual_url = request_dcm4chee_mwl_verification(profile, query_criteria)
    except UpstreamDcm4cheeError as exc:
        error_type = classify_dcm4chee_mwl_verification_error(exc)
        verification_status = (
            DCM4CHEE_MWL_VERIFICATION_FAILED
            if error_type != "mwl_ambiguous"
            else DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS
        )
        updated_attempt = store.update_dcm4chee_mwl_attempt_result(
            int(attempt["id"]),
            attempt_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING
            if error_type == "patient_missing"
            else DCM4CHEE_MWL_STATUS_FAILED,
            http_status=exc.http_status,
            response_body=exc.response_body,
            error_type=error_type,
            error_text=str(exc),
        )
        updated_mapping = store.update_dcm4chee_mwl_verification_result(
            int(order["id"]),
            attempt_id=int(updated_attempt["id"]),
            verification_status=verification_status,
            method=method,
            query_criteria=query_criteria,
            error_type=error_type,
            error_text=str(exc),
            error_payload={"responseBody": exc.response_body, "httpStatus": exc.http_status},
        )
        return {"attempt": updated_attempt, "mapping": updated_mapping}

    match_result = match_dcm4chee_mwl_items(store, mapping, response_body)
    attempt_status = (
        DCM4CHEE_MWL_STATUS_CREATED
        if match_result["status"] == DCM4CHEE_MWL_VERIFICATION_VERIFIED
        else DCM4CHEE_MWL_STATUS_FAILED
    )
    updated_attempt = store.update_dcm4chee_mwl_attempt_result(
        int(attempt["id"]),
        attempt_status=attempt_status,
        http_status=status,
        response_body=response_body,
        error_type=match_result["errorType"],
        error_text=match_result["error"],
    )
    updated_mapping = store.update_dcm4chee_mwl_verification_result(
        int(order["id"]),
        attempt_id=int(updated_attempt["id"]),
        verification_status=match_result["status"],
        method=method,
        query_criteria={**query_criteria, "requestUrl": actual_url},
        match_payload=match_result["match"],
        error_type=match_result["errorType"],
        error_text=match_result["error"],
        error_payload=match_result["errorPayload"],
    )
    return {"attempt": updated_attempt, "mapping": updated_mapping}


def dcm4chee_result_query_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    query = {
        "StudyInstanceUID": str(mapping.get("studyInstanceUid") or "").strip(),
        "AccessionNumber": str(mapping.get("accessionNumber") or "").strip(),
        "PatientID": str(mapping.get("patientId") or "").strip(),
        "IssuerOfPatientID": str(mapping.get("issuerOfPatientId") or "").strip(),
    }
    return {key: value for key, value in query.items() if value}


def dcm4chee_merge_result_metadata(
    base_metadata: dict[str, str],
    child_metadata: dict[str, str],
) -> dict[str, str]:
    merged = {**base_metadata}
    for key, value in child_metadata.items():
        if value or key not in merged:
            merged[key] = value
    return merged


def dcm4chee_result_refresh_generation() -> str:
    timestamp = datetime.now(timezone.utc).isoformat(timespec="microseconds")
    return f"{timestamp}-{uuid.uuid4().hex}"


def refresh_patient_dcm4chee_results(
    store: DemoStore,
    patient_record_id: int,
    profile: dict[str, Any],
) -> dict[str, Any]:
    store.get_patient_record(patient_record_id)
    mappings = store.list_dcm4chee_mwl_mappings_for_patient(patient_record_id)
    refreshed: list[dict[str, Any]] = []
    queries: list[dict[str, Any]] = []
    study_uid_counts: dict[str, int] = {}
    refresh_generation = dcm4chee_result_refresh_generation()
    store.begin_dcm4chee_result_refresh(patient_record_id, refresh_generation)
    if not mappings:
        diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient_record_id,
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            diagnostic_payload={"reason": "no_local_dcm4chee_orders"},
            refresh_generation=refresh_generation,
        )
        store.complete_dcm4chee_result_refresh(patient_record_id, refresh_generation)
        patient = store.get_patient_record(patient_record_id)
        return {
            "success": True,
            "patient": patient,
            "items": patient.get("dcm4chee", {}).get("dicomResults", []),
            "refreshed": [diagnostic],
            "queries": [],
            "refreshGeneration": refresh_generation,
        }

    for mapping in mappings:
        query = dcm4chee_result_query_from_mapping(mapping)
        try:
            status, studies_body, studies_url = request_dcm4chee_qido(profile, "studies", query)
        except (ValidationError, SimulatorValidationError) as exc:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
                query_payload=query,
                diagnostic_payload={"reason": "profile_invalid", "error": str(exc)},
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        except UpstreamDcm4cheeError as exc:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
                query_payload=query,
                diagnostic_payload={
                    "reason": "dcm4chee_query_failed",
                    "error": str(exc),
                    "httpStatus": exc.http_status,
                    "responseBody": exc.response_body,
                },
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        queries.append({"url": studies_url, "status": status, "query": query})
        study_datasets = store.dcm4chee_datasets_from_response_body(studies_body)
        if not study_datasets:
            diagnostic = store.record_dcm4chee_result_refresh_diagnostic(
                patient_record_id=patient_record_id,
                profile=profile,
                status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
                query_url=studies_url,
                query_payload=query,
                diagnostic_payload={"reason": "empty_study_query", "mappingId": mapping.get("id")},
                refresh_generation=refresh_generation,
            )
            refreshed.append(diagnostic)
            continue
        for study_dataset in study_datasets:
            study_metadata = store.dcm4chee_result_metadata_from_dataset(study_dataset)
            study_uid = study_metadata.get("study_instance_uid", "")
            if study_uid:
                study_uid_counts[study_uid] = study_uid_counts.get(study_uid, 0) + 1
            refreshed.append(
                store.upsert_dcm4chee_result_record(
                    study_metadata,
                    profile,
                    patient_record_id=patient_record_id,
                    query_url=studies_url,
                    query_payload=query,
                    raw_metadata=study_dataset,
                    refresh_generation=refresh_generation,
                )
            )
            if not study_uid:
                continue
            study_path = f"studies/{urllib.parse.quote(study_uid, safe='')}"
            for child_path in (f"{study_path}/series", f"{study_path}/instances"):
                try:
                    _child_status, child_body, child_url = request_dcm4chee_qido(profile, child_path, {})
                except UpstreamDcm4cheeError:
                    continue
                for child_dataset in store.dcm4chee_datasets_from_response_body(child_body):
                    child_metadata = store.dcm4chee_result_metadata_from_dataset(child_dataset)
                    metadata = dcm4chee_merge_result_metadata(study_metadata, child_metadata)
                    refreshed.append(
                        store.upsert_dcm4chee_result_record(
                            metadata,
                            profile,
                            patient_record_id=patient_record_id,
                            query_url=child_url,
                            query_payload={"parentStudyInstanceUID": study_uid},
                            raw_metadata=child_dataset,
                            refresh_generation=refresh_generation,
                        )
                    )

    for study_uid, count in study_uid_counts.items():
        if count > 1:
            refreshed.append(
                store.record_dcm4chee_result_refresh_diagnostic(
                    patient_record_id=patient_record_id,
                    profile=profile,
                    status=DCM4CHEE_RESULT_STATUS_DUPLICATE,
                    query_payload={"studyInstanceUid": study_uid},
                    diagnostic_payload={
                        "reason": "duplicate_study_candidates",
                        "studyInstanceUid": study_uid,
                        "count": count,
                    },
                    refresh_generation=refresh_generation,
                )
            )
    store.complete_dcm4chee_result_refresh(patient_record_id, refresh_generation)
    patient = store.get_patient_record(patient_record_id)
    return {
        "success": not any(
            item.get("reconciliationStatus") == DCM4CHEE_RESULT_STATUS_QUERY_FAILED
            for item in refreshed
        ),
        "patient": patient,
        "items": patient.get("dcm4chee", {}).get("dicomResults", []),
        "refreshed": refreshed,
        "queries": queries,
        "refreshGeneration": refresh_generation,
    }


def fetch_fhir_service_requests(
    base_url: str,
    token: str,
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        [
            ("_count", 20),
            ("_sort", "-_lastUpdated"),
            ("_include", "ServiceRequest:subject"),
            ("_include", "ServiceRequest:encounter"),
            ("_include", "ServiceRequest:requester"),
            ("_include", "ServiceRequest:performer"),
        ]
    )
    url = f"{base_url}/ServiceRequest?{query}"
    status_code, parsed_body = request_fhir_json(
        url, token, auth_manager=auth_manager, base_url=base_url
    )
    return {
        "resourceType": str(parsed_body.get("resourceType", "")).strip() or "Bundle",
        "status": status_code,
        "body": parsed_body,
        "requestUrl": url,
    }


def normalize_fhir_reference(value: str, resource_type: str) -> str:
    reference = value.strip()
    parts = [part.strip() for part in reference.split("/") if part.strip()]
    if len(parts) != 2 or parts[0] != resource_type:
        raise ValidationError(f"FHIR reference must look like {resource_type}/id.")
    return f"{resource_type}/{parts[1]}"


def fhir_bundle_resources(bundle: dict[str, Any], resource_type: str) -> list[dict[str, Any]]:
    if bundle.get("resourceType") != "Bundle":
        raise UpstreamFhirError(
            f"Medplum {resource_type} search returned a non-Bundle response.",
            response_payload=bundle,
        )
    entries = bundle.get("entry") or []
    if not isinstance(entries, list):
        raise UpstreamFhirError(
            f"Medplum {resource_type} Bundle entry is malformed.",
            response_payload=bundle,
        )
    resources: list[dict[str, Any]] = []
    for entry in entries:
        if not isinstance(entry, dict):
            continue
        resource = entry.get("resource")
        if isinstance(resource, dict) and resource.get("resourceType") == resource_type:
            resources.append(resource)
    return resources


def service_request_references(references: list[str]) -> list[str]:
    return [reference for reference in references if reference.startswith("ServiceRequest/")]


def diagnostic_report_effective_date(resource: dict[str, Any]) -> str:
    effective = str(resource.get("effectiveDateTime") or "").strip()
    if effective:
        return effective
    effective_period = resource.get("effectivePeriod")
    if isinstance(effective_period, dict):
        return str(
            effective_period.get("start")
            or effective_period.get("end")
            or ""
        ).strip()
    return str(resource.get("issued") or "").strip()


def attachment_reference_values(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        url = str(value.get("url") or "").strip()
        if url and re.match(r"^[A-Za-z]+/[A-Za-z0-9\-.]+$", url):
            references.append(url)
        for nested in value.values():
            for reference in attachment_reference_values(nested):
                if reference not in references:
                    references.append(reference)
    elif isinstance(value, list):
        for item in value:
            for reference in attachment_reference_values(item):
                if reference not in references:
                    references.append(reference)
    return references


def diagnostic_report_relationships(resource: dict[str, Any]) -> dict[str, Any]:
    media_references: list[str] = []
    for item in resource.get("media") or []:
        if isinstance(item, dict):
            media_references.extend(fhir_reference_values(item.get("link")))
    presented_form = resource.get("presentedForm") if isinstance(resource.get("presentedForm"), list) else []
    presented_form_references = attachment_reference_values(presented_form)
    related_references: list[dict[str, str]] = []
    for reference in all_fhir_references(resource) + presented_form_references:
        resource_type = reference.split("/", 1)[0] if "/" in reference else ""
        if resource_type not in {"Observation", "DocumentReference", "Binary"}:
            continue
        if any(item["reference"] == reference for item in related_references):
            continue
        related_references.append({"resourceType": resource_type, "reference": reference})
    return {
        "subject": fhir_reference_values(resource.get("subject")),
        "basedOn": fhir_reference_values(resource.get("basedOn")),
        "result": fhir_reference_values(resource.get("result")),
        "media": media_references,
        "presentedForm": presented_form_references,
        "related": related_references,
    }


def diagnostic_report_summary(
    resource: dict[str, Any],
    *,
    selected_service_request: str = "",
) -> dict[str, Any]:
    resource_id = str(resource.get("id") or "").strip()
    reference = f"DiagnosticReport/{resource_id}" if resource_id else ""
    relationships = diagnostic_report_relationships(resource)
    based_on = relationships["basedOn"]
    service_refs = service_request_references(based_on)
    result_refs = relationships["result"]
    attachment_count = len(relationships["media"]) + len(relationships["presentedForm"])
    relationship_type = (
        "order-linked"
        if service_refs and (not selected_service_request or selected_service_request in service_refs)
        else "patient-level"
    )
    return {
        "id": resource_id,
        "reference": reference,
        "resourceType": "DiagnosticReport",
        "code": first_code_text(resource.get("code")),
        "display": first_code_text(resource.get("code")) or reference or "DiagnosticReport",
        "status": str(resource.get("status") or "").strip(),
        "date": diagnostic_report_effective_date(resource),
        "issued": str(resource.get("issued") or "").strip(),
        "subject": relationships["subject"][0] if relationships["subject"] else "",
        "basedOn": based_on,
        "linkedOrder": service_refs[0] if service_refs else "",
        "relationshipType": relationship_type,
        "resultCount": len(result_refs),
        "attachmentCount": attachment_count,
        "relationships": relationships,
        "resource": resource,
    }


def fetch_fhir_diagnostic_report_bundle(
    base_url: str,
    token: str,
    *,
    patient_reference: str = "",
    service_request_reference: str = "",
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    base = normalize_fhir_base_url(base_url)
    patient_ref = normalize_fhir_reference(patient_reference, "Patient") if patient_reference else ""
    service_ref = (
        normalize_fhir_reference(service_request_reference, "ServiceRequest")
        if service_request_reference
        else ""
    )
    if not patient_ref and not service_ref:
        raise ValidationError("Patient or ServiceRequest reference is required.")

    def search(params: list[tuple[str, str]]) -> dict[str, Any]:
        query = urllib.parse.urlencode([("_count", "50"), ("_sort", "-date"), *params])
        url = f"{base}/DiagnosticReport?{query}"
        status_code, parsed_body = request_fhir_json(
            url, token, auth_manager=auth_manager, base_url=base
        )
        fhir_bundle_resources(parsed_body, "DiagnosticReport")
        return {"status": status_code, "body": parsed_body, "requestUrl": url}

    patient_fetch: dict[str, Any] | None = None
    patient_reports: list[dict[str, Any]] = []
    based_on_fetch: dict[str, Any] | None = None
    fallback_reason = ""
    report_resources: list[dict[str, Any]] = []
    strategy = "patient"

    def fetch_patient_reports(*, optional: bool = False) -> list[dict[str, Any]]:
        nonlocal patient_fetch, fallback_reason
        if not patient_ref:
            return []
        try:
            patient_fetch = search([("subject", patient_ref)])
            return fhir_bundle_resources(patient_fetch["body"], "DiagnosticReport")
        except UpstreamFhirError as exc:
            if not optional or exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            return []

    if service_ref:
        try:
            based_on_fetch = search([("based-on", service_ref)])
            order_reports = fhir_bundle_resources(based_on_fetch["body"], "DiagnosticReport")
            patient_reports = fetch_patient_reports(optional=True)
            patient_level_reports = [
                item for item in patient_reports
                if not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            by_reference: dict[str, dict[str, Any]] = {}
            for item in order_reports + patient_level_reports:
                item_id = str(item.get("id") or "").strip()
                key = f"DiagnosticReport/{item_id}" if item_id else json.dumps(item, sort_keys=True)
                by_reference[key] = item
            report_resources = list(by_reference.values())
            strategy = "based-on"
        except UpstreamFhirError as exc:
            if exc.http_status not in {400, 404, 422}:
                raise
            fallback_reason = str(exc)
            patient_reports = fetch_patient_reports()
            report_resources = [
                item for item in patient_reports
                if service_ref in fhir_reference_values(item.get("basedOn"))
                or not service_request_references(fhir_reference_values(item.get("basedOn")))
            ]
            strategy = "patient-filter"
    else:
        patient_reports = fetch_patient_reports()
        report_resources = patient_reports

    summaries = [
        diagnostic_report_summary(item, selected_service_request=service_ref)
        for item in report_resources
    ]
    return {
        "resourceType": "Bundle",
        "status": patient_fetch["status"] if patient_fetch else based_on_fetch["status"],
        "requestUrl": patient_fetch["requestUrl"] if patient_fetch else based_on_fetch["requestUrl"],
        "patientReference": patient_ref,
        "serviceRequestReference": service_ref,
        "strategy": strategy,
        "fallbackReason": fallback_reason,
        "empty": not summaries,
        "body": patient_fetch["body"] if patient_fetch else based_on_fetch["body"],
        "bundles": {
            "patient": patient_fetch,
            "basedOn": based_on_fetch,
        },
        "reports": summaries,
    }


def operation_outcome_from_payload(payload: dict[str, Any]) -> dict[str, Any]:
    if isinstance(payload, dict) and payload.get("resourceType") == "OperationOutcome":
        return payload
    return {}


def operation_outcome_from_error(message: str) -> dict[str, Any]:
    _, _, body = message.partition(": ")
    if not body:
        return {}
    try:
        parsed = json.loads(body)
    except json.JSONDecodeError:
        return {}
    return operation_outcome_from_payload(parsed)


def http_status_from_upstream_error(message: str) -> int | None:
    match = re.search(r"HTTP\s+(\d+)", message)
    return int(match.group(1)) if match else None


# Compatibility names backed by framework-independent domain implementations.
normalize_fhir_reference = fhir_domain.normalize_fhir_reference
fhir_bundle_resources = fhir_domain.fhir_bundle_resources
service_request_references = fhir_domain.service_request_references
diagnostic_report_effective_date = fhir_domain.diagnostic_report_effective_date
attachment_reference_values = fhir_domain.attachment_reference_values
operation_outcome_from_payload = fhir_domain.operation_outcome_from_payload
operation_outcome_from_error = fhir_domain.operation_outcome_from_error
http_status_from_upstream_error = fhir_domain.http_status_from_upstream_error


def medplum_reference_resource_url(base_url: str, reference: str) -> str:
    parts = [part.strip() for part in reference.strip().split("/") if part.strip()]
    if len(parts) != 2:
        raise ValidationError("Medplum resource reference must look like ResourceType/id.")
    resource_type, resource_id = parts
    if resource_type not in MEDPLUM_READ_RESOURCE_TYPES:
        raise ValidationError("Medplum resource reference type is not supported.")
    return (
        f"{base_url}/{urllib.parse.quote(resource_type, safe='')}/"
        f"{urllib.parse.quote(resource_id, safe='')}"
    )


def fhir_reference_values(value: Any) -> list[str]:
    if isinstance(value, str):
        return [value.strip()] if value.strip() else []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        return [reference] if reference else []
    if isinstance(value, list):
        references: list[str] = []
        for item in value:
            references.extend(fhir_reference_values(item))
        return references
    return []


def direct_patient_references(resource: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for field_name in MEDPLUM_PATIENT_REFERENCE_FIELDS:
        for reference in fhir_reference_values(resource.get(field_name)):
            if reference.startswith("Patient/") and reference not in references:
                references.append(reference)
    return references


def all_fhir_references(value: Any) -> list[str]:
    references: list[str] = []
    if isinstance(value, dict):
        reference = str(value.get("reference") or "").strip()
        if reference and reference not in references:
            references.append(reference)
        for nested in value.values():
            for nested_reference in all_fhir_references(nested):
                if nested_reference not in references:
                    references.append(nested_reference)
    elif isinstance(value, list):
        for item in value:
            for nested_reference in all_fhir_references(item):
                if nested_reference not in references:
                    references.append(nested_reference)
    return references


def first_code_text(value: Any) -> str:
    if isinstance(value, dict):
        text = str(value.get("text") or "").strip()
        if text:
            return text
        coding = value.get("coding")
        if isinstance(coding, list):
            for item in coding:
                if not isinstance(item, dict):
                    continue
                display = str(item.get("display") or item.get("code") or "").strip()
                if display:
                    return display
    return ""


def fhir_resource_summary(resource: dict[str, Any], reference: str) -> dict[str, str]:
    resource_type = str(resource.get("resourceType") or "").strip()
    status = str(resource.get("status") or "").strip()
    code = first_code_text(resource.get("code"))
    title = str(resource.get("title") or resource.get("description") or "").strip()
    if resource_type == "Patient":
        names = resource.get("name") if isinstance(resource.get("name"), list) else []
        name = ""
        for item in names:
            if not isinstance(item, dict):
                continue
            name = str(item.get("text") or "").strip()
            if not name:
                given = " ".join(str(value).strip() for value in item.get("given") or [] if str(value).strip())
                family = str(item.get("family") or "").strip()
                name = " ".join(value for value in (given, family) if value)
            if name:
                break
        identifiers = resource.get("identifier") if isinstance(resource.get("identifier"), list) else []
        mrn = ""
        for item in identifiers:
            if isinstance(item, dict) and str(item.get("value") or "").strip():
                mrn = str(item.get("value")).strip()
                break
        return {"primary": name or mrn or reference or "Patient", "secondary": mrn, "status": status}
    if resource_type == "DiagnosticReport":
        return {
            "primary": code or title or reference or "DiagnosticReport",
            "secondary": str(resource.get("issued") or resource.get("effectiveDateTime") or "").strip(),
            "status": status,
        }
    if resource_type == "Observation":
        value = ""
        if "valueQuantity" in resource and isinstance(resource["valueQuantity"], dict):
            quantity = resource["valueQuantity"]
            value = " ".join(
                str(part).strip()
                for part in (quantity.get("value"), quantity.get("unit") or quantity.get("code"))
                if str(part or "").strip()
            )
        return {"primary": code or reference or "Observation", "secondary": value, "status": status}
    if resource_type == "DocumentReference":
        return {"primary": title or code or reference or "DocumentReference", "secondary": str(resource.get("docStatus") or "").strip(), "status": status}
    return {"primary": code or title or reference or resource_type, "secondary": "", "status": status}


def medplum_inventory_record(record: dict[str, Any]) -> dict[str, Any]:
    sync_status = str((record.get("sync") or {}).get("status") or "")
    medplum = record.get("medplum") or {}
    reference = str(medplum.get("reference") or "").strip()
    resource = record.get("resource") if isinstance(record.get("resource"), dict) else {}
    patient_references = direct_patient_references(resource)
    if record.get("resourceType") == "Patient" and reference and reference not in patient_references:
        patient_references.insert(0, reference)
    references = all_fhir_references(resource)
    return {
        "id": record["id"],
        "localFhirRecordNumber": record["localFhirRecordNumber"],
        "localSourceType": record["localSourceType"],
        "localSourceId": record["localSourceId"],
        "resourceType": record["resourceType"],
        "identifier": record["identifier"],
        "patientReferences": patient_references,
        "references": references,
        "summary": fhir_resource_summary(resource, reference),
        "medplum": medplum,
        "sync": record["sync"],
        "createdAt": record["createdAt"],
        "updatedAt": record["updatedAt"],
        "retryable": sync_status in (FHIR_SYNC_STATUS_PENDING, FHIR_SYNC_STATUS_FAILED),
        "previewSource": (
            "medplum-live"
            if sync_status == FHIR_SYNC_STATUS_SYNCED and reference
            else "local-submitted"
        ),
    }


def derive_lab_overall_status(checks: dict[str, str]) -> str:
    values = [checks.get(level, "Unknown") for level in ("process", "application", "protocol")]
    known = [value for value in values if value != "Unknown"]
    if not known:
        return "Unknown"
    if "Down" in known:
        return "Down"
    if "Degraded" in known or len(known) != len(values):
        return "Degraded"
    return "Healthy"


def run_lab_protocol_check(
    server: dict[str, Any], application_status: str
) -> tuple[str, str]:
    protocol = str(server.get("protocol") or "None")
    if protocol == "GDT" and application_status == "Healthy":
        return "Healthy", "File-based GDT contract is represented by the internal lab service."
    if protocol in {"None", "GDT"}:
        return "Unknown", "No Phase 1 protocol endpoint check configured."
    if application_status == "Healthy":
        return "Healthy", "Protocol smoke check passed through application reachability."
    if application_status == "Down":
        return "Unknown", "Protocol smoke check skipped because application check failed."
    return "Unknown", "Protocol smoke check is not implemented for this service."


def smoke_status_from_steps(steps: list[dict[str, Any]]) -> str:
    required = [step for step in steps if step.get("required", True)]
    optional = [step for step in steps if not step.get("required", True)]
    if any(step["status"] == "Down" for step in required):
        return "Down"
    if any(step["status"] == "Degraded" for step in steps):
        return "Degraded"
    if any(step["status"] == "Down" for step in optional):
        return "Degraded"
    known = [step for step in steps if step["status"] != "Unknown"]
    if not known:
        return "Unknown"
    if len(known) != len(steps):
        return "Degraded"
    return "Healthy"


MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE = (
    "Auth not configured: set MEDPLUM_CLIENT_ID and MEDPLUM_CLIENT_SECRET on lab-app."
)


def describe_medplum_token_failure(exc: Exception) -> str:
    return f"Token request failed: {exc}"


def describe_medplum_service_request_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR data fetch unauthorized: {message}"
    return f"ServiceRequest fetch failed: {message}"


def describe_medplum_diagnostic_report_failure(exc: Exception) -> str:
    message = str(exc)
    if "Medplum returned HTTP 401:" in message:
        return f"FHIR DiagnosticReport fetch unauthorized: {message}"
    return f"DiagnosticReport fetch failed: {message}"


def run_gdt_bridge_smoke(app: Flask, server: dict[str, Any]) -> list[dict[str, Any]]:
    steps = [run_lab_application_check(server)]
    application_step = smoke_step("application_endpoint", steps[0][0], steps[0][1], required=False)
    bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
    probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
    try:
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        folder_step = smoke_step(
            "folder_write_read",
            "Healthy" if read_back == "ok" else "Down",
            str(bridge_dirs["root"]),
        )
    except OSError as exc:
        folder_step = smoke_step("folder_write_read", "Down", str(exc))
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    openemr_status = openemr_source.status() if openemr_source else {"configured": False}
    return [
        smoke_step("folder_structure", "Healthy", str(bridge_dirs["root"])),
        folder_step,
        smoke_step("bridge_folder_contract", "Healthy", "GDT bridge folders are writable."),
        smoke_step(
            "openemr_source_status",
            "Healthy" if openemr_status.get("configured") else "Unknown",
            json.dumps(openemr_status),
            required=False,
        ),
        application_step,
    ]


def run_gdt_folder_contract_smoke(app: Flask) -> dict[str, Any]:
    try:
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        probe_path = bridge_dirs["root"] / ".lab-smoke-probe"
        probe_path.write_text("ok", encoding="utf-8")
        read_back = probe_path.read_text(encoding="utf-8")
        probe_path.unlink(missing_ok=True)
        if read_back != "ok":
            return smoke_step(
                "gdt_folder_contract",
                "Down",
                f"Read-back mismatch under {bridge_dirs['root']}.",
            )
        return smoke_step(
            "gdt_folder_contract",
            "Healthy",
            f"GDT bridge folders are writable at {bridge_dirs['root']}.",
        )
    except OSError as exc:
        return smoke_step("gdt_folder_contract", "Down", str(exc))


def run_openemr_gdt_backend_verify(app: Flask, server: dict[str, Any]) -> list[dict[str, Any]]:
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    operation = server.get("operation") or {}
    backing_service = str(operation.get("backingService") or "").strip()
    smoke_base_url = base_url
    if operation.get("controlType") == "docker-compose":
        smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
    steps = [run_http_smoke(smoke_base_url, "openemr_http")]
    openemr_source = app.extensions.get("openemr_procedure_order_source")
    if openemr_source is None:
        steps.extend(
            [
                smoke_step("openemr_db_connection", "Down", "OpenEMR procedure-order source is unavailable."),
                smoke_step("openemr_order_schema", "Unknown", "Skipped because source is unavailable."),
                smoke_step("openemr_ecg_orders", "Unknown", "Skipped because source is unavailable.", required=False),
            ]
        )
    else:
        verify_result = openemr_source.verify_order_query()
        connection = verify_result["connection"]
        schema = verify_result["schema"]
        orders = verify_result["orders"]
        steps.extend(
            [
                smoke_step("openemr_db_connection", connection["status"], connection["message"]),
                smoke_step("openemr_order_schema", schema["status"], schema["message"]),
                smoke_step(
                    "openemr_ecg_orders",
                    orders["status"],
                    orders["message"],
                    required=False,
                ),
            ]
        )
    steps.append(run_gdt_folder_contract_smoke(app))
    return steps


def run_lab_smoke_check(
    app: Flask,
    store: DemoStore,
    server: dict[str, Any],
    *,
    auth_manager: MedplumAuthManager | None = None,
) -> dict[str, Any]:
    profile = server["operation"].get("smokeProfile") or ""
    base_url = str(server.get("baseUrl") or "").rstrip("/")
    steps: list[dict[str, Any]]
    if profile == "medplum":
        metadata_url = f"{base_url}/metadata" if base_url else ""
        steps = [
            run_http_smoke(base_url, "http_reachability"),
            run_http_smoke(metadata_url, "fhir_metadata", required=True),
        ]
        if auth_manager is not None and auth_manager.is_configured() and base_url:
            try:
                auth_manager.get_access_token(base_url)
                steps.append(smoke_step("oauth_token", "Healthy", "Token acquired.", required=False))
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("oauth_token", "Down", describe_medplum_token_failure(exc), required=False))
        else:
            steps.append(smoke_step("oauth_token", "Unknown", MEDPLUM_AUTH_NOT_CONFIGURED_MESSAGE, required=False))
        if base_url:
            try:
                fetch_result = fetch_fhir_service_requests(
                    base_url,
                    "",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                steps.append(
                    smoke_step(
                        "service_request_fetch",
                        "Healthy" if fetch_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {fetch_result['status']}",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("service_request_fetch", "Down", describe_medplum_service_request_failure(exc), required=False))
            try:
                diagnostic_result = fetch_fhir_diagnostic_report_bundle(
                    base_url,
                    "",
                    patient_reference="Patient/lab-smoke-probe",
                    auth_manager=auth_manager if auth_manager and auth_manager.is_configured() else None,
                )
                report_count = len(diagnostic_result["reports"])
                steps.append(
                    smoke_step(
                        "diagnostic_report_fetch",
                        "Healthy" if diagnostic_result["resourceType"] == "Bundle" else "Degraded",
                        f"HTTP {diagnostic_result['status']}; {report_count} report(s).",
                        required=False,
                    )
                )
            except (ValidationError, UpstreamFhirError) as exc:
                steps.append(smoke_step("diagnostic_report_fetch", "Down", describe_medplum_diagnostic_report_failure(exc), required=False))
        else:
            steps.append(smoke_step("service_request_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
            steps.append(smoke_step("diagnostic_report_fetch", "Unknown", "FHIR base URL is not configured.", required=False))
    elif profile == "gdt-bridge":
        steps = run_gdt_bridge_smoke(app, server)
    elif profile == "dcm4chee":
        dcm4chee_profile = dcm4chee_profile_from_config(app.config)
        diagnostics = validate_dcm4chee_profile(dcm4chee_profile)
        dimse = dcm4chee_profile["dimse"]
        steps = [
            smoke_step(
                "connection_profile",
                diagnostics["status"],
                diagnostics["summary"],
            ),
            run_http_smoke(dcm4chee_profile["webUiUrl"], "dicom_archive_http"),
            run_tcp_smoke(dimse["host"], dimse["port"], "dicom_dimse", required=False),
        ]
    elif profile == "oie":
        check_config = server.get("checkConfig") or {}
        mllp_host = str(check_config.get("mllpHost") or "").strip()
        mllp_port = check_config.get("mllpPort")
        operation = server.get("operation") or {}
        backing_service = str(operation.get("backingService") or "").strip()
        smoke_base_url = base_url
        if operation.get("controlType") == "docker-compose":
            smoke_base_url = DOCKER_COMPOSE_APPLICATION_URLS.get(backing_service, base_url)
        if backing_service == "oie" and mllp_host in {"127.0.0.1", "localhost"}:
            mllp_host = "oie"
        steps = [
            run_http_smoke(smoke_base_url, "oie_http"),
            run_tcp_smoke(mllp_host, mllp_port, "mllp_endpoint", required=False),
        ]
    elif profile == "hl7tester":
        steps = [
            run_tcp_smoke(str(server.get("host") or ""), server.get("port"), "hl7_listener", required=False),
            smoke_step(
                "pdf_ed_tool",
                "Healthy",
                "tests/test_b64_pdf.py is available."
                if Path("tests/test_b64_pdf.py").exists()
                else "Tool not found.",
                required=False,
            ),
        ]
    elif profile == "gdt-hospital":
        steps = [
            smoke_step("gdt_order_store", "Healthy", f"{len(store.list_gdt_orders())} order(s)."),
            smoke_step("bridge_contract", "Healthy", app.config["GDT_BRIDGE_PATH"]),
        ]
    elif profile == "openemr":
        steps = run_openemr_gdt_backend_verify(app, server)
    else:
        steps = [smoke_step("adapter", "Unknown", "No smoke profile is configured.", required=False)]
    overall_status = smoke_status_from_steps(steps)
    return {
        "profile": profile,
        "status": overall_status,
        "steps": steps,
        "requiredFailures": [step for step in steps if step.get("required", True) and step["status"] == "Down"],
        "optionalFailures": [step for step in steps if not step.get("required", True) and step["status"] == "Down"],
    }


def run_lab_server_health_check(store: DemoStore, server_id: int) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    if not server["enabled"]:
        return store.update_lab_server_health(
            server_id,
            overall_status="Unknown",
            process_status="Unknown",
            application_status="Unknown",
            protocol_status="Unknown",
            recent_error="Server is disabled.",
        )
    application_status, application_error = run_lab_application_check(server)
    protocol_status, protocol_note = run_lab_protocol_check(server, application_status)
    process_status = "Unknown"
    operation = server.get("operation") or {}
    if application_status == "Healthy" and operation.get("controlType") == "docker-compose":
        process_status = "Healthy"
    elif operation.get("controlType") == "internal-tool":
        process_status = "Healthy"
    checks = {
        "process": process_status,
        "application": application_status,
        "protocol": protocol_status,
    }
    recent_error = application_error if application_status == "Down" else ""
    if not recent_error and protocol_status in {"Degraded", "Down"}:
        recent_error = protocol_note
    return store.update_lab_server_health(
        server_id,
        overall_status=derive_lab_overall_status(checks),
        process_status=checks["process"],
        application_status=checks["application"],
        protocol_status=checks["protocol"],
        recent_error=recent_error,
    )


def resolve_lab_operator() -> str:
    return (
        os.environ.get("USERNAME")
        or os.environ.get("USER")
        or os.environ.get("LOGNAME")
        or "local-user"
    ).strip() or "local-user"


def restart_progress_steps(result: str, error_text: str = "") -> list[dict[str, str]]:
    steps = ["stop", "start", "wait_for_port", "application_health", "smoke", "final_status"]
    if result == "success":
        return [{"step": step, "status": "completed"} for step in steps]
    return [
        {
            "step": step,
            "status": "failed" if step == "final_status" else "completed",
            **({"error": error_text} if step == "final_status" and error_text else {}),
        }
        for step in steps
    ]


def run_internal_lab_operation(
    server: dict[str, Any],
    action: str,
    *,
    app: Flask,
    store: DemoStore,
    lines: int = 200,
) -> dict[str, Any]:
    service_name = server["name"]
    if action not in {"status", "smoke", "logs"}:
        raise LabOperationError(f"{service_name} does not support {action}.")
    if service_name == "GDT Bridge":
        bridge_dirs = ensure_gdt_bridge_dirs(app.config["GDT_BRIDGE_PATH"])
        status = {
            "bridgePath": str(bridge_dirs["root"]),
            "folders": {name: str(path) for name, path in bridge_dirs.items() if name != "root"},
        }
    elif service_name == "HL7Tester":
        status = {
            "message": "HL7Tester is monitored as an external service in Healthcare Lab.",
            "host": server.get("host"),
            "port": server.get("port"),
        }
    elif service_name == "GDT Hospital":
        status = {
            "bridgeRoot": app.config["GDT_BRIDGE_PATH"],
            "message": "GDT workflow APIs live in ECG AP Simulator; Healthcare Lab monitors runtime health only.",
        }
    else:
        status = {"message": f"No internal operation adapter for {service_name}."}
    output = json.dumps(status, indent=2)
    if action == "logs":
        output = "\n".join(output.splitlines()[-max(1, lines):])
    return {"output": output, "returnCode": 0, "command": ["internal", service_name, action]}


def decorate_lab_operation_availability(app: Flask, server: dict[str, Any]) -> dict[str, Any]:
    item = {**server}
    operation = {**(server.get("operation") or {})}
    if operation.get("controlType") == "docker-compose":
        reason = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"]).unavailable_reason()
        if reason:
            actions = operation.get("supportedActions") or []
            unavailable_actions = [action for action in actions if action != "smoke"]
            operation["supportedActions"] = [action for action in actions if action == "smoke"]
            operation["unavailableActions"] = unavailable_actions
            operation["unavailableReason"] = reason
    item["operation"] = operation
    return item


def dashboard_group_item(app: Flask, store: DemoStore, service_id: str) -> dict[str, Any]:
    group, servers = dashboard_servers_for_group(store, service_id)
    primary = next((server for server in servers if server["name"] == group["primary"]), servers[0])
    decorated_primary = decorate_lab_operation_availability(app, primary)
    status = derive_dashboard_group_status(servers)
    supported = set(decorated_primary.get("operation", {}).get("supportedActions") or [])
    process_statuses = [server.get("checks", {}).get("process", "Unknown") for server in servers]
    application_statuses = [server.get("checks", {}).get("application", "Unknown") for server in servers]
    protocol_statuses = [server.get("checks", {}).get("protocol", "Unknown") for server in servers]
    return {
        "id": service_id,
        "label": group["label"],
        "protocol": group["protocol"],
        "backend": group["backend"],
        "status": status,
        "enabled": all(server.get("enabled") for server in servers),
        "lastCheckAt": max((server.get("lastCheckAt") or "" for server in servers), default=""),
        "checks": {
            "process": min(process_statuses, key=dashboard_health_rank) if process_statuses else "Unknown",
            "application": min(application_statuses, key=dashboard_health_rank) if application_statuses else "Unknown",
            "protocol": min(protocol_statuses, key=dashboard_health_rank) if protocol_statuses else "Unknown",
        },
        "capabilities": {
            "check": True,
            "enable": "start" in supported,
            "disable": "stop" in supported,
            "restart": "restart" in supported,
        },
        "restartPreview": {
            "risk": group["risk"],
            "summary": group["riskSummary"],
            "affectedServices": list(group["affectedServices"]),
        },
        "children": dashboard_child_items(app, group),
        "components": [
            {
                "name": server["name"],
                "status": server["overallStatus"],
                "role": "primary" if server["name"] == group["primary"] else "supporting",
            }
            for server in servers
        ],
    }


def dashboard_child_item(app: Flask, child: dict[str, Any]) -> dict[str, Any]:
    adapter = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"])
    unavailable_reason = adapter.unavailable_reason()
    try:
        runtime = adapter.inspect(str(child["service"]), timeout_seconds=3)
    except LabOperationError as exc:
        runtime = {
            "exists": False,
            "running": False,
            "state": "Unknown",
            "detail": str(exc),
            "containerName": "",
        }
    return {
        "id": child["id"],
        "name": child["displayName"],
        "role": child["role"],
        "composeService": child["service"],
        "status": "Healthy" if runtime["running"] else (
            "Down" if runtime["state"] != "Unknown" else "Unknown"
        ),
        "runtime": runtime,
        "capabilities": {
            "check": True,
            "enable": not bool(unavailable_reason),
            "disable": not bool(unavailable_reason),
            "restart": not bool(unavailable_reason),
        },
    }


def dashboard_child_items(app: Flask, group: dict[str, Any]) -> list[dict[str, Any]]:
    children = list(group.get("children", ()))
    if not children:
        return []
    with ThreadPoolExecutor(max_workers=len(children)) as executor:
        return list(executor.map(lambda child: dashboard_child_item(app, child), children))


def dashboard_all_group_items(app: Flask, store: DemoStore) -> list[dict[str, Any]]:
    service_ids = list(LAB_DASHBOARD_SERVICE_GROUPS)
    with ThreadPoolExecutor(max_workers=len(service_ids)) as executor:
        return list(
            executor.map(
                lambda service_id: dashboard_group_item(app, store, service_id),
                service_ids,
            )
        )


def run_dashboard_group_health_check(store: DemoStore, service_id: str) -> list[dict[str, Any]]:
    _group, servers = dashboard_servers_for_group(store, service_id)
    return [run_lab_server_health_check(store, int(server["id"])) for server in servers]


def dashboard_events(store: DemoStore, items: list[dict[str, Any]], resource_snapshot: dict[str, Any]) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    for item in items:
        if item["lastCheckAt"]:
            events.append(
                {
                    "timestamp": item["lastCheckAt"],
                    "level": "info" if item["status"] == "Healthy" else "warn",
                    "serviceId": item["id"],
                    "message": f"{item['label']} health is {item['status']}.",
                }
            )
    for operation in store.list_lab_operations(limit=12):
        level = "info" if operation["result"] == "success" else "error"
        events.append(
            {
                "timestamp": operation["completedAt"] or operation["startedAt"],
                "level": level,
                "serviceId": "",
                "message": f"{operation['serviceName']} {operation['action']} {operation['result']}.",
            }
        )
    if resource_snapshot["status"] != "ok":
        events.append(
            {
                "timestamp": resource_snapshot["collectedAt"],
                "level": "warn",
                "serviceId": "",
                "message": f"Resource snapshot unavailable: {resource_snapshot['message']}",
            }
        )
    return sorted(events, key=lambda event: event["timestamp"], reverse=True)[:20]


def run_lab_operation(
    *,
    app: Flask,
    store: DemoStore,
    server_id: int,
    action: str,
    lines: int = 200,
    backing_services: list[str] | None = None,
    operation_service_name: str = "",
    refresh_health: bool = True,
) -> dict[str, Any]:
    server = store.get_lab_server(server_id)
    normalized_action = action.strip().lower()
    if normalized_action not in LAB_OPERATION_ACTIONS:
        raise SimulatorValidationError(f"Unsupported lab operation action: {normalized_action}.")
    operation = server["operation"]
    supported_actions = operation.get("supportedActions") or []
    if normalized_action not in supported_actions:
        raise SimulatorValidationError(f"{server['name']} does not support {normalized_action}.")
    started = time.monotonic()
    started_at = current_timestamp()
    output = ""
    command: list[str] = []
    result = "success"
    error_text = ""
    try:
        if normalized_action == "smoke":
            smoke_result = run_lab_smoke_check(
                app,
                store,
                server,
                auth_manager=MedplumAuthManager(
                    client_id=app.config["MEDPLUM_CLIENT_ID"],
                    client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
                    scope=app.config["MEDPLUM_SCOPE"],
                    token_url=app.config["MEDPLUM_TOKEN_URL"],
                    refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
                ),
            )
            output = json.dumps(smoke_result, indent=2)
            command = ["smoke", smoke_result["profile"] or server["name"]]
            checks = {
                "process": store.get_lab_server(server_id)["checks"]["process"],
                "application": smoke_result["status"],
                "protocol": smoke_result["status"],
            }
            error_text = ""
            if smoke_result["requiredFailures"] or smoke_result["optionalFailures"]:
                first_failure = (smoke_result["requiredFailures"] + smoke_result["optionalFailures"])[0]
                error_text = str(first_failure.get("message", "Smoke check failed."))
            store.update_lab_server_health(
                server_id,
                overall_status=derive_lab_overall_status(checks),
                process_status=checks["process"],
                application_status=checks["application"],
                protocol_status=checks["protocol"],
                recent_error=error_text,
            )
        elif operation.get("controlType") == "docker-compose":
            adapter = DockerComposeLabOperationAdapter(app.config["LAB_DEPLOY_SCRIPT"])
            unavailable_reason = adapter.unavailable_reason()
            if unavailable_reason:
                raise LabOperationError(
                    f"Docker Compose operation '{normalized_action}' is unavailable: {unavailable_reason}"
                )
            targets = backing_services or [operation.get("backingService") or server["name"]]
            outputs = []
            commands = []
            for target in targets:
                adapter_result = adapter.run(
                    normalized_action,
                    target,
                    timeout_seconds=int(operation.get("timeoutSeconds") or 60),
                    lines=lines,
                )
                outputs.append(f"[{target}]\n{adapter_result['output']}".rstrip())
                commands.append(adapter_result["command"])
            output = "\n".join(outputs)
            command = [part for adapter_command in commands for part in adapter_command]
        else:
            adapter_result = run_internal_lab_operation(
                server,
                normalized_action,
                app=app,
                store=store,
                lines=lines,
            )
            output = adapter_result["output"]
            command = adapter_result["command"]
        if refresh_health and normalized_action in {"start", "stop", "restart"}:
            run_lab_server_health_check(store, server_id)
    except (LabOperationError, ValidationError, UpstreamFhirError) as exc:
        result = "failed"
        error_text = str(exc)
    completed_at = current_timestamp()
    duration_ms = int((time.monotonic() - started) * 1000)
    progress = (
        restart_progress_steps(result, error_text)
        if normalized_action == "restart"
        else [{"step": normalized_action, "status": "completed" if result == "success" else "failed"}]
    )
    history = store.record_lab_operation(
        server_id,
        service_name=operation_service_name or server["name"],
        action=normalized_action,
        operator=resolve_lab_operator(),
        result=result,
        duration_ms=duration_ms,
        progress=progress,
        error_text=error_text,
        started_at=started_at,
        completed_at=completed_at,
    )
    response = {
        "server": decorate_lab_operation_availability(app, store.get_lab_server(server_id)),
        "operation": history,
        "output": output,
        "command": command,
    }
    if result != "success":
        raise LabOperationError(json.dumps(response))
    return response


def create_app(database_path: str | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "frontend" / "templates"),
        static_folder=str(PROJECT_ROOT / "frontend" / "static"),
    )
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1, x_proto=1, x_host=1, x_port=1)
    app.config.update(load_application_config(app.instance_path, database_path))
    Path(app.config["DATABASE_PATH"]).parent.mkdir(parents=True, exist_ok=True)
    store = DemoStore(app.config["DATABASE_PATH"])
    gdt_bridge_watcher = GdtBridgeInboundWatcher(
        store,
        app.config["GDT_BRIDGE_PATH"],
        import_gdt_bridge_files,
        poll_seconds=app.config["GDT_BRIDGE_WATCH_POLL_SECONDS"],
        success_mode=app.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"],
        filename_profile=app.config["GDT_BRIDGE_FILENAME_PROFILE"],
        receiver_id=app.config["GDT_BRIDGE_RECEIVER_ID"],
        sender_id=app.config["GDT_BRIDGE_SENDER_ID"],
        stable_seconds=app.config["GDT_BRIDGE_STABLE_SECONDS"],
    )
    openemr_source = OpenEMRProcedureOrderSource(
        host=app.config["OPENEMR_DB_HOST"],
        port=app.config["OPENEMR_DB_PORT"],
        user=app.config["OPENEMR_DB_USER"],
        password=app.config["OPENEMR_DB_PASSWORD"],
        database=app.config["OPENEMR_DB_NAME"],
        allowed_procedure_codes=app.config["OPENEMR_GDT_PROCEDURE_CODES"],
    )
    app.extensions["demo_store"] = store
    app.extensions["openemr_procedure_order_source"] = openemr_source
    app.extensions["oie_result_listener"] = OieResultListener(store, accept_oie_result_payload)
    app.extensions["gdt_bridge_watcher"] = gdt_bridge_watcher
    app.extensions["oie_settings_service"] = OieSettingsService(store.oie_settings_repository)
    app.extensions["oie_workflow_service"] = OieWorkflowService(
        store,
        app.config,
        app.extensions["oie_result_listener"],
        result_handler=accept_oie_result_payload,
        ack_parser=parse_hl7_ack,
        order_sender_provider=lambda: send_hl7_mllp_message,
    )
    app.register_blueprint(
        create_oie_blueprint(
            app.extensions["oie_settings_service"],
            app.extensions["oie_workflow_service"],
        )
    )
    app.register_blueprint(
        create_lab_servers_blueprint(
            app,
            store,
            health_checker=run_lab_server_health_check,
            decorate_availability=decorate_lab_operation_availability,
            operation_runner=run_lab_operation,
            operator_resolver=resolve_lab_operator,
        )
    )
    app.register_blueprint(
        create_dashboard_blueprint(
            app,
            store,
            all_items=dashboard_all_group_items,
            group_item=dashboard_group_item,
            child_item=dashboard_child_item,
            health_check=run_dashboard_group_health_check,
            event_builder=dashboard_events,
            operation_runner_provider=lambda: run_lab_operation,
        )
    )
    def get_auth_manager() -> MedplumAuthManager:
        return MedplumAuthManager(
            client_id=app.config["MEDPLUM_CLIENT_ID"],
            client_secret=app.config["MEDPLUM_CLIENT_SECRET"],
            scope=app.config["MEDPLUM_SCOPE"],
            token_url=app.config["MEDPLUM_TOKEN_URL"],
            refresh_grace_seconds=app.config["MEDPLUM_AUTH_GRACE_SECONDS"],
        )

    def get_openemr_source() -> OpenEMRProcedureOrderSource:
        return app.extensions["openemr_procedure_order_source"]

    def configured_medplum_base_url() -> str:
        medplum = next(
            (item for item in store.list_lab_servers() if item["name"] == "Medplum"),
            None,
        )
        return str((medplum or {}).get("baseUrl") or "").strip()

    def configured_dicom_patient_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return sync_patient_to_dcm4chee(
            *args,
            sender=send_hl7_mllp_message,
            **kwargs,
        )

    def configured_dicom_order_sync(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return sync_order_to_dcm4chee_mwl(
            *args,
            patient_syncer=configured_dicom_patient_sync,
            **kwargs,
        )

    app.register_blueprint(
        create_dcm4chee_profile_blueprint(
            app.config,
            profile_builder=dcm4chee_profile_from_config,
            profile_validator=validate_dcm4chee_profile,
        )
    )
    app.register_blueprint(
        create_patients_blueprint(
            PatientWorkflowService(
                store,
                app.config,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                fhir_sync=sync_fhir_workflow_record_to_medplum,
                dicom_patient_sync=configured_dicom_patient_sync,
                dcm_result_refresh=refresh_patient_dcm4chee_results,
                dcm_profile=dcm4chee_profile_from_config,
            )
        )
    )
    app.register_blueprint(
        create_orders_blueprint(
            OrderWorkflowService(
                store,
                app.config,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                fhir_sync=sync_fhir_workflow_record_to_medplum,
                dcm_sync=configured_dicom_order_sync,
                dcm_verify=verify_order_dcm4chee_mwl,
                dcm_profile=dcm4chee_profile_from_config,
            )
        )
    )
    app.register_blueprint(
        create_fhir_blueprint(
            FhirWorkflowService(
                store,
                inventory_types=MEDPLUM_INVENTORY_RESOURCE_TYPES,
                medplum_base_url=configured_medplum_base_url,
                auth_manager=get_auth_manager,
                inventory_mapper=medplum_inventory_record,
                diagnostic_fetcher=fetch_fhir_diagnostic_report_bundle,
                base_url_normalizer=normalize_fhir_base_url,
                reference_url_builder=medplum_reference_resource_url,
                json_request=request_fhir_json,
                operation_outcome=operation_outcome_from_payload,
                upstream_status=http_status_from_upstream_error,
                record_sync=sync_fhir_workflow_record_to_medplum,
            )
        )
    )
    app.register_blueprint(
        create_gdt_blueprint(
            GdtWorkflowService(
                store,
                app.config,
                app.extensions["gdt_bridge_watcher"],
                is_internal_file=gdt_is_internal_or_temp_file,
                has_supported_extension=gdt_has_supported_exchange_extension,
                filename_binding_matches=gdt_filename_binding_matches,
                bridge_importer=import_gdt_bridge_files,
            )
        )
    )
    app.register_blueprint(create_home_blueprint(app.config))

    return app


app = create_app()


def main() -> None:
    app.run(host=parse_app_host(), port=parse_app_port(), debug=False)


if __name__ == "__main__":
    main()
