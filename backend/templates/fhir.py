"""Pure deterministic FHIR resource builders."""

from __future__ import annotations

from typing import Any

from backend.domain.errors import SimulatorValidationError
from backend.domain.fhir_ledger import FHIR_IDENTIFIER_SYSTEMS, identifier_value
from backend.domain.fhir_order import (
    clean_text, codeable_concept, list_values, reference_item, reference_list,
)

DEFAULT_CATEGORY = "Procedure"


def build_service_request(
    values: dict[str, Any], *, record_id: int,
    local_order_number: str, patient_reference: str,
) -> dict[str, Any]:
    fhir = values.get("fhir") or {}
    resource: dict[str, Any] = {
        "resourceType": "ServiceRequest", "status": values["status"],
        "intent": values["intent"], "subject": {"reference": patient_reference},
    }
    explicit_id = clean_text(fhir.get("id") or fhir.get("serviceRequestId"))
    if explicit_id:
        resource["id"] = explicit_id
    identifier_system = clean_text(
        fhir.get("identifierSystem") or FHIR_IDENTIFIER_SYSTEMS["ServiceRequest"]
    )
    identifier_text = clean_text(
        fhir.get("identifierValue")
        or identifier_value("ServiceRequest", "local_order_records", record_id)
    )
    resource["identifier"] = [{"system": identifier_system, "value": identifier_text}]
    for item in list_values(fhir.get("identifier")):
        if "|" in item:
            system, value = item.split("|", 1)
            resource["identifier"].append({"system": system.strip(), "value": value.strip()})
        else:
            resource["identifier"].append({"value": item})
    for key in ("instantiatesCanonical", "instantiatesUri"):
        items = list_values(fhir.get(key))
        if items:
            resource[key] = items
    for key in (
        "basedOn", "replaces", "reasonReference", "insurance", "supportingInfo",
        "specimen", "relevantHistory",
    ):
        references = reference_list(fhir.get(key), key)
        if references:
            resource[key] = references
    requisition_system = clean_text(fhir.get("requisitionSystem"))
    requisition_value = clean_text(fhir.get("requisitionValue"))
    if requisition_system or requisition_value:
        resource["requisition"] = {
            key: value for key, value in {
                "system": requisition_system,
                "value": requisition_value or local_order_number,
            }.items() if value
        }
    category = codeable_concept(text=fhir.get("category") or DEFAULT_CATEGORY)
    if category:
        resource["category"] = [category]
    if values["priority"]:
        resource["priority"] = values["priority"]
    if "doNotPerform" in fhir:
        resource["doNotPerform"] = bool(fhir.get("doNotPerform"))
    code = codeable_concept(
        text=fhir.get("codeText") or values["order_code_text"],
        code=fhir.get("codeCode") or values["order_code"],
        system=fhir.get("codeSystem") or "urn:healthcare-lab:service-code",
        display=fhir.get("codeDisplay") or values["order_code_text"],
    )
    if values.get("alternate_code"):
        code.setdefault("coding", []).append({
            key: value for key, value in {
                "system": values.get("alternate_code_system"),
                "code": values.get("alternate_code"),
                "display": values.get("alternate_code_text"),
            }.items() if value
        })
    resource["code"] = code
    order_detail = codeable_concept(text=fhir.get("orderDetail"))
    if order_detail:
        resource["orderDetail"] = [order_detail]
    quantity_value = clean_text(fhir.get("quantityValue"))
    quantity_unit = clean_text(fhir.get("quantityUnit"))
    if quantity_value or quantity_unit:
        quantity: dict[str, Any] = {}
        if quantity_value:
            try:
                quantity["value"] = float(quantity_value)
            except ValueError as exc:
                raise SimulatorValidationError("FHIR Order quantity value must be numeric.") from exc
        if quantity_unit:
            quantity["unit"] = quantity_unit
        resource["quantityQuantity"] = quantity
    encounter = clean_text(fhir.get("encounter"))
    if encounter:
        resource["encounter"] = reference_item(encounter, "encounter")
    if values.get("occurrence"):
        resource["occurrenceDateTime"] = values["occurrence"]
    if "asNeededBoolean" in fhir:
        resource["asNeededBoolean"] = bool(fhir.get("asNeededBoolean"))
    as_needed = codeable_concept(text=fhir.get("asNeededCodeText"))
    if as_needed:
        resource["asNeededCodeableConcept"] = as_needed
    if values.get("authored_on"):
        resource["authoredOn"] = values["authored_on"]
    requester = clean_text(fhir.get("requester") or values["ordering_provider"])
    if requester:
        resource["requester"] = reference_item(requester, "requester") if "/" in requester else {"display": requester}
    performer_type = codeable_concept(text=fhir.get("performerType"))
    if performer_type:
        resource["performerType"] = performer_type
    performer = reference_list(fhir.get("performer"), "performer")
    if performer:
        resource["performer"] = performer
    location_code = codeable_concept(text=fhir.get("locationCode"))
    if location_code:
        resource["locationCode"] = [location_code]
    location_reference = reference_list(fhir.get("locationReference"), "locationReference")
    if location_reference:
        resource["locationReference"] = location_reference
    reason_code = codeable_concept(text=fhir.get("reasonCodeText") or values["clinical_indication"])
    if reason_code:
        resource["reasonCode"] = [reason_code]
    body_site = codeable_concept(text=fhir.get("bodySite"))
    if body_site:
        resource["bodySite"] = [body_site]
    note = clean_text(fhir.get("note"))
    if note:
        resource["note"] = [{"text": note}]
    patient_instruction = clean_text(fhir.get("patientInstruction"))
    if patient_instruction:
        resource["patientInstruction"] = patient_instruction
    return resource
