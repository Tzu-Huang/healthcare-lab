"""GDT workflow row and boundary presentation."""

from __future__ import annotations

import json
from typing import Any

from backend.domain.gdt_protocol import GDT_ORDER_TEST_CODE_FIELD, GDT_RESULT_MESSAGE_TYPE
from backend.mappers.types import RowMapping

GDT_ORDER_PROTOCOL_VERSION = "GDT 2.1"


def json_value(value: str, fallback: Any) -> Any:
    try:
        return json.loads(value or "")
    except (TypeError, ValueError):
        return fallback


def patient_snapshot(patient: dict[str, Any], gdt_patient_number: str) -> dict[str, Any]:
    demographics = patient.get("patient") if isinstance(patient.get("patient"), dict) else patient
    summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
    return {
        "patientRecordId": patient["id"], "mrn": demographics.get("mrn", summary.get("mrn", "")),
        "gdtPatientNumber": gdt_patient_number, "firstName": demographics.get("firstName", ""),
        "middleName": demographics.get("middleName", ""), "lastName": demographics.get("lastName", ""),
        "dob": demographics.get("dob", summary.get("dob", "")),
        "sex": demographics.get("sex", summary.get("sex", "")),
        "visitNumber": patient.get("visitNumber", summary.get("visitNumber", "")),
    }


def attachment_filename(url: str, path: str = "") -> str:
    source = path or url
    return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""


def project_message(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"], "direction": row["direction"],
            "messageType": row["message_type"], "rawGdtText": row["raw_gdt_text"],
            "parsedFields": json_value(row["parsed_fields_json"], {}),
            "canonical": json_value(row["canonical_json"], {}), "parseStatus": row["parse_status"],
            "matchStatus": row["match_status"], "error": row["error_text"],
            "generatedAt": row["generated_at"], "receivedAt": row["received_at"],
            "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def project_attachment(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "messageRecordId": row["message_record_id"], "role": row["role"], "url": row["url"],
            "path": row["path"], "reference": row["reference"], "contentType": row["content_type"],
            "description": row["description"], "sourceFile": row["source_file"], "status": row["status"],
            "details": json_value(row["details_json"], {}), "filename": row["filename"],
            "checksum": row["checksum"], "createdAt": row["created_at"], "updatedAt": row["updated_at"]}


def project_event(row: RowMapping) -> dict[str, Any]:
    return {"id": row["id"], "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"], "messageRecordId": row["message_record_id"],
            "attachmentRecordId": row["attachment_record_id"], "eventType": row["event_type"],
            "actor": row["actor"], "details": json_value(row["details_json"], {}),
            "createdAt": row["created_at"]}


def project_order(row: RowMapping, *, attachments: list[dict[str, Any]],
                  messages: list[dict[str, Any]], events: list[dict[str, Any]]) -> dict[str, Any]:
    name = " ".join(part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part)
    attachment_url = row["attachment_url"] or next((item["url"] for item in attachments if item["url"]), "")
    return {
        "id": row["id"], "localGdtOrderNumber": row["local_gdt_order_number"],
        "patientRecordId": row["patient_record_id"], "gdtPatientContextId": row["gdt_patient_context_id"],
        "protocolVersion": row["protocol_version"], "messageType": row["message_type"],
        "status": row["order_status"], "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
        "gdtTestCode": row["gdt_test_code"], "gdtTestLabel": row["gdt_test_label"],
        "gdtPatientNumber": row["gdt_patient_number"], "requestedAt": row["requested_at"],
        "orderingProvider": row["ordering_provider"], "clinicalIndication": row["clinical_indication"],
        "attachmentUrl": attachment_url, "attachments": attachments, "payload": row["payload_gdt"],
        "rawGdtText": row["payload_gdt"], "patientSnapshot": json_value(row["patient_snapshot_json"], {}),
        "orderSnapshot": json_value(row["order_snapshot_json"], {}), "messages": messages, "events": events,
        "exportPath": row["export_path"], "error": row["error_text"],
        "summary": {"mrn": row["mrn"], "gdtPatientNumber": row["gdt_patient_number"], "name": name,
                    "dob": row["dob"], "sex": row["sex"], "visitNumber": row["visit_number"],
                    "testCode": row["gdt_test_code"], "testLabel": row["gdt_test_label"]},
        "createdAt": row["created_at"], "updatedAt": row["updated_at"], "localOnly": True,
    }


def project_workbench(*, patients: list[dict[str, Any]], orders: list[dict[str, Any]],
                      messages: list[dict[str, Any]], attachments: list[dict[str, Any]],
                      bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    results = [item for item in messages if item.get("direction") == "inbound" and item.get("messageType") == GDT_RESULT_MESSAGE_TYPE]
    orders_by_patient: dict[int, list[dict[str, Any]]] = {}
    results_by_order: dict[int, list[dict[str, Any]]] = {}
    results_by_context: dict[int, list[dict[str, Any]]] = {}
    attachments_by_message: dict[int, list[dict[str, Any]]] = {}
    for order in orders:
        orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
    for result in results:
        if result.get("orderRecordId"):
            results_by_order.setdefault(int(result["orderRecordId"]), []).append(result)
        if result.get("patientContextId"):
            results_by_context.setdefault(int(result["patientContextId"]), []).append(result)
    for attachment in attachments:
        if attachment.get("messageRecordId"):
            attachments_by_message.setdefault(int(attachment["messageRecordId"]), []).append(attachment)
    for result in results:
        result["attachments"] = attachments_by_message.get(int(result["id"]), [])
    workbench_patients = []
    for patient in patients:
        patient_orders = orders_by_patient.get(int(patient["id"]), [])
        if not patient_orders and patient.get("protocolVersion") != GDT_ORDER_PROTOCOL_VERSION:
            continue
        context_ids = {int(order["gdtPatientContextId"]) for order in patient_orders if order.get("gdtPatientContextId")}
        patient_results = [result for context_id in context_ids for result in results_by_context.get(context_id, [])]
        item = {**patient, "orders": patient_orders, "results": patient_results,
                "orderCount": len(patient_orders), "resultCount": len(patient_results)}
        item["summary"] = {**item.get("summary", {}), "orderCount": len(patient_orders),
                           "resultCount": len(patient_results)}
        workbench_patients.append(item)
    return {"patients": workbench_patients, "orders": orders, "results": results,
            "unmatchedResults": [result for result in results if not result.get("orderRecordId") and not result.get("patientContextId")],
            "attachments": attachments, "bridgeInbox": bridge_inbox or [], "resultsByOrder": results_by_order}
