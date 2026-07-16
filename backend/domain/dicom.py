"""DICOM profile validation independent of application assembly."""

from __future__ import annotations

import json
import re
from datetime import datetime
from collections.abc import Callable
from typing import Any
from urllib.parse import quote

from backend.domain.errors import SimulatorValidationError, ValidationError
from backend.domain.validation import require_http_url
from backend.domain.statuses import (
    DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_MISSING_ACCESSION,
    DCM4CHEE_RESULT_STATUS_UNLINKED,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
)

DCM4CHEE_AUTH_MODES = ("none", "basic", "bearer", "oauth2", "mtls")
DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"
DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES = {"patient_missing", "patient_sync_failed", "profile_invalid"}
DCM4CHEE_ORDER_PROTOCOL_VERSION = "DICOM"
DCM4CHEE_RESULT_SOURCE_SIMULATED_AP = "simulated_ap_return"


def validate_dcm4chee_profile(profile: dict[str, Any]) -> dict[str, Any]:
    checks: list[dict[str, str]] = []

    def add_check(name: str, field: str, ok: bool, message: str) -> None:
        checks.append(
            {
                "name": name,
                "field": field,
                "status": "Healthy" if ok else "Down",
                "message": message,
            }
        )

    def required_text(path: tuple[str, ...], label: str) -> str:
        value: Any = profile
        for part in path:
            value = value.get(part, {}) if isinstance(value, dict) else {}
        text = str(value or "").strip()
        add_check(
            "_".join(path),
            ".".join(path),
            bool(text),
            f"{label} is configured." if text else f"{label} is required.",
        )
        return text

    required_text(("profileName",), "Profile name")
    required_text(("displayName",), "Display name")
    required_text(("environmentName",), "Environment name")
    try:
        require_http_url(profile.get("webUiUrl"), "webUiUrl")
        add_check("web_ui_url", "webUiUrl", True, "Web UI URL is valid.")
    except ValidationError as exc:
        add_check("web_ui_url", "webUiUrl", False, str(exc))

    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    required_text(("dimse", "host"), "DIMSE host")
    try:
        port = int(dimse.get("port") or 0)
        valid_port = 1 <= port <= 65535
    except (TypeError, ValueError):
        valid_port = False
    add_check(
        "dimse_port",
        "dimse.port",
        valid_port,
        "DIMSE port is valid." if valid_port else "DIMSE port must be an integer between 1 and 65535.",
    )
    required_text(("dimse", "calledAETitle"), "Called AE title")
    required_text(("dimse", "callingAETitle"), "Calling AE title")
    required_text(("mwl", "aeTitle"), "MWL AE title")
    required_text(("mwl", "defaultScheduledStationAETitle"), "Default Scheduled Station AE Title")

    hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
    required_text(("hl7", "host"), "HL7 host")
    try:
        port = int(hl7.get("port") or 0)
        valid_port = 1 <= port <= 65535
    except (TypeError, ValueError):
        valid_port = False
    add_check(
        "hl7_port",
        "hl7.port",
        valid_port,
        "HL7 port is valid." if valid_port else "HL7 port must be an integer between 1 and 65535.",
    )
    required_text(("hl7", "sendingApplication"), "HL7 sending application")
    required_text(("hl7", "sendingFacility"), "HL7 sending facility")
    required_text(("hl7", "receivingApplication"), "HL7 receiving application")
    required_text(("hl7", "receivingFacility"), "HL7 receiving facility")
    required_text(("hl7", "patientAssigningAuthority"), "HL7 Patient assigning authority")

    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    for field in ("baseUrl", "qidoRsUrl", "wadoRsUrl", "stowRsUrl"):
        try:
            require_http_url(dicomweb.get(field), f"dicomweb.{field}")
            add_check(f"dicomweb_{field}", f"dicomweb.{field}", True, f"DICOMweb {field} is valid.")
        except ValidationError as exc:
            add_check(f"dicomweb_{field}", f"dicomweb.{field}", False, str(exc))

    security = profile.get("security") if isinstance(profile.get("security"), dict) else {}
    auth_mode = str(security.get("authMode") or "").strip().lower()
    add_check(
        "security_auth_mode",
        "security.authMode",
        auth_mode in DCM4CHEE_AUTH_MODES,
        "Auth mode is supported." if auth_mode in DCM4CHEE_AUTH_MODES else "Auth mode is unsupported.",
    )
    tls_enabled_value = security.get("tlsEnabled")
    tls_verify_value = security.get("tlsVerify")
    add_check(
        "security_tls_enabled",
        "security.tlsEnabled",
        isinstance(tls_enabled_value, bool),
        "TLS enabled value is valid." if isinstance(tls_enabled_value, bool) else "TLS enabled must be true or false.",
    )
    add_check(
        "security_tls_verify",
        "security.tlsVerify",
        isinstance(tls_verify_value, bool),
        "TLS verify value is valid." if isinstance(tls_verify_value, bool) else "TLS verify must be true or false.",
    )
    tls_enabled = tls_enabled_value is True
    has_cert_material = bool(security.get("certificatePath") or security.get("privateKeyPath"))
    add_check(
        "security_tls",
        "security.certificatePath",
        tls_enabled or not has_cert_material,
        "TLS settings are consistent."
        if tls_enabled or not has_cert_material
        else "Certificate or key paths require TLS to be enabled.",
    )
    if auth_mode == "none":
        add_check(
            "security_local_lab",
            "security.authMode",
            True,
            "Local profile is unauthenticated and is not production-ready.",
        )

    valid = all(check["status"] == "Healthy" for check in checks)
    return {
        "valid": valid,
        "status": "Healthy" if valid else "Down",
        "summary": "dcm4chee profile is valid." if valid else "dcm4chee profile is incomplete or invalid.",
        "checks": checks,
    }


