"""Pure dcm4chee Patient ADT and MWL payload builders."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime
from typing import Any

from backend.domain.dicom import (
    DCM4CHEE_DEFAULT_UID_ROOT,
    accession_number,
    patient_identifiers,
    requested_procedure_id,
    scheduled_procedure_step_id,
    study_instance_uid,
    identifiers_from_payload as project_identifiers_from_payload,
)
from backend.domain.errors import SimulatorValidationError
from backend.templates.patient import hl7_escape, hl7_escape_composite

HL7_V2_MSH_SUFFIX = "2.5.1||||||UNICODE UTF-8"
ORDER_DEFAULT_TEXT = "12 Lead ECG"


def _json_element(vr: str, value: Any = None) -> dict[str, Any]:
    element: dict[str, Any] = {"vr": vr}
    if value is not None:
        element["Value"] = value if isinstance(value, list) else [value]
    return element


def build_mwl_payload(
    order: dict[str, Any], profile: dict[str, Any], *,
    uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
    timestamp_factory: Callable[[], str],
) -> dict[str, Any]:
    order_id = int(order["id"])
    patient = order.get("patient") or {}
    mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
    station = str(mwl.get("defaultScheduledStationAETitle") or "").strip()
    if not station:
        raise SimulatorValidationError("dcm4chee default Scheduled Station AE Title is required.")
    patient_name = "^".join(str(patient.get(key) or "").strip() for key in ("lastName", "firstName", "middleName")).rstrip("^")
    if not patient_name:
        raise SimulatorValidationError("dcm4chee MWL Patient's Name is required.")
    patient_id = str(patient.get("mrn") or "").strip()
    if not patient_id:
        raise SimulatorValidationError("dcm4chee MWL Patient ID is required.")
    requested_at = "".join(character for character in str(order.get("requestedAt") or "") if character.isdigit())
    scheduled_date = requested_at[:8] if len(requested_at) >= 8 else datetime.now().strftime("%Y%m%d")
    scheduled_time = requested_at[8:14] if len(requested_at) >= 14 else ""
    worklist_label = str(order.get("orderCodeText") or order.get("orderCode") or ORDER_DEFAULT_TEXT).strip()
    sps_item = {
        "00400001": _json_element("AE", station),
        "00400009": _json_element("SH", scheduled_procedure_step_id(order_id)),
        "00400020": _json_element("CS", "SCHEDULED"),
        "00400007": _json_element("LO", worklist_label),
        "00400002": _json_element("DA", scheduled_date),
    }
    if scheduled_time:
        sps_item["00400003"] = _json_element("TM", scheduled_time)
    return {
        "00100010": _json_element("PN", {"Alphabetic": patient_name}),
        "00100020": _json_element("LO", patient_id),
        "00100021": _json_element("LO", str(profile.get("profileName") or "HEALTHCARE_LAB").strip()),
        "00100030": _json_element("DA", str(patient.get("dob") or "").strip()),
        "00100040": _json_element("CS", str(patient.get("sex") or "").strip() or "U"),
        "00080050": _json_element("SH", accession_number(order_id)),
        "0020000D": _json_element(
            "UI", study_instance_uid(
                uid_root, order_record_id=order_id,
                timestamp=str(order.get("requestedAt") or ""), timestamp_factory=timestamp_factory,
            ),
        ),
        "00401001": _json_element("SH", requested_procedure_id(order_id)),
        "00741202": _json_element("LO", worklist_label),
        "00400100": {"vr": "SQ", "Value": [sps_item]},
    }


def identifiers_from_payload(
    order: dict[str, Any], profile: dict[str, Any], *, uid_root: Any,
    payload: dict[str, Any] | None, timestamp_factory: Callable[[], str],
) -> dict[str, str]:
    return project_identifiers_from_payload(
        order, profile, uid_root=uid_root, payload=payload or {},
        order_default_text=ORDER_DEFAULT_TEXT, timestamp_factory=timestamp_factory,
    )


def build_patient_adt_payload(
    patient: dict[str, Any], profile: dict[str, Any], *, event_type: str = "A04",
    timestamp: str = "", timestamp_factory: Callable[[], str],
) -> str:
    fields = patient.get("patient") if isinstance(patient.get("patient"), dict) else {}
    summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
    hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
    identifiers = patient_identifiers(patient, profile)
    patient_name = "^".join(hl7_escape(str(fields.get(key) or "").strip()) for key in ("lastName", "firstName", "middleName")).rstrip("^")
    if not patient_name:
        raise SimulatorValidationError("dcm4chee Patient name is required.")
    if not identifiers["patient_id"]:
        raise SimulatorValidationError("dcm4chee Patient ID is required.")
    if not identifiers["issuer_of_patient_id"]:
        raise SimulatorValidationError("dcm4chee Patient issuer is required.")
    message_time = timestamp or timestamp_factory()
    event = str(event_type or "A04").strip().upper()
    if not event.startswith("A"):
        event = f"A{event}"
    control_id = f"DCMADT{message_time}{int(patient['id']):06d}"
    visit = str(patient.get("visitNumber") or summary.get("visitNumber") or "").strip()
    segments = [
        "MSH|^~\\&|"
        f"{hl7_escape(str(hl7.get('sendingApplication') or 'HEALTHCARE_LAB'))}|"
        f"{hl7_escape(str(hl7.get('sendingFacility') or 'LAB_APP'))}|"
        f"{hl7_escape(str(hl7.get('receivingApplication') or 'DCM4CHEE'))}|"
        f"{hl7_escape(str(hl7.get('receivingFacility') or 'DCM4CHEE'))}|"
        f"{message_time}||ADT^{event}^ADT_A01|{control_id}|P|{HL7_V2_MSH_SUFFIX}",
        f"EVN|{event}|{message_time}",
        "PID|1||"
        f"{hl7_escape(identifiers['patient_id'])}^^^{hl7_escape(identifiers['issuer_of_patient_id'])}^MR||"
        f"{patient_name}||{hl7_escape(str(fields.get('dob') or summary.get('dob') or ''))}|"
        f"{hl7_escape(str(fields.get('sex') or summary.get('sex') or ''))}|||"
        f"{hl7_escape_composite(str(fields.get('address') or ''))}||{hl7_escape(str(fields.get('phone') or ''))}|||||"
        f"{hl7_escape(str(patient.get('accountNumber') or ''))}",
        "PV1|1|"
        f"{hl7_escape(str(patient.get('patientClass') or 'O').strip() or 'O')}|"
        f"{hl7_escape_composite(str(patient.get('assignedLocation') or '').strip())}||||"
        f"{hl7_escape_composite(str(patient.get('attendingProvider') or '').strip())}||||||||||||{hl7_escape(visit)}",
    ]
    return "\r".join(segments)
