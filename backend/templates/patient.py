"""Pure Patient HL7, FHIR, GDT, and DICOM payload builders."""

from __future__ import annotations

import json
from typing import Any, Callable

from backend.domain.patient import record_number, visit_number

HL7_MSH_SUFFIX = "2.5.1||||||UNICODE UTF-8"
GDT_PATIENT_SEX_CODES = {"M": "1", "F": "2"}


def hl7_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (text.replace("\\", "\\E\\").replace("|", "\\F\\").replace("^", "\\S\\")
            .replace("&", "\\T\\").replace("~", "\\R\\").replace("\r\n", "\n")
            .replace("\r", "\n").replace("\n", "\\.br\\"))


def hl7_escape_composite(value: Any) -> str:
    return "^".join(hl7_escape(component) for component in str(value if value is not None else "").split("^"))


def build_hl7(values: dict[str, Any], *, record_id: int, timestamp: str) -> tuple[str, str]:
    visit = values["visit_number"] or visit_number(record_id)
    name = "^".join(hl7_escape(part) for part in (values["last_name"], values["first_name"], values["middle_name"])).rstrip("^")
    control_id = f"A04{timestamp}{record_id:06d}"
    segments = [
        f"MSH|^~\\&|HEALTHCARE_LAB|LAB_DEMO|OIE|ADT|{timestamp}||ADT^A04^ADT_A01|{control_id}|P|{HL7_MSH_SUFFIX}",
        f"EVN|A04|{timestamp}",
        "PID|1||" + f"{hl7_escape(values['mrn'])}^^^HEALTHCARE_LAB^MR||{name}||{hl7_escape(values['dob'])}|{hl7_escape(values['sex'])}|||{hl7_escape_composite(values['address'])}||{hl7_escape(values['phone'])}|||||{hl7_escape(values['account_number'])}",
        "PV1|1|" + f"{hl7_escape(values['patient_class'])}|{hl7_escape_composite(values['assigned_location'])}||||{hl7_escape_composite(values['attending_provider'])}||||||||||||{hl7_escape(visit)}",
    ]
    return "\r".join(segments), visit


def build_fhir(values: dict[str, Any], *, record_id: int) -> tuple[str, str]:
    visit = values["visit_number"] or visit_number(record_id)
    name = " ".join(part for part in (values["first_name"], values["middle_name"], values["last_name"]) if part)
    telecom = []
    if values["phone"]:
        telecom.append({"system": "phone", "value": values["phone"]})
    if values["email"]:
        telecom.append({"system": "email", "value": values["email"]})
    address = {}
    for source, target in (("address", "text"), ("address_city", "city"), ("address_state", "state"),
                           ("address_postal_code", "postalCode"), ("address_country", "country")):
        if values[source]:
            address[target] = values[source]
    if values["address_line"]:
        address["line"] = [values["address_line"]]
    resource = {
        "resourceType": "Patient", "id": record_number(record_id), "active": bool(values["fhir_active"]),
        "meta": {"profile": ["https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"]},
        "identifier": [{"system": "urn:healthcare-lab:mrn", "value": values["mrn"]}],
        "name": [{"use": "official", "text": name, "family": values["last_name"], "given": [part for part in (values["first_name"], values["middle_name"]) if part]}],
        "gender": {"M": "male", "F": "female", "O": "other", "U": "unknown"}[values["sex"]],
        "birthDate": f"{values['dob'][:4]}-{values['dob'][4:6]}-{values['dob'][6:]}",
        "telecom": telecom, "address": [address] if address else [],
        "extension": [{"url": "urn:healthcare-lab:visit-number", "valueString": visit}],
    }
    organization = {}
    if values["managing_organization_reference"]:
        organization["reference"] = values["managing_organization_reference"]
    if values["managing_organization_display"]:
        organization["display"] = values["managing_organization_display"]
    if organization:
        resource["managingOrganization"] = organization
    return json.dumps(resource, indent=2), visit


def build_gdt(
    values: dict[str, Any], *, record_id: int, renderer: Callable[..., str]
) -> tuple[str, str]:
    visit = values["visit_number"] or visit_number(record_id)
    dob = values["dob"]
    records: list[tuple[str, Any]] = [("8315", "LABGDT"), ("8316", "HCLAB"), ("3000", values["mrn"]),
                                     ("3101", values["last_name"]), ("3102", values["first_name"]),
                                     ("3103", f"{dob[6:]}{dob[4:6]}{dob[:4]}")]
    if GDT_PATIENT_SEX_CODES.get(values["sex"]):
        records.append(("3110", GDT_PATIENT_SEX_CODES[values["sex"]]))
    return renderer(records, set_type="6301"), visit


def build_dicom(values: dict[str, Any], *, record_id: int) -> tuple[str, str]:
    visit = values["visit_number"] or visit_number(record_id)
    dataset = {
        "(0010,0010) PatientName": "^".join(part for part in (values["last_name"], values["first_name"], values["middle_name"]) if part),
        "(0010,0020) PatientID": values["mrn"], "(0010,0030) PatientBirthDate": values["dob"],
        "(0010,0040) PatientSex": values["sex"], "(0010,2154) PatientTelephoneNumbers": values["phone"],
        "(0038,0010) AdmissionID": visit, "(0038,0500) PatientState": values["patient_class"],
    }
    if values["address"]:
        dataset["(0010,1040) PatientAddress"] = values["address"]
    return json.dumps(dataset, indent=2), visit


def build(values: dict[str, Any], *, record_id: int, timestamp: str, hl7_time: str,
          gdt_renderer: Callable[..., str]) -> tuple[str, str]:
    if values["mode"] == "fhir":
        return build_fhir(values, record_id=record_id)
    if values["mode"] == "gdt":
        return build_gdt(values, record_id=record_id, renderer=gdt_renderer)
    if values["mode"] == "dicom":
        return build_dicom(values, record_id=record_id)
    return build_hl7(values, record_id=record_id, timestamp=hl7_time)