# Reconciliation policy is pure: callers provide the candidate MWL mappings.
def patient_matches(mapping: dict[str, Any], metadata: dict[str, str]) -> bool:
    patient_id = str(metadata.get("patient_id") or "").strip()
    issuer = str(metadata.get("issuer_of_patient_id") or "").strip()
    expected_patient_id = str(mapping.get("patientId") or "").strip()
    expected_issuer = str(mapping.get("issuerOfPatientId") or "").strip()
    if patient_id and expected_patient_id and patient_id != expected_patient_id:
        return False
    if issuer and expected_issuer and issuer != expected_issuer:
        return False
    return True

def reconcile_result_metadata(
    metadata: dict[str, str],
    mappings: list[dict[str, Any]],
    *,
    profile_name: str = "",
    server_identity: str = "",
) -> dict[str, Any]:
    if not mappings:
        return {
            "status": DCM4CHEE_RESULT_STATUS_UNLINKED,
            "method": "",
            "strength": "none",
            "mapping": None,
            "diagnostic": {"reason": "no_local_dcm4chee_mapping"},
        }

    study_uid = str(metadata.get("study_instance_uid") or "").strip()
    accession = str(metadata.get("accession_number") or "").strip()
    requested = str(metadata.get("requested_procedure_id") or "").strip()
    sps = str(metadata.get("scheduled_procedure_step_id") or "").strip()
    profile = str(profile_name or "").strip()
    server = str(server_identity or "").strip()

    def in_namespace(mapping: dict[str, Any]) -> bool:
        return (
            (not profile or mapping.get("profileName") == profile)
            and (not server or mapping.get("serverIdentity") == server)
        )

    candidates: list[tuple[str, str, dict[str, Any]]] = []
    if study_uid:
        candidates = [
            ("study_instance_uid", "strong", mapping)
            for mapping in mappings
            if str(mapping.get("studyInstanceUid") or "").strip() == study_uid
        ]
    if not candidates and accession:
        same_accession = [
            mapping
            for mapping in mappings
            if in_namespace(mapping)
            and str(mapping.get("accessionNumber") or "").strip() == accession
        ]
        wrong_patient = [mapping for mapping in same_accession if not patient_matches(mapping, metadata)]
        if wrong_patient:
            return {
                "status": DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
                "method": "accession_number",
                "strength": "strong",
                "mapping": None,
                "diagnostic": {
                    "reason": "patient_identity_mismatch",
                    "candidateMappingIds": [item["id"] for item in wrong_patient],
                },
            }
        candidates = [("accession_number", "strong", mapping) for mapping in same_accession]
    if not candidates and requested and sps:
        same_procedure = [
            mapping
            for mapping in mappings
            if in_namespace(mapping)
            and str(mapping.get("requestedProcedureId") or "").strip() == requested
            and str(mapping.get("scheduledProcedureStepId") or "").strip() == sps
        ]
        wrong_patient = [mapping for mapping in same_procedure if not patient_matches(mapping, metadata)]
        if wrong_patient:
            return {
                "status": DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
                "method": "requested_procedure_step",
                "strength": "strong",
                "mapping": None,
                "diagnostic": {
                    "reason": "patient_identity_mismatch",
                    "candidateMappingIds": [item["id"] for item in wrong_patient],
                },
            }
        candidates = [("requested_procedure_step", "strong", mapping) for mapping in same_procedure]
    if not candidates:
        weak_candidates = [
            mapping
            for mapping in mappings
            if patient_matches(mapping, metadata)
        ]
        if len(weak_candidates) == 1:
            candidates = [("patient_identity", "weak", weak_candidates[0])]
        elif len(weak_candidates) > 1:
            return {
                "status": DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
                "method": "patient_identity",
                "strength": "weak",
                "mapping": None,
                "diagnostic": {
                    "reason": "multiple_weak_candidates",
                    "candidateMappingIds": [item["id"] for item in weak_candidates],
                },
            }
        elif not accession:
            return {
                "status": DCM4CHEE_RESULT_STATUS_MISSING_ACCESSION,
                "method": "",
                "strength": "none",
                "mapping": None,
                "diagnostic": {"reason": "missing_accession_and_no_strong_identifier"},
            }
        else:
            return {
                "status": DCM4CHEE_RESULT_STATUS_UNLINKED,
                "method": "",
                "strength": "none",
                "mapping": None,
                "diagnostic": {"reason": "no_matching_mapping"},
            }
    if len(candidates) > 1:
        return {
            "status": DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
            "method": candidates[0][0],
            "strength": candidates[0][1],
            "mapping": None,
            "diagnostic": {
                "reason": "multiple_strong_candidates",
                "candidateMappingIds": [item[2]["id"] for item in candidates],
            },
        }
    method, strength, mapping = candidates[0]
    return {
        "status": DCM4CHEE_RESULT_STATUS_MATCHED,
        "method": method,
        "strength": strength,
        "mapping": mapping,
        "diagnostic": {"reason": "matched", "mappingId": mapping["id"]},
    }


