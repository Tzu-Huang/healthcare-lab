"""DICOM profile validation independent of application assembly."""

from __future__ import annotations

from typing import Any

from backend.domain.errors import ValidationError
from backend.domain.validation import require_http_url
from backend.domain.statuses import (
    DCM4CHEE_RESULT_STATUS_AMBIGUOUS,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_MISSING_ACCESSION,
    DCM4CHEE_RESULT_STATUS_UNLINKED,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
)

DCM4CHEE_AUTH_MODES = ("none", "basic", "bearer", "oauth2", "mtls")


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
