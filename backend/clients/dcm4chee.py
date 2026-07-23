"""dcm4chee DICOMweb HTTP transport operations."""

from __future__ import annotations

import base64
import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from backend.domain.errors import UpstreamDcm4cheeError
from backend.domain.validation import require_http_url


def request_dcm4chee_mwl_create(
    profile: dict[str, Any], payload: dict[str, Any]
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    url = f"{base_url}/mwlitems"
    body = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    request = urllib.request.Request(
        url,
        data=body,
        headers={
            "Accept": "application/dicom+json, application/json, text/plain",
            "Content-Type": "application/dicom+json",
        },
        method="POST",
    )
    return _send(request, profile, url, "dcm4chee", "dcm4chee request")


def dcm4chee_archive_rs_base_url(profile: dict[str, Any]) -> str:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
    mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    called_ae_title = str(dimse.get("calledAETitle") or "DCM4CHEE").strip()
    mwl_ae_title = str(mwl.get("aeTitle") or "").strip()
    if mwl_ae_title and f"/aets/{mwl_ae_title}/rs" in base_url:
        return base_url.replace(f"/aets/{mwl_ae_title}/rs", f"/aets/{called_ae_title}/rs")
    return base_url


def request_dcm4chee_patient_search(
    profile: dict[str, Any], *, patient_id: str, issuer_of_patient_id: str
) -> tuple[int, str, str]:
    query = {"PatientID": patient_id}
    if issuer_of_patient_id:
        query["IssuerOfPatientID"] = issuer_of_patient_id
    url = f"{dcm4chee_archive_rs_base_url(profile)}/patients?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/dicom+json, application/json, text/plain"},
        method="GET",
    )
    return _send(request, profile, url, "dcm4chee patient lookup", "dcm4chee patient lookup")


def request_dcm4chee_patient_create(
    profile: dict[str, Any], patient_payload: dict[str, Any]
) -> tuple[int, str, str]:
    url = f"{dcm4chee_archive_rs_base_url(profile)}/patients"
    request = urllib.request.Request(
        url,
        data=json.dumps(patient_payload, separators=(",", ":"), sort_keys=True).encode("utf-8"),
        headers={
            "Accept": "application/json, application/dicom+json, text/plain",
            "Content-Type": "application/dicom+json",
        },
        method="POST",
    )
    return _send(request, profile, url, "dcm4chee patient create", "dcm4chee patient create")


def request_dcm4chee_mwl_readback(
    profile: dict[str, Any], identifiers: dict[str, str]
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    query = {
        key: value
        for key, value in {
            "StudyInstanceUID": identifiers.get("study_instance_uid", ""),
            "AccessionNumber": identifiers.get("accession_number", ""),
            "RequestedProcedureID": identifiers.get("requested_procedure_id", ""),
            "ScheduledProcedureStepID": identifiers.get("scheduled_procedure_step_id", ""),
            "PatientID": identifiers.get("patient_id", ""),
            "IssuerOfPatientID": identifiers.get("issuer_of_patient_id", ""),
        }.items()
        if value
    }
    url = f"{base_url}/mwlitems"
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/dicom+json, application/json, text/plain"},
        method="GET",
    )
    return _send(request, profile, url, "dcm4chee read-back", "dcm4chee read-back")


def request_dcm4chee_mwl_verification(
    profile: dict[str, Any], query_criteria: dict[str, str]
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(dicomweb.get("baseUrl"), "dicomweb.baseUrl")
    url = f"{base_url}/mwlitems"
    query = {key: value for key, value in query_criteria.items() if value}
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/dicom+json, application/json, text/plain"},
        method="GET",
    )
    return _send(request, profile, url, "dcm4chee MWL verification", "dcm4chee MWL verification")