def local_order_number(record_id: int) -> str:
    return f"LAB-ORD-{record_id:06d}"


def accession_number(record_id: int) -> str:
    return f"ACC-{record_id:06d}"


def requested_procedure_id(record_id: int) -> str:
    return f"RP-{record_id:06d}"


def scheduled_procedure_step_id(record_id: int) -> str:
    return f"SPS-{record_id:06d}"


def normalize_uid_root(value: Any) -> str:
    root = str(value or DCM4CHEE_DEFAULT_UID_ROOT).strip().strip(".") or DCM4CHEE_DEFAULT_UID_ROOT
    if not re.match(r"^[0-9]+(?:\.[0-9]+)*$", root):
        raise SimulatorValidationError("dcm4chee UID root must contain only digits and dots.")
    if any(part != "0" and part.startswith("0") for part in root.split(".")):
        raise SimulatorValidationError("dcm4chee UID root components must not have leading zeroes.")
    if len(root) > 54:
        raise SimulatorValidationError("dcm4chee UID root is too long for generated Study Instance UIDs.")
    return root


def study_instance_uid(
    uid_root: Any, *, order_record_id: int, timestamp: str = "",
    timestamp_factory: Callable[[], str],
) -> str:
    root = normalize_uid_root(uid_root)
    fallback = timestamp_factory()
    digits = "".join(character for character in str(timestamp or fallback) if character.isdigit())
    suffix = f"{digits[:14] or fallback}.{int(order_record_id)}"
    uid = f"{root}.{suffix}"
    if len(uid) > 64:
        suffix = f"{digits[:8] or datetime.now().strftime('%Y%m%d')}.{int(order_record_id)}"
        uid = f"{root}.{suffix}"
    if len(uid) > 64:
        raise SimulatorValidationError("Generated Study Instance UID exceeds 64 characters.")
    return uid


