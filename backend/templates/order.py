"""Pure generic Order HL7 ORM payload builder."""

from __future__ import annotations

from typing import Any

from backend.domain.order import account_number, record_number, visit_id
from backend.templates.patient import hl7_escape, hl7_escape_composite

HL7_MSH_SUFFIX = "2.5.1||||||UNICODE UTF-8"


def build_orm(values: dict[str, Any], *, record_id: int, timestamp: str) -> str:
    number = values["local_order_number"] or record_number(record_id)
    visit = values["visit_id"] or visit_id(record_id)
    account = values["account_number"] or account_number(record_id)
    name = "^".join(hl7_escape(part) for part in (values["last_name"], values["first_name"], values["middle_name"])).rstrip("^")
    service = "^".join(hl7_escape(part) for part in (values["order_code"], values["order_code_text"], "L", values["alternate_code"], values["alternate_code_text"], values["alternate_code_system"]))
    control_id = f"ORM{timestamp}{record_id:06d}"
    return "\r".join([
        f"MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|{timestamp}||ORM^O01^ORM_O01|{control_id}|P|{HL7_MSH_SUFFIX}",
        "PID|1||" + f"{hl7_escape(values['mrn'])}^^^HEALTHCARE_LAB^MR||{name}||{hl7_escape(values['dob'])}|{hl7_escape(values['sex'])}|||||||||||{hl7_escape(account)}",
        "PV1|1|" + f"{hl7_escape(values['patient_class'])}|{hl7_escape_composite(values['assigned_location'])}||||{hl7_escape_composite(values['ordering_provider'])}||||||||||||{hl7_escape(visit)}",
        "ORC|NW|" + f"{hl7_escape(number)}||{hl7_escape(values['filler_order_number'])}|||^^^{hl7_escape(values['requested_at'])}^{hl7_escape(values['priority'])}||{timestamp}|||{hl7_escape_composite(values['ordering_provider'])}",
        "OBR|1|" + f"{hl7_escape(number)}|{hl7_escape(values['filler_order_number'])}|{service}|{hl7_escape(values['priority'])}|{hl7_escape(values['requested_at'])}||||||||{hl7_escape(values['clinical_indication'])}|||{hl7_escape_composite(values['ordering_provider'])}",
    ])