def request_dcm4chee_qido(
    profile: dict[str, Any], path: str, query_criteria: dict[str, str] | None = None
) -> tuple[int, str, str]:
    dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
    base_url = require_http_url(
        dicomweb.get("qidoRsUrl") or dicomweb.get("baseUrl"), "dicomweb.qidoRsUrl"
    )
    url = f"{base_url}/{path.strip('/')}"
    query = {
        key: value
        for key, value in (query_criteria or {}).items()
        if str(value or "").strip()
    }
    if query:
        url = f"{url}?{urllib.parse.urlencode(query)}"
    request = urllib.request.Request(
        url,
        headers={"Accept": "application/dicom+json, application/json, text/plain"},
        method="GET",
    )
    return _send(request, profile, url, "dcm4chee QIDO query", "dcm4chee QIDO query")


def secure_request(
    request: urllib.request.Request,
    profile: dict[str, Any],
    *,
    timeout: float,
) -> ssl.SSLContext | None:
    security = profile.get("security") if isinstance(profile.get("security"), dict) else {}
    secrets = getattr(profile, "secrets", {})
    mode = str(security.get("authMode") or "none")
    if mode == "basic":
        credentials = f"{security.get('username', '')}:{secrets.get('password', '')}"
        encoded = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
        request.add_header("Authorization", f"Basic {encoded}")
    elif mode == "bearer":
        request.add_header("Authorization", f"Bearer {secrets.get('token', '')}")
    elif mode == "oauth2":
        token = _oauth2_token(security, secrets, timeout)
        request.add_header("Authorization", f"Bearer {token}")
    if not security.get("tlsEnabled"):
        return None
    context = ssl.create_default_context()
    if security.get("tlsVerify") is False:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE
    certificate = str(security.get("certificatePath") or "").strip()
    private_key = str(security.get("privateKeyPath") or "").strip()
    if certificate or private_key:
        context.load_cert_chain(certificate, private_key or None)
    return context


def open_secured(
    request: urllib.request.Request,
    profile: dict[str, Any],
    *,
    timeout: float,
):
    context = secure_request(request, profile, timeout=timeout)
    if context is None:
        return urllib.request.urlopen(request, timeout=timeout)
    return urllib.request.urlopen(request, timeout=timeout, context=context)


def _oauth2_token(
    security: dict[str, Any], secrets: dict[str, Any], timeout: float
) -> str:
    body = urllib.parse.urlencode(
        {
            "grant_type": "client_credentials",
            "client_id": str(security.get("username") or ""),
        }
    ).encode("utf-8")
    credentials = f"{security.get('username', '')}:{secrets.get('clientSecret', '')}"
    authorization = base64.b64encode(credentials.encode("utf-8")).decode("ascii")
    token_request = urllib.request.Request(
        str(security.get("tokenUrl") or ""),
        data=body,
        headers={
            "Accept": "application/json",
            "Authorization": f"Basic {authorization}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(token_request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except Exception as exc:
        raise urllib.error.URLError("OAuth token request failed") from exc
    token = payload.get("access_token") if isinstance(payload, dict) else None
    if not token:
        raise urllib.error.URLError("OAuth token response did not contain an access token")
    return str(token)


def _send(
    request: urllib.request.Request,
    profile: dict[str, Any],
    url: str,
    http_operation: str,
    transport_operation: str,
) -> tuple[int, str, str]:
    try:
        with open_secured(request, profile, timeout=30) as response:
            return response.status, response.read().decode("utf-8", errors="replace"), url
    except urllib.error.HTTPError as exc:
        error_body = exc.read().decode("utf-8", errors="replace")
        raise UpstreamDcm4cheeError(
            f"{http_operation} returned HTTP {exc.code}: {error_body}",
            http_status=exc.code,
            response_body=error_body,
        ) from exc
    except urllib.error.URLError as exc:
        raise UpstreamDcm4cheeError(f"{transport_operation} failed: {exc.reason}") from exc
    except (OSError, ValueError) as exc:
        raise UpstreamDcm4cheeError(
            f"{transport_operation} failed: TLS configuration is invalid."
        ) from exc