def patient_identifiers(patient: dict[str, Any], profile: dict[str, Any]) -> dict[str, str]:
    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
    summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
    fields = patient.get("patient") if isinstance(patient.get("patient"), dict) else {}
    return {
        "profile_name": str(profile.get("profileName") or "").strip(),
        "server_identity": str(dimse.get("calledAETitle") or "").strip(),
        "patient_id": str(summary.get("mrn") or fields.get("mrn") or patient.get("mrn") or "").strip(),
        "issuer_of_patient_id": str(hl7.get("patientAssigningAuthority") or profile.get("profileName") or "HEALTHCARE_LAB").strip(),
        "hl7_host": str(hl7.get("host") or "").strip(),
        "hl7_port": str(hl7.get("port") or "").strip(),
        "receiving_application": str(hl7.get("receivingApplication") or "").strip(),
        "receiving_facility": str(hl7.get("receivingFacility") or "").strip(),
    }


def dicom_first_value(payload: dict[str, Any], tag: str, default: str = "") -> str:
    element = payload.get(tag) if isinstance(payload, dict) else None
    if not isinstance(element, dict):
        return default
    values = element.get("Value")
    if not isinstance(values, list) or not values:
        return default
    value = values[0]
    if isinstance(value, dict):
        return str(value.get("Alphabetic") or default).strip()
    return str(value or default).strip()


def sps_payload(payload: dict[str, Any]) -> dict[str, Any]:
    sequence = payload.get("00400100") if isinstance(payload, dict) else None
    values = sequence.get("Value") if isinstance(sequence, dict) else None
    return values[0] if isinstance(values, list) and values and isinstance(values[0], dict) else {}


def historical_mwl_identifiers(
    payload: dict[str, Any],
    *,
    patient_id_default: str = "",
    issuer_default: str = "",
    worklist_label_default: str = "",
    scheduled_station_default: str = "",
) -> dict[str, str]:
    """Project historical MWL identifiers without coupling SQL to DICOM tags."""
    sps = sps_payload(payload)
    return {
        "patient_id": dicom_first_value(payload, "00100020", patient_id_default),
        "issuer_of_patient_id": dicom_first_value(payload, "00100021", issuer_default),
        "worklist_label": dicom_first_value(payload, "00741202", worklist_label_default),
        "scheduled_station_ae_title": scheduled_station_default
        or dicom_first_value(sps, "00400001"),
    }


def identifiers_from_dataset(dataset: dict[str, Any]) -> dict[str, str]:
    dataset = dataset.get("attrs") if isinstance(dataset.get("attrs"), dict) else dataset
    if not isinstance(dataset, dict):
        return {}
    sps = sps_payload(dataset)
    values = {
        "patient_id": dicom_first_value(dataset, "00100020"),
        "issuer_of_patient_id": dicom_first_value(dataset, "00100021"),
        "accession_number": dicom_first_value(dataset, "00080050"),
        "requested_procedure_id": dicom_first_value(dataset, "00401001"),
        "scheduled_procedure_step_id": dicom_first_value(sps, "00400009"),
        "study_instance_uid": dicom_first_value(dataset, "0020000D"),
        "worklist_label": dicom_first_value(dataset, "00741202") or dicom_first_value(sps, "00400007"),
        "scheduled_station_ae_title": dicom_first_value(sps, "00400001"),
    }
    return {key: value for key, value in values.items() if value}


def datasets_from_response_body(response_body: str) -> list[dict[str, Any]]:
    try:
        parsed = json.loads(response_body or "")
    except (TypeError, ValueError):
        return []
    values = parsed if isinstance(parsed, list) else [parsed]
    return [
        value.get("attrs") if isinstance(value.get("attrs"), dict) else value
        for value in values if isinstance(value, dict)
    ]


def identifiers_from_response_body(response_body: str) -> dict[str, str]:
    datasets = datasets_from_response_body(response_body)
    return identifiers_from_dataset(datasets[0]) if datasets else {}


def verification_query_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
    query = {
        "AccessionNumber": str(mapping.get("accessionNumber") or "").strip(),
        "RequestedProcedureID": str(mapping.get("requestedProcedureId") or "").strip(),
        "ScheduledProcedureStepID": str(mapping.get("scheduledProcedureStepId") or "").strip(),
        "PatientID": str(mapping.get("patientId") or "").strip(),
        "IssuerOfPatientID": str(mapping.get("issuerOfPatientId") or "").strip(),
        "ScheduledStationAETitle": str(mapping.get("scheduledStationAETitle") or "").strip(),
    }
    return {key: value for key, value in query.items() if value}


def identifiers_from_payload(
    order: dict[str, Any], profile: dict[str, Any], *, uid_root: Any,
    payload: dict[str, Any], order_default_text: str,
    timestamp_factory: Callable[[], str],
) -> dict[str, str]:
    order_id = int(order["id"])
    patient = order.get("patient") if isinstance(order.get("patient"), dict) else {}
    mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    sps = sps_payload(payload)
    root = normalize_uid_root(uid_root)
    return {
        "profile_name": str(profile.get("profileName") or "").strip(),
        "server_identity": str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
        "mwl_ae_title": str(mwl.get("aeTitle") or "").strip(),
        "scheduled_station_ae_title": dicom_first_value(sps, "00400001", str(mwl.get("defaultScheduledStationAETitle") or "").strip()),
        "local_dcm4chee_order_number": local_order_number(order_id),
        "patient_id": dicom_first_value(payload, "00100020", str(patient.get("mrn") or "").strip()),
        "issuer_of_patient_id": dicom_first_value(payload, "00100021", str(profile.get("profileName") or "HEALTHCARE_LAB").strip()),
        "accession_number": dicom_first_value(payload, "00080050", accession_number(order_id)),
        "requested_procedure_id": dicom_first_value(payload, "00401001", requested_procedure_id(order_id)),
        "scheduled_procedure_step_id": dicom_first_value(sps, "00400009", scheduled_procedure_step_id(order_id)),
        "study_instance_uid": dicom_first_value(
            payload, "0020000D",
            study_instance_uid(root, order_record_id=order_id, timestamp=str(order.get("requestedAt") or ""), timestamp_factory=timestamp_factory),
        ),
        "worklist_label": dicom_first_value(payload, "00741202", str(order.get("orderCodeText") or order.get("orderCode") or order_default_text).strip()),
        "uid_root": root,
    }


def sequence_first(payload: dict[str, Any], tag: str) -> dict[str, Any]:
    element = payload.get(tag) if isinstance(payload, dict) else None
    values = element.get("Value") if isinstance(element, dict) else None
    return values[0] if isinstance(values, list) and values and isinstance(values[0], dict) else {}


def dicom_datetime(payload: dict[str, Any], date_tag: str, time_tag: str) -> str:
    date = dicom_first_value(payload, date_tag)
    time = dicom_first_value(payload, time_tag)
    return f"{date}{time}" if date and time else date or time


def result_metadata_from_dataset(dataset: dict[str, Any]) -> dict[str, str]:
    dataset = dataset.get("attrs") if isinstance(dataset.get("attrs"), dict) else dataset
    if not isinstance(dataset, dict):
        return {}
    request_attrs = sequence_first(dataset, "00400275")
    identifiers = identifiers_from_dataset(dataset)
    return {
        **identifiers,
        "requested_procedure_id": identifiers.get("requested_procedure_id") or dicom_first_value(request_attrs, "00401001"),
        "scheduled_procedure_step_id": identifiers.get("scheduled_procedure_step_id") or dicom_first_value(request_attrs, "00400009") or dicom_first_value(sps_payload(dataset), "00400009"),
        "series_instance_uid": dicom_first_value(dataset, "0020000E"),
        "sop_instance_uid": dicom_first_value(dataset, "00080018"),
        "modality": dicom_first_value(dataset, "00080060"),
        "study_datetime": dicom_datetime(dataset, "00080020", "00080030"),
        "series_datetime": dicom_datetime(dataset, "00080021", "00080031"),
        "instance_datetime": dicom_datetime(dataset, "00080012", "00080013") or dicom_datetime(dataset, "00080023", "00080033"),
    }


def profile_identity(profile: dict[str, Any]) -> tuple[str, str, str]:
    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
    profile_name = str(profile.get("profileName") or "").strip()
    server_identity = str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip()
    return profile_name, server_identity, str(dimse.get("calledAETitle") or server_identity).strip()


def result_key(
    *, profile_name: str, server_identity: str, patient_record_id: int | None = None,
    status: str = "", study_instance_uid: str = "", series_instance_uid: str = "",
    sop_instance_uid: str = "", accession_number: str = "", requested_procedure_id: str = "",
    scheduled_procedure_step_id: str = "",
) -> str:
    study, series, sop = (str(value or "").strip() for value in (study_instance_uid, series_instance_uid, sop_instance_uid))
    if study or series or sop:
        return "|".join(["dicom", str(profile_name or "").strip(), str(server_identity or "").strip(), study, series, sop])
    accession, requested, sps = (str(value or "").strip() for value in (accession_number, requested_procedure_id, scheduled_procedure_step_id))
    if accession or requested or sps:
        return "|".join(["dicom-identifiers", str(profile_name or "").strip(), str(server_identity or "").strip(), accession, requested, sps])
    return "|".join(["diagnostic", str(profile_name or "").strip(), str(server_identity or "").strip(), str(patient_record_id or ""), str(status or "").strip()])


def result_links(profile: dict[str, Any], metadata: dict[str, str]) -> dict[str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    viewer = profile.get("viewer") if isinstance(profile.get("viewer"), dict) else {}
    wado_url = str(dicomweb.get("wadoRsUrl") or dicomweb.get("baseUrl") or "").strip().rstrip("/")
    study = str(metadata.get("study_instance_uid") or "").strip()
    series = str(metadata.get("series_instance_uid") or "").strip()
    sop = str(metadata.get("sop_instance_uid") or "").strip()
    links = {"viewer_url": "", "study_retrieve_url": "", "series_retrieve_url": "", "instance_retrieve_url": ""}
    template = str(viewer.get("studyUrlTemplate") or "").strip()
    if study and template:
        links["viewer_url"] = template.replace("{studyInstanceUid}", quote(study, safe=""))
    if study and wado_url:
        links["study_retrieve_url"] = f"{wado_url}/studies/{quote(study, safe='')}"
        if series:
            links["series_retrieve_url"] = f"{links['study_retrieve_url']}/series/{quote(series, safe='')}"
            if sop:
                links["instance_retrieve_url"] = f"{links['series_retrieve_url']}/instances/{quote(sop, safe='')}"
    return links


def mwl_retryable(status: str, error_type: str = "") -> bool:
    if str(error_type or "").strip() in DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES:
        return False
    return str(status or "").strip() in {DCM4CHEE_MWL_STATUS_PENDING, DCM4CHEE_MWL_STATUS_FAILED}


def mwl_display_status(status: str, retryable: bool) -> tuple[str, str]:
    if status == DCM4CHEE_MWL_STATUS_CREATED:
        return "Synced", "synced"
    if status == DCM4CHEE_MWL_STATUS_PENDING:
        return ("Retry needed", "retry-needed") if retryable else ("Pending", "pending")
    if status == DCM4CHEE_MWL_STATUS_FAILED:
        return ("Retry needed", "retry-needed") if retryable else ("Failed", "failed")
    if status == DCM4CHEE_MWL_STATUS_PATIENT_MISSING:
        return "Failed", "failed"
    return status or "Unknown", "unknown"


def mwl_status_view(attempt: dict[str, Any] | None, mapping: dict[str, Any] | None) -> dict[str, Any]:
    attempt = attempt or {}
    mapping = mapping or {}
    status = str(mapping.get("status") or attempt.get("status") or "").strip()
    error_type = str(mapping.get("lastErrorType") or attempt.get("errorType") or "").strip()
    error_text = str(mapping.get("lastError") or attempt.get("error") or "").strip()
    response_body = str(mapping.get("lastResponseBody") or attempt.get("responseBody") or "").strip()
    http_status = mapping.get("lastHttpStatus") or attempt.get("httpStatus")
    retryable = mwl_retryable(status, error_type)
    display_status, display_state = mwl_display_status(status, retryable)
    return {
        **attempt,
        "mapping": mapping or None,
        "verification": mapping.get("verification") if mapping else None,
        "status": status,
        "httpStatus": http_status,
        "responseBody": response_body,
        "errorType": error_type,
        "error": error_text,
        "displayStatus": display_status,
        "displayState": display_state,
        "retryable": retryable,
        "latest": {
            "attemptId": attempt.get("id"),
            "mappingId": mapping.get("id") or attempt.get("mappingId"),
            "operationType": attempt.get("operationType") or "",
            "status": status,
            "displayStatus": display_status,
            "retryable": retryable,
            "httpStatus": http_status,
            "errorType": error_type,
            "error": error_text,
            "responseBody": response_body,
            "retryCount": mapping.get("retryCount", 0),
            "lastSyncAt": mapping.get("lastSyncAt") or attempt.get("completedAt") or "",
            "updatedAt": mapping.get("updatedAt") or attempt.get("updatedAt") or "",
        },
    }
