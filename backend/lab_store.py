from __future__ import annotations

import hashlib
import json
import math
import re
import sqlite3
import threading
import urllib.parse
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

try:
    import pymysql
    import pymysql.cursors
except ImportError:  # pragma: no cover - optional OpenEMR integration dependency
    pymysql = None

from backend.gdt_adapter import (
    GDT_DEFAULT_CHARSET_MARKER,
    GDT_DEFAULT_ENCODING,
    GDT_ORDER_MESSAGE_TYPE,
    GDT_ORDER_TEST_CODE,
    GDT_ORDER_TEST_CODE_FIELD,
    GDT_RESULT_MESSAGE_TYPE,
    GDT_VERSION,
    GdtValidationError,
    attachment_payloads_from_result_fields,
    build_gdt_6302_request,
    first_gdt_field as adapter_first_gdt_field,
    parse_gdt_6310_result,
    parse_gdt_message as adapter_parse_gdt_message,
    render_gdt_message as adapter_render_gdt_message,
    render_gdt_record as adapter_render_gdt_record,
)

OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES = ("1001",)
HL7_V2_VERSION = "2.5.1"
HL7_V2_CHARSET = "UNICODE UTF-8"
HL7_V2_MSH_SUFFIX = f"{HL7_V2_VERSION}||||||{HL7_V2_CHARSET}"
PATIENT_PROTOCOL_VERSION = HL7_V2_VERSION
PATIENT_MESSAGE_TYPE = "ADT^A04"
PATIENT_MODES = {
    "hl7-v2": {"protocol": "HL7 v2.5.1", "message_type": "ADT^A04"},
    "fhir": {"protocol": "FHIR R4", "message_type": "Patient"},
    "gdt": {"protocol": "GDT 2.1", "message_type": "6301"},
    "dicom": {"protocol": "DICOM", "message_type": "Patient Module"},
}
PATIENT_CLASS_DEFAULT = "O"
GDT_PATIENT_SEX_CODES = {"M": "1", "F": "2"}
ORDER_PROTOCOL_VERSION = HL7_V2_VERSION
ORDER_MESSAGE_TYPE = "ORM^O01"
ORDER_STATUS_READY = "Ready to send"
ORDER_STATUS_ACCEPTED = "Accepted"
ORDER_STATUS_ERROR = "Error"
ORDER_STATUS_REJECTED = "Rejected"
ORDER_STATUS_TRANSPORT_ERROR = "Transport error"
ORDER_ALLOWED_PRIORITIES = ("R", "S", "A")
ORDER_DEFAULT_CODE = "ECG12"
ORDER_DEFAULT_TEXT = "12 Lead ECG"
ORDER_DEFAULT_ALT_CODE = "93000"
ORDER_DEFAULT_ALT_TEXT = "Electrocardiogram, routine ECG with at least 12 leads"
ORDER_DEFAULT_ALT_SYSTEM = "C4"
ORDER_DEFAULT_PROVIDER = "1001^WANG^AMY"
OIE_SETTINGS_PROFILE_NAME = "local-oie"
OIE_MANAGEMENT_API_BASE_URL = "http://oie:8080"
OIE_MANAGEMENT_API_USERNAME = "admin"
OIE_MANAGEMENT_API_PASSWORD = "Admin"
OIE_MANAGEMENT_API_TIMEOUT_SECONDS = 10
OIE_RESULT_LISTENER_HOST = "0.0.0.0"
OIE_RESULT_LISTENER_PORT = 6665
DCM4CHEE_ORDER_PROTOCOL_VERSION = "DICOM"
DCM4CHEE_ORDER_MESSAGE_TYPE = "MWL"
DCM4CHEE_MWL_STATUS_PENDING = "Pending sync"
DCM4CHEE_MWL_STATUS_CREATED = "Created"
DCM4CHEE_MWL_STATUS_FAILED = "Sync failed"
DCM4CHEE_MWL_STATUS_PATIENT_MISSING = "Patient missing"
DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES = {"patient_missing", "patient_sync_failed", "profile_invalid"}
DCM4CHEE_PATIENT_SYNC_STATUS_PENDING = "Pending sync"
DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED = "Synced"
DCM4CHEE_PATIENT_SYNC_STATUS_FAILED = "Sync failed"
DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE = "adt-create"
DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_UPDATE = "adt-update"
DCM4CHEE_PATIENT_SYNC_OPERATION_PREFLIGHT = "preflight"
DCM4CHEE_MWL_OPERATION_CREATE = "create"
DCM4CHEE_MWL_OPERATION_READBACK = "read-back"
DCM4CHEE_MWL_OPERATION_VERIFY = "verify-mwl"
DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED = "not_verified"
DCM4CHEE_MWL_VERIFICATION_VERIFIED = "verified"
DCM4CHEE_MWL_VERIFICATION_FAILED = "verification_failed"
DCM4CHEE_MWL_VERIFICATION_AMBIGUOUS = "verification_ambiguous"
DCM4CHEE_RESULT_STATUS_MATCHED = "matched"
DCM4CHEE_RESULT_STATUS_NO_RESULT = "no_result"
DCM4CHEE_RESULT_STATUS_AMBIGUOUS = "ambiguous"
DCM4CHEE_RESULT_STATUS_DUPLICATE = "duplicate"
DCM4CHEE_RESULT_STATUS_WRONG_PATIENT = "wrong_patient"
DCM4CHEE_RESULT_STATUS_MISSING_ACCESSION = "missing_accession"
DCM4CHEE_RESULT_STATUS_UNLINKED = "unlinked"
DCM4CHEE_RESULT_STATUS_QUERY_FAILED = "query_failed"
DCM4CHEE_RESULT_SOURCE_SIMULATED_AP = "simulated_ap_return"
DCM4CHEE_DEFAULT_UID_ROOT = "1.2.826.0.1.3680043.10.543"
FHIR_ORDER_PROTOCOL_VERSION = "FHIR R4"
FHIR_ORDER_MESSAGE_TYPE = "ServiceRequest"
FHIR_ORDER_STATUS_CREATED = "Created"
FHIR_ORDER_DEFAULT_STATUS = "active"
FHIR_ORDER_DEFAULT_INTENT = "order"
FHIR_ORDER_DEFAULT_CATEGORY = "Procedure"
FHIR_ORDER_DEFAULT_PRIORITY = "routine"
GDT_ORDER_PROTOCOL_VERSION = "GDT 2.1"
GDT_ORDER_STATUS_CREATED = "Created"
GDT_ORDER_STATUS_ERROR = "Error"
GDT_ORDER_STATUS_RESULT_RECEIVED = "Result received"
GDT_ORDER_TEST_LABEL = "12-lead resting ECG"
LAB_SERVER_TYPES = (
    "HL7 Engine",
    "FHIR Server",
    "EMR",
    "GDT Bridge",
    "DICOM Archive",
    "Test Tool",
    "Generic HTTP Service",
)
LAB_SERVER_PROTOCOLS = ("HTTP", "TCP", "MLLP", "FHIR", "GDT", "DICOM", "None")
LAB_HEALTH_STATUSES = ("Healthy", "Degraded", "Down", "Unknown")
LAB_OPERATION_ACTIONS = ("status", "start", "stop", "restart", "smoke", "logs")
FHIR_SYNC_STATUS_PENDING = "Pending sync"
FHIR_SYNC_STATUS_SYNCING = "Syncing"
FHIR_SYNC_STATUS_SYNCED = "Synced"
FHIR_SYNC_STATUS_FAILED = "Sync failed"
FHIR_SYNC_STATUSES = (
    FHIR_SYNC_STATUS_PENDING,
    FHIR_SYNC_STATUS_SYNCING,
    FHIR_SYNC_STATUS_SYNCED,
    FHIR_SYNC_STATUS_FAILED,
)
FHIR_SUPPORTED_RESOURCE_TYPES = (
    "Patient",
    "ServiceRequest",
    "Binary",
    "Observation",
    "DocumentReference",
    "DiagnosticReport",
    "Provenance",
)
FHIR_RESOURCE_DEPENDENCY_ORDER = {
    "Patient": 10,
    "ServiceRequest": 20,
    "Binary": 40,
    "Observation": 50,
    "DocumentReference": 60,
    "DiagnosticReport": 70,
    "Provenance": 80,
}
FHIR_IDENTIFIER_SYSTEMS = {
    "Patient": "https://healthcare-lab.local/fhir/identifier/patient",
    "ServiceRequest": "https://healthcare-lab.local/fhir/identifier/service-request",
    "Binary": "https://healthcare-lab.local/fhir/identifier/binary",
    "Observation": "https://healthcare-lab.local/fhir/identifier/observation",
    "DocumentReference": "https://healthcare-lab.local/fhir/identifier/document-reference",
    "DiagnosticReport": "https://healthcare-lab.local/fhir/identifier/diagnostic-report",
    "Provenance": "https://healthcare-lab.local/fhir/identifier/provenance",
}
FHIR_RESOURCE_MAPPINGS = {
    "Patient": {
        "local_source_type": "local_patient_records",
        "depends_on": (),
    },
    "ServiceRequest": {
        "local_source_type": "local_order_records",
        "depends_on": ("Patient",),
    },
    "Binary": {
        "local_source_type": "local_fhir_artifacts",
        "depends_on": (),
    },
    "Observation": {
        "local_source_type": "local_fhir_results",
        "depends_on": ("Patient", "ServiceRequest"),
    },
    "DocumentReference": {
        "local_source_type": "local_fhir_artifacts",
        "depends_on": ("Patient", "ServiceRequest", "Binary"),
    },
    "DiagnosticReport": {
        "local_source_type": "local_fhir_results",
        "depends_on": ("Patient", "ServiceRequest", "Observation", "DocumentReference"),
    },
    "Provenance": {
        "local_source_type": "local_fhir_provenance",
        "depends_on": (
            "Patient",
            "ServiceRequest",
            "Binary",
            "Observation",
            "DocumentReference",
            "DiagnosticReport",
        ),
    },
}

DEFAULT_LAB_SERVERS = (
    {
        "name": "OIE",
        "server_type": "HL7 Engine",
        "description": "Open Integration Engine / Mirth-style HL7 engine",
        "host": "127.0.0.1",
        "port": 18080,
        "base_url": "http://127.0.0.1:18080",
        "protocol": "MLLP",
        "check_config": {"mllpHost": "127.0.0.1", "mllpPort": 6661},
    },
    {
        "name": "Medplum",
        "server_type": "FHIR Server",
        "description": "FHIR R4 API server",
        "host": "127.0.0.1",
        "port": 8103,
        "base_url": "http://127.0.0.1:8103/fhir/R4",
        "protocol": "FHIR",
    },
    {
        "name": "OpenEMR",
        "server_type": "EMR",
        "description": "OpenEMR clinical system",
        "host": "127.0.0.1",
        "port": 8088,
        "base_url": "http://127.0.0.1:8088",
        "protocol": "HTTP",
    },
    {
        "name": "GDT Bridge",
        "server_type": "GDT Bridge",
        "description": "Shared-folder GDT exchange bridge",
        "host": "",
        "port": None,
        "base_url": "",
        "protocol": "GDT",
    },
    {
        "name": "dcm4chee",
        "server_type": "DICOM Archive",
        "description": "DICOM archive service",
        "host": "127.0.0.1",
        "port": 8082,
        "base_url": "http://127.0.0.1:8082/dcm4chee-arc/ui2",
        "protocol": "DICOM",
    },
    {
        "name": "HL7Tester",
        "server_type": "Test Tool",
        "description": "HL7 message generation and test tool",
        "host": "127.0.0.1",
        "port": 6671,
        "base_url": "",
        "protocol": "MLLP",
    },
    {
        "name": "GDT Hospital",
        "server_type": "Test Tool",
        "description": "GDT hospital-side simulator",
        "host": "",
        "port": None,
        "base_url": "",
        "protocol": "GDT",
    },
)

DEFAULT_LAB_OPERATION_METADATA = {
    "OIE": {
        "control_type": "docker-compose",
        "backing_service": "oie",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 120,
        "smoke_profile": "oie",
    },
    "Medplum": {
        "control_type": "docker-compose",
        "backing_service": "medplum",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 180,
        "smoke_profile": "medplum",
    },
    "OpenEMR": {
        "control_type": "docker-compose",
        "backing_service": "openemr",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 240,
        "smoke_profile": "openemr",
    },
    "GDT Bridge": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "gdt-bridge",
    },
    "dcm4chee": {
        "control_type": "docker-compose",
        "backing_service": "dcm4chee",
        "supported_actions": ["status", "start", "stop", "restart", "smoke", "logs"],
        "timeout_seconds": 240,
        "smoke_profile": "dcm4chee",
    },
    "HL7Tester": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "hl7tester",
    },
    "GDT Hospital": {
        "control_type": "internal-tool",
        "backing_service": "lab-app",
        "supported_actions": ["status", "smoke", "logs"],
        "timeout_seconds": 60,
        "smoke_profile": "gdt-hospital",
    },
}


class SimulatorValidationError(ValueError):
    pass


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


def urllib_quote_safe(value: Any) -> str:
    return urllib.parse.quote(str(value or "").strip(), safe="")


def hl7_timestamp() -> str:
    return datetime.now().strftime("%Y%m%d%H%M%S")


def _hl7_escape(value: Any) -> str:
    text = str(value if value is not None else "")
    return (
        text.replace("\\", "\\E\\")
        .replace("|", "\\F\\")
        .replace("^", "\\S\\")
        .replace("&", "\\T\\")
        .replace("~", "\\R\\")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
        .replace("\n", "\\.br\\")
    )


def _hl7_escape_composite(value: Any) -> str:
    return "^".join(
        _hl7_escape(component)
        for component in str(value if value is not None else "").split("^")
    )


def _gdt_clean_value(value: Any) -> str:
    return str(value if value is not None else "").strip().replace("\r", " ").replace("\n", " ")


def _encode_gdt_text(value: str) -> bytes:
    try:
        return value.encode(GDT_DEFAULT_ENCODING)
    except UnicodeEncodeError as exc:
        raise SimulatorValidationError(
            "GDT 2.1 patient fields must use ANSI/ISO-8859-1 compatible characters."
        ) from exc


def render_gdt_record(code: str, value: Any) -> bytes:
    try:
        return adapter_render_gdt_record(code, value)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def render_gdt_message(records: list[tuple[str, Any]], *, set_type: str) -> str:
    try:
        return adapter_render_gdt_message(records, set_type=set_type)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def parse_gdt_message(payload: str) -> dict[str, list[str]]:
    try:
        return adapter_parse_gdt_message(payload)
    except GdtValidationError as exc:
        raise SimulatorValidationError(str(exc)) from exc


def first_gdt_field(fields: dict[str, list[str]], code: str) -> str:
    return adapter_first_gdt_field(fields, code)


def ensure_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    """Resolve the configured GDT paths without creating them."""
    root = Path(base_path)
    return {
        "root": root,
        "inbox": root / "inbox",
        "outbox": root / "outbox",
        "processed": root / "processed",
        "processing": root / "processing",
        "error": root / "error",
        "reports": root / "reports",
        "archive": root / "archive",
    }


def validate_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    directories = ensure_gdt_bridge_dirs(base_path)
    probe_name = f".write-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    for name in ("inbox", "outbox"):
        if not directories[name].is_dir():
            raise SimulatorValidationError(
                f"GDT {name} folder does not exist: {directories[name]}"
            )
        probe_path = directories[name] / probe_name
        try:
            probe_path.write_text("ok", encoding="utf-8")
            probe_path.unlink()
        except OSError as exc:
            raise SimulatorValidationError(
                f"GDT {name} folder is not writable: {directories[name]}"
            ) from exc
    return directories


def normalize_openemr_dob(value: Any) -> str:
    text = str(value or "").strip()
    return text[:10] if len(text) >= 10 else text


def normalize_openemr_gender(value: Any) -> str:
    normalized = str(value or "").strip().lower()
    if normalized in {"m", "male", "man"}:
        return "M"
    if normalized in {"f", "female", "woman"}:
        return "F"
    if normalized in {"o", "other"}:
        return "O"
    return "U" if normalized else ""


def parse_openemr_allowed_procedure_codes(value: Any) -> tuple[str, ...]:
    if value is None:
        return OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES
    if isinstance(value, str):
        codes = [item.strip() for item in value.replace(";", ",").split(",")]
    else:
        codes = [str(item).strip() for item in value]
    return tuple(code for code in codes if code)


def openemr_provider_name(row: dict[str, Any]) -> str:
    full_name = " ".join(
        part
        for part in (
            str(row.get("provider_fname") or "").strip(),
            str(row.get("provider_lname") or "").strip(),
        )
        if part
    )
    return full_name or str(row.get("provider_username") or "").strip()


def openemr_row_source_key(row: dict[str, Any]) -> tuple[int, int]:
    return int(row["procedure_order_id"]), int(row.get("procedure_order_seq") or 1)


def map_openemr_procedure_order_to_gdt_order(row: dict[str, Any]) -> dict[str, Any]:
    procedure_order_id, procedure_order_seq = openemr_row_source_key(row)
    order_number = f"OE-PO-{procedure_order_id}-{procedure_order_seq}"
    patient_mrn = str(row.get("pubpid") or row.get("pid") or row.get("patient_id") or "").strip()
    return {
        "source": "openemr",
        "sourceProcedureOrderId": procedure_order_id,
        "sourceProcedureOrderSeq": procedure_order_seq,
        "sourceFingerprint": hashlib.sha256(
            json.dumps(row, default=str, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        "orderNumber": order_number,
        "placerOrderNumber": order_number,
        "fillerOrderNumber": "",
        "correlationId": f"openemr-procedure-order:{procedure_order_id}:{procedure_order_seq}",
        "patientMrn": patient_mrn,
        "patient": {
            "mrn": patient_mrn,
            "first_name": str(row.get("patient_fname") or "").strip(),
            "last_name": str(row.get("patient_lname") or "").strip(),
            "middle_name": "",
            "dob": normalize_openemr_dob(row.get("patient_dob")),
            "gender": normalize_openemr_gender(row.get("patient_sex")),
        },
        "encounterId": str(row.get("encounter_id") or "").strip(),
        "examCode": str(row.get("procedure_code") or "").strip(),
        "examDescription": str(row.get("procedure_name") or "").strip(),
        "orderingProvider": openemr_provider_name(row),
        "orderDate": str(row.get("date_ordered") or "").strip(),
        "encounterDate": str(row.get("encounter_date") or "").strip(),
        "encounterReason": str(row.get("encounter_reason") or "").strip(),
        "status": "QUEUED_FOR_GDT",
    }


class OpenEMRProcedureOrderSource:
    def __init__(
        self,
        *,
        host: str = "",
        port: int = 3306,
        user: str = "",
        password: str = "",
        database: str = "",
        allowed_procedure_codes: tuple[str, ...] = OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
        connection_factory: Callable[..., Any] | None = None,
    ) -> None:
        self.host = host.strip()
        self.port = int(port)
        self.user = user.strip()
        self.password = password
        self.database = database.strip()
        self.allowed_procedure_codes = tuple(allowed_procedure_codes)
        self.connection_factory = connection_factory

    def configured(self) -> bool:
        return bool(self.host and self.user and self.database and self.allowed_procedure_codes)

    def status(self) -> dict[str, Any]:
        return {
            "configured": self.configured(),
            "host": self.host,
            "port": self.port,
            "database": self.database,
            "user": self.user,
            "allowedProcedureCodes": list(self.allowed_procedure_codes),
            "driverAvailable": bool(pymysql or self.connection_factory),
        }

    def list_orders(self) -> list[dict[str, Any]]:
        if not self.configured():
            raise SimulatorValidationError("OpenEMR procedure-order source is not configured.")
        try:
            rows = self._fetch_rows()
        except Exception as exc:
            if self._is_missing_order_schema_error(exc):
                return []
            raise
        return [map_openemr_procedure_order_to_gdt_order(row) for row in rows]

    def get_order(self, procedure_order_id: int, procedure_order_seq: int) -> dict[str, Any]:
        for order in self.list_orders():
            if (
                order["sourceProcedureOrderId"] == int(procedure_order_id)
                and order["sourceProcedureOrderSeq"] == int(procedure_order_seq)
            ):
                return order
        raise KeyError(f"{procedure_order_id}:{procedure_order_seq}")

    def _connect(self) -> Any:
        if self.connection_factory:
            return self.connection_factory()
        if pymysql is None:
            raise SimulatorValidationError(
                "PyMySQL is required for OpenEMR MariaDB access. Install requirements first."
            )
        return pymysql.connect(
            host=self.host,
            port=self.port,
            user=self.user,
            password=self.password,
            database=self.database,
            charset="utf8mb4",
            cursorclass=pymysql.cursors.DictCursor,
        )

    def verify_order_query(self) -> dict[str, Any]:
        result: dict[str, Any] = {
            "configured": self.configured(),
            "connection": {
                "status": "Down",
                "message": "OpenEMR procedure-order source is not configured.",
            },
            "schema": {
                "status": "Unknown",
                "message": "OpenEMR procedure-order source is not configured.",
            },
            "orders": {
                "status": "Unknown",
                "message": "OpenEMR procedure-order source is not configured.",
                "count": 0,
            },
        }
        if not self.configured():
            return result
        try:
            connection = self._connect()
        except Exception as exc:
            message = str(exc)
            result["connection"] = {"status": "Down", "message": message}
            result["schema"] = {"status": "Unknown", "message": "Skipped because MariaDB connection failed."}
            result["orders"] = {
                "status": "Unknown",
                "message": "Skipped because MariaDB connection failed.",
                "count": 0,
            }
            return result
        result["connection"] = {"status": "Healthy", "message": "MariaDB connection opened."}
        try:
            rows = self._fetch_rows_with_connection(connection)
        except Exception as exc:
            message = str(exc)
            if self._is_missing_order_schema_error(exc):
                message = f"Required OpenEMR procedure-order schema is unavailable: {message}"
            result["schema"] = {"status": "Down", "message": message}
            result["orders"] = {
                "status": "Unknown",
                "message": "Skipped because procedure-order query failed.",
                "count": 0,
            }
            return result
        finally:
            connection.close()
        count = len(rows)
        result["schema"] = {
            "status": "Healthy",
            "message": "OpenEMR procedure-order query executed.",
        }
        result["orders"] = {
            "status": "Healthy" if count else "Degraded",
            "message": f"{count} matching ECG procedure order(s).",
            "count": count,
        }
        return result

    @staticmethod
    def _is_missing_order_schema_error(exc: Exception) -> bool:
        args = getattr(exc, "args", ())
        code = args[0] if args else None
        message = str(args[1] if len(args) > 1 else exc).lower()
        order_tables = ("procedure_order", "procedure_order_code", "patient_data")
        return code == 1146 and "doesn't exist" in message and any(
            table in message for table in order_tables
        )

    def _fetch_rows(self) -> list[dict[str, Any]]:
        connection = self._connect()
        try:
            return self._fetch_rows_with_connection(connection)
        finally:
            connection.close()

    def _fetch_rows_with_connection(self, connection: Any) -> list[dict[str, Any]]:
        placeholders = ", ".join(["%s"] * len(self.allowed_procedure_codes))
        query = f"""
            SELECT
              po.procedure_order_id,
              po.uuid AS order_uuid,
              po.provider_id,
              po.patient_id,
              po.encounter_id,
              po.date_ordered,
              poc.procedure_order_seq,
              poc.procedure_code,
              poc.procedure_name,
              pd.pubpid,
              pd.pid,
              pd.fname AS patient_fname,
              pd.lname AS patient_lname,
              pd.DOB AS patient_dob,
              pd.sex AS patient_sex,
              fe.reason AS encounter_reason,
              fe.date AS encounter_date,
              u.username AS provider_username,
              u.fname AS provider_fname,
              u.lname AS provider_lname,
              u.npi AS provider_npi
            FROM procedure_order po
            JOIN procedure_order_code poc
              ON poc.procedure_order_id = po.procedure_order_id
            JOIN patient_data pd
              ON pd.id = po.patient_id
            LEFT JOIN form_encounter fe
              ON fe.encounter = po.encounter_id
             AND fe.pid = po.patient_id
            LEFT JOIN users u
              ON u.id = po.provider_id
            WHERE poc.procedure_code IN ({placeholders})
            ORDER BY po.procedure_order_id DESC, poc.procedure_order_seq ASC
        """
        with connection.cursor() as cursor:
            cursor.execute(query, self.allowed_procedure_codes)
            return [dict(row) for row in cursor.fetchall()]


class DemoStore:
    def __init__(self, path: str | Path):
        self.path = str(path)
        self.lock = threading.RLock()
        self.initialize()
        from backend.repositories.oie_settings import OieSettingsRepository

        self.oie_settings_repository = OieSettingsRepository(
            self.connect,
            self.lock,
            profile_name=OIE_SETTINGS_PROFILE_NAME,
            validator=self.validate_oie_settings_payload,
            serializer=self._oie_settings_profile_dict,
            timestamp_factory=now_iso,
        )

    @contextmanager
    def connect(self):
        connection = sqlite3.connect(self.path, timeout=5)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        try:
            yield connection
            connection.commit()
        finally:
            connection.close()

    def initialize(self) -> None:
        with self.lock, self.connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS lab_servers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT NOT NULL UNIQUE,
                    server_type TEXT NOT NULL,
                    description TEXT NOT NULL DEFAULT '',
                    host TEXT NOT NULL DEFAULT '',
                    port INTEGER,
                    base_url TEXT NOT NULL DEFAULT '',
                    protocol TEXT NOT NULL DEFAULT 'None',
                    enabled INTEGER NOT NULL DEFAULT 1,
                    version TEXT NOT NULL DEFAULT '',
                    check_config_json TEXT NOT NULL DEFAULT '{}',
                    control_type TEXT NOT NULL DEFAULT '',
                    backing_service TEXT NOT NULL DEFAULT '',
                    supported_actions_json TEXT NOT NULL DEFAULT '[]',
                    operation_timeout_seconds INTEGER NOT NULL DEFAULT 60,
                    smoke_profile TEXT NOT NULL DEFAULT '',
                    overall_status TEXT NOT NULL DEFAULT 'Unknown',
                    process_status TEXT NOT NULL DEFAULT 'Unknown',
                    application_status TEXT NOT NULL DEFAULT 'Unknown',
                    protocol_status TEXT NOT NULL DEFAULT 'Unknown',
                    last_check_at TEXT NOT NULL DEFAULT '',
                    recent_error TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS lab_operation_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    server_id INTEGER,
                    service_name TEXT NOT NULL,
                    action TEXT NOT NULL,
                    operator TEXT NOT NULL,
                    result TEXT NOT NULL,
                    duration_ms INTEGER NOT NULL DEFAULT 0,
                    progress_json TEXT NOT NULL DEFAULT '[]',
                    error_text TEXT NOT NULL DEFAULT '',
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL,
                    FOREIGN KEY(server_id) REFERENCES lab_servers(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_identifier_sequences (
                    name TEXT PRIMARY KEY,
                    next_value INTEGER NOT NULL CHECK(next_value > 0)
                );
                CREATE TABLE IF NOT EXISTS local_patient_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_patient_number TEXT NOT NULL UNIQUE,
                    protocol_version TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    mrn TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    middle_name TEXT NOT NULL DEFAULT '',
                    dob TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    address TEXT NOT NULL DEFAULT '',
                    phone TEXT NOT NULL DEFAULT '',
                    email TEXT NOT NULL DEFAULT '',
                    fhir_active INTEGER NOT NULL DEFAULT 1,
                    address_line TEXT NOT NULL DEFAULT '',
                    address_city TEXT NOT NULL DEFAULT '',
                    address_state TEXT NOT NULL DEFAULT '',
                    address_postal_code TEXT NOT NULL DEFAULT '',
                    address_country TEXT NOT NULL DEFAULT '',
                    managing_organization_reference TEXT NOT NULL DEFAULT '',
                    managing_organization_display TEXT NOT NULL DEFAULT '',
                    visit_number TEXT NOT NULL,
                    patient_class TEXT NOT NULL DEFAULT 'O',
                    assigned_location TEXT NOT NULL DEFAULT '',
                    attending_provider TEXT NOT NULL DEFAULT '',
                    account_number TEXT NOT NULL DEFAULT '',
                    validation_status TEXT NOT NULL,
                    validation_messages_json TEXT NOT NULL DEFAULT '[]',
                    payload_hl7 TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS local_order_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_order_number TEXT NOT NULL UNIQUE,
                    patient_record_id INTEGER NOT NULL,
                    protocol_version TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    order_status TEXT NOT NULL,
                    mrn TEXT NOT NULL,
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    middle_name TEXT NOT NULL DEFAULT '',
                    dob TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    visit_id TEXT NOT NULL,
                    patient_class TEXT NOT NULL DEFAULT 'O',
                    assigned_location TEXT NOT NULL DEFAULT '',
                    account_number TEXT NOT NULL DEFAULT '',
                    placer_order_number TEXT NOT NULL,
                    filler_order_number TEXT NOT NULL DEFAULT '',
                    priority TEXT NOT NULL DEFAULT 'R',
                    requested_at TEXT NOT NULL,
                    ordering_provider TEXT NOT NULL,
                    clinical_indication TEXT NOT NULL DEFAULT '',
                    order_code TEXT NOT NULL,
                    order_code_text TEXT NOT NULL,
                    alternate_code TEXT NOT NULL DEFAULT '',
                    alternate_code_text TEXT NOT NULL DEFAULT '',
                    alternate_code_system TEXT NOT NULL DEFAULT '',
                    validation_status TEXT NOT NULL,
                    validation_messages_json TEXT NOT NULL DEFAULT '[]',
                    payload_hl7 TEXT NOT NULL,
                    ack_code TEXT NOT NULL DEFAULT '',
                    ack_control_id TEXT NOT NULL DEFAULT '',
                    ack_text TEXT NOT NULL DEFAULT '',
                    ack_payload TEXT NOT NULL DEFAULT '',
                    transport_error TEXT NOT NULL DEFAULT '',
                    last_sent_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS oie_result_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    message_control_id TEXT NOT NULL DEFAULT '',
                    message_type TEXT NOT NULL,
                    patient_mrn TEXT NOT NULL DEFAULT '',
                    placer_order_number TEXT NOT NULL DEFAULT '',
                    filler_order_number TEXT NOT NULL DEFAULT '',
                    matched_patient_record_id INTEGER,
                    matched_order_record_id INTEGER,
                    match_status TEXT NOT NULL,
                    duplicate_of_id INTEGER,
                    parse_status TEXT NOT NULL,
                    error_text TEXT NOT NULL DEFAULT '',
                    payload_hl7 TEXT NOT NULL,
                    received_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(matched_patient_record_id) REFERENCES local_patient_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(matched_order_record_id) REFERENCES local_order_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(duplicate_of_id) REFERENCES oie_result_records(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS oie_settings_profiles (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_name TEXT NOT NULL UNIQUE,
                    management_api_base_url TEXT NOT NULL,
                    management_api_username TEXT NOT NULL,
                    management_api_password TEXT NOT NULL,
                    management_api_tls_verify INTEGER NOT NULL DEFAULT 0,
                    management_api_timeout_seconds REAL NOT NULL,
                    result_listener_host TEXT NOT NULL,
                    result_listener_port INTEGER NOT NULL,
                    result_listener_mllp_framing INTEGER NOT NULL DEFAULT 1,
                    result_listener_auto_start INTEGER NOT NULL DEFAULT 1,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS oie_managed_channel_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    profile_id INTEGER NOT NULL,
                    logical_type TEXT NOT NULL,
                    oie_channel_id TEXT NOT NULL DEFAULT '',
                    channel_name TEXT NOT NULL,
                    template_version TEXT NOT NULL DEFAULT '',
                    last_known_revision TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(profile_id) REFERENCES oie_settings_profiles(id) ON DELETE CASCADE,
                    UNIQUE(profile_id, logical_type)
                );
                CREATE TABLE IF NOT EXISTS local_gdt_order_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_gdt_order_number TEXT NOT NULL UNIQUE,
                    patient_record_id INTEGER NOT NULL,
                    gdt_patient_context_id INTEGER,
                    protocol_version TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    order_status TEXT NOT NULL,
                    mrn TEXT NOT NULL,
                    gdt_patient_number TEXT NOT NULL DEFAULT '',
                    first_name TEXT NOT NULL,
                    last_name TEXT NOT NULL,
                    middle_name TEXT NOT NULL DEFAULT '',
                    dob TEXT NOT NULL,
                    sex TEXT NOT NULL,
                    visit_number TEXT NOT NULL DEFAULT '',
                    gdt_test_code TEXT NOT NULL,
                    gdt_test_label TEXT NOT NULL,
                    requested_at TEXT NOT NULL,
                    ordering_provider TEXT NOT NULL DEFAULT '',
                    clinical_indication TEXT NOT NULL DEFAULT '',
                    attachment_url TEXT NOT NULL DEFAULT '',
                    payload_gdt TEXT NOT NULL,
                    patient_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    order_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    export_path TEXT NOT NULL DEFAULT '',
                    error_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(gdt_patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS local_gdt_patient_contexts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_record_id INTEGER NOT NULL UNIQUE,
                    generated_gdt_patient_number TEXT NOT NULL UNIQUE,
                    gdt_patient_number_override TEXT NOT NULL DEFAULT '',
                    effective_gdt_patient_number TEXT NOT NULL UNIQUE,
                    patient_snapshot_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE RESTRICT
                );
                CREATE TABLE IF NOT EXISTS local_gdt_message_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_record_id INTEGER,
                    patient_context_id INTEGER,
                    direction TEXT NOT NULL,
                    message_type TEXT NOT NULL,
                    raw_gdt_text TEXT NOT NULL,
                    parsed_fields_json TEXT NOT NULL DEFAULT '{}',
                    canonical_json TEXT NOT NULL DEFAULT '{}',
                    parse_status TEXT NOT NULL,
                    match_status TEXT NOT NULL DEFAULT '',
                    error_text TEXT NOT NULL DEFAULT '',
                    generated_at TEXT NOT NULL DEFAULT '',
                    received_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_gdt_attachment_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_record_id INTEGER,
                    message_record_id INTEGER,
                    role TEXT NOT NULL,
                    url TEXT NOT NULL DEFAULT '',
                    path TEXT NOT NULL DEFAULT '',
                    reference TEXT NOT NULL DEFAULT '',
                    content_type TEXT NOT NULL DEFAULT '',
                    description TEXT NOT NULL DEFAULT '',
                    source_file TEXT NOT NULL DEFAULT '',
                    status TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    filename TEXT NOT NULL DEFAULT '',
                    checksum TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(message_record_id) REFERENCES local_gdt_message_records(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_gdt_workflow_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_record_id INTEGER,
                    patient_context_id INTEGER,
                    message_record_id INTEGER,
                    attachment_record_id INTEGER,
                    event_type TEXT NOT NULL,
                    actor TEXT NOT NULL DEFAULT '',
                    details_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_gdt_order_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(patient_context_id) REFERENCES local_gdt_patient_contexts(id) ON DELETE SET NULL,
                    FOREIGN KEY(message_record_id) REFERENCES local_gdt_message_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(attachment_record_id) REFERENCES local_gdt_attachment_records(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_fhir_workflow_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    local_fhir_record_number TEXT NOT NULL UNIQUE,
                    local_source_type TEXT NOT NULL,
                    local_source_id TEXT NOT NULL,
                    resource_type TEXT NOT NULL,
                    identifier_system TEXT NOT NULL,
                    identifier_value TEXT NOT NULL,
                    resource_json TEXT NOT NULL,
                    dependency_json TEXT NOT NULL DEFAULT '[]',
                    medplum_resource_id TEXT NOT NULL DEFAULT '',
                    medplum_resource_reference TEXT NOT NULL DEFAULT '',
                    sync_status TEXT NOT NULL,
                    sync_error TEXT NOT NULL DEFAULT '',
                    operation_outcome_json TEXT NOT NULL DEFAULT '{}',
                    last_sync_at TEXT NOT NULL DEFAULT '',
                    sync_started_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS local_fhir_sync_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    fhir_record_id INTEGER NOT NULL,
                    method TEXT NOT NULL,
                    request_url TEXT NOT NULL,
                    request_payload_json TEXT NOT NULL DEFAULT '{}',
                    http_status INTEGER,
                    response_payload_json TEXT NOT NULL DEFAULT '{}',
                    operation_outcome_json TEXT NOT NULL DEFAULT '{}',
                    error_text TEXT NOT NULL DEFAULT '',
                    attempted_at TEXT NOT NULL,
                    FOREIGN KEY(fhir_record_id) REFERENCES local_fhir_workflow_records(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_mwl_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    mapping_id INTEGER,
                    operation_type TEXT NOT NULL DEFAULT 'create',
                    order_record_id INTEGER NOT NULL,
                    profile_name TEXT NOT NULL,
                    server_identity TEXT NOT NULL,
                    mwl_ae_title TEXT NOT NULL,
                    scheduled_station_ae_title TEXT NOT NULL,
                    local_dcm4chee_order_number TEXT NOT NULL,
                    accession_number TEXT NOT NULL,
                    requested_procedure_id TEXT NOT NULL,
                    scheduled_procedure_step_id TEXT NOT NULL,
                    study_instance_uid TEXT NOT NULL,
                    uid_root TEXT NOT NULL,
                    request_url TEXT NOT NULL,
                    request_payload_json TEXT NOT NULL DEFAULT '{}',
                    http_status INTEGER,
                    response_body TEXT NOT NULL DEFAULT '',
                    attempt_status TEXT NOT NULL,
                    error_type TEXT NOT NULL DEFAULT '',
                    error_text TEXT NOT NULL DEFAULT '',
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(mapping_id) REFERENCES local_dcm4chee_mwl_mappings(id) ON DELETE SET NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE CASCADE
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_mwl_mappings (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_record_id INTEGER NOT NULL UNIQUE,
                    profile_name TEXT NOT NULL,
                    server_identity TEXT NOT NULL,
                    mwl_ae_title TEXT NOT NULL,
                    scheduled_station_ae_title TEXT NOT NULL,
                    local_dcm4chee_order_number TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    issuer_of_patient_id TEXT NOT NULL,
                    accession_number TEXT NOT NULL,
                    requested_procedure_id TEXT NOT NULL,
                    scheduled_procedure_step_id TEXT NOT NULL,
                    study_instance_uid TEXT NOT NULL,
                    worklist_label TEXT NOT NULL,
                    uid_root TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    last_sync_at TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_id INTEGER,
                    last_http_status INTEGER,
                    last_response_body TEXT NOT NULL DEFAULT '',
                    last_error_type TEXT NOT NULL DEFAULT '',
                    last_error_text TEXT NOT NULL DEFAULT '',
                    last_error_payload_json TEXT NOT NULL DEFAULT '{}',
                    latest_request_payload_json TEXT NOT NULL DEFAULT '{}',
                    latest_readback_payload_json TEXT NOT NULL DEFAULT '{}',
                    verification_status TEXT NOT NULL DEFAULT 'not_verified',
                    last_verification_at TEXT NOT NULL DEFAULT '',
                    last_verification_method TEXT NOT NULL DEFAULT '',
                    last_verification_attempt_id INTEGER,
                    last_verification_query_json TEXT NOT NULL DEFAULT '{}',
                    last_verification_match_json TEXT NOT NULL DEFAULT '{}',
                    last_verification_error_type TEXT NOT NULL DEFAULT '',
                    last_verification_error_text TEXT NOT NULL DEFAULT '',
                    last_verification_error_payload_json TEXT NOT NULL DEFAULT '{}',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE CASCADE,
                    FOREIGN KEY(last_attempt_id) REFERENCES local_dcm4chee_mwl_attempts(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_result_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    result_key TEXT NOT NULL UNIQUE,
                    patient_record_id INTEGER,
                    order_record_id INTEGER,
                    mapping_id INTEGER,
                    profile_name TEXT NOT NULL DEFAULT '',
                    server_identity TEXT NOT NULL DEFAULT '',
                    source_ae_title TEXT NOT NULL DEFAULT '',
                    study_instance_uid TEXT NOT NULL DEFAULT '',
                    series_instance_uid TEXT NOT NULL DEFAULT '',
                    sop_instance_uid TEXT NOT NULL DEFAULT '',
                    accession_number TEXT NOT NULL DEFAULT '',
                    patient_id TEXT NOT NULL DEFAULT '',
                    issuer_of_patient_id TEXT NOT NULL DEFAULT '',
                    requested_procedure_id TEXT NOT NULL DEFAULT '',
                    scheduled_procedure_step_id TEXT NOT NULL DEFAULT '',
                    modality TEXT NOT NULL DEFAULT '',
                    study_datetime TEXT NOT NULL DEFAULT '',
                    series_datetime TEXT NOT NULL DEFAULT '',
                    instance_datetime TEXT NOT NULL DEFAULT '',
                    viewer_url TEXT NOT NULL DEFAULT '',
                    study_retrieve_url TEXT NOT NULL DEFAULT '',
                    series_retrieve_url TEXT NOT NULL DEFAULT '',
                    instance_retrieve_url TEXT NOT NULL DEFAULT '',
                    reconciliation_status TEXT NOT NULL DEFAULT '',
                    match_method TEXT NOT NULL DEFAULT '',
                    match_strength TEXT NOT NULL DEFAULT '',
                    query_url TEXT NOT NULL DEFAULT '',
                    query_payload_json TEXT NOT NULL DEFAULT '{}',
                    diagnostic_payload_json TEXT NOT NULL DEFAULT '{}',
                    raw_metadata_json TEXT NOT NULL DEFAULT '{}',
                    refresh_generation TEXT NOT NULL DEFAULT '',
                    first_seen_at TEXT NOT NULL,
                    last_refreshed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(order_record_id) REFERENCES local_order_records(id) ON DELETE SET NULL,
                    FOREIGN KEY(mapping_id) REFERENCES local_dcm4chee_mwl_mappings(id) ON DELETE SET NULL
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_result_refresh_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_record_id INTEGER NOT NULL,
                    refresh_generation TEXT NOT NULL,
                    started_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT '',
                    results_snapshot_json TEXT NOT NULL DEFAULT '[]',
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE,
                    UNIQUE(patient_record_id, refresh_generation)
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_patient_syncs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_record_id INTEGER NOT NULL,
                    profile_name TEXT NOT NULL,
                    server_identity TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    issuer_of_patient_id TEXT NOT NULL,
                    hl7_host TEXT NOT NULL,
                    hl7_port INTEGER NOT NULL,
                    receiving_application TEXT NOT NULL,
                    receiving_facility TEXT NOT NULL,
                    sync_status TEXT NOT NULL,
                    last_sync_at TEXT NOT NULL DEFAULT '',
                    retry_count INTEGER NOT NULL DEFAULT 0,
                    last_attempt_id INTEGER,
                    last_ack_code TEXT NOT NULL DEFAULT '',
                    last_ack_control_id TEXT NOT NULL DEFAULT '',
                    last_ack_text TEXT NOT NULL DEFAULT '',
                    last_response_payload TEXT NOT NULL DEFAULT '',
                    last_error_type TEXT NOT NULL DEFAULT '',
                    last_error_text TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE,
                    FOREIGN KEY(last_attempt_id) REFERENCES local_dcm4chee_patient_sync_attempts(id) ON DELETE SET NULL,
                    UNIQUE(patient_record_id, profile_name, server_identity)
                );
                CREATE TABLE IF NOT EXISTS local_dcm4chee_patient_sync_attempts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    patient_sync_id INTEGER,
                    operation_type TEXT NOT NULL,
                    patient_record_id INTEGER NOT NULL,
                    profile_name TEXT NOT NULL,
                    server_identity TEXT NOT NULL,
                    patient_id TEXT NOT NULL,
                    issuer_of_patient_id TEXT NOT NULL,
                    request_url TEXT NOT NULL,
                    request_payload TEXT NOT NULL DEFAULT '',
                    response_payload TEXT NOT NULL DEFAULT '',
                    ack_code TEXT NOT NULL DEFAULT '',
                    ack_control_id TEXT NOT NULL DEFAULT '',
                    ack_text TEXT NOT NULL DEFAULT '',
                    attempt_status TEXT NOT NULL,
                    error_type TEXT NOT NULL DEFAULT '',
                    error_text TEXT NOT NULL DEFAULT '',
                    attempted_at TEXT NOT NULL,
                    completed_at TEXT NOT NULL DEFAULT '',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    FOREIGN KEY(patient_sync_id) REFERENCES local_dcm4chee_patient_syncs(id) ON DELETE SET NULL,
                    FOREIGN KEY(patient_record_id) REFERENCES local_patient_records(id) ON DELETE CASCADE
                );
                CREATE UNIQUE INDEX IF NOT EXISTS idx_oie_result_control_id
                ON oie_result_records(message_control_id)
                WHERE message_control_id != '';
                CREATE INDEX IF NOT EXISTS idx_oie_managed_channel_profile
                ON oie_managed_channel_mappings(profile_id, logical_type);
                CREATE UNIQUE INDEX IF NOT EXISTS idx_fhir_record_identifier
                ON local_fhir_workflow_records(resource_type, identifier_system, identifier_value);
                CREATE INDEX IF NOT EXISTS idx_fhir_record_source
                ON local_fhir_workflow_records(local_source_type, local_source_id);
                CREATE INDEX IF NOT EXISTS idx_fhir_record_sync_status
                ON local_fhir_workflow_records(sync_status);
                CREATE INDEX IF NOT EXISTS idx_fhir_attempt_record
                ON local_fhir_sync_attempts(fhir_record_id, attempted_at);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_attempt_order
                ON local_dcm4chee_mwl_attempts(order_record_id, attempted_at);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_study_uid
                ON local_dcm4chee_mwl_mappings(study_instance_uid)
                WHERE study_instance_uid != '';
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_accession
                ON local_dcm4chee_mwl_mappings(profile_name, server_identity, accession_number)
                WHERE accession_number != '';
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_mwl_mapping_procedure
                ON local_dcm4chee_mwl_mappings(
                    profile_name, server_identity, requested_procedure_id, scheduled_procedure_step_id
                )
                WHERE requested_procedure_id != '' AND scheduled_procedure_step_id != '';
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_patient
                ON local_dcm4chee_result_records(patient_record_id, last_refreshed_at);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_mapping
                ON local_dcm4chee_result_records(mapping_id);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_generation
                ON local_dcm4chee_result_records(patient_record_id, refresh_generation)
                WHERE refresh_generation != '';
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_result_refresh_run_patient
                ON local_dcm4chee_result_refresh_runs(patient_record_id, id);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_patient
                ON local_dcm4chee_patient_syncs(patient_record_id);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_identifier
                ON local_dcm4chee_patient_syncs(profile_name, server_identity, patient_id, issuer_of_patient_id);
                CREATE INDEX IF NOT EXISTS idx_dcm4chee_patient_sync_attempt_patient
                ON local_dcm4chee_patient_sync_attempts(patient_record_id, attempted_at);
                """
            )
            self._ensure_column(connection, "lab_servers", "control_type", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "lab_servers", "backing_service", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(
                connection,
                "lab_servers",
                "supported_actions_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                connection,
                "lab_servers",
                "operation_timeout_seconds",
                "INTEGER NOT NULL DEFAULT 60",
            )
            self._ensure_column(connection, "lab_servers", "smoke_profile", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "local_dcm4chee_mwl_attempts", "mapping_id", "INTEGER")
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_attempts",
                "operation_type",
                "TEXT NOT NULL DEFAULT 'create'",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "verification_status",
                "TEXT NOT NULL DEFAULT 'not_verified'",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_at",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_method",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_attempt_id",
                "INTEGER",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_query_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_match_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_error_type",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_error_text",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_mwl_mappings",
                "last_verification_error_payload_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_result_records",
                "refresh_generation",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_result_refresh_runs",
                "completed_at",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_dcm4chee_result_refresh_runs",
                "results_snapshot_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._backfill_dcm4chee_mwl_mappings(connection)
            self._ensure_column(connection, "local_patient_records", "email", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "local_patient_records", "fhir_active", "INTEGER NOT NULL DEFAULT 1")
            self._ensure_column(connection, "local_patient_records", "address_line", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "local_patient_records", "address_city", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(connection, "local_patient_records", "address_state", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(
                connection,
                "local_patient_records",
                "address_postal_code",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(connection, "local_patient_records", "address_country", "TEXT NOT NULL DEFAULT ''")
            self._ensure_column(
                connection,
                "local_patient_records",
                "managing_organization_reference",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_patient_records",
                "managing_organization_display",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(connection, "local_gdt_order_records", "gdt_patient_context_id", "INTEGER")
            self._ensure_column(
                connection,
                "local_gdt_order_records",
                "gdt_patient_number",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_gdt_order_records",
                "patient_snapshot_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_gdt_order_records",
                "order_snapshot_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_gdt_attachment_records",
                "reference",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_gdt_attachment_records",
                "description",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_gdt_attachment_records",
                "source_file",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_gdt_attachment_records",
                "status",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._ensure_column(
                connection,
                "local_gdt_attachment_records",
                "details_json",
                "TEXT NOT NULL DEFAULT '{}'",
            )
            self._ensure_column(
                connection,
                "local_fhir_workflow_records",
                "dependency_json",
                "TEXT NOT NULL DEFAULT '[]'",
            )
            self._ensure_column(
                connection,
                "local_fhir_workflow_records",
                "sync_started_at",
                "TEXT NOT NULL DEFAULT ''",
            )
            self._seed_patient_mrn_sequence(connection)
            self._seed_lab_servers(connection)
            self._seed_oie_settings_profile(connection)

    @staticmethod
    def _seed_patient_mrn_sequence(connection: sqlite3.Connection) -> None:
        highest_existing = 0
        for row in connection.execute("SELECT mrn FROM local_patient_records"):
            match = re.fullmatch(r"MRN-(\d+)", str(row["mrn"] or ""))
            if match:
                highest_existing = max(highest_existing, int(match.group(1)))
        connection.execute(
            """
            INSERT INTO local_identifier_sequences (name, next_value)
            VALUES ('patient_mrn', ?)
            ON CONFLICT(name) DO UPDATE SET
                next_value = MAX(local_identifier_sequences.next_value, excluded.next_value)
            """,
            (highest_existing + 1,),
        )

    @staticmethod
    def _seed_oie_settings_profile(connection: sqlite3.Connection) -> None:
        timestamp = now_iso()
        connection.execute(
            """
            INSERT INTO oie_settings_profiles (
                profile_name, management_api_base_url, management_api_username,
                management_api_password, management_api_tls_verify,
                management_api_timeout_seconds, result_listener_host,
                result_listener_port, result_listener_mllp_framing,
                result_listener_auto_start, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, 0, ?, ?, ?, 1, 1, ?, ?)
            ON CONFLICT(profile_name) DO NOTHING
            """,
            (
                OIE_SETTINGS_PROFILE_NAME,
                OIE_MANAGEMENT_API_BASE_URL,
                OIE_MANAGEMENT_API_USERNAME,
                OIE_MANAGEMENT_API_PASSWORD,
                OIE_MANAGEMENT_API_TIMEOUT_SECONDS,
                OIE_RESULT_LISTENER_HOST,
                OIE_RESULT_LISTENER_PORT,
                timestamp,
                timestamp,
            ),
        )

    @staticmethod
    def _oie_required_object(payload: dict[str, Any], key: str, label: str) -> dict[str, Any]:
        value = payload.get(key)
        if not isinstance(value, dict):
            raise SimulatorValidationError(f"OIE {label} must be a JSON object.")
        return value

    @staticmethod
    def _oie_required_boolean(payload: dict[str, Any], key: str, label: str) -> bool:
        if key not in payload or not isinstance(payload[key], bool):
            raise SimulatorValidationError(f"OIE {label} must be true or false.")
        return payload[key]

    @classmethod
    def validate_oie_settings_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("OIE settings payload must be a JSON object.")

        management = cls._oie_required_object(payload, "managementApi", "managementApi")
        result_listener = cls._oie_required_object(
            payload,
            "resultListener",
            "resultListener",
        )
        managed_channels = payload.get("managedChannels")
        if not isinstance(managed_channels, list):
            raise SimulatorValidationError("OIE managedChannels must be a JSON array.")

        base_url = str(management.get("baseUrl") or "").strip()
        try:
            parsed_url = urllib.parse.urlparse(base_url)
            parsed_hostname = parsed_url.hostname
            parsed_url.port
        except ValueError as exc:
            raise SimulatorValidationError(
                "OIE Management API baseUrl must be an HTTP or HTTPS URL with a host."
            ) from exc
        if parsed_url.scheme.lower() not in {"http", "https"} or not parsed_hostname:
            raise SimulatorValidationError(
                "OIE Management API baseUrl must be an HTTP or HTTPS URL with a host."
            )
        username = str(management.get("username") or "").strip()
        if not username:
            raise SimulatorValidationError("OIE Management API username is required.")
        raw_timeout = management.get("timeoutSeconds")
        if isinstance(raw_timeout, bool):
            raise SimulatorValidationError(
                "OIE Management API timeoutSeconds must be a positive number."
            )
        try:
            timeout_seconds = float(raw_timeout)
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError(
                "OIE Management API timeoutSeconds must be a positive number."
            ) from exc
        if not math.isfinite(timeout_seconds) or timeout_seconds <= 0:
            raise SimulatorValidationError(
                "OIE Management API timeoutSeconds must be a positive number."
            )

        listener_host = str(result_listener.get("host") or "").strip()
        if not listener_host:
            raise SimulatorValidationError("OIE resultListener host is required.")
        raw_port = result_listener.get("port")
        if isinstance(raw_port, bool):
            raise SimulatorValidationError(
                "OIE resultListener port must be an integer between 1 and 65535."
            )
        try:
            listener_port = int(raw_port)
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError(
                "OIE resultListener port must be an integer between 1 and 65535."
            ) from exc
        if str(raw_port).strip() != str(listener_port) or not 1 <= listener_port <= 65535:
            raise SimulatorValidationError(
                "OIE resultListener port must be an integer between 1 and 65535."
            )

        normalized_channels: list[dict[str, str]] = []
        logical_types: set[str] = set()
        for index, mapping in enumerate(managed_channels):
            if not isinstance(mapping, dict):
                raise SimulatorValidationError(
                    f"OIE managedChannels[{index}] must be a JSON object."
                )
            logical_type = str(mapping.get("logicalType") or "").strip().lower()
            if not logical_type:
                raise SimulatorValidationError(
                    f"OIE managedChannels[{index}].logicalType is required."
                )
            channel_name = str(mapping.get("channelName") or "").strip()
            if not channel_name:
                raise SimulatorValidationError(
                    f"OIE managedChannels[{index}].channelName is required."
                )
            if logical_type in logical_types:
                raise SimulatorValidationError(
                    f"OIE managedChannels contains duplicate logicalType '{logical_type}'."
                )
            logical_types.add(logical_type)
            normalized_channels.append(
                {
                    "logical_type": logical_type,
                    "oie_channel_id": str(mapping.get("channelId") or "").strip(),
                    "channel_name": channel_name,
                    "template_version": str(mapping.get("templateVersion") or "").strip(),
                    "last_known_revision": str(mapping.get("lastKnownRevision") or "").strip(),
                }
            )

        password_provided = "password" in management
        password = ""
        if password_provided:
            raw_password = management.get("password")
            if not isinstance(raw_password, str) or not raw_password.strip():
                raise SimulatorValidationError(
                    "OIE Management API password must be a non-empty string when provided."
                )
            password = raw_password

        return {
            "management_api_base_url": base_url,
            "management_api_username": username,
            "management_api_tls_verify": int(
                cls._oie_required_boolean(management, "tlsVerify", "Management API tlsVerify")
            ),
            "management_api_timeout_seconds": timeout_seconds,
            "result_listener_host": listener_host,
            "result_listener_port": listener_port,
            "result_listener_mllp_framing": int(
                cls._oie_required_boolean(
                    result_listener,
                    "mllpFraming",
                    "resultListener mllpFraming",
                )
            ),
            "result_listener_auto_start": int(
                cls._oie_required_boolean(
                    result_listener,
                    "autoStart",
                    "resultListener autoStart",
                )
            ),
            "managed_channels": normalized_channels,
            "password_provided": password_provided,
            "management_api_password": password,
        }

    @staticmethod
    def _oie_settings_profile_dict(
        profile: sqlite3.Row,
        mappings: list[sqlite3.Row],
    ) -> dict[str, Any]:
        timeout_seconds = float(profile["management_api_timeout_seconds"])
        normalized_timeout: int | float = (
            int(timeout_seconds) if timeout_seconds.is_integer() else timeout_seconds
        )
        return {
            "profileName": profile["profile_name"],
            "managementApi": {
                "baseUrl": profile["management_api_base_url"],
                "username": profile["management_api_username"],
                "passwordConfigured": bool(profile["management_api_password"]),
                "tlsVerify": bool(profile["management_api_tls_verify"]),
                "timeoutSeconds": normalized_timeout,
            },
            "resultListener": {
                "host": profile["result_listener_host"],
                "port": profile["result_listener_port"],
                "mllpFraming": bool(profile["result_listener_mllp_framing"]),
                "autoStart": bool(profile["result_listener_auto_start"]),
            },
            "managedChannels": [
                {
                    "logicalType": mapping["logical_type"],
                    "channelId": mapping["oie_channel_id"],
                    "channelName": mapping["channel_name"],
                    "templateVersion": mapping["template_version"],
                    "lastKnownRevision": mapping["last_known_revision"],
                }
                for mapping in mappings
            ],
            "createdAt": profile["created_at"],
            "updatedAt": profile["updated_at"],
        }

    def get_oie_settings_profile(self) -> dict[str, Any]:
        return self.oie_settings_repository.get()

    def update_oie_settings_profile(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self.oie_settings_repository.update(payload)

    @staticmethod
    def _clean_patient_text(value: Any, field_name: str, required: bool = False) -> str:
        text = str(value or "").strip()
        if required and not text:
            raise SimulatorValidationError(f"Patient {field_name} is required.")
        return text

    @staticmethod
    def _normalize_patient_sex(value: Any) -> str:
        normalized = str(value or "").strip().upper()
        if normalized not in {"M", "F", "O", "U"}:
            raise SimulatorValidationError("Patient sex must be M, F, O, or U.")
        return normalized

    @staticmethod
    def _normalize_patient_dob(value: Any) -> str:
        raw = str(value or "").strip()
        digits = "".join(character for character in raw if character.isdigit())
        if len(digits) != 8:
            raise SimulatorValidationError("Patient dob must be YYYYMMDD.")
        try:
            datetime.strptime(digits, "%Y%m%d")
        except ValueError as exc:
            raise SimulatorValidationError("Patient dob must be a valid YYYYMMDD date.") from exc
        return digits

    @staticmethod
    def _patient_record_number(record_id: int) -> str:
        return f"PAT-{record_id:06d}"

    @staticmethod
    def _patient_visit_number(record_id: int) -> str:
        return f"VISIT-{record_id:06d}"

    @staticmethod
    def _next_patient_mrn(connection: sqlite3.Connection) -> str:
        while True:
            row = connection.execute(
                "SELECT next_value FROM local_identifier_sequences WHERE name = 'patient_mrn'"
            ).fetchone()
            if not row:
                DemoStore._seed_patient_mrn_sequence(connection)
                continue
            value = int(row["next_value"])
            connection.execute(
                "UPDATE local_identifier_sequences SET next_value = ? WHERE name = 'patient_mrn'",
                (value + 1,),
            )
            candidate = f"MRN-{value:06d}"
            duplicate = connection.execute(
                "SELECT 1 FROM local_patient_records WHERE mrn = ? LIMIT 1",
                (candidate,),
            ).fetchone()
            if not duplicate:
                return candidate

    @staticmethod
    def _normalize_patient_mode(payload: dict[str, Any]) -> str:
        mode = str(payload.get("mode", payload.get("protocolMode", "hl7-v2"))).strip().lower()
        aliases = {
            "hl7": "hl7-v2",
            "hl7v2": "hl7-v2",
            "hl7-v2.5.1": "hl7-v2",
            "hl7-v251": "hl7-v2",
            "fhir-r4": "fhir",
            "gdt-2.1": "gdt",
            "dicom-patient": "dicom",
        }
        normalized = aliases.get(mode, mode)
        if normalized not in PATIENT_MODES:
            raise SimulatorValidationError("Patient mode must be HL7 v2, FHIR, GDT, or DICOM.")
        return normalized

    @staticmethod
    def _normalize_patient_active(value: Any) -> bool:
        if isinstance(value, bool):
            return value
        normalized = str(value if value is not None else "true").strip().lower()
        if normalized in {"", "1", "true", "yes", "y", "on", "active"}:
            return True
        if normalized in {"0", "false", "no", "n", "off", "inactive"}:
            return False
        raise SimulatorValidationError("Patient active must be true or false.")

    def _validate_patient_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("Patient payload must be a JSON object.")
        return {
            "mode": self._normalize_patient_mode(payload),
            "mrn": self._clean_patient_text(payload.get("mrn"), "mrn"),
            "first_name": self._clean_patient_text(payload.get("firstName"), "firstName", required=True),
            "last_name": self._clean_patient_text(payload.get("lastName"), "lastName", required=True),
            "middle_name": self._clean_patient_text(payload.get("middleName"), "middleName"),
            "dob": self._normalize_patient_dob(payload.get("dob")),
            "sex": self._normalize_patient_sex(payload.get("sex")),
            "address": self._clean_patient_text(payload.get("address"), "address"),
            "phone": self._clean_patient_text(payload.get("phone"), "phone"),
            "email": self._clean_patient_text(payload.get("email"), "email"),
            "fhir_active": self._normalize_patient_active(payload.get("active", payload.get("fhirActive", True))),
            "address_line": self._clean_patient_text(payload.get("addressLine"), "addressLine"),
            "address_city": self._clean_patient_text(payload.get("addressCity"), "addressCity"),
            "address_state": self._clean_patient_text(payload.get("addressState"), "addressState"),
            "address_postal_code": self._clean_patient_text(payload.get("addressPostalCode"), "addressPostalCode"),
            "address_country": self._clean_patient_text(payload.get("addressCountry"), "addressCountry"),
            "managing_organization_reference": self._clean_patient_text(
                payload.get("managingOrganizationReference"),
                "managingOrganizationReference",
            ),
            "managing_organization_display": self._clean_patient_text(
                payload.get("managingOrganizationDisplay"),
                "managingOrganizationDisplay",
            ),
            "visit_number": self._clean_patient_text(payload.get("visitNumber"), "visitNumber"),
            "patient_class": self._clean_patient_text(
                payload.get("patientClass", PATIENT_CLASS_DEFAULT),
                "patientClass",
            )
            or PATIENT_CLASS_DEFAULT,
            "assigned_location": self._clean_patient_text(payload.get("assignedLocation"), "assignedLocation"),
            "attending_provider": self._clean_patient_text(payload.get("attendingProvider"), "attendingProvider"),
            "account_number": self._clean_patient_text(payload.get("accountNumber"), "accountNumber"),
        }

    @staticmethod
    def _build_patient_a04_payload(
        values: dict[str, str], *, record_id: int, timestamp: str
    ) -> tuple[str, str]:
        visit_number = values["visit_number"] or DemoStore._patient_visit_number(record_id)
        patient_name = "^".join(
            _hl7_escape(part)
            for part in (values["last_name"], values["first_name"], values["middle_name"])
        ).rstrip("^")
        control_id = f"A04{timestamp}{record_id:06d}"
        segments = [
            f"MSH|^~\\&|HEALTHCARE_LAB|LAB_DEMO|OIE|ADT|{timestamp}||ADT^A04^ADT_A01|{control_id}|P|{HL7_V2_MSH_SUFFIX}",
            f"EVN|A04|{timestamp}",
            (
                "PID|1||"
                f"{_hl7_escape(values['mrn'])}^^^HEALTHCARE_LAB^MR||"
                f"{patient_name}||{_hl7_escape(values['dob'])}|{_hl7_escape(values['sex'])}|||"
                f"{_hl7_escape_composite(values['address'])}||{_hl7_escape(values['phone'])}|||||"
                f"{_hl7_escape(values['account_number'])}"
            ),
            (
                "PV1|1|"
                f"{_hl7_escape(values['patient_class'])}|{_hl7_escape_composite(values['assigned_location'])}||||"
                f"{_hl7_escape_composite(values['attending_provider'])}||||||||||||"
                f"{_hl7_escape(visit_number)}"
            ),
        ]
        return "\r".join(segments), visit_number

    @staticmethod
    def _patient_fhir_gender(sex: str) -> str:
        return {"M": "male", "F": "female", "O": "other", "U": "unknown"}[sex]

    @staticmethod
    def _patient_fhir_birth_date(dob: str) -> str:
        return f"{dob[:4]}-{dob[4:6]}-{dob[6:]}"

    @staticmethod
    def _build_patient_fhir_payload(values: dict[str, str], *, record_id: int) -> tuple[str, str]:
        visit_number = values["visit_number"] or DemoStore._patient_visit_number(record_id)
        patient_name = " ".join(
            part for part in (values["first_name"], values["middle_name"], values["last_name"]) if part
        )
        telecom = []
        if values["phone"]:
            telecom.append({"system": "phone", "value": values["phone"]})
        if values["email"]:
            telecom.append({"system": "email", "value": values["email"]})
        address = {}
        if values["address"]:
            address["text"] = values["address"]
        if values["address_line"]:
            address["line"] = [values["address_line"]]
        if values["address_city"]:
            address["city"] = values["address_city"]
        if values["address_state"]:
            address["state"] = values["address_state"]
        if values["address_postal_code"]:
            address["postalCode"] = values["address_postal_code"]
        if values["address_country"]:
            address["country"] = values["address_country"]
        resource = {
            "resourceType": "Patient",
            "id": DemoStore._patient_record_number(record_id),
            "active": bool(values["fhir_active"]),
            "meta": {
                "profile": [
                    "https://twcore.mohw.gov.tw/ig/twcore/StructureDefinition/Patient-twcore"
                ],
            },
            "identifier": [
                {
                    "system": "urn:healthcare-lab:mrn",
                    "value": values["mrn"],
                }
            ],
            "name": [
                {
                    "use": "official",
                    "text": patient_name,
                    "family": values["last_name"],
                    "given": [
                        part for part in (values["first_name"], values["middle_name"]) if part
                    ],
                }
            ],
            "gender": DemoStore._patient_fhir_gender(values["sex"]),
            "birthDate": DemoStore._patient_fhir_birth_date(values["dob"]),
            "telecom": telecom,
            "address": [address] if address else [],
            "extension": [
                {
                    "url": "urn:healthcare-lab:visit-number",
                    "valueString": visit_number,
                }
            ],
        }
        managing_organization = {}
        if values["managing_organization_reference"]:
            managing_organization["reference"] = values["managing_organization_reference"]
        if values["managing_organization_display"]:
            managing_organization["display"] = values["managing_organization_display"]
        if managing_organization:
            resource["managingOrganization"] = managing_organization
        return json.dumps(resource, indent=2), visit_number

    @staticmethod
    def _build_patient_gdt_payload(
        values: dict[str, str], *, record_id: int, timestamp: str
    ) -> tuple[str, str]:
        visit_number = values["visit_number"] or DemoStore._patient_visit_number(record_id)
        birth_date = f"{values['dob'][6:]}{values['dob'][4:6]}{values['dob'][:4]}"
        records: list[tuple[str, Any]] = [
            ("8315", "LABGDT"),
            ("8316", "HCLAB"),
            ("3000", values["mrn"]),
            ("3101", values["last_name"]),
            ("3102", values["first_name"]),
            ("3103", birth_date),
        ]
        sex_code = GDT_PATIENT_SEX_CODES.get(values["sex"])
        if sex_code:
            records.append(("3110", sex_code))
        return render_gdt_message(records, set_type="6301"), visit_number

    @staticmethod
    def _build_patient_dicom_payload(values: dict[str, str], *, record_id: int) -> tuple[str, str]:
        visit_number = values["visit_number"] or DemoStore._patient_visit_number(record_id)
        patient_name = "^".join(
            part for part in (values["last_name"], values["first_name"], values["middle_name"]) if part
        )
        dataset = {
            "(0010,0010) PatientName": patient_name,
            "(0010,0020) PatientID": values["mrn"],
            "(0010,0030) PatientBirthDate": values["dob"],
            "(0010,0040) PatientSex": values["sex"],
            "(0010,2154) PatientTelephoneNumbers": values["phone"],
            "(0038,0010) AdmissionID": visit_number,
            "(0038,0500) PatientState": values["patient_class"],
        }
        if values["address"]:
            dataset["(0010,1040) PatientAddress"] = values["address"]
        return json.dumps(dataset, indent=2), visit_number

    @staticmethod
    def _build_patient_payload(
        values: dict[str, str], *, record_id: int, timestamp: str, hl7_time: str
    ) -> tuple[str, str]:
        if values["mode"] == "fhir":
            return DemoStore._build_patient_fhir_payload(values, record_id=record_id)
        if values["mode"] == "gdt":
            return DemoStore._build_patient_gdt_payload(values, record_id=record_id, timestamp=timestamp)
        if values["mode"] == "dicom":
            return DemoStore._build_patient_dicom_payload(values, record_id=record_id)
        return DemoStore._build_patient_a04_payload(values, record_id=record_id, timestamp=hl7_time)

    def create_patient_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_patient_payload(payload)
        timestamp = now_iso()
        hl7_time = hl7_timestamp()
        with self.lock, self.connect() as connection:
            values["mrn"] = values["mrn"] or self._next_patient_mrn(connection)
            duplicate = connection.execute(
                "SELECT 1 FROM local_patient_records WHERE mrn = ? LIMIT 1",
                (values["mrn"],),
            ).fetchone()
            if duplicate:
                raise SimulatorValidationError(f"Patient MRN {values['mrn']} already exists.")
            cursor = connection.execute(
                """
                INSERT INTO local_patient_records (
                    local_patient_number, protocol_version, message_type, mrn,
                    first_name, last_name, middle_name, dob, sex, address, phone,
                    email, fhir_active, address_line, address_city, address_state,
                    address_postal_code, address_country, managing_organization_reference,
                    managing_organization_display,
                    visit_number, patient_class, assigned_location, attending_provider,
                    account_number, validation_status, validation_messages_json,
                    payload_hl7, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    PATIENT_MODES[values["mode"]]["protocol"],
                    PATIENT_MODES[values["mode"]]["message_type"],
                    values["mrn"],
                    values["first_name"],
                    values["last_name"],
                    values["middle_name"],
                    values["dob"],
                    values["sex"],
                    values["address"],
                    values["phone"],
                    values["email"],
                    int(values["fhir_active"]),
                    values["address_line"],
                    values["address_city"],
                    values["address_state"],
                    values["address_postal_code"],
                    values["address_country"],
                    values["managing_organization_reference"],
                    values["managing_organization_display"],
                    values["visit_number"],
                    values["patient_class"],
                    values["assigned_location"],
                    values["attending_provider"],
                    values["account_number"],
                    "valid",
                    "[]",
                    "",
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_patient_number = self._patient_record_number(record_id)
            payload_hl7, visit_number = self._build_patient_payload(
                values,
                record_id=record_id,
                timestamp=timestamp,
                hl7_time=hl7_time,
            )
            connection.execute(
                """
                UPDATE local_patient_records
                SET local_patient_number = ?, visit_number = ?, payload_hl7 = ?, updated_at = ?
                WHERE id = ?
                """,
                (local_patient_number, visit_number, payload_hl7, timestamp, record_id),
            )
        return self.get_patient_record(record_id)

    def list_patient_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        with self.connect() as connection:
            if protocol_version:
                rows = connection.execute(
                    """
                    SELECT * FROM local_patient_records
                    WHERE protocol_version = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (protocol_version,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_patient_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
        return self._patient_record_dicts_with_fhir(rows)

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._patient_record_dicts_with_fhir([row])[0]

    def create_patient_fhir_workflow_record(self, patient_record: dict[str, Any]) -> dict[str, Any]:
        if patient_record.get("protocolVersion") != "FHIR R4":
            raise SimulatorValidationError("Patient record is not FHIR mode.")
        resource = self._json_value(patient_record.get("payload"), {})
        return self.create_fhir_workflow_record(
            {
                "localSourceType": "local_patient_records",
                "localSourceId": str(patient_record["id"]),
                "resourceType": "Patient",
                "resource": resource,
            }
        )

    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]:
        return self.list_patient_records(PATIENT_MODES["hl7-v2"]["protocol"])

    @staticmethod
    def _order_record_number(record_id: int) -> str:
        return f"ORD-{record_id:06d}"

    @staticmethod
    def _order_visit_id(record_id: int) -> str:
        return f"VISIT-ORD-{record_id:06d}"

    @staticmethod
    def _order_account_number(record_id: int) -> str:
        return f"ACC-ORD-{record_id:06d}"

    @staticmethod
    def _dcm4chee_local_order_number(record_id: int) -> str:
        return f"LAB-ORD-{record_id:06d}"

    @staticmethod
    def _dcm4chee_accession_number(record_id: int) -> str:
        return f"ACC-{record_id:06d}"

    @staticmethod
    def _dcm4chee_requested_procedure_id(record_id: int) -> str:
        return f"RP-{record_id:06d}"

    @staticmethod
    def _dcm4chee_scheduled_procedure_step_id(record_id: int) -> str:
        return f"SPS-{record_id:06d}"

    @staticmethod
    def normalize_dcm4chee_uid_root(value: Any) -> str:
        root = str(value or DCM4CHEE_DEFAULT_UID_ROOT).strip().strip(".")
        if not root:
            root = DCM4CHEE_DEFAULT_UID_ROOT
        if not re.match(r"^[0-9]+(?:\.[0-9]+)*$", root):
            raise SimulatorValidationError("dcm4chee UID root must contain only digits and dots.")
        if any(part != "0" and part.startswith("0") for part in root.split(".")):
            raise SimulatorValidationError("dcm4chee UID root components must not have leading zeroes.")
        if len(root) > 54:
            raise SimulatorValidationError("dcm4chee UID root is too long for generated Study Instance UIDs.")
        return root

    @classmethod
    def dcm4chee_study_instance_uid(cls, uid_root: Any, *, order_record_id: int, timestamp: str = "") -> str:
        root = cls.normalize_dcm4chee_uid_root(uid_root)
        digits = "".join(character for character in str(timestamp or hl7_timestamp()) if character.isdigit())
        suffix = f"{digits[:14] or hl7_timestamp()}.{int(order_record_id)}"
        uid = f"{root}.{suffix}"
        if len(uid) > 64:
            suffix = f"{digits[:8] or datetime.now().strftime('%Y%m%d')}.{int(order_record_id)}"
            uid = f"{root}.{suffix}"
        if len(uid) > 64:
            raise SimulatorValidationError("Generated Study Instance UID exceeds 64 characters.")
        return uid

    @staticmethod
    def _dicom_json_element(vr: str, value: Any = None) -> dict[str, Any]:
        element: dict[str, Any] = {"vr": vr}
        if value is not None:
            element["Value"] = value if isinstance(value, list) else [value]
        return element

    @classmethod
    def build_dcm4chee_mwl_payload(
        cls,
        order: dict[str, Any],
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
    ) -> dict[str, Any]:
        order_id = int(order["id"])
        patient = order.get("patient") or {}
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        scheduled_station_ae_title = str(mwl.get("defaultScheduledStationAETitle") or "").strip()
        if not scheduled_station_ae_title:
            raise SimulatorValidationError("dcm4chee default Scheduled Station AE Title is required.")
        patient_name = "^".join(
            str(patient.get(key) or "").strip()
            for key in ("lastName", "firstName", "middleName")
        ).rstrip("^")
        if not patient_name:
            raise SimulatorValidationError("dcm4chee MWL Patient's Name is required.")
        patient_id = str(patient.get("mrn") or "").strip()
        if not patient_id:
            raise SimulatorValidationError("dcm4chee MWL Patient ID is required.")
        issuer = str(profile.get("profileName") or "HEALTHCARE_LAB").strip()
        accession_number = cls._dcm4chee_accession_number(order_id)
        requested_procedure_id = cls._dcm4chee_requested_procedure_id(order_id)
        sps_id = cls._dcm4chee_scheduled_procedure_step_id(order_id)
        study_uid = cls.dcm4chee_study_instance_uid(
            uid_root,
            order_record_id=order_id,
            timestamp=str(order.get("requestedAt") or ""),
        )
        worklist_label = str(order.get("orderCodeText") or order.get("orderCode") or ORDER_DEFAULT_TEXT).strip()
        requested_at = "".join(character for character in str(order.get("requestedAt") or "") if character.isdigit())
        scheduled_date = requested_at[:8] if len(requested_at) >= 8 else datetime.now().strftime("%Y%m%d")
        scheduled_time = requested_at[8:14] if len(requested_at) >= 14 else ""
        sps_item = {
            "00400001": cls._dicom_json_element("AE", scheduled_station_ae_title),
            "00400009": cls._dicom_json_element("SH", sps_id),
            "00400020": cls._dicom_json_element("CS", "SCHEDULED"),
            "00400007": cls._dicom_json_element("LO", worklist_label),
            "00400002": cls._dicom_json_element("DA", scheduled_date),
        }
        if scheduled_time:
            sps_item["00400003"] = cls._dicom_json_element("TM", scheduled_time)
        return {
            "00100010": cls._dicom_json_element("PN", {"Alphabetic": patient_name}),
            "00100020": cls._dicom_json_element("LO", patient_id),
            "00100021": cls._dicom_json_element("LO", issuer),
            "00100030": cls._dicom_json_element("DA", str(patient.get("dob") or "").strip()),
            "00100040": cls._dicom_json_element("CS", str(patient.get("sex") or "").strip() or "U"),
            "00080050": cls._dicom_json_element("SH", accession_number),
            "0020000D": cls._dicom_json_element("UI", study_uid),
            "00401001": cls._dicom_json_element("SH", requested_procedure_id),
            "00741202": cls._dicom_json_element("LO", worklist_label),
            "00400100": {"vr": "SQ", "Value": [sps_item]},
        }

    @classmethod
    def dcm4chee_patient_identifiers(
        cls,
        patient: dict[str, Any],
        profile: dict[str, Any],
    ) -> dict[str, str]:
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
        summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
        patient_fields = patient.get("patient") if isinstance(patient.get("patient"), dict) else {}
        patient_id = str(summary.get("mrn") or patient_fields.get("mrn") or patient.get("mrn") or "").strip()
        issuer = str(hl7.get("patientAssigningAuthority") or profile.get("profileName") or "HEALTHCARE_LAB").strip()
        return {
            "profile_name": str(profile.get("profileName") or "").strip(),
            "server_identity": str(dimse.get("calledAETitle") or "").strip(),
            "patient_id": patient_id,
            "issuer_of_patient_id": issuer,
            "hl7_host": str(hl7.get("host") or "").strip(),
            "hl7_port": str(hl7.get("port") or "").strip(),
            "receiving_application": str(hl7.get("receivingApplication") or "").strip(),
            "receiving_facility": str(hl7.get("receivingFacility") or "").strip(),
        }

    @classmethod
    def build_dcm4chee_patient_adt_payload(
        cls,
        patient: dict[str, Any],
        profile: dict[str, Any],
        *,
        event_type: str = "A04",
        timestamp: str = "",
    ) -> str:
        patient_fields = patient.get("patient") if isinstance(patient.get("patient"), dict) else {}
        summary = patient.get("summary") if isinstance(patient.get("summary"), dict) else {}
        hl7 = profile.get("hl7") if isinstance(profile.get("hl7"), dict) else {}
        identifiers = cls.dcm4chee_patient_identifiers(patient, profile)
        patient_name = "^".join(
            _hl7_escape(str(patient_fields.get(key) or "").strip())
            for key in ("lastName", "firstName", "middleName")
        ).rstrip("^")
        if not patient_name:
            raise SimulatorValidationError("dcm4chee Patient name is required.")
        if not identifiers["patient_id"]:
            raise SimulatorValidationError("dcm4chee Patient ID is required.")
        if not identifiers["issuer_of_patient_id"]:
            raise SimulatorValidationError("dcm4chee Patient issuer is required.")
        message_time = timestamp or hl7_timestamp()
        normalized_event = str(event_type or "A04").strip().upper()
        if not normalized_event.startswith("A"):
            normalized_event = f"A{normalized_event}"
        message_type = f"ADT^{normalized_event}"
        message_structure = "ADT_A01"
        control_id = f"DCMADT{message_time}{int(patient['id']):06d}"
        visit_number = str(patient.get("visitNumber") or summary.get("visitNumber") or "").strip()
        patient_class = str(patient.get("patientClass") or "O").strip() or "O"
        assigned_location = str(patient.get("assignedLocation") or "").strip()
        attending_provider = str(patient.get("attendingProvider") or "").strip()
        account_number = str(patient.get("accountNumber") or "").strip()
        segments = [
            (
                "MSH|^~\\&|"
                f"{_hl7_escape(str(hl7.get('sendingApplication') or 'HEALTHCARE_LAB'))}|"
                f"{_hl7_escape(str(hl7.get('sendingFacility') or 'LAB_APP'))}|"
                f"{_hl7_escape(str(hl7.get('receivingApplication') or 'DCM4CHEE'))}|"
                f"{_hl7_escape(str(hl7.get('receivingFacility') or 'DCM4CHEE'))}|"
                f"{message_time}||{message_type}^{message_structure}|{control_id}|P|{HL7_V2_MSH_SUFFIX}"
            ),
            f"EVN|{normalized_event}|{message_time}",
            (
                "PID|1||"
                f"{_hl7_escape(identifiers['patient_id'])}^^^{_hl7_escape(identifiers['issuer_of_patient_id'])}^MR||"
                f"{patient_name}||{_hl7_escape(str(patient_fields.get('dob') or summary.get('dob') or ''))}|"
                f"{_hl7_escape(str(patient_fields.get('sex') or summary.get('sex') or ''))}|||"
                f"{_hl7_escape_composite(str(patient_fields.get('address') or ''))}||"
                f"{_hl7_escape(str(patient_fields.get('phone') or ''))}|||||"
                f"{_hl7_escape(account_number)}"
            ),
            (
                "PV1|1|"
                f"{_hl7_escape(patient_class)}|{_hl7_escape_composite(assigned_location)}||||"
                f"{_hl7_escape_composite(attending_provider)}||||||||||||{_hl7_escape(visit_number)}"
            ),
        ]
        return "\r".join(segments)

    def upsert_dcm4chee_patient_sync(
        self,
        patient_record_id: int,
        profile: dict[str, Any],
        *,
        sync_status: str = DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
        increment_retry: bool = False,
    ) -> dict[str, Any]:
        patient = self.get_patient_record(patient_record_id)
        identifiers = self.dcm4chee_patient_identifiers(patient, profile)
        if not identifiers["patient_id"]:
            raise SimulatorValidationError("dcm4chee Patient ID is required.")
        if not identifiers["issuer_of_patient_id"]:
            raise SimulatorValidationError("dcm4chee Patient issuer is required.")
        now = now_iso()
        with self.lock, self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM local_dcm4chee_patient_syncs
                WHERE patient_record_id = ? AND profile_name = ? AND server_identity = ?
                """,
                (int(patient_record_id), identifiers["profile_name"], identifiers["server_identity"]),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_patient_syncs
                    SET patient_id = ?, issuer_of_patient_id = ?, hl7_host = ?, hl7_port = ?,
                        receiving_application = ?, receiving_facility = ?, sync_status = ?,
                        retry_count = retry_count + ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["hl7_host"],
                        int(identifiers["hl7_port"] or 0),
                        identifiers["receiving_application"],
                        identifiers["receiving_facility"],
                        sync_status,
                        1 if increment_retry else 0,
                        now,
                        existing["id"],
                    ),
                )
                sync_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_patient_syncs (
                        patient_record_id, profile_name, server_identity, patient_id,
                        issuer_of_patient_id, hl7_host, hl7_port, receiving_application,
                        receiving_facility, sync_status, retry_count, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(patient_record_id),
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["hl7_host"],
                        int(identifiers["hl7_port"] or 0),
                        identifiers["receiving_application"],
                        identifiers["receiving_facility"],
                        sync_status,
                        1 if increment_retry else 0,
                        now,
                        now,
                    ),
                )
                sync_id = int(cursor.lastrowid)
        return self.get_dcm4chee_patient_sync(sync_id)

    def get_dcm4chee_patient_sync(self, sync_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_patient_syncs WHERE id = ?",
                (int(sync_id),),
            ).fetchone()
            if not row:
                raise KeyError(sync_id)
        return self._dcm4chee_patient_sync_dict(row)

    def get_dcm4chee_patient_sync_for_patient(
        self,
        patient_record_id: int,
        profile: dict[str, Any] | None = None,
    ) -> dict[str, Any] | None:
        with self.connect() as connection:
            if profile:
                identifiers = self.dcm4chee_patient_identifiers(self.get_patient_record(patient_record_id), profile)
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_patient_syncs
                    WHERE patient_record_id = ? AND profile_name = ? AND server_identity = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (int(patient_record_id), identifiers["profile_name"], identifiers["server_identity"]),
                ).fetchone()
            else:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_patient_syncs
                    WHERE patient_record_id = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (int(patient_record_id),),
                ).fetchone()
        return self._dcm4chee_patient_sync_dict(row) if row else None

    def create_dcm4chee_patient_sync_attempt(
        self,
        patient_record_id: int,
        profile: dict[str, Any],
        *,
        operation_type: str = DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
        request_url: str = "",
        request_payload: str = "",
        attempt_status: str = DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        response_payload: str = "",
        ack: dict[str, str] | None = None,
        patient_sync_id: int | None = None,
    ) -> dict[str, Any]:
        patient = self.get_patient_record(patient_record_id)
        identifiers = self.dcm4chee_patient_identifiers(patient, profile)
        if patient_sync_id is None:
            sync = self.upsert_dcm4chee_patient_sync(
                int(patient_record_id),
                profile,
                sync_status=DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
            )
            patient_sync_id = int(sync["id"])
        ack = ack or {}
        now = now_iso()
        with self.lock, self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_patient_sync_attempts (
                    patient_sync_id, operation_type, patient_record_id, profile_name,
                    server_identity, patient_id, issuer_of_patient_id, request_url,
                    request_payload, response_payload, ack_code, ack_control_id,
                    ack_text, attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    patient_sync_id,
                    operation_type,
                    int(patient_record_id),
                    identifiers["profile_name"],
                    identifiers["server_identity"],
                    identifiers["patient_id"],
                    identifiers["issuer_of_patient_id"],
                    request_url,
                    request_payload,
                    response_payload,
                    str(ack.get("code") or ""),
                    str(ack.get("controlId") or ""),
                    str(ack.get("text") or ""),
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now if attempt_status != DCM4CHEE_PATIENT_SYNC_STATUS_PENDING else "",
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_dcm4chee_patient_sync_attempt(attempt_id)

    def update_dcm4chee_patient_sync_attempt_result(
        self,
        attempt_id: int,
        *,
        attempt_status: str,
        response_payload: str = "",
        ack: dict[str, str] | None = None,
        error_type: str = "",
        error_text: str = "",
    ) -> dict[str, Any]:
        ack = ack or {}
        now = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_patient_sync_attempts WHERE id = ?",
                (int(attempt_id),),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
            connection.execute(
                """
                UPDATE local_dcm4chee_patient_sync_attempts
                SET response_payload = ?, ack_code = ?, ack_control_id = ?, ack_text = ?,
                    attempt_status = ?, error_type = ?, error_text = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    response_payload,
                    str(ack.get("code") or ""),
                    str(ack.get("controlId") or ""),
                    str(ack.get("text") or ""),
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now,
                    int(attempt_id),
                ),
            )
        return self.get_dcm4chee_patient_sync_attempt(attempt_id)

    def update_dcm4chee_patient_sync_from_attempt(
        self,
        patient_sync_id: int,
        attempt: dict[str, Any],
        *,
        sync_status: str,
    ) -> dict[str, Any]:
        now = now_iso()
        with self.lock, self.connect() as connection:
            connection.execute(
                """
                UPDATE local_dcm4chee_patient_syncs
                SET sync_status = ?, last_sync_at = ?, last_attempt_id = ?,
                    last_ack_code = ?, last_ack_control_id = ?, last_ack_text = ?,
                    last_response_payload = ?, last_error_type = ?, last_error_text = ?,
                    updated_at = ?
                WHERE id = ?
                """,
                (
                    sync_status,
                    now if sync_status == DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED else "",
                    int(attempt["id"]),
                    str((attempt.get("ack") or {}).get("code") or ""),
                    str((attempt.get("ack") or {}).get("controlId") or ""),
                    str((attempt.get("ack") or {}).get("text") or ""),
                    str(attempt.get("responsePayload") or ""),
                    str(attempt.get("errorType") or ""),
                    str(attempt.get("error") or ""),
                    now,
                    int(patient_sync_id),
                ),
            )
        return self.get_dcm4chee_patient_sync(int(patient_sync_id))

    def get_dcm4chee_patient_sync_attempt(self, attempt_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_patient_sync_attempts WHERE id = ?",
                (int(attempt_id),),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
        return self._dcm4chee_patient_sync_attempt_dict(row)

    def list_dcm4chee_patient_sync_attempts(self, patient_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if patient_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_patient_sync_attempts
                    ORDER BY attempted_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_patient_sync_attempts
                    WHERE patient_record_id = ?
                    ORDER BY attempted_at DESC, id DESC
                    """,
                    (int(patient_record_id),),
                ).fetchall()
        return [self._dcm4chee_patient_sync_attempt_dict(row) for row in rows]

    @staticmethod
    def _clean_order_text(value: Any, field_name: str, required: bool = False) -> str:
        text = str(value or "").strip()
        if required and not text:
            raise SimulatorValidationError(f"Order {field_name} is required.")
        return text

    @staticmethod
    def _normalize_order_priority(value: Any) -> str:
        normalized = str(value or "R").strip().upper() or "R"
        if normalized not in ORDER_ALLOWED_PRIORITIES:
            raise SimulatorValidationError(
                f"Order priority must be one of: {', '.join(ORDER_ALLOWED_PRIORITIES)}."
            )
        return normalized

    @staticmethod
    def _normalize_requested_at(value: Any) -> str:
        raw = str(value or "").strip()
        if not raw:
            return hl7_timestamp()
        digits = "".join(character for character in raw if character.isdigit())
        if len(digits) not in {8, 12, 14}:
            raise SimulatorValidationError(
                "Order requested time must be YYYYMMDD, YYYYMMDDHHMM, or YYYYMMDDHHMMSS."
            )
        try:
            datetime.strptime(digits[:8], "%Y%m%d")
            if len(digits) >= 12:
                datetime.strptime(digits[:12], "%Y%m%d%H%M")
            if len(digits) == 14:
                datetime.strptime(digits, "%Y%m%d%H%M%S")
        except ValueError as exc:
            raise SimulatorValidationError("Order requested time is not a valid HL7 timestamp.") from exc
        return digits

    def _validate_order_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("Order payload must be a JSON object.")
        try:
            patient_record_id = int(payload.get("patientRecordId"))
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError("Order patientRecordId is required.") from exc
        return {
            "patient_record_id": patient_record_id,
            "priority": self._normalize_order_priority(payload.get("priority")),
            "requested_at": self._normalize_requested_at(payload.get("requestedAt")),
            "ordering_provider": self._clean_order_text(
                payload.get("orderingProvider", ORDER_DEFAULT_PROVIDER),
                "orderingProvider",
            )
            or ORDER_DEFAULT_PROVIDER,
            "clinical_indication": self._clean_order_text(payload.get("clinicalIndication"), "clinicalIndication"),
            "order_code": self._clean_order_text(payload.get("orderCode", ORDER_DEFAULT_CODE), "orderCode") or ORDER_DEFAULT_CODE,
            "order_code_text": self._clean_order_text(
                payload.get("orderCodeText", ORDER_DEFAULT_TEXT),
                "orderCodeText",
            )
            or ORDER_DEFAULT_TEXT,
            "alternate_code": self._clean_order_text(payload.get("alternateCode", ORDER_DEFAULT_ALT_CODE), "alternateCode")
            or ORDER_DEFAULT_ALT_CODE,
            "alternate_code_text": self._clean_order_text(
                payload.get("alternateCodeText", ORDER_DEFAULT_ALT_TEXT),
                "alternateCodeText",
            )
            or ORDER_DEFAULT_ALT_TEXT,
            "alternate_code_system": self._clean_order_text(
                payload.get("alternateCodeSystem", ORDER_DEFAULT_ALT_SYSTEM),
                "alternateCodeSystem",
            )
            or ORDER_DEFAULT_ALT_SYSTEM,
        }

    @staticmethod
    def _fhir_order_values(payload: dict[str, Any]) -> dict[str, Any]:
        fhir = payload.get("fhir") if isinstance(payload.get("fhir"), dict) else payload
        return fhir if isinstance(fhir, dict) else {}

    @staticmethod
    def _clean_fhir_order_text(value: Any) -> str:
        return str(value or "").strip()

    @staticmethod
    def _fhir_order_list(value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list | tuple):
            raw_items = value
        else:
            raw_items = str(value).replace(",", "\n").splitlines()
        return [str(item or "").strip() for item in raw_items if str(item or "").strip()]

    @staticmethod
    def _fhir_reference_item(value: str, field_name: str) -> dict[str, str]:
        text = value.strip()
        if not text:
            return {}
        if "/" not in text:
            raise SimulatorValidationError(f"FHIR Order {field_name} must be a FHIR reference like Resource/id.")
        return {"reference": text}

    @classmethod
    def _fhir_reference_list(cls, value: Any, field_name: str) -> list[dict[str, str]]:
        return [
            reference
            for reference in (
                cls._fhir_reference_item(item, field_name)
                for item in cls._fhir_order_list(value)
            )
            if reference
        ]

    @classmethod
    def _fhir_codeable_concept(
        cls,
        *,
        text: Any = "",
        code: Any = "",
        system: Any = "",
        display: Any = "",
    ) -> dict[str, Any]:
        concept: dict[str, Any] = {}
        text_value = cls._clean_fhir_order_text(text)
        code_value = cls._clean_fhir_order_text(code)
        system_value = cls._clean_fhir_order_text(system)
        display_value = cls._clean_fhir_order_text(display)
        if text_value:
            concept["text"] = text_value
        if code_value or system_value or display_value:
            coding: dict[str, str] = {}
            if system_value:
                coding["system"] = system_value
            if code_value:
                coding["code"] = code_value
            if display_value:
                coding["display"] = display_value
            concept["coding"] = [coding]
            if not concept.get("text"):
                concept["text"] = display_value or code_value
        return concept

    @staticmethod
    def _fhir_order_datetime(value: Any, fallback: str = "") -> str:
        text = str(value or "").strip()
        if not text:
            return fallback
        if "T" in text:
            match = re.match(
                r"^(\d{4}-\d{2}-\d{2})T(\d{2}):(\d{2})(?::(\d{2})(\.\d+)?)?(Z|[+-]\d{2}:?\d{2})?$",
                text,
            )
            if not match:
                return text
            date_part, hour, minute, second, fraction, offset = match.groups()
            normalized = f"{date_part}T{hour}:{minute}:{second or '00'}{fraction or ''}"
            if offset:
                if offset != "Z" and ":" not in offset:
                    offset = f"{offset[:3]}:{offset[3:]}"
                return f"{normalized}{offset}"
            local_offset = datetime.now().astimezone().strftime("%z")
            return f"{normalized}{local_offset[:3]}:{local_offset[3:]}"
        digits = "".join(character for character in text if character.isdigit())
        if len(digits) == 8:
            return f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}"
        if len(digits) >= 12:
            base = f"{digits[:4]}-{digits[4:6]}-{digits[6:8]}T{digits[8:10]}:{digits[10:12]}"
            if len(digits) >= 14:
                base = f"{base}:{digits[12:14]}"
            else:
                base = f"{base}:00"
            local_offset = datetime.now().astimezone().strftime("%z")
            return f"{base}{local_offset[:3]}:{local_offset[3:]}"
        return text

    @staticmethod
    def _fhir_order_storage_timestamp(value: Any) -> str:
        text = str(value or "").strip()
        digits = "".join(character for character in text if character.isdigit())
        if len(digits) >= 14:
            return digits[:14]
        if len(digits) >= 12:
            return digits[:12]
        if len(digits) >= 8:
            return digits[:8]
        return hl7_timestamp()

    @staticmethod
    def _fhir_order_storage_priority(value: Any) -> str:
        normalized = str(value or FHIR_ORDER_DEFAULT_PRIORITY).strip().lower()
        return {
            "routine": "R",
            "stat": "S",
            "asap": "A",
            "urgent": "A",
        }.get(normalized, "R")

    @classmethod
    def _validate_fhir_order_payload(cls, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("FHIR Order payload must be a JSON object.")
        try:
            patient_record_id = int(payload.get("patientRecordId"))
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError("FHIR Order patientRecordId is required.") from exc
        fhir = cls._fhir_order_values(payload)
        status = cls._clean_fhir_order_text(fhir.get("status") or FHIR_ORDER_DEFAULT_STATUS)
        intent = cls._clean_fhir_order_text(fhir.get("intent") or FHIR_ORDER_DEFAULT_INTENT)
        if not status:
            raise SimulatorValidationError("FHIR Order status is required.")
        if not intent:
            raise SimulatorValidationError("FHIR Order intent is required.")
        priority = cls._clean_fhir_order_text(fhir.get("priority") or FHIR_ORDER_DEFAULT_PRIORITY)
        occurrence = cls._fhir_order_datetime(fhir.get("occurrenceDateTime") or payload.get("requestedAt"))
        authored_on = cls._fhir_order_datetime(fhir.get("authoredOn"), fallback=now_iso())
        requested_at = cls._fhir_order_storage_timestamp(occurrence or authored_on)
        order_code = cls._clean_fhir_order_text(
            fhir.get("codeCode") or fhir.get("code") or payload.get("orderCode") or ORDER_DEFAULT_CODE
        )
        order_text = cls._clean_fhir_order_text(
            fhir.get("codeDisplay") or payload.get("orderCodeText") or ORDER_DEFAULT_TEXT
        )
        return {
            "patient_record_id": patient_record_id,
            "status": status,
            "intent": intent,
            "priority": priority,
            "requested_at": requested_at,
            "ordering_provider": cls._clean_fhir_order_text(
                fhir.get("requester") or payload.get("orderingProvider") or ORDER_DEFAULT_PROVIDER
            ),
            "clinical_indication": cls._clean_fhir_order_text(
                fhir.get("reasonCodeText") or payload.get("clinicalIndication")
            ),
            "order_code": order_code or ORDER_DEFAULT_CODE,
            "order_code_text": order_text or ORDER_DEFAULT_TEXT,
            "alternate_code": cls._clean_fhir_order_text(
                fhir.get("alternateCode") or payload.get("alternateCode") or ORDER_DEFAULT_ALT_CODE
            ),
            "alternate_code_text": cls._clean_fhir_order_text(
                fhir.get("alternateCodeText") or payload.get("alternateCodeText") or ORDER_DEFAULT_ALT_TEXT
            ),
            "alternate_code_system": cls._clean_fhir_order_text(
                fhir.get("alternateCodeSystem") or payload.get("alternateCodeSystem") or ORDER_DEFAULT_ALT_SYSTEM
            ),
            "fhir": dict(fhir),
            "occurrence": occurrence,
            "authored_on": authored_on,
        }

    @staticmethod
    def _build_order_orm_payload(values: dict[str, Any], *, record_id: int, timestamp: str) -> str:
        order_number = values["local_order_number"] or DemoStore._order_record_number(record_id)
        visit_id = values["visit_id"] or DemoStore._order_visit_id(record_id)
        account_number = values["account_number"] or DemoStore._order_account_number(record_id)
        patient_name = "^".join(
            _hl7_escape(part)
            for part in (values["last_name"], values["first_name"], values["middle_name"])
        ).rstrip("^")
        universal_service_id = "^".join(
            _hl7_escape(part)
            for part in (
                values["order_code"],
                values["order_code_text"],
                "L",
                values["alternate_code"],
                values["alternate_code_text"],
                values["alternate_code_system"],
            )
        )
        control_id = f"ORM{timestamp}{record_id:06d}"
        segments = [
            f"MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|{timestamp}||ORM^O01^ORM_O01|{control_id}|P|{HL7_V2_MSH_SUFFIX}",
            (
                "PID|1||"
                f"{_hl7_escape(values['mrn'])}^^^HEALTHCARE_LAB^MR||"
                f"{patient_name}||{_hl7_escape(values['dob'])}|{_hl7_escape(values['sex'])}|||||||||||"
                f"{_hl7_escape(account_number)}"
            ),
            (
                "PV1|1|"
                f"{_hl7_escape(values['patient_class'])}|{_hl7_escape_composite(values['assigned_location'])}"
                f"||||{_hl7_escape_composite(values['ordering_provider'])}||||||||||||{_hl7_escape(visit_id)}"
            ),
            (
                "ORC|NW|"
                f"{_hl7_escape(order_number)}||{_hl7_escape(values['filler_order_number'])}|||"
                f"^^^{_hl7_escape(values['requested_at'])}^{_hl7_escape(values['priority'])}||{timestamp}|||"
                f"{_hl7_escape_composite(values['ordering_provider'])}"
            ),
            (
                "OBR|1|"
                f"{_hl7_escape(order_number)}|{_hl7_escape(values['filler_order_number'])}|"
                f"{universal_service_id}|{_hl7_escape(values['priority'])}|{_hl7_escape(values['requested_at'])}"
                f"||||||||{_hl7_escape(values['clinical_indication'])}|||"
                f"{_hl7_escape_composite(values['ordering_provider'])}"
            ),
        ]
        return "\r".join(segments)

    @classmethod
    def _build_service_request_resource(
        cls,
        values: dict[str, Any],
        *,
        record_id: int,
        local_order_number: str,
        patient_reference: str,
    ) -> dict[str, Any]:
        fhir = values.get("fhir") or {}
        resource: dict[str, Any] = {
            "resourceType": "ServiceRequest",
            "status": values["status"],
            "intent": values["intent"],
            "subject": {"reference": patient_reference},
        }
        explicit_id = cls._clean_fhir_order_text(fhir.get("id") or fhir.get("serviceRequestId"))
        if explicit_id:
            resource["id"] = explicit_id

        identifier_system = cls._clean_fhir_order_text(
            fhir.get("identifierSystem") or FHIR_IDENTIFIER_SYSTEMS["ServiceRequest"]
        )
        identifier_value = cls._clean_fhir_order_text(
            fhir.get("identifierValue") or cls.fhir_identifier_value(
                "ServiceRequest",
                "local_order_records",
                record_id,
            )
        )
        resource["identifier"] = [{"system": identifier_system, "value": identifier_value}]
        for item in cls._fhir_order_list(fhir.get("identifier")):
            if "|" in item:
                system, value = item.split("|", 1)
                resource["identifier"].append({"system": system.strip(), "value": value.strip()})
            else:
                resource["identifier"].append({"value": item})

        instantiates_canonical = cls._fhir_order_list(fhir.get("instantiatesCanonical"))
        if instantiates_canonical:
            resource["instantiatesCanonical"] = instantiates_canonical
        instantiates_uri = cls._fhir_order_list(fhir.get("instantiatesUri"))
        if instantiates_uri:
            resource["instantiatesUri"] = instantiates_uri
        for key, field_name in (
            ("basedOn", "basedOn"),
            ("replaces", "replaces"),
            ("reasonReference", "reasonReference"),
            ("insurance", "insurance"),
            ("supportingInfo", "supportingInfo"),
            ("specimen", "specimen"),
            ("relevantHistory", "relevantHistory"),
        ):
            references = cls._fhir_reference_list(fhir.get(key), field_name)
            if references:
                resource[key] = references

        requisition_system = cls._clean_fhir_order_text(fhir.get("requisitionSystem"))
        requisition_value = cls._clean_fhir_order_text(fhir.get("requisitionValue"))
        if requisition_system or requisition_value:
            resource["requisition"] = {
                key: value
                for key, value in {
                    "system": requisition_system,
                    "value": requisition_value or local_order_number,
                }.items()
                if value
            }

        category = cls._fhir_codeable_concept(text=fhir.get("category") or FHIR_ORDER_DEFAULT_CATEGORY)
        if category:
            resource["category"] = [category]
        if values["priority"]:
            resource["priority"] = values["priority"]
        if "doNotPerform" in fhir:
            resource["doNotPerform"] = bool(fhir.get("doNotPerform"))

        code = cls._fhir_codeable_concept(
            text=fhir.get("codeText") or values["order_code_text"],
            code=fhir.get("codeCode") or values["order_code"],
            system=fhir.get("codeSystem") or "urn:healthcare-lab:service-code",
            display=fhir.get("codeDisplay") or values["order_code_text"],
        )
        if values.get("alternate_code"):
            coding = code.setdefault("coding", [])
            coding.append(
                {
                    key: value
                    for key, value in {
                        "system": values.get("alternate_code_system"),
                        "code": values.get("alternate_code"),
                        "display": values.get("alternate_code_text"),
                    }.items()
                    if value
                }
            )
        resource["code"] = code

        order_detail = cls._fhir_codeable_concept(text=fhir.get("orderDetail"))
        if order_detail:
            resource["orderDetail"] = [order_detail]
        quantity_value = cls._clean_fhir_order_text(fhir.get("quantityValue"))
        quantity_unit = cls._clean_fhir_order_text(fhir.get("quantityUnit"))
        if quantity_value or quantity_unit:
            quantity: dict[str, Any] = {}
            if quantity_value:
                try:
                    quantity["value"] = float(quantity_value)
                except ValueError:
                    raise SimulatorValidationError("FHIR Order quantity value must be numeric.")
            if quantity_unit:
                quantity["unit"] = quantity_unit
            resource["quantityQuantity"] = quantity

        encounter = cls._clean_fhir_order_text(fhir.get("encounter"))
        if encounter:
            resource["encounter"] = cls._fhir_reference_item(encounter, "encounter")
        if values.get("occurrence"):
            resource["occurrenceDateTime"] = values["occurrence"]
        if "asNeededBoolean" in fhir:
            resource["asNeededBoolean"] = bool(fhir.get("asNeededBoolean"))
        as_needed = cls._fhir_codeable_concept(text=fhir.get("asNeededCodeText"))
        if as_needed:
            resource["asNeededCodeableConcept"] = as_needed
        if values.get("authored_on"):
            resource["authoredOn"] = values["authored_on"]

        requester = cls._clean_fhir_order_text(fhir.get("requester") or values["ordering_provider"])
        if requester:
            resource["requester"] = (
                cls._fhir_reference_item(requester, "requester")
                if "/" in requester
                else {"display": requester}
            )
        performer_type = cls._fhir_codeable_concept(text=fhir.get("performerType"))
        if performer_type:
            resource["performerType"] = performer_type
        performer = cls._fhir_reference_list(fhir.get("performer"), "performer")
        if performer:
            resource["performer"] = performer
        location_code = cls._fhir_codeable_concept(text=fhir.get("locationCode"))
        if location_code:
            resource["locationCode"] = [location_code]
        location_reference = cls._fhir_reference_list(fhir.get("locationReference"), "locationReference")
        if location_reference:
            resource["locationReference"] = location_reference
        reason_code = cls._fhir_codeable_concept(text=fhir.get("reasonCodeText") or values["clinical_indication"])
        if reason_code:
            resource["reasonCode"] = [reason_code]
        body_site = cls._fhir_codeable_concept(text=fhir.get("bodySite"))
        if body_site:
            resource["bodySite"] = [body_site]
        note = cls._clean_fhir_order_text(fhir.get("note"))
        if note:
            resource["note"] = [{"text": note}]
        patient_instruction = cls._clean_fhir_order_text(fhir.get("patientInstruction"))
        if patient_instruction:
            resource["patientInstruction"] = patient_instruction
        return resource

    def create_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_order_payload(payload)
        timestamp = now_iso()
        hl7_time = hl7_timestamp()
        with self.lock, self.connect() as connection:
            patient_row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient_row:
                raise KeyError(values["patient_record_id"])
            cursor = connection.execute(
                """
                INSERT INTO local_order_records (
                    local_order_number, patient_record_id, protocol_version, message_type,
                    order_status, mrn, first_name, last_name, middle_name, dob, sex,
                    visit_id, patient_class, assigned_location, account_number,
                    placer_order_number, filler_order_number, priority, requested_at,
                    ordering_provider, clinical_indication, order_code, order_code_text,
                    alternate_code, alternate_code_text, alternate_code_system,
                    validation_status, validation_messages_json, payload_hl7,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    values["patient_record_id"],
                    ORDER_PROTOCOL_VERSION,
                    ORDER_MESSAGE_TYPE,
                    ORDER_STATUS_READY,
                    patient_row["mrn"],
                    patient_row["first_name"],
                    patient_row["last_name"],
                    patient_row["middle_name"],
                    patient_row["dob"],
                    patient_row["sex"],
                    patient_row["visit_number"],
                    patient_row["patient_class"],
                    patient_row["assigned_location"],
                    patient_row["account_number"],
                    "",
                    "",
                    values["priority"],
                    values["requested_at"],
                    values["ordering_provider"],
                    values["clinical_indication"],
                    values["order_code"],
                    values["order_code_text"],
                    values["alternate_code"],
                    values["alternate_code_text"],
                    values["alternate_code_system"],
                    "valid",
                    "[]",
                    "",
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_order_number = self._order_record_number(record_id)
            visit_id = patient_row["visit_number"] or self._order_visit_id(record_id)
            account_number = patient_row["account_number"] or self._order_account_number(record_id)
            payload_values = {
                **values,
                "local_order_number": local_order_number,
                "filler_order_number": "",
                "mrn": patient_row["mrn"],
                "first_name": patient_row["first_name"],
                "last_name": patient_row["last_name"],
                "middle_name": patient_row["middle_name"],
                "dob": patient_row["dob"],
                "sex": patient_row["sex"],
                "visit_id": visit_id,
                "patient_class": patient_row["patient_class"],
                "assigned_location": patient_row["assigned_location"],
                "account_number": account_number,
            }
            payload_hl7 = self._build_order_orm_payload(
                payload_values,
                record_id=record_id,
                timestamp=hl7_time,
            )
            connection.execute(
                """
                UPDATE local_order_records
                SET local_order_number = ?, placer_order_number = ?, visit_id = ?,
                    account_number = ?, payload_hl7 = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    local_order_number,
                    local_order_number,
                    visit_id,
                    account_number,
                    payload_hl7,
                    timestamp,
                    record_id,
                ),
            )
        return self.get_order_record(record_id)

    def create_dcm4chee_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        item = self.create_order_record(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            connection.execute(
                """
                UPDATE local_order_records
                SET protocol_version = ?, message_type = ?, order_status = ?,
                    payload_hl7 = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    DCM4CHEE_ORDER_PROTOCOL_VERSION,
                    DCM4CHEE_ORDER_MESSAGE_TYPE,
                    "Created",
                    "",
                    timestamp,
                    int(item["id"]),
                ),
            )
        return self.get_order_record(int(item["id"]))

    @staticmethod
    def _dicom_first_value(payload: dict[str, Any], tag: str, default: str = "") -> str:
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

    @staticmethod
    def _dcm4chee_sps_payload(payload: dict[str, Any]) -> dict[str, Any]:
        sequence = payload.get("00400100") if isinstance(payload, dict) else None
        if not isinstance(sequence, dict):
            return {}
        values = sequence.get("Value")
        if not isinstance(values, list) or not values or not isinstance(values[0], dict):
            return {}
        return values[0]

    @classmethod
    def dcm4chee_identifiers_from_payload(
        cls,
        order: dict[str, Any],
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, str]:
        order_id = int(order["id"])
        patient = order.get("patient") or {}
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        payload = payload or {}
        sps_payload = cls._dcm4chee_sps_payload(payload)
        uid_root_text = cls.normalize_dcm4chee_uid_root(uid_root)
        return {
            "profile_name": str(profile.get("profileName") or "").strip(),
            "server_identity": str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
            "mwl_ae_title": str(mwl.get("aeTitle") or "").strip(),
            "scheduled_station_ae_title": cls._dicom_first_value(
                sps_payload,
                "00400001",
                str(mwl.get("defaultScheduledStationAETitle") or "").strip(),
            ),
            "local_dcm4chee_order_number": cls._dcm4chee_local_order_number(order_id),
            "patient_id": cls._dicom_first_value(payload, "00100020", str(patient.get("mrn") or "").strip()),
            "issuer_of_patient_id": cls._dicom_first_value(
                payload,
                "00100021",
                str(profile.get("profileName") or "HEALTHCARE_LAB").strip(),
            ),
            "accession_number": cls._dicom_first_value(payload, "00080050", cls._dcm4chee_accession_number(order_id)),
            "requested_procedure_id": cls._dicom_first_value(
                payload,
                "00401001",
                cls._dcm4chee_requested_procedure_id(order_id),
            ),
            "scheduled_procedure_step_id": cls._dicom_first_value(
                sps_payload,
                "00400009",
                cls._dcm4chee_scheduled_procedure_step_id(order_id),
            ),
            "study_instance_uid": cls._dicom_first_value(
                payload,
                "0020000D",
                cls.dcm4chee_study_instance_uid(
                    uid_root_text,
                    order_record_id=order_id,
                    timestamp=str(order.get("requestedAt") or ""),
                ),
            ),
            "worklist_label": cls._dicom_first_value(
                payload,
                "00741202",
                str(order.get("orderCodeText") or order.get("orderCode") or ORDER_DEFAULT_TEXT).strip(),
            ),
            "uid_root": uid_root_text,
        }

    @classmethod
    def dcm4chee_identifiers_from_response_body(cls, response_body: str) -> dict[str, str]:
        try:
            parsed = json.loads(response_body or "")
        except (TypeError, ValueError):
            return {}
        if isinstance(parsed, list):
            parsed = parsed[0] if parsed and isinstance(parsed[0], dict) else {}
        if not isinstance(parsed, dict):
            return {}
        return cls.dcm4chee_identifiers_from_dataset(parsed)

    @classmethod
    def dcm4chee_datasets_from_response_body(cls, response_body: str) -> list[dict[str, Any]]:
        try:
            parsed = json.loads(response_body or "")
        except (TypeError, ValueError):
            return []
        if isinstance(parsed, list):
            values = parsed
        else:
            values = [parsed]
        datasets: list[dict[str, Any]] = []
        for value in values:
            if not isinstance(value, dict):
                continue
            dataset = value.get("attrs") if isinstance(value.get("attrs"), dict) else value
            if isinstance(dataset, dict):
                datasets.append(dataset)
        return datasets

    @classmethod
    def dcm4chee_identifiers_from_dataset(cls, dataset: dict[str, Any]) -> dict[str, str]:
        dataset = dataset.get("attrs") if isinstance(dataset.get("attrs"), dict) else dataset
        if not isinstance(dataset, dict):
            return {}
        sps_payload = cls._dcm4chee_sps_payload(dataset)
        values = {
            "patient_id": cls._dicom_first_value(dataset, "00100020"),
            "issuer_of_patient_id": cls._dicom_first_value(dataset, "00100021"),
            "accession_number": cls._dicom_first_value(dataset, "00080050"),
            "requested_procedure_id": cls._dicom_first_value(dataset, "00401001"),
            "scheduled_procedure_step_id": cls._dicom_first_value(sps_payload, "00400009"),
            "study_instance_uid": cls._dicom_first_value(dataset, "0020000D"),
            "worklist_label": cls._dicom_first_value(dataset, "00741202")
            or cls._dicom_first_value(sps_payload, "00400007"),
            "scheduled_station_ae_title": cls._dicom_first_value(sps_payload, "00400001"),
        }
        return {key: value for key, value in values.items() if value}

    @staticmethod
    def dcm4chee_mwl_verification_query_from_mapping(mapping: dict[str, Any]) -> dict[str, str]:
        query = {
            "AccessionNumber": str(mapping.get("accessionNumber") or "").strip(),
            "RequestedProcedureID": str(mapping.get("requestedProcedureId") or "").strip(),
            "ScheduledProcedureStepID": str(mapping.get("scheduledProcedureStepId") or "").strip(),
            "PatientID": str(mapping.get("patientId") or "").strip(),
            "IssuerOfPatientID": str(mapping.get("issuerOfPatientId") or "").strip(),
            "ScheduledStationAETitle": str(mapping.get("scheduledStationAETitle") or "").strip(),
        }
        return {key: value for key, value in query.items() if value}

    def upsert_dcm4chee_mwl_mapping(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_payload: dict[str, Any] | None = None,
        sync_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        increment_retry: bool = False,
    ) -> dict[str, Any]:
        order = self.get_order_record(order_record_id)
        identifiers = self.dcm4chee_identifiers_from_payload(
            order,
            profile,
            uid_root=uid_root,
            payload=request_payload,
        )
        now = now_iso()
        request_payload_json = json.dumps(request_payload or {}, sort_keys=True)
        with self.lock, self.connect() as connection:
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id = ?",
                (int(order_record_id),),
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_mwl_mappings
                    SET profile_name = ?, server_identity = ?, mwl_ae_title = ?,
                        scheduled_station_ae_title = ?, local_dcm4chee_order_number = ?,
                        patient_id = ?, issuer_of_patient_id = ?, accession_number = ?,
                        requested_procedure_id = ?, scheduled_procedure_step_id = ?,
                        study_instance_uid = ?, worklist_label = ?, uid_root = ?,
                        sync_status = ?, retry_count = retry_count + ?,
                        latest_request_payload_json = CASE WHEN ? != '{}' THEN ? ELSE latest_request_payload_json END,
                        updated_at = ?
                    WHERE order_record_id = ?
                    """,
                    (
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["mwl_ae_title"],
                        identifiers["scheduled_station_ae_title"],
                        identifiers["local_dcm4chee_order_number"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["accession_number"],
                        identifiers["requested_procedure_id"],
                        identifiers["scheduled_procedure_step_id"],
                        identifiers["study_instance_uid"],
                        identifiers["worklist_label"],
                        identifiers["uid_root"],
                        sync_status,
                        1 if increment_retry else 0,
                        request_payload_json,
                        request_payload_json,
                        now,
                        int(order_record_id),
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO local_dcm4chee_mwl_mappings (
                        order_record_id, profile_name, server_identity, mwl_ae_title,
                        scheduled_station_ae_title, local_dcm4chee_order_number,
                        patient_id, issuer_of_patient_id, accession_number,
                        requested_procedure_id, scheduled_procedure_step_id,
                        study_instance_uid, worklist_label, uid_root, sync_status,
                        retry_count, latest_request_payload_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        int(order_record_id),
                        identifiers["profile_name"],
                        identifiers["server_identity"],
                        identifiers["mwl_ae_title"],
                        identifiers["scheduled_station_ae_title"],
                        identifiers["local_dcm4chee_order_number"],
                        identifiers["patient_id"],
                        identifiers["issuer_of_patient_id"],
                        identifiers["accession_number"],
                        identifiers["requested_procedure_id"],
                        identifiers["scheduled_procedure_step_id"],
                        identifiers["study_instance_uid"],
                        identifiers["worklist_label"],
                        identifiers["uid_root"],
                        sync_status,
                        1 if increment_retry else 0,
                        request_payload_json,
                        now,
                        now,
                    ),
                )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))

    def update_dcm4chee_mwl_mapping_from_attempt(
        self,
        order_record_id: int,
        *,
        attempt_id: int | None,
        sync_status: str,
        http_status: int | None = None,
        response_body: str = "",
        error_type: str = "",
        error_text: str = "",
        error_payload: dict[str, Any] | None = None,
        readback_payload: dict[str, Any] | list[Any] | None = None,
        identifiers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        identifiers = {key: value for key, value in (identifiers or {}).items() if value}
        assignments = []
        values: list[Any] = []
        for key, column in (
            ("patient_id", "patient_id"),
            ("issuer_of_patient_id", "issuer_of_patient_id"),
            ("accession_number", "accession_number"),
            ("requested_procedure_id", "requested_procedure_id"),
            ("scheduled_procedure_step_id", "scheduled_procedure_step_id"),
            ("study_instance_uid", "study_instance_uid"),
            ("worklist_label", "worklist_label"),
            ("scheduled_station_ae_title", "scheduled_station_ae_title"),
        ):
            if identifiers.get(key):
                assignments.append(f"{column} = ?")
                values.append(identifiers[key])
        timestamp = now_iso()
        readback_json = json.dumps(readback_payload or {}, sort_keys=True)
        error_payload_json = json.dumps(error_payload or {}, sort_keys=True)
        assignments.extend(
            [
                "sync_status = ?",
                "last_sync_at = ?",
                "last_attempt_id = ?",
                "last_http_status = ?",
                "last_response_body = ?",
                "last_error_type = ?",
                "last_error_text = ?",
                "last_error_payload_json = ?",
                "latest_readback_payload_json = CASE WHEN ? != '{}' THEN ? ELSE latest_readback_payload_json END",
                "updated_at = ?",
            ]
        )
        values.extend(
            [
                sync_status,
                timestamp,
                attempt_id,
                http_status,
                response_body,
                error_type,
                error_text,
                error_payload_json,
                readback_json,
                readback_json,
                timestamp,
                int(order_record_id),
            ]
        )
        with self.lock, self.connect() as connection:
            connection.execute(
                f"""
                UPDATE local_dcm4chee_mwl_mappings
                SET {", ".join(assignments)}
                WHERE order_record_id = ?
                """,
                values,
            )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))

    def get_dcm4chee_mwl_mapping_for_order(self, order_record_id: int) -> dict[str, Any] | None:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_mappings WHERE order_record_id = ?",
                (int(order_record_id),),
            ).fetchone()
        return self._dcm4chee_mwl_mapping_dict(row) if row else None

    def find_dcm4chee_mwl_mapping_for_reconciliation(
        self,
        *,
        study_instance_uid: str = "",
        accession_number: str = "",
        requested_procedure_id: str = "",
        scheduled_procedure_step_id: str = "",
        profile_name: str = "",
        server_identity: str = "",
    ) -> dict[str, Any] | None:
        study_uid = str(study_instance_uid or "").strip()
        accession = str(accession_number or "").strip()
        requested_procedure = str(requested_procedure_id or "").strip()
        sps_id = str(scheduled_procedure_step_id or "").strip()
        profile = str(profile_name or "").strip()
        server = str(server_identity or "").strip()
        with self.connect() as connection:
            if study_uid:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE study_instance_uid = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (study_uid,),
                ).fetchone()
                if row:
                    return self._dcm4chee_mwl_mapping_dict(row)
            if accession and profile and server:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE accession_number = ? AND profile_name = ? AND server_identity = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (accession, profile, server),
                ).fetchone()
                if row:
                    return self._dcm4chee_mwl_mapping_dict(row)
            if requested_procedure and sps_id and profile and server:
                row = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE requested_procedure_id = ?
                    AND scheduled_procedure_step_id = ?
                    AND profile_name = ?
                    AND server_identity = ?
                    ORDER BY updated_at DESC, id DESC
                    LIMIT 1
                    """,
                    (requested_procedure, sps_id, profile, server),
                ).fetchone()
                if row:
                    return self._dcm4chee_mwl_mapping_dict(row)
        return None

    @classmethod
    def dcm4chee_result_metadata_from_dataset(cls, dataset: dict[str, Any]) -> dict[str, str]:
        dataset = dataset.get("attrs") if isinstance(dataset.get("attrs"), dict) else dataset
        if not isinstance(dataset, dict):
            return {}
        sps_payload = cls._dcm4chee_sps_payload(dataset)
        request_attrs = cls._dicom_sequence_first(dataset, "00400275")
        identifiers = cls.dcm4chee_identifiers_from_dataset(dataset)
        requested_procedure_id = (
            identifiers.get("requested_procedure_id")
            or cls._dicom_first_value(request_attrs, "00401001")
        )
        scheduled_procedure_step_id = (
            identifiers.get("scheduled_procedure_step_id")
            or cls._dicom_first_value(request_attrs, "00400009")
            or cls._dicom_first_value(sps_payload, "00400009")
        )
        return {
            **identifiers,
            "requested_procedure_id": requested_procedure_id,
            "scheduled_procedure_step_id": scheduled_procedure_step_id,
            "series_instance_uid": cls._dicom_first_value(dataset, "0020000E"),
            "sop_instance_uid": cls._dicom_first_value(dataset, "00080018"),
            "modality": cls._dicom_first_value(dataset, "00080060"),
            "study_datetime": cls._dicom_datetime(dataset, "00080020", "00080030"),
            "series_datetime": cls._dicom_datetime(dataset, "00080021", "00080031"),
            "instance_datetime": cls._dicom_datetime(dataset, "00080012", "00080013")
            or cls._dicom_datetime(dataset, "00080023", "00080033"),
        }

    @staticmethod
    def _dicom_sequence_first(payload: dict[str, Any], tag: str) -> dict[str, Any]:
        element = payload.get(tag) if isinstance(payload, dict) else None
        if not isinstance(element, dict):
            return {}
        values = element.get("Value")
        if not isinstance(values, list) or not values or not isinstance(values[0], dict):
            return {}
        return values[0]

    @classmethod
    def _dicom_datetime(cls, payload: dict[str, Any], date_tag: str, time_tag: str) -> str:
        date = cls._dicom_first_value(payload, date_tag)
        time = cls._dicom_first_value(payload, time_tag)
        if date and time:
            return f"{date}{time}"
        return date or time

    @staticmethod
    def _dcm4chee_profile_identity(profile: dict[str, Any]) -> tuple[str, str, str]:
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        profile_name = str(profile.get("profileName") or "").strip()
        server_identity = str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip()
        source_ae_title = str(dimse.get("calledAETitle") or server_identity).strip()
        return profile_name, server_identity, source_ae_title

    @staticmethod
    def _dcm4chee_result_key(
        *,
        profile_name: str,
        server_identity: str,
        patient_record_id: int | None = None,
        status: str = "",
        study_instance_uid: str = "",
        series_instance_uid: str = "",
        sop_instance_uid: str = "",
        accession_number: str = "",
        requested_procedure_id: str = "",
        scheduled_procedure_step_id: str = "",
    ) -> str:
        study = str(study_instance_uid or "").strip()
        series = str(series_instance_uid or "").strip()
        sop = str(sop_instance_uid or "").strip()
        if study or series or sop:
            return "|".join(
                [
                    "dicom",
                    str(profile_name or "").strip(),
                    str(server_identity or "").strip(),
                    study,
                    series,
                    sop,
                ]
            )
        accession = str(accession_number or "").strip()
        requested = str(requested_procedure_id or "").strip()
        sps = str(scheduled_procedure_step_id or "").strip()
        if accession or requested or sps:
            return "|".join(
                [
                    "dicom-identifiers",
                    str(profile_name or "").strip(),
                    str(server_identity or "").strip(),
                    accession,
                    requested,
                    sps,
                ]
            )
        return "|".join(
            [
                "diagnostic",
                str(profile_name or "").strip(),
                str(server_identity or "").strip(),
                str(patient_record_id or ""),
                str(status or "").strip(),
            ]
        )

    @staticmethod
    def _dcm4chee_patient_matches(mapping: dict[str, Any], metadata: dict[str, str]) -> bool:
        patient_id = str(metadata.get("patient_id") or "").strip()
        issuer = str(metadata.get("issuer_of_patient_id") or "").strip()
        expected_patient_id = str(mapping.get("patientId") or "").strip()
        expected_issuer = str(mapping.get("issuerOfPatientId") or "").strip()
        if patient_id and expected_patient_id and patient_id != expected_patient_id:
            return False
        if issuer and expected_issuer and issuer != expected_issuer:
            return False
        return True

    def _dcm4chee_mappings_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT m.* FROM local_dcm4chee_mwl_mappings m
                JOIN local_order_records o ON o.id = m.order_record_id
                WHERE o.patient_record_id = ?
                ORDER BY m.updated_at DESC, m.id DESC
                """,
                (int(patient_record_id),),
            ).fetchall()
        return [self._dcm4chee_mwl_mapping_dict(row) for row in rows]

    def list_dcm4chee_mwl_mappings_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        return self._dcm4chee_mappings_for_patient(patient_record_id)

    def reconcile_dcm4chee_result_metadata(
        self,
        metadata: dict[str, str],
        *,
        patient_record_id: int | None = None,
        profile_name: str = "",
        server_identity: str = "",
    ) -> dict[str, Any]:
        mappings = (
            self._dcm4chee_mappings_for_patient(int(patient_record_id))
            if patient_record_id is not None
            else []
        )
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
            wrong_patient = [mapping for mapping in same_accession if not self._dcm4chee_patient_matches(mapping, metadata)]
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
            wrong_patient = [mapping for mapping in same_procedure if not self._dcm4chee_patient_matches(mapping, metadata)]
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
                if self._dcm4chee_patient_matches(mapping, metadata)
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

    @staticmethod
    def dcm4chee_result_links(profile: dict[str, Any], metadata: dict[str, str]) -> dict[str, str]:
        dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
        viewer = profile.get("viewer") if isinstance(profile.get("viewer"), dict) else {}
        wado_url = str(dicomweb.get("wadoRsUrl") or dicomweb.get("baseUrl") or "").strip().rstrip("/")
        study_uid = str(metadata.get("study_instance_uid") or "").strip()
        series_uid = str(metadata.get("series_instance_uid") or "").strip()
        sop_uid = str(metadata.get("sop_instance_uid") or "").strip()
        viewer_template = str(viewer.get("studyUrlTemplate") or "").strip()
        links = {
            "viewer_url": "",
            "study_retrieve_url": "",
            "series_retrieve_url": "",
            "instance_retrieve_url": "",
        }
        if study_uid and viewer_template:
            links["viewer_url"] = viewer_template.replace("{studyInstanceUid}", urllib_quote_safe(study_uid))
        if study_uid and wado_url:
            study_path = f"{wado_url}/studies/{urllib_quote_safe(study_uid)}"
            links["study_retrieve_url"] = study_path
            if series_uid:
                series_path = f"{study_path}/series/{urllib_quote_safe(series_uid)}"
                links["series_retrieve_url"] = series_path
                if sop_uid:
                    links["instance_retrieve_url"] = f"{series_path}/instances/{urllib_quote_safe(sop_uid)}"
        return links

    def upsert_dcm4chee_result_record(
        self,
        metadata: dict[str, str],
        profile: dict[str, Any],
        *,
        patient_record_id: int | None = None,
        query_url: str = "",
        query_payload: dict[str, Any] | None = None,
        raw_metadata: dict[str, Any] | None = None,
        refresh_generation: str = "",
    ) -> dict[str, Any]:
        profile_name, server_identity, source_ae_title = self._dcm4chee_profile_identity(profile)
        reconciliation = self.reconcile_dcm4chee_result_metadata(
            metadata,
            patient_record_id=patient_record_id,
            profile_name=profile_name,
            server_identity=server_identity,
        )
        mapping = reconciliation.get("mapping") or {}
        links = self.dcm4chee_result_links(profile, metadata)
        result_key = self._dcm4chee_result_key(
            profile_name=profile_name,
            server_identity=server_identity,
            patient_record_id=patient_record_id,
            status=str(reconciliation.get("status") or ""),
            study_instance_uid=metadata.get("study_instance_uid", ""),
            series_instance_uid=metadata.get("series_instance_uid", ""),
            sop_instance_uid=metadata.get("sop_instance_uid", ""),
            accession_number=metadata.get("accession_number", ""),
            requested_procedure_id=metadata.get("requested_procedure_id", ""),
            scheduled_procedure_step_id=metadata.get("scheduled_procedure_step_id", ""),
        )
        now = now_iso()
        values = {
            "patient_record_id": int(patient_record_id) if patient_record_id is not None else None,
            "order_record_id": int(mapping["orderRecordId"]) if mapping else None,
            "mapping_id": int(mapping["id"]) if mapping else None,
            "profile_name": profile_name,
            "server_identity": server_identity,
            "source_ae_title": source_ae_title,
            "study_instance_uid": metadata.get("study_instance_uid", ""),
            "series_instance_uid": metadata.get("series_instance_uid", ""),
            "sop_instance_uid": metadata.get("sop_instance_uid", ""),
            "accession_number": metadata.get("accession_number", ""),
            "patient_id": metadata.get("patient_id", ""),
            "issuer_of_patient_id": metadata.get("issuer_of_patient_id", ""),
            "requested_procedure_id": metadata.get("requested_procedure_id", ""),
            "scheduled_procedure_step_id": metadata.get("scheduled_procedure_step_id", ""),
            "modality": metadata.get("modality", ""),
            "study_datetime": metadata.get("study_datetime", ""),
            "series_datetime": metadata.get("series_datetime", ""),
            "instance_datetime": metadata.get("instance_datetime", ""),
            "viewer_url": links["viewer_url"],
            "study_retrieve_url": links["study_retrieve_url"],
            "series_retrieve_url": links["series_retrieve_url"],
            "instance_retrieve_url": links["instance_retrieve_url"],
            "reconciliation_status": reconciliation.get("status") or DCM4CHEE_RESULT_STATUS_UNLINKED,
            "match_method": reconciliation.get("method") or "",
            "match_strength": reconciliation.get("strength") or "",
            "query_url": query_url,
            "query_payload_json": json.dumps(query_payload or {}, sort_keys=True),
            "diagnostic_payload_json": json.dumps(reconciliation.get("diagnostic") or {}, sort_keys=True),
            "raw_metadata_json": json.dumps(raw_metadata or metadata or {}, sort_keys=True),
            "refresh_generation": str(refresh_generation or "").strip(),
        }
        with self.lock, self.connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                values["patient_record_id"],
                values["refresh_generation"],
                now,
            )
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE result_key = ?",
                (result_key,),
            ).fetchone()
            if existing and self._dcm4chee_result_row_is_newer_than_generation(
                connection,
                existing,
                values["patient_record_id"],
                values["refresh_generation"],
            ):
                return self._dcm4chee_result_record_dict(existing)
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_result_records
                    SET patient_record_id = ?, order_record_id = ?, mapping_id = ?,
                        profile_name = ?, server_identity = ?, source_ae_title = ?,
                        study_instance_uid = ?, series_instance_uid = ?, sop_instance_uid = ?,
                        accession_number = ?, patient_id = ?, issuer_of_patient_id = ?,
                        requested_procedure_id = ?, scheduled_procedure_step_id = ?,
                        modality = ?, study_datetime = ?, series_datetime = ?, instance_datetime = ?,
                        viewer_url = ?, study_retrieve_url = ?, series_retrieve_url = ?,
                        instance_retrieve_url = ?, reconciliation_status = ?, match_method = ?,
                        match_strength = ?, query_url = ?, query_payload_json = ?,
                        diagnostic_payload_json = ?, raw_metadata_json = ?,
                        refresh_generation = ?,
                        last_refreshed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        values["patient_record_id"],
                        values["order_record_id"],
                        values["mapping_id"],
                        values["profile_name"],
                        values["server_identity"],
                        values["source_ae_title"],
                        values["study_instance_uid"],
                        values["series_instance_uid"],
                        values["sop_instance_uid"],
                        values["accession_number"],
                        values["patient_id"],
                        values["issuer_of_patient_id"],
                        values["requested_procedure_id"],
                        values["scheduled_procedure_step_id"],
                        values["modality"],
                        values["study_datetime"],
                        values["series_datetime"],
                        values["instance_datetime"],
                        values["viewer_url"],
                        values["study_retrieve_url"],
                        values["series_retrieve_url"],
                        values["instance_retrieve_url"],
                        values["reconciliation_status"],
                        values["match_method"],
                        values["match_strength"],
                        values["query_url"],
                        values["query_payload_json"],
                        values["diagnostic_payload_json"],
                        values["raw_metadata_json"],
                        values["refresh_generation"],
                        now,
                        now,
                        int(existing["id"]),
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_result_records (
                        result_key, patient_record_id, order_record_id, mapping_id,
                        profile_name, server_identity, source_ae_title,
                        study_instance_uid, series_instance_uid, sop_instance_uid,
                        accession_number, patient_id, issuer_of_patient_id,
                        requested_procedure_id, scheduled_procedure_step_id,
                        modality, study_datetime, series_datetime, instance_datetime,
                        viewer_url, study_retrieve_url, series_retrieve_url, instance_retrieve_url,
                        reconciliation_status, match_method, match_strength,
                        query_url, query_payload_json, diagnostic_payload_json, raw_metadata_json,
                        refresh_generation,
                        first_seen_at, last_refreshed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_key,
                        values["patient_record_id"],
                        values["order_record_id"],
                        values["mapping_id"],
                        values["profile_name"],
                        values["server_identity"],
                        values["source_ae_title"],
                        values["study_instance_uid"],
                        values["series_instance_uid"],
                        values["sop_instance_uid"],
                        values["accession_number"],
                        values["patient_id"],
                        values["issuer_of_patient_id"],
                        values["requested_procedure_id"],
                        values["scheduled_procedure_step_id"],
                        values["modality"],
                        values["study_datetime"],
                        values["series_datetime"],
                        values["instance_datetime"],
                        values["viewer_url"],
                        values["study_retrieve_url"],
                        values["series_retrieve_url"],
                        values["instance_retrieve_url"],
                        values["reconciliation_status"],
                        values["match_method"],
                        values["match_strength"],
                        values["query_url"],
                        values["query_payload_json"],
                        values["diagnostic_payload_json"],
                        values["raw_metadata_json"],
                        values["refresh_generation"],
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                record_id = int(cursor.lastrowid)
        return self.get_dcm4chee_result_record(record_id)

    @staticmethod
    def dcm4chee_e2e_demo_patient_payload() -> dict[str, Any]:
        return {
            "mode": "dicom",
            "mrn": "MRN-DCM-E2E-001",
            "firstName": "Avery",
            "middleName": "Lee",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
            "patientClass": "O",
            "assignedLocation": "CARDIOLOGY^ROOM1",
            "visitNumber": "VISIT-DCM-E2E-001",
        }

    @staticmethod
    def dcm4chee_e2e_demo_order_payload(patient_record_id: int) -> dict[str, Any]:
        return {
            "mode": "dicom",
            "patientRecordId": int(patient_record_id),
            "requestedAt": "20260713103000",
            "orderingProvider": ORDER_DEFAULT_PROVIDER,
            "orderCode": ORDER_DEFAULT_CODE,
            "orderCodeText": ORDER_DEFAULT_TEXT,
            "clinicalIndication": "ZAC-42 production-like dcm4chee E2E verification fixture",
        }

    def create_dcm4chee_e2e_demo_fixture(
        self,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
    ) -> dict[str, Any]:
        patient = self.create_patient_record(self.dcm4chee_e2e_demo_patient_payload())
        order = self.create_dcm4chee_order_record(self.dcm4chee_e2e_demo_order_payload(int(patient["id"])))
        payload = self.build_dcm4chee_mwl_payload(order, profile, uid_root=uid_root)
        mapping = self.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=uid_root,
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_PENDING,
        )
        patient = self.get_patient_record(int(patient["id"]))
        order = self.get_order_record(int(order["id"]))
        return {
            "patient": patient,
            "order": order,
            "mapping": mapping,
            "evidence": self.dcm4chee_e2e_evidence_for_order(int(order["id"]), profile),
        }

    def dcm4chee_e2e_evidence_for_order(self, order_record_id: int, profile: dict[str, Any]) -> dict[str, Any]:
        order = self.get_order_record(int(order_record_id))
        patient = self.get_patient_record(int(order["patientRecordId"]))
        mapping = self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id)) or {}
        patient_sync = self.get_dcm4chee_patient_sync_for_patient(int(patient["id"]), profile)
        results = self.list_dcm4chee_results_for_patient(int(patient["id"]))
        order_results = [
            item for item in results
            if str(item.get("orderRecordId") or "") == str(order_record_id)
            or (mapping.get("studyInstanceUid") and item.get("studyInstanceUid") == mapping.get("studyInstanceUid"))
            or (mapping.get("accessionNumber") and item.get("accessionNumber") == mapping.get("accessionNumber"))
        ]
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dicomweb = profile.get("dicomweb") if isinstance(profile.get("dicomweb"), dict) else {}
        verification = mapping.get("verification") if isinstance(mapping.get("verification"), dict) else {}
        return {
            "mode": "dcm4chee-production-like-e2e",
            "patientRecordId": patient["id"],
            "orderRecordId": order["id"],
            "profileName": profile.get("profileName", ""),
            "identifiers": {
                "patientId": mapping.get("patientId") or (patient.get("summary") or {}).get("mrn", ""),
                "issuerOfPatientId": mapping.get("issuerOfPatientId") or profile.get("profileName", ""),
                "accessionNumber": mapping.get("accessionNumber", ""),
                "requestedProcedureId": mapping.get("requestedProcedureId", ""),
                "scheduledProcedureStepId": mapping.get("scheduledProcedureStepId", ""),
                "studyInstanceUid": mapping.get("studyInstanceUid", ""),
                "seriesInstanceUid": next((item.get("seriesInstanceUid") for item in order_results if item.get("seriesInstanceUid")), ""),
                "sopInstanceUid": next((item.get("sopInstanceUid") for item in order_results if item.get("sopInstanceUid")), ""),
            },
            "aeTitles": {
                "archiveCalledAETitle": dimse.get("calledAETitle", ""),
                "healthcareLabCallingAETitle": dimse.get("callingAETitle", ""),
                "mwlAETitle": mwl.get("aeTitle", ""),
                "scheduledStationAETitle": mapping.get("scheduledStationAETitle") or mwl.get("defaultScheduledStationAETitle", ""),
            },
            "endpoints": {
                "mwlRestUrl": f"{str(dicomweb.get('baseUrl') or '').rstrip('/')}/mwlitems" if dicomweb.get("baseUrl") else "",
                "qidoRsUrl": dicomweb.get("qidoRsUrl", ""),
                "wadoRsUrl": dicomweb.get("wadoRsUrl", ""),
                "webUiUrl": profile.get("webUiUrl", ""),
            },
            "steps": {
                "patientPrecondition": (patient_sync or {}).get("status") or "not_synced",
                "mwlCreate": mapping.get("status") or "not_created",
                "mwlQueryable": verification.get("status") or DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
                "apReturn": "recorded" if order_results else "not_recorded",
                "resultReconciliation": next((item.get("reconciliationStatus") for item in order_results if item.get("reconciliationStatus")), DCM4CHEE_RESULT_STATUS_NO_RESULT),
                "uiVisibleResult": bool(order_results),
            },
            "results": order_results,
            "generatedAt": now_iso(),
        }

    def create_simulated_dcm4chee_ap_return(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        result_type: str = "both",
        artifact_url: str = "",
        artifact_path: str = "",
    ) -> dict[str, Any]:
        order = self.get_order_record(int(order_record_id))
        if order.get("protocolVersion") != DCM4CHEE_ORDER_PROTOCOL_VERSION:
            raise SimulatorValidationError("Order record is not DICOM MWL mode.")
        mapping = self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))
        if not mapping:
            payload = self.build_dcm4chee_mwl_payload(order, profile)
            mapping = self.upsert_dcm4chee_mwl_mapping(
                int(order_record_id),
                profile,
                request_payload=payload,
                sync_status=DCM4CHEE_MWL_STATUS_PENDING,
            )
        result_type = str(result_type or "both").strip().lower()
        if result_type not in {"both", "pdf", "dicom"}:
            raise SimulatorValidationError("Simulated AP return type must be pdf, dicom, or both.")
        generation = (
            self.latest_simulated_dcm4chee_ap_return_generation(int(order_record_id))
            if result_type in {"pdf", "dicom"}
            else ""
        ) or f"simulated-ap-return-{now_iso()}"
        self.begin_dcm4chee_result_refresh(
            int(order["patientRecordId"]),
            generation,
            promote_existing=True,
        )
        base_metadata = {
            "study_instance_uid": str(mapping.get("studyInstanceUid") or ""),
            "accession_number": str(mapping.get("accessionNumber") or ""),
            "patient_id": str(mapping.get("patientId") or ""),
            "issuer_of_patient_id": str(mapping.get("issuerOfPatientId") or ""),
            "requested_procedure_id": str(mapping.get("requestedProcedureId") or ""),
            "scheduled_procedure_step_id": str(mapping.get("scheduledProcedureStepId") or ""),
            "modality": "ECG",
            "study_datetime": "20260713104500",
        }
        created: list[dict[str, Any]] = []
        if result_type in {"both", "dicom"}:
            metadata = {
                **base_metadata,
                "series_instance_uid": f"{base_metadata['study_instance_uid']}.1",
                "sop_instance_uid": f"{base_metadata['study_instance_uid']}.1.1",
                "series_datetime": "20260713104600",
                "instance_datetime": "20260713104630",
            }
            created.append(
                self.upsert_dcm4chee_result_record(
                    metadata,
                    profile,
                    patient_record_id=int(order["patientRecordId"]),
                    query_url="simulated://ap-return/dicom",
                    query_payload={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "dicom"},
                    raw_metadata={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "dicom", "metadata": metadata},
                    refresh_generation=generation,
                )
            )
        if result_type in {"both", "pdf"}:
            url = artifact_url or "http://localhost/reports/dcm4chee-simulated-ecg-report.pdf"
            path = artifact_path or "reports/dcm4chee-simulated-ecg-report.pdf"
            metadata = {
                **base_metadata,
                "series_instance_uid": f"{base_metadata['study_instance_uid']}.9001",
                "sop_instance_uid": f"{base_metadata['study_instance_uid']}.9001.1",
                "modality": "DOC",
                "series_datetime": "20260713104700",
                "instance_datetime": "20260713104730",
            }
            created.append(
                self.upsert_dcm4chee_result_record(
                    metadata,
                    profile,
                    patient_record_id=int(order["patientRecordId"]),
                    query_url="simulated://ap-return/pdf",
                    query_payload={"source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP, "type": "pdf"},
                    raw_metadata={
                        "source": DCM4CHEE_RESULT_SOURCE_SIMULATED_AP,
                        "type": "pdf",
                        "metadata": metadata,
                        "artifact": {
                            "label": "Simulated AP ECG PDF",
                            "mediaType": "application/pdf",
                            "url": url,
                            "path": path,
                            "role": "ap-return-report",
                        },
                    },
                    refresh_generation=generation,
                )
            )
        self.complete_dcm4chee_result_refresh(int(order["patientRecordId"]), generation)
        return {
            "items": created,
            "evidence": self.dcm4chee_e2e_evidence_for_order(int(order_record_id), profile),
            "refreshGeneration": generation,
        }

    def latest_simulated_dcm4chee_ap_return_generation(self, order_record_id: int) -> str:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT refresh_generation FROM local_dcm4chee_result_records
                WHERE order_record_id = ?
                AND refresh_generation LIKE 'simulated-ap-return-%'
                AND query_url LIKE 'simulated://ap-return/%'
                ORDER BY last_refreshed_at DESC, id DESC
                LIMIT 1
                """,
                (int(order_record_id),),
            ).fetchone()
        return str(row["refresh_generation"] or "").strip() if row else ""

    def record_dcm4chee_result_refresh_diagnostic(
        self,
        *,
        patient_record_id: int,
        profile: dict[str, Any],
        status: str,
        query_url: str = "",
        query_payload: dict[str, Any] | None = None,
        diagnostic_payload: dict[str, Any] | None = None,
        refresh_generation: str = "",
    ) -> dict[str, Any]:
        profile_name, server_identity, source_ae_title = self._dcm4chee_profile_identity(profile)
        result_key = self._dcm4chee_result_key(
            profile_name=profile_name,
            server_identity=server_identity,
            patient_record_id=patient_record_id,
            status=status,
        )
        now = now_iso()
        generation = str(refresh_generation or "").strip()
        diagnostic_json = json.dumps(diagnostic_payload or {}, sort_keys=True)
        query_json = json.dumps(query_payload or {}, sort_keys=True)
        with self.lock, self.connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                now,
            )
            existing = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE result_key = ?",
                (result_key,),
            ).fetchone()
            if existing and self._dcm4chee_result_row_is_newer_than_generation(
                connection,
                existing,
                int(patient_record_id),
                generation,
            ):
                return self._dcm4chee_result_record_dict(existing)
            if existing:
                connection.execute(
                    """
                    UPDATE local_dcm4chee_result_records
                    SET patient_record_id = ?, order_record_id = NULL, mapping_id = NULL,
                        profile_name = ?, server_identity = ?, source_ae_title = ?,
                        query_url = ?, query_payload_json = ?, diagnostic_payload_json = ?,
                        reconciliation_status = ?, match_method = '', match_strength = '',
                        refresh_generation = ?,
                        last_refreshed_at = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (
                        int(patient_record_id),
                        profile_name,
                        server_identity,
                        source_ae_title,
                        query_url,
                        query_json,
                        diagnostic_json,
                        status,
                        generation,
                        now,
                        now,
                        int(existing["id"]),
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_dcm4chee_result_records (
                        result_key, patient_record_id, profile_name, server_identity, source_ae_title,
                        reconciliation_status, query_url, query_payload_json, diagnostic_payload_json,
                        refresh_generation, first_seen_at, last_refreshed_at, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        result_key,
                        int(patient_record_id),
                        profile_name,
                        server_identity,
                        source_ae_title,
                        status,
                        query_url,
                        query_json,
                        diagnostic_json,
                        generation,
                        now,
                        now,
                        now,
                        now,
                    ),
                )
                record_id = int(cursor.lastrowid)
        return self.get_dcm4chee_result_record(record_id)

    @staticmethod
    def _record_dcm4chee_result_refresh_run(
        connection: sqlite3.Connection,
        patient_record_id: int | None,
        refresh_generation: str,
        started_at: str,
    ) -> None:
        generation = str(refresh_generation or "").strip()
        if patient_record_id is None or not generation:
            return
        connection.execute(
            """
            INSERT OR IGNORE INTO local_dcm4chee_result_refresh_runs (
                patient_record_id, refresh_generation, started_at
            ) VALUES (?, ?, ?)
            """,
            (int(patient_record_id), generation, started_at),
        )

    @staticmethod
    def _dcm4chee_result_refresh_run_id(
        connection: sqlite3.Connection,
        patient_record_id: int,
        refresh_generation: str,
    ) -> int | None:
        row = connection.execute(
            """
            SELECT id FROM local_dcm4chee_result_refresh_runs
            WHERE patient_record_id = ? AND refresh_generation = ?
            """,
            (int(patient_record_id), str(refresh_generation or "").strip()),
        ).fetchone()
        return int(row["id"]) if row else None

    @classmethod
    def _dcm4chee_result_row_is_newer_than_generation(
        cls,
        connection: sqlite3.Connection,
        existing: sqlite3.Row,
        patient_record_id: int | None,
        refresh_generation: str,
    ) -> bool:
        existing_generation = str(existing["refresh_generation"] or "").strip()
        incoming_generation = str(refresh_generation or "").strip()
        if patient_record_id is None or not existing_generation or not incoming_generation:
            return False
        existing_run_id = cls._dcm4chee_result_refresh_run_id(
            connection,
            int(patient_record_id),
            existing_generation,
        )
        incoming_run_id = cls._dcm4chee_result_refresh_run_id(
            connection,
            int(patient_record_id),
            incoming_generation,
        )
        return bool(
            existing_run_id is not None
            and incoming_run_id is not None
            and existing_run_id > incoming_run_id
        )

    def begin_dcm4chee_result_refresh(
        self,
        patient_record_id: int,
        refresh_generation: str,
        *,
        promote_existing: bool = False,
    ) -> None:
        generation = str(refresh_generation or "").strip()
        if not generation:
            raise SimulatorValidationError("DICOM result refresh generation is required.")
        started_at = now_iso()
        with self.lock, self.connect() as connection:
            existing_run = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND refresh_generation = ?
                """,
                (int(patient_record_id), generation),
            ).fetchone()
            latest_run = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if (
                promote_existing
                and existing_run
                and latest_run
                and int(existing_run["id"]) != int(latest_run["id"])
            ):
                connection.execute(
                    "DELETE FROM local_dcm4chee_result_refresh_runs WHERE id = ?",
                    (int(existing_run["id"]),),
                )
            completed = connection.execute(
                """
                SELECT id FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND completed_at != ''
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if not completed:
                legacy_rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_result_records
                    WHERE patient_record_id = ?
                    ORDER BY last_refreshed_at DESC, id DESC
                    """,
                    (int(patient_record_id),),
                ).fetchall()
                if legacy_rows:
                    legacy_generation = str(legacy_rows[0]["refresh_generation"] or "").strip()
                    if legacy_generation:
                        legacy_rows = [
                            row for row in legacy_rows
                            if str(row["refresh_generation"] or "").strip() == legacy_generation
                        ]
                    else:
                        legacy_generation = "legacy-snapshot"
                    legacy_snapshot = [self._dcm4chee_result_record_dict(row) for row in legacy_rows]
                    self._record_dcm4chee_result_refresh_run(
                        connection,
                        int(patient_record_id),
                        legacy_generation,
                        started_at,
                    )
                    connection.execute(
                        """
                        UPDATE local_dcm4chee_result_refresh_runs
                        SET completed_at = ?, results_snapshot_json = ?
                        WHERE patient_record_id = ? AND refresh_generation = ?
                        """,
                        (
                            started_at,
                            json.dumps(legacy_snapshot, sort_keys=True),
                            int(patient_record_id),
                            legacy_generation,
                        ),
                    )
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                started_at,
            )

    def complete_dcm4chee_result_refresh(
        self,
        patient_record_id: int,
        refresh_generation: str,
    ) -> list[dict[str, Any]]:
        generation = str(refresh_generation or "").strip()
        if not generation:
            raise SimulatorValidationError("DICOM result refresh generation is required.")
        completed_at = now_iso()
        with self.lock, self.connect() as connection:
            self._record_dcm4chee_result_refresh_run(
                connection,
                int(patient_record_id),
                generation,
                completed_at,
            )
            latest_run = connection.execute(
                """
                SELECT refresh_generation FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if latest_run and str(latest_run["refresh_generation"] or "").strip() != generation:
                return []
            rows = connection.execute(
                """
                SELECT * FROM local_dcm4chee_result_records
                WHERE patient_record_id = ? AND refresh_generation = ?
                ORDER BY last_refreshed_at DESC, id DESC
                """,
                (int(patient_record_id), generation),
            ).fetchall()
            snapshot = [self._dcm4chee_result_record_dict(row) for row in rows]
            connection.execute(
                """
                UPDATE local_dcm4chee_result_refresh_runs
                SET completed_at = ?, results_snapshot_json = ?
                WHERE patient_record_id = ? AND refresh_generation = ?
                """,
                (
                    completed_at,
                    json.dumps(snapshot, sort_keys=True),
                    int(patient_record_id),
                    generation,
                ),
            )
        return snapshot

    def get_dcm4chee_result_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_result_records WHERE id = ?",
                (int(record_id),),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._dcm4chee_result_record_dict(row)

    def list_dcm4chee_results_for_patient(self, patient_record_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            latest = connection.execute(
                """
                SELECT results_snapshot_json FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ? AND completed_at != ''
                ORDER BY id DESC
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if latest:
                snapshot = self._json_value(latest["results_snapshot_json"], [])
                return snapshot if isinstance(snapshot, list) else []
            has_run = connection.execute(
                """
                SELECT 1 FROM local_dcm4chee_result_refresh_runs
                WHERE patient_record_id = ?
                LIMIT 1
                """,
                (int(patient_record_id),),
            ).fetchone()
            if has_run:
                return []
            rows = connection.execute(
                """
                SELECT * FROM local_dcm4chee_result_records
                WHERE patient_record_id = ?
                ORDER BY last_refreshed_at DESC, id DESC
                """,
                (int(patient_record_id),),
            ).fetchall()
        return [self._dcm4chee_result_record_dict(row) for row in rows]

    def create_dcm4chee_mwl_attempt(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_url: str = "",
        request_payload: dict[str, Any] | None = None,
        attempt_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        http_status: int | None = None,
        response_body: str = "",
        operation_type: str = DCM4CHEE_MWL_OPERATION_CREATE,
        mapping_id: int | None = None,
    ) -> dict[str, Any]:
        order = self.get_order_record(order_record_id)
        generated_payload = request_payload or self.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=uid_root,
        )
        order_id = int(order["id"])
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        uid_root_text = self.normalize_dcm4chee_uid_root(uid_root)
        study_uid = str(generated_payload["0020000D"]["Value"][0])
        accession_number = str(generated_payload["00080050"]["Value"][0])
        requested_procedure_id = str(generated_payload["00401001"]["Value"][0])
        sps_item = generated_payload["00400100"]["Value"][0]
        scheduled_procedure_step_id = str(sps_item["00400009"]["Value"][0])
        scheduled_station_ae_title = str(sps_item["00400001"]["Value"][0])
        now = now_iso()
        with self.lock, self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    mapping_id,
                    operation_type,
                    order_id,
                    str(profile.get("profileName") or "").strip(),
                    str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("aeTitle") or "").strip(),
                    scheduled_station_ae_title,
                    self._dcm4chee_local_order_number(order_id),
                    accession_number,
                    requested_procedure_id,
                    scheduled_procedure_step_id,
                    study_uid,
                    uid_root_text,
                    request_url,
                    json.dumps(generated_payload, sort_keys=True),
                    http_status,
                    response_body,
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now if attempt_status != DCM4CHEE_MWL_STATUS_PENDING else "",
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def create_dcm4chee_mwl_profile_failure_attempt(
        self,
        order_record_id: int,
        profile: dict[str, Any],
        *,
        uid_root: Any = DCM4CHEE_DEFAULT_UID_ROOT,
        request_url: str = "",
        diagnostics: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        order = self.get_order_record(order_record_id)
        order_id = int(order["id"])
        mwl = profile.get("mwl") if isinstance(profile.get("mwl"), dict) else {}
        dimse = profile.get("dimse") if isinstance(profile.get("dimse"), dict) else {}
        uid_root_text = self.normalize_dcm4chee_uid_root(uid_root)
        mapping = self.upsert_dcm4chee_mwl_mapping(
            order_id,
            profile,
            uid_root=uid_root_text,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
        )
        study_uid = self.dcm4chee_study_instance_uid(
            uid_root_text,
            order_record_id=order_id,
            timestamp=str(order.get("requestedAt") or ""),
        )
        now = now_iso()
        diagnostic_payload = diagnostics or {}
        with self.lock, self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(mapping["id"]),
                    DCM4CHEE_MWL_OPERATION_CREATE,
                    order_id,
                    str(profile.get("profileName") or "").strip(),
                    str(dimse.get("calledAETitle") or mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("aeTitle") or "").strip(),
                    str(mwl.get("defaultScheduledStationAETitle") or "").strip(),
                    self._dcm4chee_local_order_number(order_id),
                    self._dcm4chee_accession_number(order_id),
                    self._dcm4chee_requested_procedure_id(order_id),
                    self._dcm4chee_scheduled_procedure_step_id(order_id),
                    study_uid,
                    uid_root_text,
                    request_url,
                    "{}",
                    None,
                    json.dumps(diagnostic_payload, sort_keys=True),
                    DCM4CHEE_MWL_STATUS_FAILED,
                    "profile_invalid",
                    str(diagnostic_payload.get("summary") or "dcm4chee profile is incomplete or invalid."),
                    now,
                    now,
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        self.update_dcm4chee_mwl_mapping_from_attempt(
            order_id,
            attempt_id=attempt_id,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
            response_body=json.dumps(diagnostic_payload, sort_keys=True),
            error_type="profile_invalid",
            error_text=str(diagnostic_payload.get("summary") or "dcm4chee profile is incomplete or invalid."),
            error_payload=diagnostic_payload,
        )
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def update_dcm4chee_mwl_attempt_result(
        self,
        attempt_id: int,
        *,
        attempt_status: str,
        http_status: int | None = None,
        response_body: str = "",
        error_type: str = "",
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_dcm4chee_mwl_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
            connection.execute(
                """
                UPDATE local_dcm4chee_mwl_attempts
                SET attempt_status = ?, http_status = ?, response_body = ?,
                    error_type = ?, error_text = ?, completed_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    attempt_status,
                    http_status,
                    response_body,
                    error_type,
                    error_text,
                    timestamp,
                    timestamp,
                    attempt_id,
                ),
            )
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def get_dcm4chee_mwl_attempt(self, attempt_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_dcm4chee_mwl_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
            if not row:
                raise KeyError(attempt_id)
        return self._dcm4chee_mwl_attempt_dict(row)

    def list_dcm4chee_mwl_attempts(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_attempts
                    ORDER BY attempted_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_dcm4chee_mwl_attempts
                    WHERE order_record_id = ?
                    ORDER BY attempted_at DESC, id DESC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [self._dcm4chee_mwl_attempt_dict(row) for row in rows]

    def create_dcm4chee_mwl_verification_attempt(
        self,
        order_record_id: int,
        mapping: dict[str, Any],
        *,
        request_url: str,
        query_criteria: dict[str, str],
        attempt_status: str = DCM4CHEE_MWL_STATUS_PENDING,
        error_type: str = "",
        error_text: str = "",
        http_status: int | None = None,
        response_body: str = "",
    ) -> dict[str, Any]:
        now = now_iso()
        with self.lock, self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_attempts (
                    mapping_id, operation_type, order_record_id, profile_name,
                    server_identity, mwl_ae_title, scheduled_station_ae_title, local_dcm4chee_order_number,
                    accession_number, requested_procedure_id,
                    scheduled_procedure_step_id, study_instance_uid, uid_root,
                    request_url, request_payload_json, http_status, response_body,
                    attempt_status, error_type, error_text, attempted_at,
                    completed_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(mapping["id"]) if mapping.get("id") else None,
                    DCM4CHEE_MWL_OPERATION_VERIFY,
                    int(order_record_id),
                    str(mapping.get("profileName") or "").strip(),
                    str(mapping.get("serverIdentity") or "").strip(),
                    str(mapping.get("mwlAETitle") or "").strip(),
                    str(mapping.get("scheduledStationAETitle") or "").strip(),
                    str(mapping.get("localDcm4cheeOrderNumber") or "").strip(),
                    str(mapping.get("accessionNumber") or "").strip(),
                    str(mapping.get("requestedProcedureId") or "").strip(),
                    str(mapping.get("scheduledProcedureStepId") or "").strip(),
                    str(mapping.get("studyInstanceUid") or "").strip(),
                    str(mapping.get("uidRoot") or "").strip(),
                    request_url,
                    json.dumps(query_criteria, sort_keys=True),
                    http_status,
                    response_body,
                    attempt_status,
                    error_type,
                    error_text,
                    now,
                    now if attempt_status != DCM4CHEE_MWL_STATUS_PENDING else "",
                    now,
                    now,
                ),
            )
            attempt_id = int(cursor.lastrowid)
        return self.get_dcm4chee_mwl_attempt(attempt_id)

    def update_dcm4chee_mwl_verification_result(
        self,
        order_record_id: int,
        *,
        attempt_id: int,
        verification_status: str,
        method: str,
        query_criteria: dict[str, Any],
        match_payload: dict[str, Any] | None = None,
        error_type: str = "",
        error_text: str = "",
        error_payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            connection.execute(
                """
                UPDATE local_dcm4chee_mwl_mappings
                SET verification_status = ?,
                    last_verification_at = ?,
                    last_verification_method = ?,
                    last_verification_attempt_id = ?,
                    last_verification_query_json = ?,
                    last_verification_match_json = ?,
                    last_verification_error_type = ?,
                    last_verification_error_text = ?,
                    last_verification_error_payload_json = ?,
                    updated_at = ?
                WHERE order_record_id = ?
                """,
                (
                    verification_status,
                    timestamp,
                    method,
                    int(attempt_id),
                    json.dumps(query_criteria, sort_keys=True),
                    json.dumps(match_payload or {}, sort_keys=True),
                    error_type,
                    error_text,
                    json.dumps(error_payload or {}, sort_keys=True),
                    timestamp,
                    int(order_record_id),
                ),
            )
        return self.get_dcm4chee_mwl_mapping_for_order(int(order_record_id))

    def _synced_patient_reference_for_fhir_order(self, patient_record_id: int) -> str:
        patient = self.get_patient_record(patient_record_id)
        fhir = patient.get("fhir") or {}
        sync_status = (fhir.get("sync") or {}).get("status")
        reference = str((fhir.get("medplum") or {}).get("reference") or "").strip()
        if (
            patient.get("protocolVersion") != "FHIR R4"
            or sync_status != FHIR_SYNC_STATUS_SYNCED
            or not reference.startswith("Patient/")
        ):
            raise SimulatorValidationError(
                "FHIR Order requires a selected Patient with synced Medplum Patient/<id> reference."
            )
        return reference

    def create_fhir_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_fhir_order_payload(payload)
        patient_reference = self._synced_patient_reference_for_fhir_order(values["patient_record_id"])
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            patient_row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient_row:
                raise KeyError(values["patient_record_id"])
            cursor = connection.execute(
                """
                INSERT INTO local_order_records (
                    local_order_number, patient_record_id, protocol_version, message_type,
                    order_status, mrn, first_name, last_name, middle_name, dob, sex,
                    visit_id, patient_class, assigned_location, account_number,
                    placer_order_number, filler_order_number, priority, requested_at,
                    ordering_provider, clinical_indication, order_code, order_code_text,
                    alternate_code, alternate_code_text, alternate_code_system,
                    validation_status, validation_messages_json, payload_hl7,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    values["patient_record_id"],
                    FHIR_ORDER_PROTOCOL_VERSION,
                    FHIR_ORDER_MESSAGE_TYPE,
                    FHIR_ORDER_STATUS_CREATED,
                    patient_row["mrn"],
                    patient_row["first_name"],
                    patient_row["last_name"],
                    patient_row["middle_name"],
                    patient_row["dob"],
                    patient_row["sex"],
                    patient_row["visit_number"],
                    patient_row["patient_class"],
                    patient_row["assigned_location"],
                    patient_row["account_number"],
                    "",
                    "",
                    self._fhir_order_storage_priority(values["priority"]),
                    values["requested_at"],
                    values["ordering_provider"],
                    values["clinical_indication"],
                    values["order_code"],
                    values["order_code_text"],
                    values["alternate_code"],
                    values["alternate_code_text"],
                    values["alternate_code_system"],
                    "valid",
                    "[]",
                    "",
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_order_number = self._order_record_number(record_id)
            visit_id = patient_row["visit_number"] or self._order_visit_id(record_id)
            account_number = patient_row["account_number"] or self._order_account_number(record_id)
            resource = self._build_service_request_resource(
                values,
                record_id=record_id,
                local_order_number=local_order_number,
                patient_reference=patient_reference,
            )
            connection.execute(
                """
                UPDATE local_order_records
                SET local_order_number = ?, placer_order_number = ?, visit_id = ?,
                    account_number = ?, payload_hl7 = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    local_order_number,
                    local_order_number,
                    visit_id,
                    account_number,
                    json.dumps(resource, indent=2, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
        return self.get_order_record(record_id)

    def create_order_service_request_fhir_workflow_record(self, order: dict[str, Any]) -> dict[str, Any]:
        if order.get("protocolVersion") != FHIR_ORDER_PROTOCOL_VERSION:
            raise SimulatorValidationError("Order record is not FHIR mode.")
        resource = self._json_value(order.get("payload"), {})
        return self.create_fhir_workflow_record(
            {
                "localSourceType": "local_order_records",
                "localSourceId": str(order["id"]),
                "resourceType": "ServiceRequest",
                "resource": resource,
            }
        )

    def list_order_records(self, protocol_version: str = "") -> list[dict[str, Any]]:
        with self.connect() as connection:
            if protocol_version:
                rows = connection.execute(
                    """
                    SELECT * FROM local_order_records
                    WHERE protocol_version = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (protocol_version,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_order_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
        return self._order_record_dicts_with_fhir(rows)

    def get_order_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_order_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._order_record_dicts_with_fhir([row])[0]

    def update_order_send_result(
        self,
        record_id: int,
        *,
        order_status: str,
        ack_code: str = "",
        ack_control_id: str = "",
        ack_text: str = "",
        ack_payload: str = "",
        transport_error: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_order_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            connection.execute(
                """
                UPDATE local_order_records
                SET order_status = ?, ack_code = ?, ack_control_id = ?, ack_text = ?,
                    ack_payload = ?, transport_error = ?, last_sent_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    order_status,
                    ack_code,
                    ack_control_id,
                    ack_text,
                    ack_payload,
                    transport_error,
                    timestamp,
                    timestamp,
                    record_id,
                ),
            )
        return self.get_order_record(record_id)

    def list_oie_local_order_inventory(self) -> list[dict[str, Any]]:
        return self.list_order_records(ORDER_PROTOCOL_VERSION)

    @staticmethod
    def _gdt_order_record_number(record_id: int) -> str:
        return f"GDT-ORD-{record_id:06d}"

    @staticmethod
    def _gdt_patient_context_number(patient_record_id: int) -> str:
        return f"GDT-PAT-{patient_record_id:06d}"

    @staticmethod
    def _validate_gdt_patient_number(value: Any, field_name: str = "gdtPatientNumber") -> str:
        text = str(value or "").strip()
        if not text:
            return ""
        if len(text) > 64:
            raise SimulatorValidationError(f"{field_name} must be 64 characters or fewer.")
        if any(character in text for character in "\r\n"):
            raise SimulatorValidationError(f"{field_name} cannot contain line breaks.")
        _encode_gdt_text(text)
        return text

    @staticmethod
    def _gdt_patient_snapshot(patient_row: sqlite3.Row, gdt_patient_number: str) -> dict[str, Any]:
        return {
            "patientRecordId": patient_row["id"],
            "mrn": patient_row["mrn"],
            "gdtPatientNumber": gdt_patient_number,
            "firstName": patient_row["first_name"],
            "middleName": patient_row["middle_name"],
            "lastName": patient_row["last_name"],
            "dob": patient_row["dob"],
            "sex": patient_row["sex"],
            "visitNumber": patient_row["visit_number"],
        }

    @staticmethod
    def _gdt_attachment_filename(url: str, path: str = "") -> str:
        source = path or url
        return source.rstrip("/").replace("\\", "/").split("/")[-1] if source else ""

    @staticmethod
    def _is_url_reference(value: str) -> bool:
        return value.lower().startswith(("http://", "https://"))

    @staticmethod
    def _gdt_artifact_status(reference: str, bridge_root: str = "") -> tuple[str, dict[str, Any]]:
        normalized = str(reference or "").strip()
        if not normalized:
            return "missing-reference", {"warning": "Artifact reference is empty."}
        if DemoStore._is_url_reference(normalized):
            return "reference-only", {"kind": "url"}
        reference_path = Path(normalized)
        candidates = [reference_path]
        if bridge_root and not reference_path.is_absolute():
            root = Path(bridge_root)
            candidates.extend([root / normalized, root / "reports" / normalized])
        if any(candidate.exists() for candidate in candidates):
            return "available", {"kind": "path"}
        return "warning", {"warning": "Referenced artifact target was not found.", "reference": normalized}

    def _record_gdt_event(
        self,
        connection: sqlite3.Connection,
        *,
        event_type: str,
        timestamp: str,
        order_record_id: int | None = None,
        patient_context_id: int | None = None,
        message_record_id: int | None = None,
        attachment_record_id: int | None = None,
        actor: str = "",
        details: dict[str, Any] | None = None,
    ) -> int:
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_workflow_events (
                order_record_id, patient_context_id, message_record_id,
                attachment_record_id, event_type, actor, details_json, created_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                patient_context_id,
                message_record_id,
                attachment_record_id,
                event_type,
                actor,
                json.dumps(details or {}, sort_keys=True),
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _ensure_gdt_patient_context(
        self,
        connection: sqlite3.Connection,
        patient_row: sqlite3.Row,
        *,
        override: str = "",
        timestamp: str,
    ) -> sqlite3.Row:
        context = connection.execute(
            """
            SELECT * FROM local_gdt_patient_contexts
            WHERE patient_record_id = ?
            """,
            (patient_row["id"],),
        ).fetchone()
        generated = self._gdt_patient_context_number(int(patient_row["id"]))
        override = self._validate_gdt_patient_number(override, "gdtPatientNumberOverride")
        effective = override or generated
        patient_snapshot_json = json.dumps(
            self._gdt_patient_snapshot(patient_row, effective),
            sort_keys=True,
        )
        if not context:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO local_gdt_patient_contexts (
                        patient_record_id, generated_gdt_patient_number,
                        gdt_patient_number_override, effective_gdt_patient_number,
                        patient_snapshot_json, created_at, updated_at
                    )
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        patient_row["id"],
                        generated,
                        override,
                        effective,
                        patient_snapshot_json,
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            context_id = int(cursor.lastrowid)
            self._record_gdt_event(
                connection,
                event_type="patient-number-generated",
                patient_context_id=context_id,
                timestamp=timestamp,
                details={"generatedGdtPatientNumber": generated},
            )
            if override:
                self._record_gdt_event(
                    connection,
                    event_type="patient-number-overridden",
                    patient_context_id=context_id,
                    timestamp=timestamp,
                    details={
                        "generatedGdtPatientNumber": generated,
                        "effectiveGdtPatientNumber": effective,
                    },
                )
        elif override and override != context["gdt_patient_number_override"]:
            try:
                connection.execute(
                    """
                    UPDATE local_gdt_patient_contexts
                    SET gdt_patient_number_override = ?,
                        effective_gdt_patient_number = ?,
                        patient_snapshot_json = ?,
                        updated_at = ?
                    WHERE id = ?
                    """,
                    (override, effective, patient_snapshot_json, timestamp, context["id"]),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("GDT patient number must be unique.") from exc
            self._record_gdt_event(
                connection,
                event_type="patient-number-overridden",
                patient_context_id=context["id"],
                timestamp=timestamp,
                details={
                    "previousGdtPatientNumber": context["effective_gdt_patient_number"],
                    "effectiveGdtPatientNumber": effective,
                },
            )
        else:
            effective = context["effective_gdt_patient_number"]
            patient_snapshot_json = json.dumps(
                self._gdt_patient_snapshot(patient_row, effective),
                sort_keys=True,
            )
            connection.execute(
                """
                UPDATE local_gdt_patient_contexts
                SET patient_snapshot_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (patient_snapshot_json, timestamp, context["id"]),
            )
        return connection.execute(
            """
            SELECT * FROM local_gdt_patient_contexts
            WHERE patient_record_id = ?
            """,
            (patient_row["id"],),
        ).fetchone()

    def _create_gdt_message_record(
        self,
        connection: sqlite3.Connection,
        *,
        order_record_id: int | None,
        patient_context_id: int | None,
        direction: str,
        raw_gdt_text: str,
        canonical: dict[str, Any],
        timestamp: str,
        match_status: str = "",
        error_text: str = "",
    ) -> int:
        parsed_fields = parse_gdt_message(raw_gdt_text)
        message_type = first_gdt_field(parsed_fields, "8000")
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_message_records (
                order_record_id, patient_context_id, direction, message_type,
                raw_gdt_text, parsed_fields_json, canonical_json, parse_status,
                match_status, error_text, generated_at, received_at,
                created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, 'accepted', ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                patient_context_id,
                direction,
                message_type,
                raw_gdt_text,
                json.dumps(parsed_fields, sort_keys=True),
                json.dumps(canonical, sort_keys=True),
                match_status,
                error_text,
                timestamp if direction == "outbound" else "",
                timestamp if direction == "inbound" else "",
                timestamp,
                timestamp,
            ),
        )
        return int(cursor.lastrowid)

    def _create_gdt_attachment_record(
        self,
        connection: sqlite3.Connection,
        *,
        order_record_id: int | None,
        message_record_id: int | None,
        role: str,
        timestamp: str,
        url: str = "",
        path: str = "",
        reference: str = "",
        content_type: str = "",
        description: str = "",
        source_file: str = "",
        status: str = "",
        details: dict[str, Any] | None = None,
        filename: str = "",
        checksum: str = "",
    ) -> int:
        normalized_role = self._clean_order_text(role, "attachment role") or "other"
        normalized_url = self._clean_order_text(url, "attachment url")
        normalized_path = self._clean_order_text(path, "attachment path")
        normalized_reference = self._clean_order_text(reference, "attachment reference") or normalized_url or normalized_path
        normalized_filename = self._clean_order_text(filename, "attachment filename") or self._gdt_attachment_filename(
            normalized_url,
            normalized_path or normalized_reference,
        )
        cursor = connection.execute(
            """
            INSERT INTO local_gdt_attachment_records (
                order_record_id, message_record_id, role, url, path, reference,
                content_type, description, source_file, status, details_json,
                filename, checksum, created_at, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                order_record_id,
                message_record_id,
                normalized_role,
                normalized_url,
                normalized_path,
                normalized_reference,
                self._clean_order_text(content_type, "attachment contentType"),
                self._clean_order_text(description, "attachment description"),
                self._clean_order_text(source_file, "attachment sourceFile"),
                self._clean_order_text(status, "attachment status"),
                json.dumps(details or {}, sort_keys=True),
                normalized_filename,
                self._clean_order_text(checksum, "attachment checksum"),
                timestamp,
                timestamp,
            ),
        )
        attachment_id = int(cursor.lastrowid)
        self._record_gdt_event(
            connection,
            event_type="attachment-registered",
            order_record_id=order_record_id,
            message_record_id=message_record_id,
            attachment_record_id=attachment_id,
            timestamp=timestamp,
            details={
                "role": normalized_role,
                "filename": normalized_filename,
                "status": self._clean_order_text(status, "attachment status"),
            },
        )
        return attachment_id

    @staticmethod
    def _validate_gdt_8402_code(value: Any) -> str:
        normalized = str(value or GDT_ORDER_TEST_CODE).strip().upper()
        if normalized != GDT_ORDER_TEST_CODE:
            raise SimulatorValidationError(
                f"GDT ECG order MVP only supports {GDT_ORDER_TEST_CODE_FIELD}={GDT_ORDER_TEST_CODE}."
            )
        prefix = normalized[:-2]
        suffix = normalized[-2:]
        if (
            not 1 <= len(normalized) <= 6
            or not prefix.isalpha()
            or not prefix.isupper()
            or len(prefix) > 4
            or not suffix.isdigit()
        ):
            raise SimulatorValidationError(
                "GDT 8402 test code must use up to four uppercase letters followed by two digits."
            )
        return normalized

    def _validate_gdt_order_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("GDT order payload must be a JSON object.")
        try:
            patient_record_id = int(payload.get("patientRecordId"))
        except (TypeError, ValueError) as exc:
            raise SimulatorValidationError("GDT order patientRecordId is required.") from exc
        return {
            "patient_record_id": patient_record_id,
            "requested_at": self._normalize_requested_at(payload.get("requestedAt")),
            "ordering_provider": self._clean_order_text(payload.get("orderingProvider"), "orderingProvider"),
            "clinical_indication": self._clean_order_text(payload.get("clinicalIndication"), "clinicalIndication"),
            "attachment_url": self._clean_order_text(payload.get("attachmentUrl"), "attachmentUrl"),
            "gdt_patient_number_override": self._validate_gdt_patient_number(
                payload.get(
                    "gdtPatientNumberOverride",
                    payload.get("gdtPatientNumber", payload.get("patientNumberOverride", "")),
                ),
                "gdtPatientNumberOverride",
            ),
            "gdt_test_code": self._validate_gdt_8402_code(
                payload.get("gdtTestCode", payload.get("testCode", payload.get("examCode", GDT_ORDER_TEST_CODE)))
            ),
        }

    @staticmethod
    def _gdt_birth_date(dob: str) -> str:
        return f"{dob[6:]}{dob[4:6]}{dob[:4]}"

    @staticmethod
    def _build_gdt_order_payload(
        values: dict[str, Any],
        patient_row: sqlite3.Row,
        *,
        record_id: int,
    ) -> str:
        order_number = values.get("local_gdt_order_number") or DemoStore._gdt_order_record_number(record_id)
        try:
            return build_gdt_6302_request(
                {
                    "gdtPatientNumber": values["gdt_patient_number"],
                    "lastName": patient_row["last_name"],
                    "firstName": patient_row["first_name"],
                    "birthDate": DemoStore._gdt_birth_date(patient_row["dob"]),
                    "localGdtOrderNumber": order_number,
                    "sex": GDT_PATIENT_SEX_CODES.get(patient_row["sex"], ""),
                    "requestedAt": values.get("requested_at", ""),
                    "orderingProvider": values.get("ordering_provider", ""),
                    "clinicalIndication": values.get("clinical_indication", ""),
                    "patient": DemoStore._gdt_patient_snapshot(patient_row, values["gdt_patient_number"]),
                    "order": {"localGdtOrderNumber": order_number},
                    "testLabel": GDT_ORDER_TEST_LABEL,
                }
            ).raw_gdt_text
        except GdtValidationError as exc:
            raise SimulatorValidationError(str(exc)) from exc

    def create_gdt_order_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_gdt_order_payload(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            patient_row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (values["patient_record_id"],),
            ).fetchone()
            if not patient_row:
                raise KeyError(values["patient_record_id"])
            patient_context = self._ensure_gdt_patient_context(
                connection,
                patient_row,
                override=values["gdt_patient_number_override"],
                timestamp=timestamp,
            )
            gdt_patient_number = patient_context["effective_gdt_patient_number"]
            patient_snapshot = self._gdt_patient_snapshot(patient_row, gdt_patient_number)
            order_snapshot = {
                "requestedAt": values["requested_at"],
                "orderingProvider": values["ordering_provider"],
                "clinicalIndication": values["clinical_indication"],
                "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
                "gdtTestCode": values["gdt_test_code"],
                "gdtTestLabel": GDT_ORDER_TEST_LABEL,
            }
            cursor = connection.execute(
                """
                INSERT INTO local_gdt_order_records (
                    local_gdt_order_number, patient_record_id, gdt_patient_context_id,
                    protocol_version, message_type, order_status, mrn,
                    gdt_patient_number, first_name, last_name, middle_name, dob,
                    sex, visit_number, gdt_test_code,
                    gdt_test_label, requested_at, ordering_provider,
                    clinical_indication, attachment_url, payload_gdt,
                    patient_snapshot_json, order_snapshot_json,
                    created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "",
                    values["patient_record_id"],
                    patient_context["id"],
                    GDT_ORDER_PROTOCOL_VERSION,
                    GDT_ORDER_MESSAGE_TYPE,
                    GDT_ORDER_STATUS_CREATED,
                    patient_row["mrn"],
                    gdt_patient_number,
                    patient_row["first_name"],
                    patient_row["last_name"],
                    patient_row["middle_name"],
                    patient_row["dob"],
                    patient_row["sex"],
                    patient_row["visit_number"],
                    values["gdt_test_code"],
                    GDT_ORDER_TEST_LABEL,
                    values["requested_at"],
                    values["ordering_provider"],
                    values["clinical_indication"],
                    values["attachment_url"],
                    "",
                    json.dumps(patient_snapshot, sort_keys=True),
                    json.dumps(order_snapshot, sort_keys=True),
                    timestamp,
                    timestamp,
                ),
            )
            record_id = int(cursor.lastrowid)
            local_gdt_order_number = self._gdt_order_record_number(record_id)
            order_snapshot = {**order_snapshot, "localGdtOrderNumber": local_gdt_order_number}
            try:
                adapter_result = build_gdt_6302_request(
                    {
                        "gdtPatientNumber": gdt_patient_number,
                        "lastName": patient_row["last_name"],
                        "firstName": patient_row["first_name"],
                        "birthDate": self._gdt_birth_date(patient_row["dob"]),
                        "localGdtOrderNumber": local_gdt_order_number,
                        "sex": GDT_PATIENT_SEX_CODES.get(patient_row["sex"], ""),
                        "requestedAt": values["requested_at"],
                        "orderingProvider": values["ordering_provider"],
                        "clinicalIndication": values["clinical_indication"],
                        "patient": patient_snapshot,
                        "order": order_snapshot,
                        "testLabel": GDT_ORDER_TEST_LABEL,
                    }
                )
            except GdtValidationError as exc:
                raise SimulatorValidationError(str(exc)) from exc
            payload_gdt = adapter_result.raw_gdt_text
            canonical = adapter_result.canonical
            message_record_id = self._create_gdt_message_record(
                connection,
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                direction="outbound",
                raw_gdt_text=payload_gdt,
                canonical=canonical,
                timestamp=timestamp,
            )
            connection.execute(
                """
                UPDATE local_gdt_order_records
                SET local_gdt_order_number = ?, payload_gdt = ?,
                    order_snapshot_json = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    local_gdt_order_number,
                    payload_gdt,
                    json.dumps(order_snapshot, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
            self._record_gdt_event(
                connection,
                event_type="order-created",
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                timestamp=timestamp,
                details={"localGdtOrderNumber": local_gdt_order_number},
            )
            self._record_gdt_event(
                connection,
                event_type="message-generated",
                order_record_id=record_id,
                patient_context_id=patient_context["id"],
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"messageType": GDT_ORDER_MESSAGE_TYPE},
            )
            if values["attachment_url"]:
                self._create_gdt_attachment_record(
                    connection,
                    order_record_id=record_id,
                    message_record_id=message_record_id,
                    role="order-attachment",
                    url=values["attachment_url"],
                    timestamp=timestamp,
                )
        return self.get_gdt_order_record(record_id)

    def list_gdt_order_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_gdt_order_records
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._gdt_order_record_dict(row) for row in rows]

    def get_gdt_order_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_order_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._gdt_order_record_dict(row)

    def list_gdt_messages(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_message_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_message_records
                    WHERE order_record_id = ?
                    ORDER BY created_at DESC, id DESC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [self._gdt_message_record_dict(row) for row in rows]

    def list_gdt_events(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_workflow_events
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                order_row = connection.execute(
                    "SELECT gdt_patient_context_id FROM local_gdt_order_records WHERE id = ?",
                    (order_record_id,),
                ).fetchone()
                patient_context_id = order_row["gdt_patient_context_id"] if order_row else None
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_workflow_events
                    WHERE order_record_id = ?
                       OR (
                         ? IS NOT NULL
                         AND patient_context_id = ?
                         AND order_record_id IS NULL
                       )
                    ORDER BY created_at ASC, id ASC
                    """,
                    (order_record_id, patient_context_id, patient_context_id),
                ).fetchall()
        return [self._gdt_event_record_dict(row) for row in rows]

    def list_gdt_attachments(self, order_record_id: int | None = None) -> list[dict[str, Any]]:
        with self.connect() as connection:
            if order_record_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_attachment_records
                    ORDER BY created_at DESC, id DESC
                    """
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_gdt_attachment_records
                    WHERE order_record_id = ?
                    ORDER BY created_at ASC, id ASC
                    """,
                    (order_record_id,),
                ).fetchall()
        return [self._gdt_attachment_record_dict(row) for row in rows]

    def record_gdt_order_export(
        self,
        order_record_id: int,
        *,
        export_path: str,
        status: str,
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_order_records WHERE id = ?",
                (order_record_id,),
            ).fetchone()
            if not row:
                raise KeyError(order_record_id)
            connection.execute(
                """
                UPDATE local_gdt_order_records
                SET export_path = ?, error_text = ?, updated_at = ?
                WHERE id = ?
                """,
                (export_path, error_text, timestamp, order_record_id),
            )
            self._record_gdt_event(
                connection,
                event_type="order-exported" if status == "exported" else "order-export-failed",
                order_record_id=order_record_id,
                patient_context_id=row["gdt_patient_context_id"],
                timestamp=timestamp,
                details={"status": status, "path": export_path, "error": error_text},
            )
        return self.get_gdt_order_record(order_record_id)

    def create_gdt_demo_result(self, order_record_id: int) -> dict[str, Any]:
        order = self.get_gdt_order_record(order_record_id)
        order_number = order["localGdtOrderNumber"]
        artifact_prefix = order_number.lower()
        raw_gdt_text = render_gdt_message(
            [
                ("8315", "HCLAB"),
                ("8316", "DEMOECG"),
                ("3000", order["gdtPatientNumber"]),
                ("3101", order["patientSnapshot"].get("lastName", "")),
                ("3102", order["patientSnapshot"].get("firstName", "")),
                ("6200", order_number),
                ("8402", GDT_ORDER_TEST_CODE),
                ("8410", "HR"),
                ("8420", "72"),
                ("8421", "bpm"),
                ("8410", "PR"),
                ("8420", "160"),
                ("8421", "ms"),
                ("8410", "QRS"),
                ("8420", "92"),
                ("8421", "ms"),
                ("8410", "QT"),
                ("8420", "390"),
                ("8421", "ms"),
                ("8410", "QTC"),
                ("8420", "427"),
                ("8421", "ms"),
                ("8418", "final"),
                ("6220", "Normal sinus rhythm. No acute ST-T changes."),
                ("6227", "Demo ECG generated by Healthcare Lab."),
                ("6228", "Measurements are deterministic for bridge validation."),
                ("6302", "report"),
                ("6303", "PDF"),
                ("6304", "ECG PDF report"),
                ("6305", f"reports/{artifact_prefix}-report.pdf"),
                ("6302", "dicom"),
                ("6303", "DICOM"),
                ("6304", "DICOM ECG object reference"),
                ("6305", f"reports/{artifact_prefix}.dcm"),
            ],
            set_type=GDT_RESULT_MESSAGE_TYPE,
        )
        return self.record_gdt_result({"rawGdtText": raw_gdt_text, "sourceFile": "demo-result"})

    def list_gdt_workbench(self, *, bridge_inbox: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        patients = self.list_patient_records()
        orders = self.list_gdt_order_records()
        messages = self.list_gdt_messages()
        inbound_results = [
            item for item in messages
            if item.get("direction") == "inbound" and item.get("messageType") == GDT_RESULT_MESSAGE_TYPE
        ]
        attachments = self.list_gdt_attachments()
        orders_by_patient: dict[int, list[dict[str, Any]]] = {}
        results_by_order: dict[int, list[dict[str, Any]]] = {}
        results_by_patient_context: dict[int, list[dict[str, Any]]] = {}
        attachments_by_message: dict[int, list[dict[str, Any]]] = {}
        for order in orders:
            orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
        for result in inbound_results:
            if result.get("orderRecordId"):
                results_by_order.setdefault(int(result["orderRecordId"]), []).append(result)
            if result.get("patientContextId"):
                results_by_patient_context.setdefault(int(result["patientContextId"]), []).append(result)
        for attachment in attachments:
            if attachment.get("messageRecordId"):
                attachments_by_message.setdefault(int(attachment["messageRecordId"]), []).append(attachment)
        for result in inbound_results:
            result["attachments"] = attachments_by_message.get(int(result["id"]), [])
        workbench_patients = []
        for patient in patients:
            patient_id = int(patient["id"])
            patient_orders = orders_by_patient.get(patient_id, [])
            if not patient_orders and patient.get("protocolVersion") != GDT_ORDER_PROTOCOL_VERSION:
                continue
            patient_context_ids = {
                int(order["gdtPatientContextId"])
                for order in patient_orders
                if order.get("gdtPatientContextId")
            }
            patient_results = [
                result
                for context_id in patient_context_ids
                for result in results_by_patient_context.get(context_id, [])
            ]
            item = {
                **patient,
                "orders": patient_orders,
                "results": patient_results,
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            item["summary"] = {
                **item["summary"],
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            workbench_patients.append(item)
        unmatched_results = [
            result for result in inbound_results
            if not result.get("orderRecordId") and not result.get("patientContextId")
        ]
        return {
            "patients": workbench_patients,
            "orders": orders,
            "results": inbound_results,
            "unmatchedResults": unmatched_results,
            "attachments": attachments,
            "bridgeInbox": bridge_inbox or [],
            "resultsByOrder": results_by_order,
        }

    @staticmethod
    def _attachment_payloads_from_result_fields(fields: dict[str, list[str]]) -> list[dict[str, str]]:
        return attachment_payloads_from_result_fields(fields)

    @staticmethod
    def _gdt_result_measurements(fields: dict[str, list[str]]) -> dict[str, str]:
        return {
            label: first_gdt_field(fields, code)
            for label, code in (
                ("HR", "8401"),
                ("PR", "8402"),
                ("QRS", "8403"),
                ("QT", "8404"),
                ("QTC", "8405"),
            )
            if first_gdt_field(fields, code)
        }

    def record_gdt_result(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("GDT result payload must be a JSON object.")
        raw_gdt_text = str(
            payload.get("rawGdtText", payload.get("payload", payload.get("raw", ""))) or ""
        )
        source_file = str(payload.get("sourceFile") or payload.get("source_file") or "").strip()
        try:
            adapter_result = parse_gdt_6310_result(raw_gdt_text)
        except GdtValidationError as exc:
            raise SimulatorValidationError(str(exc)) from exc
        fields = adapter_result.parsed_fields
        timestamp = now_iso()
        order_identifiers = [
            value
            for code in ("6330", "6200", "8410")
            for value in fields.get(code, [])
            if value
        ]
        gdt_patient_number = first_gdt_field(fields, "3000")
        with self.lock, self.connect() as connection:
            order_row = None
            if order_identifiers:
                placeholders = ", ".join("?" for _ in order_identifiers)
                order_row = connection.execute(
                    f"""
                    SELECT * FROM local_gdt_order_records
                    WHERE local_gdt_order_number IN ({placeholders})
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    order_identifiers,
                ).fetchone()
            patient_context_id = order_row["gdt_patient_context_id"] if order_row else None
            if not patient_context_id and gdt_patient_number:
                context_row = connection.execute(
                    """
                    SELECT * FROM local_gdt_patient_contexts
                    WHERE effective_gdt_patient_number = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (gdt_patient_number,),
                ).fetchone()
                patient_context_id = context_row["id"] if context_row else None
            match_status = "order-matched" if order_row else "unmatched"
            canonical = adapter_result.canonical
            canonical["order"] = {
                **canonical.get("order", {}),
                "localGdtOrderNumber": order_row["local_gdt_order_number"] if order_row else "",
                "identifiers": order_identifiers,
            }
            canonical["correlation"] = {
                **canonical.get("correlation", {}),
                "matchStatus": match_status,
                "identifiers": order_identifiers,
            }
            message_record_id = self._create_gdt_message_record(
                connection,
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                direction="inbound",
                raw_gdt_text=raw_gdt_text,
                canonical=canonical,
                timestamp=timestamp,
                match_status=match_status,
            )
            attachment_payloads = canonical["attachments"] + list(payload.get("attachments") or [])
            for attachment in attachment_payloads:
                if not isinstance(attachment, dict):
                    continue
                reference = str(attachment.get("reference") or "")
                path = str(attachment.get("path") or "")
                url = str(attachment.get("url") or "")
                artifact_status, artifact_details = self._gdt_artifact_status(
                    reference or path or url,
                    str(payload.get("bridgeRoot") or payload.get("bridge_root") or ""),
                )
                explicit_status = str(attachment.get("status") or "")
                details = attachment.get("details") if isinstance(attachment.get("details"), dict) else {}
                self._create_gdt_attachment_record(
                    connection,
                    order_record_id=order_row["id"] if order_row else None,
                    message_record_id=message_record_id,
                    role=str(attachment.get("role") or "result-artifact"),
                    url=url,
                    path=path,
                    reference=reference,
                    content_type=str(attachment.get("contentType") or attachment.get("content_type") or ""),
                    description=str(attachment.get("description") or ""),
                    source_file=str(attachment.get("sourceFile") or attachment.get("source_file") or source_file),
                    status=explicit_status or artifact_status,
                    details={**artifact_details, **details},
                    filename=str(attachment.get("filename") or ""),
                    checksum=str(attachment.get("checksum") or ""),
                    timestamp=timestamp,
                )
            self._record_gdt_event(
                connection,
                event_type="result-imported",
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"messageType": GDT_RESULT_MESSAGE_TYPE, "matchStatus": match_status},
            )
            self._record_gdt_event(
                connection,
                event_type="result-matched" if order_row else "result-unmatched",
                order_record_id=order_row["id"] if order_row else None,
                patient_context_id=patient_context_id,
                message_record_id=message_record_id,
                timestamp=timestamp,
                details={"identifiers": order_identifiers},
            )
            if order_row:
                connection.execute(
                    """
                    UPDATE local_gdt_order_records
                    SET order_status = ?, updated_at = ?
                    WHERE id = ?
                    """,
                    (GDT_ORDER_STATUS_RESULT_RECEIVED, timestamp, order_row["id"]),
                )
                self._record_gdt_event(
                    connection,
                    event_type="status-changed",
                    order_record_id=order_row["id"],
                    patient_context_id=patient_context_id,
                    message_record_id=message_record_id,
                    timestamp=timestamp,
                    details={"status": GDT_ORDER_STATUS_RESULT_RECEIVED},
                )
        return self._gdt_message_record_dict_by_id(message_record_id)

    def record_oie_result(self, payload_hl7: str, parsed: dict[str, str]) -> dict[str, Any]:
        timestamp = now_iso()
        message_control_id = str(parsed.get("messageControlId") or "").strip()
        message_type = str(parsed.get("messageType") or "").strip()
        patient_mrn = str(parsed.get("patientMrn") or "").strip()
        placer_order_number = str(parsed.get("placerOrderNumber") or "").strip()
        filler_order_number = str(parsed.get("fillerOrderNumber") or "").strip()
        with self.lock, self.connect() as connection:
            if message_control_id:
                duplicate = connection.execute(
                    """
                    SELECT * FROM oie_result_records
                    WHERE message_control_id = ?
                    """,
                    (message_control_id,),
                ).fetchone()
                if duplicate:
                    item = self._result_record_dict(duplicate)
                    item["duplicate"] = True
                    item["duplicateOfId"] = duplicate["id"]
                    return item
            patient_row = None
            if patient_mrn:
                patient_row = connection.execute(
                    """
                    SELECT * FROM local_patient_records
                    WHERE mrn = ? AND protocol_version = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (patient_mrn, PATIENT_MODES["hl7-v2"]["protocol"]),
                ).fetchone()
            order_row = None
            if patient_row and (placer_order_number or filler_order_number):
                order_row = connection.execute(
                    """
                    SELECT * FROM local_order_records
                    WHERE patient_record_id = ? AND protocol_version = ?
                      AND (
                        (? != '' AND placer_order_number = ?)
                        OR (? != '' AND filler_order_number = ?)
                        OR (? != '' AND local_order_number = ?)
                      )
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (
                        patient_row["id"],
                        ORDER_PROTOCOL_VERSION,
                        placer_order_number,
                        placer_order_number,
                        filler_order_number,
                        filler_order_number,
                        filler_order_number,
                        filler_order_number,
                    ),
                ).fetchone()
            if order_row:
                match_status = "order-matched"
            elif patient_row:
                match_status = "patient-only"
            else:
                match_status = "unmatched-patient"
            cursor = connection.execute(
                """
                INSERT INTO oie_result_records (
                    message_control_id, message_type, patient_mrn, placer_order_number,
                    filler_order_number, matched_patient_record_id, matched_order_record_id,
                    match_status, duplicate_of_id, parse_status, error_text, payload_hl7,
                    received_at, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, NULL, 'accepted', '', ?, ?, ?, ?)
                """,
                (
                    message_control_id,
                    message_type,
                    patient_mrn,
                    placer_order_number,
                    filler_order_number,
                    patient_row["id"] if patient_row else None,
                    order_row["id"] if order_row else None,
                    match_status,
                    payload_hl7,
                    timestamp,
                    timestamp,
                    timestamp,
                ),
            )
            result_id = int(cursor.lastrowid)
            row = connection.execute(
                "SELECT * FROM oie_result_records WHERE id = ?",
                (result_id,),
            ).fetchone()
        return self._result_record_dict(row)

    def record_oie_result_error(self, payload_hl7: str, message_type: str, error_text: str) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            cursor = connection.execute(
                """
                INSERT INTO oie_result_records (
                    message_control_id, message_type, patient_mrn, placer_order_number,
                    filler_order_number, matched_patient_record_id, matched_order_record_id,
                    match_status, duplicate_of_id, parse_status, error_text, payload_hl7,
                    received_at, created_at, updated_at
                )
                VALUES ('', ?, '', '', '', NULL, NULL, 'unmatched-patient', NULL, 'error', ?, ?, ?, ?, ?)
                """,
                (message_type, error_text, payload_hl7, timestamp, timestamp, timestamp),
            )
            row = connection.execute(
                "SELECT * FROM oie_result_records WHERE id = ?",
                (int(cursor.lastrowid),),
            ).fetchone()
        return self._result_record_dict(row)

    def list_oie_results(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM oie_result_records
                ORDER BY received_at DESC, id DESC
                """
            ).fetchall()
        return [self._result_record_dict(row) for row in rows]

    def list_oie_workbench(self) -> dict[str, Any]:
        patients = self.list_patient_records(PATIENT_MODES["hl7-v2"]["protocol"])
        orders = self.list_order_records(ORDER_PROTOCOL_VERSION)
        results = self.list_oie_results()
        orders_by_patient: dict[int, list[dict[str, Any]]] = {}
        results_by_patient: dict[int, list[dict[str, Any]]] = {}
        unmatched_results: list[dict[str, Any]] = []
        for order in orders:
            orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
        visible_patient_ids = {int(patient["id"]) for patient in patients}
        for result in results:
            patient_id = result.get("matchedPatientRecordId")
            if patient_id and int(patient_id) in visible_patient_ids:
                results_by_patient.setdefault(int(patient_id), []).append(result)
            else:
                unmatched_results.append(result)
        workbench_patients = []
        for patient in patients:
            patient_id = int(patient["id"])
            patient_orders = orders_by_patient.get(patient_id, [])
            patient_results = results_by_patient.get(patient_id, [])
            item = {
                **patient,
                "orders": patient_orders,
                "results": patient_results,
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            item["summary"] = {
                **item["summary"],
                "orderCount": len(patient_orders),
                "resultCount": len(patient_results),
            }
            workbench_patients.append(item)
        return {"patients": workbench_patients, "unmatchedResults": unmatched_results}

    def _order_record_dicts_with_fhir(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        source_ids = [str(row["id"]) for row in rows]
        fhir_by_source_id: dict[str, dict[str, dict[str, Any]]] = {}
        dcm4chee_by_source_id: dict[str, dict[str, Any]] = {}
        dcm4chee_mapping_by_source_id: dict[str, dict[str, Any]] = {}
        if source_ids:
            placeholders = ", ".join("?" for _ in source_ids)
            with self.connect() as connection:
                fhir_rows = connection.execute(
                    f"""
                    SELECT * FROM local_fhir_workflow_records
                    WHERE local_source_type = 'local_order_records'
                    AND local_source_id IN ({placeholders})
                    AND resource_type = 'ServiceRequest'
                    """,
                    source_ids,
                ).fetchall()
                dcm4chee_rows = connection.execute(
                    f"""
                    SELECT * FROM local_dcm4chee_mwl_attempts
                    WHERE order_record_id IN ({placeholders})
                    ORDER BY attempted_at DESC, id DESC
                    """,
                    [int(source_id) for source_id in source_ids],
                ).fetchall()
                dcm4chee_mapping_rows = connection.execute(
                    f"""
                    SELECT * FROM local_dcm4chee_mwl_mappings
                    WHERE order_record_id IN ({placeholders})
                    """,
                    [int(source_id) for source_id in source_ids],
                ).fetchall()
            for fhir_row in fhir_rows:
                source_id = str(fhir_row["local_source_id"])
                fhir_by_source_id.setdefault(source_id, {})[fhir_row["resource_type"]] = (
                    self._fhir_workflow_record_dict(fhir_row)
                )
            for dcm4chee_row in dcm4chee_rows:
                source_id = str(dcm4chee_row["order_record_id"])
                if source_id not in dcm4chee_by_source_id:
                    dcm4chee_by_source_id[source_id] = self._dcm4chee_mwl_attempt_dict(dcm4chee_row)
            for mapping_row in dcm4chee_mapping_rows:
                source_id = str(mapping_row["order_record_id"])
                dcm4chee_mapping_by_source_id[source_id] = self._dcm4chee_mwl_mapping_dict(mapping_row)
        return [
            self._order_record_dict(
                row,
                fhir_by_source_id.get(str(row["id"]), {}),
                dcm4chee_by_source_id.get(str(row["id"])),
                dcm4chee_mapping_by_source_id.get(str(row["id"])),
            )
            for row in rows
        ]

    @staticmethod
    def _order_record_dict(
        row: sqlite3.Row,
        fhir_records: dict[str, dict[str, Any]] | None = None,
        dcm4chee_attempt: dict[str, Any] | None = None,
        dcm4chee_mapping: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        validation_messages = json.loads(row["validation_messages_json"] or "[]")
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
        fhir_records = fhir_records or {}
        service_request = fhir_records.get("ServiceRequest")
        return {
            "id": row["id"],
            "localOrderNumber": row["local_order_number"],
            "patientRecordId": row["patient_record_id"],
            "protocolVersion": row["protocol_version"],
            "messageType": row["message_type"],
            "status": row["order_status"],
            "patient": {
                "mrn": row["mrn"],
                "firstName": row["first_name"],
                "lastName": row["last_name"],
                "middleName": row["middle_name"],
                "dob": row["dob"],
                "sex": row["sex"],
            },
            "summary": {
                "mrn": row["mrn"],
                "name": summary_name,
                "dob": row["dob"],
                "sex": row["sex"],
                "visitNumber": row["visit_id"],
                "visitId": row["visit_id"],
                "orderCode": row["order_code"],
                "orderText": row["order_code_text"],
            },
            "visitNumber": row["visit_id"],
            "visitId": row["visit_id"],
            "patientClass": row["patient_class"],
            "assignedLocation": row["assigned_location"],
            "accountNumber": row["account_number"],
            "placerOrderNumber": row["placer_order_number"],
            "fillerOrderNumber": row["filler_order_number"],
            "priority": row["priority"],
            "requestedAt": row["requested_at"],
            "orderingProvider": row["ordering_provider"],
            "clinicalIndication": row["clinical_indication"],
            "orderCode": row["order_code"],
            "orderCodeText": row["order_code_text"],
            "alternateCode": row["alternate_code"],
            "alternateCodeText": row["alternate_code_text"],
            "alternateCodeSystem": row["alternate_code_system"],
            "fhir": {
                "serviceRequest": service_request,
            }
            if row["protocol_version"] == FHIR_ORDER_PROTOCOL_VERSION
            else None,
            "dcm4chee": {
                "mwl": DemoStore._dcm4chee_mwl_status_view(dcm4chee_attempt, dcm4chee_mapping)
                if dcm4chee_attempt or dcm4chee_mapping
                else None,
            }
            if row["protocol_version"] == DCM4CHEE_ORDER_PROTOCOL_VERSION or dcm4chee_attempt or dcm4chee_mapping
            else None,
            "validation": {
                "status": row["validation_status"],
                "messages": validation_messages,
            },
            "payload": row["payload_hl7"],
            "ack": {
                "code": row["ack_code"],
                "controlId": row["ack_control_id"],
                "text": row["ack_text"],
                "payload": row["ack_payload"],
            },
            "transportError": row["transport_error"],
            "lastSentAt": row["last_sent_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": True,
        }

    @staticmethod
    def _dcm4chee_result_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        raw_metadata = DemoStore._json_value(row["raw_metadata_json"], {})
        diagnostic = DemoStore._json_value(row["diagnostic_payload_json"], {})
        artifact = raw_metadata.get("artifact") if isinstance(raw_metadata.get("artifact"), dict) else {}
        return {
            "id": row["id"],
            "resultKey": row["result_key"],
            "patientRecordId": row["patient_record_id"],
            "orderRecordId": row["order_record_id"],
            "mappingId": row["mapping_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "sourceAETitle": row["source_ae_title"],
            "studyInstanceUid": row["study_instance_uid"],
            "seriesInstanceUid": row["series_instance_uid"],
            "sopInstanceUid": row["sop_instance_uid"],
            "accessionNumber": row["accession_number"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "requestedProcedureId": row["requested_procedure_id"],
            "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
            "modality": row["modality"],
            "studyDateTime": row["study_datetime"],
            "seriesDateTime": row["series_datetime"],
            "instanceDateTime": row["instance_datetime"],
            "viewerUrl": row["viewer_url"],
            "studyRetrieveUrl": row["study_retrieve_url"],
            "seriesRetrieveUrl": row["series_retrieve_url"],
            "instanceRetrieveUrl": row["instance_retrieve_url"],
            "reconciliationStatus": row["reconciliation_status"],
            "matchMethod": row["match_method"],
            "matchStrength": row["match_strength"],
            "queryUrl": row["query_url"],
            "queryPayload": DemoStore._json_value(row["query_payload_json"], {}),
            "diagnostic": diagnostic,
            "rawMetadata": raw_metadata,
            "source": raw_metadata.get("source", "") if isinstance(raw_metadata, dict) else "",
            "sourceType": raw_metadata.get("type", "") if isinstance(raw_metadata, dict) else "",
            "artifact": artifact,
            "refreshGeneration": row["refresh_generation"] if "refresh_generation" in row.keys() else "",
            "firstSeenAt": row["first_seen_at"],
            "lastRefreshedAt": row["last_refreshed_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _dcm4chee_mwl_attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        request_payload = DemoStore._json_value(row["request_payload_json"], {})
        return {
            "id": row["id"],
            "mappingId": row["mapping_id"] if "mapping_id" in row.keys() else None,
            "operationType": row["operation_type"] if "operation_type" in row.keys() else DCM4CHEE_MWL_OPERATION_CREATE,
            "orderRecordId": row["order_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "mwlAETitle": row["mwl_ae_title"],
            "scheduledStationAETitle": row["scheduled_station_ae_title"],
            "localDcm4cheeOrderNumber": row["local_dcm4chee_order_number"],
            "accessionNumber": row["accession_number"],
            "requestedProcedureId": row["requested_procedure_id"],
            "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
            "studyInstanceUid": row["study_instance_uid"],
            "uidRoot": row["uid_root"],
            "requestUrl": row["request_url"],
            "requestPayload": request_payload,
            "httpStatus": row["http_status"],
            "responseBody": row["response_body"],
            "status": row["attempt_status"],
            "errorType": row["error_type"],
            "error": row["error_text"],
            "attemptedAt": row["attempted_at"],
            "completedAt": row["completed_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _dcm4chee_mwl_mapping_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "mwlAETitle": row["mwl_ae_title"],
            "scheduledStationAETitle": row["scheduled_station_ae_title"],
            "localDcm4cheeOrderNumber": row["local_dcm4chee_order_number"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "accessionNumber": row["accession_number"],
            "requestedProcedureId": row["requested_procedure_id"],
            "scheduledProcedureStepId": row["scheduled_procedure_step_id"],
            "studyInstanceUid": row["study_instance_uid"],
            "worklistLabel": row["worklist_label"],
            "uidRoot": row["uid_root"],
            "status": row["sync_status"],
            "lastSyncAt": row["last_sync_at"],
            "retryCount": row["retry_count"],
            "lastAttemptId": row["last_attempt_id"],
            "lastHttpStatus": row["last_http_status"],
            "lastResponseBody": row["last_response_body"],
            "lastErrorType": row["last_error_type"],
            "lastError": row["last_error_text"],
            "lastErrorPayload": DemoStore._json_value(row["last_error_payload_json"], {}),
            "latestRequestPayload": DemoStore._json_value(row["latest_request_payload_json"], {}),
            "latestReadbackPayload": DemoStore._json_value(row["latest_readback_payload_json"], {}),
            "verification": {
                "status": row["verification_status"] if "verification_status" in row.keys() else DCM4CHEE_MWL_VERIFICATION_NOT_VERIFIED,
                "lastVerifiedAt": row["last_verification_at"] if "last_verification_at" in row.keys() else "",
                "method": row["last_verification_method"] if "last_verification_method" in row.keys() else "",
                "attemptId": row["last_verification_attempt_id"] if "last_verification_attempt_id" in row.keys() else None,
                "query": DemoStore._json_value(
                    row["last_verification_query_json"] if "last_verification_query_json" in row.keys() else "{}",
                    {},
                ),
                "match": DemoStore._json_value(
                    row["last_verification_match_json"] if "last_verification_match_json" in row.keys() else "{}",
                    {},
                ),
                "errorType": row["last_verification_error_type"]
                if "last_verification_error_type" in row.keys()
                else "",
                "error": row["last_verification_error_text"]
                if "last_verification_error_text" in row.keys()
                else "",
                "errorPayload": DemoStore._json_value(
                    row["last_verification_error_payload_json"]
                    if "last_verification_error_payload_json" in row.keys()
                    else "{}",
                    {},
                ),
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _dcm4chee_mwl_status_view(
        attempt: dict[str, Any] | None,
        mapping: dict[str, Any] | None,
    ) -> dict[str, Any]:
        attempt = attempt or {}
        mapping = mapping or {}
        status = str(mapping.get("status") or attempt.get("status") or "").strip()
        error_type = str(mapping.get("lastErrorType") or attempt.get("errorType") or "").strip()
        error_text = str(mapping.get("lastError") or attempt.get("error") or "").strip()
        response_body = str(mapping.get("lastResponseBody") or attempt.get("responseBody") or "").strip()
        http_status = mapping.get("lastHttpStatus") or attempt.get("httpStatus")
        retryable = DemoStore._dcm4chee_mwl_retryable(status, error_type)
        display_status, display_state = DemoStore._dcm4chee_mwl_display_status(status, retryable)
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

    @staticmethod
    def _dcm4chee_mwl_retryable(status: str, error_type: str = "") -> bool:
        normalized_error = str(error_type or "").strip()
        if normalized_error in DCM4CHEE_MWL_NON_RETRYABLE_ERROR_TYPES:
            return False
        return str(status or "").strip() in {DCM4CHEE_MWL_STATUS_PENDING, DCM4CHEE_MWL_STATUS_FAILED}

    @staticmethod
    def _dcm4chee_mwl_display_status(status: str, retryable: bool) -> tuple[str, str]:
        if status == DCM4CHEE_MWL_STATUS_CREATED:
            return "Synced", "synced"
        if status == DCM4CHEE_MWL_STATUS_PENDING:
            return ("Retry needed", "retry-needed") if retryable else ("Pending", "pending")
        if status == DCM4CHEE_MWL_STATUS_FAILED:
            return ("Retry needed", "retry-needed") if retryable else ("Failed", "failed")
        if status == DCM4CHEE_MWL_STATUS_PATIENT_MISSING:
            return "Failed", "failed"
        return status or "Unknown", "unknown"

    @staticmethod
    def _json_value(value: str, fallback: Any) -> Any:
        try:
            return json.loads(value or "")
        except (TypeError, ValueError):
            return fallback

    @staticmethod
    def _fhir_record_number(record_id: int) -> str:
        return f"FHIR-{record_id:06d}"

    @staticmethod
    def _fhir_clean_text(value: Any, field_name: str, required: bool = False) -> str:
        text = str(value or "").strip()
        if required and not text:
            raise SimulatorValidationError(f"FHIR {field_name} is required.")
        return text

    @staticmethod
    def _fhir_identifier_token(value: Any) -> str:
        text = str(value if value is not None else "").strip().lower()
        cleaned = []
        previous_dash = False
        for character in text:
            if character.isalnum():
                cleaned.append(character)
                previous_dash = False
            elif not previous_dash:
                cleaned.append("-")
                previous_dash = True
        return "".join(cleaned).strip("-") or "record"

    @classmethod
    def fhir_mapping_for_resource_type(cls, resource_type: str) -> dict[str, Any]:
        normalized = cls._fhir_clean_text(resource_type, "resourceType", required=True)
        if normalized not in FHIR_SUPPORTED_RESOURCE_TYPES:
            raise SimulatorValidationError(
                f"FHIR resourceType must be one of: {', '.join(FHIR_SUPPORTED_RESOURCE_TYPES)}."
            )
        mapping = FHIR_RESOURCE_MAPPINGS[normalized]
        return {
            "resourceType": normalized,
            "localSourceType": mapping["local_source_type"],
            "identifierSystem": FHIR_IDENTIFIER_SYSTEMS[normalized],
            "identifierPath": "identifier",
            "dependsOn": list(mapping["depends_on"]),
            "dependencyOrder": FHIR_RESOURCE_DEPENDENCY_ORDER[normalized],
        }

    @classmethod
    def list_fhir_resource_mappings(cls) -> list[dict[str, Any]]:
        return [
            cls.fhir_mapping_for_resource_type(resource_type)
            for resource_type in FHIR_SUPPORTED_RESOURCE_TYPES
        ]

    @classmethod
    def fhir_identifier_value(
        cls,
        resource_type: str,
        local_source_type: str,
        local_source_id: Any,
    ) -> str:
        mapping = cls.fhir_mapping_for_resource_type(resource_type)
        source_type = cls._fhir_identifier_token(local_source_type or mapping["localSourceType"])
        source_id = cls._fhir_identifier_token(local_source_id)
        return f"{source_type}-{source_id}"

    @classmethod
    def _fhir_resource_with_identifier(
        cls,
        resource: dict[str, Any],
        *,
        resource_type: str,
        identifier_system: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        if not isinstance(resource, dict):
            raise SimulatorValidationError("FHIR resource must be a JSON object.")
        normalized = dict(resource)
        normalized["resourceType"] = resource_type
        identifiers = normalized.get("identifier")
        if not isinstance(identifiers, list):
            identifiers = []
        else:
            identifiers = [item for item in identifiers if isinstance(item, dict)]
        if not any(
            item.get("system") == identifier_system and item.get("value") == identifier_value
            for item in identifiers
        ):
            identifiers.insert(0, {"system": identifier_system, "value": identifier_value})
        normalized["identifier"] = identifiers
        return normalized

    def _validate_fhir_record_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("FHIR workflow payload must be a JSON object.")
        raw_resource = payload.get("resource") or payload.get("resourceJson") or {}
        if isinstance(raw_resource, str):
            try:
                raw_resource = json.loads(raw_resource)
            except json.JSONDecodeError as exc:
                raise SimulatorValidationError("FHIR resource JSON is invalid.") from exc
        if not isinstance(raw_resource, dict):
            raise SimulatorValidationError("FHIR resource must be a JSON object.")
        resource_type = self._fhir_clean_text(
            payload.get("resourceType") or raw_resource.get("resourceType"),
            "resourceType",
            required=True,
        )
        mapping = self.fhir_mapping_for_resource_type(resource_type)
        local_source_type = self._fhir_clean_text(
            payload.get("localSourceType") or mapping["localSourceType"],
            "localSourceType",
            required=True,
        )
        local_source_id = self._fhir_clean_text(
            payload.get("localSourceId"),
            "localSourceId",
            required=True,
        )
        identifier_system = self._fhir_clean_text(
            payload.get("identifierSystem") or mapping["identifierSystem"],
            "identifierSystem",
            required=True,
        )
        identifier_value = self._fhir_clean_text(
            payload.get("identifierValue")
            or self.fhir_identifier_value(resource_type, local_source_type, local_source_id),
            "identifierValue",
            required=True,
        )
        dependencies = payload.get("dependencies", payload.get("dependsOn", mapping["dependsOn"]))
        if not isinstance(dependencies, list | tuple):
            raise SimulatorValidationError("FHIR dependencies must be a list.")
        resource = self._fhir_resource_with_identifier(
            raw_resource,
            resource_type=resource_type,
            identifier_system=identifier_system,
            identifier_value=identifier_value,
        )
        return {
            "local_source_type": local_source_type,
            "local_source_id": local_source_id,
            "resource_type": resource_type,
            "identifier_system": identifier_system,
            "identifier_value": identifier_value,
            "resource_json": json.dumps(resource, sort_keys=True),
            "dependency_json": json.dumps(list(dependencies)),
        }

    def create_fhir_workflow_record(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self._validate_fhir_record_payload(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            existing = connection.execute(
                """
                SELECT * FROM local_fhir_workflow_records
                WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?
                """,
                (
                    values["resource_type"],
                    values["identifier_system"],
                    values["identifier_value"],
                ),
            ).fetchone()
            if existing:
                payload_changed = (
                    existing["resource_json"] != values["resource_json"]
                    or existing["dependency_json"] != values["dependency_json"]
                )
                next_status = (
                    FHIR_SYNC_STATUS_PENDING
                    if payload_changed
                    else existing["sync_status"]
                )
                connection.execute(
                    """
                    UPDATE local_fhir_workflow_records
                    SET local_source_type = ?, local_source_id = ?, resource_json = ?,
                        dependency_json = ?, sync_status = ?, updated_at = ?,
                        sync_error = CASE WHEN ? THEN '' ELSE sync_error END,
                        operation_outcome_json = CASE WHEN ? THEN '{}' ELSE operation_outcome_json END,
                        sync_started_at = CASE WHEN ? THEN '' ELSE sync_started_at END
                    WHERE id = ?
                    """,
                    (
                        values["local_source_type"],
                        values["local_source_id"],
                        values["resource_json"],
                        values["dependency_json"],
                        next_status,
                        timestamp,
                        int(payload_changed),
                        int(payload_changed),
                        int(payload_changed),
                        existing["id"],
                    ),
                )
                record_id = int(existing["id"])
            else:
                cursor = connection.execute(
                    """
                    INSERT INTO local_fhir_workflow_records (
                        local_fhir_record_number, local_source_type, local_source_id,
                        resource_type, identifier_system, identifier_value, resource_json,
                        dependency_json, sync_status, created_at, updated_at
                    )
                    VALUES ('', ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["local_source_type"],
                        values["local_source_id"],
                        values["resource_type"],
                        values["identifier_system"],
                        values["identifier_value"],
                        values["resource_json"],
                        values["dependency_json"],
                        FHIR_SYNC_STATUS_PENDING,
                        timestamp,
                        timestamp,
                    ),
                )
                record_id = int(cursor.lastrowid)
                connection.execute(
                    """
                    UPDATE local_fhir_workflow_records
                    SET local_fhir_record_number = ?
                    WHERE id = ?
                    """,
                    (self._fhir_record_number(record_id), record_id),
                )
        return self.get_fhir_workflow_record(record_id)

    def list_fhir_workflow_records(self, sync_status: str = "") -> list[dict[str, Any]]:
        with self.connect() as connection:
            if sync_status:
                rows = connection.execute(
                    """
                    SELECT * FROM local_fhir_workflow_records
                    WHERE sync_status = ?
                    ORDER BY id DESC
                    """,
                    (sync_status,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM local_fhir_workflow_records
                    ORDER BY id DESC
                    """
                ).fetchall()
        return [self._fhir_workflow_record_dict(row) for row in rows]

    def get_fhir_workflow_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._fhir_workflow_record_dict(row)

    def get_fhir_workflow_record_by_identifier(
        self,
        *,
        resource_type: str,
        identifier_system: str,
        identifier_value: str,
    ) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                """
                SELECT * FROM local_fhir_workflow_records
                WHERE resource_type = ? AND identifier_system = ? AND identifier_value = ?
                """,
                (resource_type, identifier_system, identifier_value),
            ).fetchone()
            if not row:
                raise KeyError(identifier_value)
        return self._fhir_workflow_record_dict(row)

    def mark_fhir_syncing(self, record_id: int) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET sync_status = ?, sync_started_at = ?, sync_error = '',
                    operation_outcome_json = '{}', updated_at = ?
                WHERE id = ?
                """,
                (FHIR_SYNC_STATUS_SYNCING, timestamp, timestamp, record_id),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_success(
        self,
        record_id: int,
        *,
        medplum_resource_id: str,
        medplum_resource_reference: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        resource_id = self._fhir_clean_text(medplum_resource_id, "medplumResourceId", required=True)
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT resource_type FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            reference = (
                medplum_resource_reference.strip()
                if medplum_resource_reference
                else f"{row['resource_type']}/{resource_id}"
            )
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET medplum_resource_id = ?, medplum_resource_reference = ?,
                    sync_status = ?, sync_error = '', operation_outcome_json = '{}',
                    last_sync_at = ?, sync_started_at = '', updated_at = ?
                WHERE id = ?
                """,
                (
                    resource_id,
                    reference,
                    FHIR_SYNC_STATUS_SYNCED,
                    timestamp,
                    timestamp,
                    record_id,
                ),
            )
        return self.get_fhir_workflow_record(record_id)

    def mark_fhir_sync_failure(
        self,
        record_id: int,
        *,
        error_text: str,
        operation_outcome: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET sync_status = ?, sync_error = ?, operation_outcome_json = ?,
                    sync_started_at = '', updated_at = ?
                WHERE id = ?
                """,
                (
                    FHIR_SYNC_STATUS_FAILED,
                    str(error_text or "").strip(),
                    json.dumps(operation_outcome or {}, sort_keys=True),
                    timestamp,
                    record_id,
                ),
            )
        return self.get_fhir_workflow_record(record_id)

    def record_fhir_sync_attempt(
        self,
        record_id: int,
        *,
        method: str,
        request_url: str,
        request_payload: dict[str, Any] | None = None,
        http_status: int | None = None,
        response_payload: dict[str, Any] | None = None,
        operation_outcome: dict[str, Any] | None = None,
        error_text: str = "",
    ) -> dict[str, Any]:
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM local_fhir_workflow_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
            cursor = connection.execute(
                """
                INSERT INTO local_fhir_sync_attempts (
                    fhir_record_id, method, request_url, request_payload_json,
                    http_status, response_payload_json, operation_outcome_json,
                    error_text, attempted_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    record_id,
                    method.strip().upper(),
                    request_url.strip(),
                    json.dumps(request_payload or {}, sort_keys=True),
                    http_status,
                    json.dumps(response_payload or {}, sort_keys=True),
                    json.dumps(operation_outcome or {}, sort_keys=True),
                    str(error_text or "").strip(),
                    timestamp,
                ),
            )
            attempt_id = int(cursor.lastrowid)
            attempt_row = connection.execute(
                "SELECT * FROM local_fhir_sync_attempts WHERE id = ?",
                (attempt_id,),
            ).fetchone()
        return self._fhir_sync_attempt_dict(attempt_row)

    def list_fhir_sync_attempts(self, record_id: int) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_fhir_sync_attempts
                WHERE fhir_record_id = ?
                ORDER BY id DESC
                """,
                (record_id,),
            ).fetchall()
        return [self._fhir_sync_attempt_dict(row) for row in rows]

    def ordered_fhir_workflow_records(self, record_ids: list[int]) -> list[dict[str, Any]]:
        records = [self.get_fhir_workflow_record(record_id) for record_id in record_ids]
        return sorted(
            records,
            key=lambda item: (
                FHIR_RESOURCE_DEPENDENCY_ORDER.get(item["resourceType"], 999),
                int(item["id"]),
            ),
        )

    def _fhir_workflow_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        resource = self._json_value(row["resource_json"], {})
        operation_outcome = self._json_value(row["operation_outcome_json"], {})
        mapping = (
            self.fhir_mapping_for_resource_type(row["resource_type"])
            if row["resource_type"] in FHIR_SUPPORTED_RESOURCE_TYPES
            else None
        )
        return {
            "id": row["id"],
            "localFhirRecordNumber": row["local_fhir_record_number"],
            "localSourceType": row["local_source_type"],
            "localSourceId": row["local_source_id"],
            "resourceType": row["resource_type"],
            "identifier": {
                "system": row["identifier_system"],
                "value": row["identifier_value"],
            },
            "resource": resource,
            "dependencies": self._json_value(row["dependency_json"], []),
            "mapping": mapping,
            "medplum": {
                "id": row["medplum_resource_id"],
                "reference": row["medplum_resource_reference"],
            },
            "sync": {
                "status": row["sync_status"],
                "error": row["sync_error"],
                "operationOutcome": operation_outcome,
                "lastSyncAt": row["last_sync_at"],
                "syncStartedAt": row["sync_started_at"],
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": row["sync_status"] != FHIR_SYNC_STATUS_SYNCED,
        }

    def _fhir_sync_attempt_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "fhirRecordId": row["fhir_record_id"],
            "method": row["method"],
            "requestUrl": row["request_url"],
            "requestPayload": self._json_value(row["request_payload_json"], {}),
            "httpStatus": row["http_status"],
            "responsePayload": self._json_value(row["response_payload_json"], {}),
            "operationOutcome": self._json_value(row["operation_outcome_json"], {}),
            "error": row["error_text"],
            "attemptedAt": row["attempted_at"],
        }

    def _gdt_order_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
        attachments = self.list_gdt_attachments(row["id"])
        messages = self.list_gdt_messages(row["id"])
        events = self.list_gdt_events(row["id"])
        primary_attachment_url = row["attachment_url"] or next(
            (item["url"] for item in attachments if item["url"]),
            "",
        )
        return {
            "id": row["id"],
            "localGdtOrderNumber": row["local_gdt_order_number"],
            "patientRecordId": row["patient_record_id"],
            "gdtPatientContextId": row["gdt_patient_context_id"],
            "protocolVersion": row["protocol_version"],
            "messageType": row["message_type"],
            "status": row["order_status"],
            "gdtTestField": GDT_ORDER_TEST_CODE_FIELD,
            "gdtTestCode": row["gdt_test_code"],
            "gdtTestLabel": row["gdt_test_label"],
            "gdtPatientNumber": row["gdt_patient_number"],
            "requestedAt": row["requested_at"],
            "orderingProvider": row["ordering_provider"],
            "clinicalIndication": row["clinical_indication"],
            "attachmentUrl": primary_attachment_url,
            "attachments": attachments,
            "payload": row["payload_gdt"],
            "rawGdtText": row["payload_gdt"],
            "patientSnapshot": self._json_value(row["patient_snapshot_json"], {}),
            "orderSnapshot": self._json_value(row["order_snapshot_json"], {}),
            "messages": messages,
            "events": events,
            "exportPath": row["export_path"],
            "error": row["error_text"],
            "summary": {
                "mrn": row["mrn"],
                "gdtPatientNumber": row["gdt_patient_number"],
                "name": summary_name,
                "dob": row["dob"],
                "sex": row["sex"],
                "visitNumber": row["visit_number"],
                "testCode": row["gdt_test_code"],
                "testLabel": row["gdt_test_label"],
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": True,
        }

    def _gdt_message_record_dict_by_id(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_gdt_message_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._gdt_message_record_dict(row)

    def _gdt_message_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"],
            "direction": row["direction"],
            "messageType": row["message_type"],
            "rawGdtText": row["raw_gdt_text"],
            "parsedFields": self._json_value(row["parsed_fields_json"], {}),
            "canonical": self._json_value(row["canonical_json"], {}),
            "parseStatus": row["parse_status"],
            "matchStatus": row["match_status"],
            "error": row["error_text"],
            "generatedAt": row["generated_at"],
            "receivedAt": row["received_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _gdt_attachment_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "messageRecordId": row["message_record_id"],
            "role": row["role"],
            "url": row["url"],
            "path": row["path"],
            "reference": row["reference"],
            "contentType": row["content_type"],
            "description": row["description"],
            "sourceFile": row["source_file"],
            "status": row["status"],
            "details": self._json_value(row["details_json"], {}),
            "filename": row["filename"],
            "checksum": row["checksum"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _gdt_event_record_dict(self, row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "orderRecordId": row["order_record_id"],
            "patientContextId": row["patient_context_id"],
            "messageRecordId": row["message_record_id"],
            "attachmentRecordId": row["attachment_record_id"],
            "eventType": row["event_type"],
            "actor": row["actor"],
            "details": self._json_value(row["details_json"], {}),
            "createdAt": row["created_at"],
        }

    @staticmethod
    def _result_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "messageControlId": row["message_control_id"],
            "messageType": row["message_type"],
            "patientMrn": row["patient_mrn"],
            "placerOrderNumber": row["placer_order_number"],
            "fillerOrderNumber": row["filler_order_number"],
            "matchedPatientRecordId": row["matched_patient_record_id"],
            "matchedOrderRecordId": row["matched_order_record_id"],
            "matchStatus": row["match_status"],
            "duplicateOfId": row["duplicate_of_id"],
            "parseStatus": row["parse_status"],
            "error": row["error_text"],
            "payload": row["payload_hl7"],
            "receivedAt": row["received_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def _patient_record_dicts_with_fhir(self, rows: list[sqlite3.Row]) -> list[dict[str, Any]]:
        source_ids = [str(row["id"]) for row in rows]
        fhir_by_source_id: dict[str, dict[str, Any]] = {}
        dcm4chee_by_source_id: dict[str, dict[str, Any]] = {}
        dcm4chee_results_by_source_id: dict[str, list[dict[str, Any]]] = {}
        if source_ids:
            placeholders = ", ".join("?" for _ in source_ids)
            with self.connect() as connection:
                fhir_rows = connection.execute(
                    f"""
                    SELECT * FROM local_fhir_workflow_records
                    WHERE local_source_type = 'local_patient_records'
                    AND local_source_id IN ({placeholders})
                    AND resource_type = 'Patient'
                    """,
                    source_ids,
                ).fetchall()
                dcm4chee_rows = connection.execute(
                    f"""
                    SELECT * FROM local_dcm4chee_patient_syncs
                    WHERE patient_record_id IN ({placeholders})
                    ORDER BY updated_at DESC, id DESC
                    """,
                    [int(source_id) for source_id in source_ids],
                ).fetchall()
                dcm4chee_result_rows = connection.execute(
                    f"""
                    SELECT * FROM local_dcm4chee_result_records
                    WHERE patient_record_id IN ({placeholders})
                    ORDER BY last_refreshed_at DESC, id DESC
                    """,
                    [int(source_id) for source_id in source_ids],
                ).fetchall()
                dcm4chee_result_refresh_rows = connection.execute(
                    f"""
                    SELECT patient_record_id, completed_at, results_snapshot_json
                    FROM local_dcm4chee_result_refresh_runs
                    WHERE patient_record_id IN ({placeholders})
                    ORDER BY id DESC
                    """,
                    [int(source_id) for source_id in source_ids],
                ).fetchall()
            for fhir_row in fhir_rows:
                fhir_by_source_id[str(fhir_row["local_source_id"])] = self._fhir_workflow_record_dict(fhir_row)
            for dcm4chee_row in dcm4chee_rows:
                source_id = str(dcm4chee_row["patient_record_id"])
                if source_id not in dcm4chee_by_source_id:
                    dcm4chee_by_source_id[source_id] = self._dcm4chee_patient_sync_dict(dcm4chee_row)
            dcm4chee_result_run_patient_ids: set[str] = set()
            for refresh_row in dcm4chee_result_refresh_rows:
                source_id = str(refresh_row["patient_record_id"])
                dcm4chee_result_run_patient_ids.add(source_id)
                if refresh_row["completed_at"] and source_id not in dcm4chee_results_by_source_id:
                    snapshot = self._json_value(refresh_row["results_snapshot_json"], [])
                    dcm4chee_results_by_source_id[source_id] = snapshot if isinstance(snapshot, list) else []
            latest_result_generation_by_source_id: dict[str, str] = {}
            for dcm4chee_result_row in dcm4chee_result_rows:
                source_id = str(dcm4chee_result_row["patient_record_id"])
                if source_id in dcm4chee_result_run_patient_ids:
                    continue
                generation = str(dcm4chee_result_row["refresh_generation"] or "")
                if generation and source_id not in latest_result_generation_by_source_id:
                    latest_result_generation_by_source_id[source_id] = generation
            for dcm4chee_result_row in dcm4chee_result_rows:
                source_id = str(dcm4chee_result_row["patient_record_id"])
                if source_id in dcm4chee_result_run_patient_ids:
                    continue
                latest_generation = latest_result_generation_by_source_id.get(source_id)
                if latest_generation and dcm4chee_result_row["refresh_generation"] != latest_generation:
                    continue
                dcm4chee_results_by_source_id.setdefault(source_id, []).append(
                    self._dcm4chee_result_record_dict(dcm4chee_result_row)
                )
        return [
            self._patient_record_dict(
                row,
                fhir_by_source_id.get(str(row["id"])),
                dcm4chee_by_source_id.get(str(row["id"])),
                dcm4chee_results_by_source_id.get(str(row["id"]), []),
            )
            for row in rows
        ]

    @staticmethod
    def _patient_record_dict(
        row: sqlite3.Row,
        fhir_record: dict[str, Any] | None = None,
        dcm4chee_patient_sync: dict[str, Any] | None = None,
        dcm4chee_results: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        validation_messages = json.loads(row["validation_messages_json"] or "[]")
        dcm4chee_results = dcm4chee_results or []
        patient = {
            "mrn": row["mrn"],
            "firstName": row["first_name"],
            "lastName": row["last_name"],
            "middleName": row["middle_name"],
            "dob": row["dob"],
            "sex": row["sex"],
            "address": row["address"],
            "phone": row["phone"],
            "email": row["email"],
            "active": bool(row["fhir_active"]),
            "addressLine": row["address_line"],
            "addressCity": row["address_city"],
            "addressState": row["address_state"],
            "addressPostalCode": row["address_postal_code"],
            "addressCountry": row["address_country"],
            "managingOrganizationReference": row["managing_organization_reference"],
            "managingOrganizationDisplay": row["managing_organization_display"],
        }
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
        fhir = None
        if fhir_record:
            fhir = {
                "recordId": fhir_record["id"],
                "localFhirRecordNumber": fhir_record["localFhirRecordNumber"],
                "resourceType": fhir_record["resourceType"],
                "identifier": fhir_record["identifier"],
                "medplum": fhir_record["medplum"],
                "sync": fhir_record["sync"],
                "localOnly": fhir_record["localOnly"],
            }
        return {
            "id": row["id"],
            "localPatientNumber": row["local_patient_number"],
            "protocolVersion": row["protocol_version"],
            "messageType": row["message_type"],
            "patient": patient,
            "summary": {
                "mrn": row["mrn"],
                "name": summary_name,
                "dob": row["dob"],
                "sex": row["sex"],
                "visitNumber": row["visit_number"],
            },
            "visitNumber": row["visit_number"],
            "patientClass": row["patient_class"],
            "assignedLocation": row["assigned_location"],
            "attendingProvider": row["attending_provider"],
            "accountNumber": row["account_number"],
            "validation": {
                "status": row["validation_status"],
                "messages": validation_messages,
            },
            "payload": row["payload_hl7"],
            "fhir": fhir,
            "dcm4chee": {
                **({"patient": dcm4chee_patient_sync} if dcm4chee_patient_sync else {}),
                "dicomResults": dcm4chee_results,
                "resultCount": len(dcm4chee_results),
            },
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": True,
        }

    @staticmethod
    def _dcm4chee_patient_sync_dict(row: sqlite3.Row) -> dict[str, Any]:
        status = str(row["sync_status"] or "")
        retryable = status in {DCM4CHEE_PATIENT_SYNC_STATUS_PENDING, DCM4CHEE_PATIENT_SYNC_STATUS_FAILED}
        return {
            "id": row["id"],
            "patientRecordId": row["patient_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "hl7Host": row["hl7_host"],
            "hl7Port": row["hl7_port"],
            "receivingApplication": row["receiving_application"],
            "receivingFacility": row["receiving_facility"],
            "status": status,
            "displayStatus": "Synced" if status == DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED else status,
            "retryable": retryable,
            "retryCount": row["retry_count"],
            "lastAttemptId": row["last_attempt_id"],
            "ack": {
                "code": row["last_ack_code"],
                "controlId": row["last_ack_control_id"],
                "text": row["last_ack_text"],
            },
            "lastResponsePayload": row["last_response_payload"],
            "lastErrorType": row["last_error_type"],
            "lastError": row["last_error_text"],
            "lastSyncAt": row["last_sync_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _dcm4chee_patient_sync_attempt_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "patientSyncId": row["patient_sync_id"],
            "operationType": row["operation_type"],
            "patientRecordId": row["patient_record_id"],
            "profileName": row["profile_name"],
            "serverIdentity": row["server_identity"],
            "patientId": row["patient_id"],
            "issuerOfPatientId": row["issuer_of_patient_id"],
            "requestUrl": row["request_url"],
            "requestPayload": row["request_payload"],
            "responsePayload": row["response_payload"],
            "ack": {
                "code": row["ack_code"],
                "controlId": row["ack_control_id"],
                "text": row["ack_text"],
            },
            "status": row["attempt_status"],
            "errorType": row["error_type"],
            "error": row["error_text"],
            "attemptedAt": row["attempted_at"],
            "completedAt": row["completed_at"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    @staticmethod
    def _ensure_column(
        connection: sqlite3.Connection, table_name: str, column_name: str, definition: str
    ) -> None:
        columns = {
            row["name"]
            for row in connection.execute(f"PRAGMA table_info({table_name})").fetchall()
        }
        if column_name not in columns:
            try:
                connection.execute(
                    f"ALTER TABLE {table_name} ADD COLUMN {column_name} {definition}"
                )
            except sqlite3.OperationalError as exc:
                if "duplicate column name" not in str(exc).lower():
                    raise

    @classmethod
    def _backfill_dcm4chee_mwl_mappings(cls, connection: sqlite3.Connection) -> None:
        rows = connection.execute(
            """
            SELECT a.*, o.mrn, o.order_code, o.order_code_text
            FROM local_dcm4chee_mwl_attempts a
            JOIN local_order_records o ON o.id = a.order_record_id
            WHERE NOT EXISTS (
                SELECT 1 FROM local_dcm4chee_mwl_mappings m
                WHERE m.order_record_id = a.order_record_id
            )
            AND a.id = (
                SELECT latest.id
                FROM local_dcm4chee_mwl_attempts latest
                WHERE latest.order_record_id = a.order_record_id
                ORDER BY latest.attempted_at DESC, latest.id DESC
                LIMIT 1
            )
            ORDER BY a.order_record_id
            """
        ).fetchall()
        for row in rows:
            request_payload = cls._json_value(row["request_payload_json"], {})
            sps_payload = cls._dcm4chee_sps_payload(request_payload)
            patient_id = cls._dicom_first_value(request_payload, "00100020", row["mrn"])
            issuer = cls._dicom_first_value(request_payload, "00100021", row["profile_name"])
            worklist_label = cls._dicom_first_value(
                request_payload,
                "00741202",
                str(row["order_code_text"] or row["order_code"] or ORDER_DEFAULT_TEXT).strip(),
            )
            scheduled_station = row["scheduled_station_ae_title"] or cls._dicom_first_value(
                sps_payload,
                "00400001",
            )
            completed_or_attempted = row["completed_at"] or row["attempted_at"]
            response_body = row["response_body"] or ""
            error_payload = {"responseBody": response_body} if row["error_type"] else {}
            cursor = connection.execute(
                """
                INSERT INTO local_dcm4chee_mwl_mappings (
                    order_record_id, profile_name, server_identity, mwl_ae_title,
                    scheduled_station_ae_title, local_dcm4chee_order_number,
                    patient_id, issuer_of_patient_id, accession_number,
                    requested_procedure_id, scheduled_procedure_step_id,
                    study_instance_uid, worklist_label, uid_root, sync_status,
                    last_sync_at, retry_count, last_attempt_id, last_http_status,
                    last_response_body, last_error_type, last_error_text,
                    last_error_payload_json, latest_request_payload_json,
                    latest_readback_payload_json, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["order_record_id"],
                    row["profile_name"],
                    row["server_identity"],
                    row["mwl_ae_title"],
                    scheduled_station,
                    row["local_dcm4chee_order_number"],
                    patient_id,
                    issuer,
                    row["accession_number"],
                    row["requested_procedure_id"],
                    row["scheduled_procedure_step_id"],
                    row["study_instance_uid"],
                    worklist_label,
                    row["uid_root"],
                    row["attempt_status"],
                    completed_or_attempted,
                    max(
                        0,
                        int(
                            connection.execute(
                                """
                                SELECT COUNT(*) FROM local_dcm4chee_mwl_attempts
                                WHERE order_record_id = ?
                                """,
                                (row["order_record_id"],),
                            ).fetchone()[0]
                        )
                        - 1,
                    ),
                    row["id"],
                    row["http_status"],
                    response_body,
                    row["error_type"],
                    row["error_text"],
                    json.dumps(error_payload, sort_keys=True),
                    row["request_payload_json"] or "{}",
                    "{}",
                    row["created_at"],
                    row["updated_at"],
                ),
            )
            mapping_id = int(cursor.lastrowid)
            connection.execute(
                """
                UPDATE local_dcm4chee_mwl_attempts
                SET mapping_id = ?, operation_type = COALESCE(NULLIF(operation_type, ''), ?)
                WHERE order_record_id = ? AND mapping_id IS NULL
                """,
                (mapping_id, DCM4CHEE_MWL_OPERATION_CREATE, row["order_record_id"]),
            )

    @staticmethod
    def _operation_metadata_for_name(name: str) -> dict[str, Any]:
        return DEFAULT_LAB_OPERATION_METADATA.get(
            name,
            {
                "control_type": "external",
                "backing_service": "",
                "supported_actions": ["status", "smoke"],
                "timeout_seconds": 60,
                "smoke_profile": "",
            },
        )

    def _seed_lab_servers(self, connection: sqlite3.Connection) -> None:
        timestamp = now_iso()
        for item in DEFAULT_LAB_SERVERS:
            metadata = self._operation_metadata_for_name(item["name"])
            supported_actions_json = json.dumps(metadata["supported_actions"])
            check_config_json = json.dumps(item.get("check_config", {}))
            existing = connection.execute(
                "SELECT id FROM lab_servers WHERE name = ?", (item["name"],)
            ).fetchone()
            if existing:
                connection.execute(
                    """
                    UPDATE lab_servers
                    SET control_type = ?, backing_service = ?, supported_actions_json = ?,
                        operation_timeout_seconds = ?, smoke_profile = ?,
                        check_config_json = CASE
                            WHEN check_config_json IN ('', '{}') THEN ?
                            ELSE check_config_json
                        END
                    WHERE id = ?
                    """,
                    (
                        metadata["control_type"],
                        metadata["backing_service"],
                        supported_actions_json,
                        metadata["timeout_seconds"],
                        metadata["smoke_profile"],
                        check_config_json,
                        existing["id"],
                    ),
                )
            else:
                connection.execute(
                    """
                    INSERT INTO lab_servers (
                        name, server_type, description, host, port, base_url, protocol,
                        enabled, version, check_config_json, control_type, backing_service,
                        supported_actions_json, operation_timeout_seconds, smoke_profile,
                        created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 1, '', ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        item["name"],
                        item["server_type"],
                        item["description"],
                        item["host"],
                        item["port"],
                        item["base_url"],
                        item["protocol"],
                        check_config_json,
                        metadata["control_type"],
                        metadata["backing_service"],
                        supported_actions_json,
                        metadata["timeout_seconds"],
                        metadata["smoke_profile"],
                        timestamp,
                        timestamp,
                    ),
                )

    @staticmethod
    def validate_lab_server_payload(
        payload: dict[str, Any], *, partial: bool = False
    ) -> dict[str, Any]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("Server payload must be a JSON object.")
        validated: dict[str, Any] = {}
        if "name" in payload or not partial:
            name = str(payload.get("name", "")).strip()
            if not name:
                raise SimulatorValidationError("Server name is required.")
            validated["name"] = name
        if "serverType" in payload or "server_type" in payload or not partial:
            server_type = str(
                payload.get("serverType", payload.get("server_type", ""))
            ).strip()
            if server_type not in LAB_SERVER_TYPES:
                raise SimulatorValidationError(
                    f"Server type must be one of: {', '.join(LAB_SERVER_TYPES)}."
                )
            validated["server_type"] = server_type
        for source_key, target_key in (
            ("description", "description"),
            ("host", "host"),
            ("baseUrl", "base_url"),
            ("base_url", "base_url"),
            ("version", "version"),
        ):
            if source_key in payload:
                validated[target_key] = str(payload.get(source_key, "")).strip()
        if "port" in payload:
            raw_port = payload.get("port")
            if raw_port in (None, ""):
                validated["port"] = None
            else:
                try:
                    port = int(raw_port)
                except (TypeError, ValueError) as exc:
                    raise SimulatorValidationError(
                        "Port must be an integer between 1 and 65535."
                    ) from exc
                if not 1 <= port <= 65535:
                    raise SimulatorValidationError(
                        "Port must be an integer between 1 and 65535."
                    )
                validated["port"] = port
        if "protocol" in payload or not partial:
            protocol = str(payload.get("protocol", "None")).strip() or "None"
            if protocol not in LAB_SERVER_PROTOCOLS:
                raise SimulatorValidationError(
                    f"Protocol must be one of: {', '.join(LAB_SERVER_PROTOCOLS)}."
                )
            validated["protocol"] = protocol
        if "enabled" in payload:
            validated["enabled"] = 1 if bool(payload.get("enabled")) else 0
        if "checkConfig" in payload:
            check_config = payload.get("checkConfig") or {}
            if not isinstance(check_config, dict):
                raise SimulatorValidationError("Check config must be a JSON object.")
            validated["check_config_json"] = json.dumps(check_config)
        operation_config = payload.get("operation")
        if isinstance(operation_config, dict):
            if "controlType" in operation_config:
                validated["control_type"] = str(operation_config.get("controlType", "")).strip()
            if "backingService" in operation_config:
                validated["backing_service"] = str(operation_config.get("backingService", "")).strip()
            if "supportedActions" in operation_config:
                actions = operation_config.get("supportedActions") or []
                if not isinstance(actions, list) or not all(isinstance(action, str) for action in actions):
                    raise SimulatorValidationError("Supported actions must be a list of strings.")
                unsupported = [action for action in actions if action not in LAB_OPERATION_ACTIONS]
                if unsupported:
                    raise SimulatorValidationError(
                        f"Unsupported lab operation action: {unsupported[0]}."
                    )
                validated["supported_actions_json"] = json.dumps(actions)
            if "timeoutSeconds" in operation_config:
                try:
                    timeout_seconds = int(operation_config.get("timeoutSeconds"))
                except (TypeError, ValueError) as exc:
                    raise SimulatorValidationError("Operation timeout must be a positive integer.") from exc
                if timeout_seconds <= 0:
                    raise SimulatorValidationError("Operation timeout must be a positive integer.")
                validated["operation_timeout_seconds"] = timeout_seconds
            if "smokeProfile" in operation_config:
                validated["smoke_profile"] = str(operation_config.get("smokeProfile", "")).strip()
        endpoint_base_url = validated.get("base_url", str(payload.get("baseUrl", "")).strip())
        endpoint_host = validated.get("host", str(payload.get("host", "")).strip())
        endpoint_port = validated.get("port", payload.get("port"))
        if endpoint_base_url and not endpoint_base_url.startswith(("http://", "https://")):
            raise SimulatorValidationError("Base URL must start with http:// or https://.")
        if not partial and not endpoint_base_url and not (endpoint_host and endpoint_port):
            protocol = validated.get("protocol", "None")
            if protocol not in {"GDT", "None"}:
                raise SimulatorValidationError(
                    "Server requires either a base URL or host and port."
                )
        return validated

    @staticmethod
    def _lab_server_dict(row: sqlite3.Row) -> dict[str, Any]:
        supported_actions = json.loads(row["supported_actions_json"] or "[]")
        return {
            "id": row["id"],
            "name": row["name"],
            "serverType": row["server_type"],
            "description": row["description"],
            "host": row["host"],
            "port": row["port"],
            "baseUrl": row["base_url"],
            "protocol": row["protocol"],
            "enabled": bool(row["enabled"]),
            "version": row["version"],
            "checkConfig": json.loads(row["check_config_json"] or "{}"),
            "operation": {
                "controlType": row["control_type"],
                "backingService": row["backing_service"],
                "supportedActions": supported_actions,
                "timeoutSeconds": row["operation_timeout_seconds"],
                "smokeProfile": row["smoke_profile"],
            },
            "overallStatus": row["overall_status"],
            "checks": {
                "process": row["process_status"],
                "application": row["application_status"],
                "protocol": row["protocol_status"],
            },
            "lastCheckAt": row["last_check_at"],
            "recentError": row["recent_error"],
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
        }

    def list_lab_servers(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                "SELECT * FROM lab_servers ORDER BY enabled DESC, name COLLATE NOCASE"
            ).fetchall()
        return [self._lab_server_dict(row) for row in rows]

    def get_lab_server(self, server_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM lab_servers WHERE id = ?", (server_id,)
            ).fetchone()
            if not row:
                raise KeyError(server_id)
        return self._lab_server_dict(row)

    def create_lab_server(self, payload: dict[str, Any]) -> dict[str, Any]:
        values = self.validate_lab_server_payload(payload)
        timestamp = now_iso()
        with self.lock, self.connect() as connection:
            try:
                cursor = connection.execute(
                    """
                    INSERT INTO lab_servers (
                        name, server_type, description, host, port, base_url,
                        protocol, enabled, version, check_config_json, control_type,
                        backing_service, supported_actions_json, operation_timeout_seconds,
                        smoke_profile, created_at, updated_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    """,
                    (
                        values["name"],
                        values["server_type"],
                        values.get("description", ""),
                        values.get("host", ""),
                        values.get("port"),
                        values.get("base_url", ""),
                        values.get("protocol", "None"),
                        values.get("enabled", 1),
                        values.get("version", ""),
                        values.get("check_config_json", "{}"),
                        values.get("control_type", ""),
                        values.get("backing_service", ""),
                        values.get("supported_actions_json", "[]"),
                        values.get("operation_timeout_seconds", 60),
                        values.get("smoke_profile", ""),
                        timestamp,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("Server name must be unique.") from exc
            server_id = cursor.lastrowid
        return self.get_lab_server(server_id)

    def update_lab_server(self, server_id: int, payload: dict[str, Any]) -> dict[str, Any]:
        values = self.validate_lab_server_payload(payload, partial=True)
        if not values:
            return self.get_lab_server(server_id)
        assignments = [f"{key} = ?" for key in values]
        params = list(values.values())
        assignments.append("updated_at = ?")
        params.append(now_iso())
        params.append(server_id)
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM lab_servers WHERE id = ?", (server_id,)
            ).fetchone()
            if not row:
                raise KeyError(server_id)
            try:
                connection.execute(
                    f"UPDATE lab_servers SET {', '.join(assignments)} WHERE id = ?",
                    params,
                )
            except sqlite3.IntegrityError as exc:
                raise SimulatorValidationError("Server name must be unique.") from exc
        return self.get_lab_server(server_id)

    def update_lab_server_health(
        self,
        server_id: int,
        *,
        overall_status: str,
        process_status: str,
        application_status: str,
        protocol_status: str,
        recent_error: str = "",
        version: str = "",
    ) -> dict[str, Any]:
        if overall_status not in LAB_HEALTH_STATUSES:
            raise SimulatorValidationError("Unknown overall health status.")
        for status in (process_status, application_status, protocol_status):
            if status not in LAB_HEALTH_STATUSES:
                raise SimulatorValidationError("Unknown health check status.")
        with self.lock, self.connect() as connection:
            row = connection.execute(
                "SELECT id FROM lab_servers WHERE id = ?", (server_id,)
            ).fetchone()
            if not row:
                raise KeyError(server_id)
            connection.execute(
                """
                UPDATE lab_servers
                SET overall_status = ?, process_status = ?, application_status = ?,
                    protocol_status = ?, recent_error = ?, version = COALESCE(NULLIF(?, ''), version),
                    last_check_at = ?, updated_at = ?
                WHERE id = ?
                """,
                (
                    overall_status,
                    process_status,
                    application_status,
                    protocol_status,
                    recent_error,
                    version,
                    now_iso(),
                    now_iso(),
                    server_id,
                ),
            )
        return self.get_lab_server(server_id)

    def record_lab_operation(
        self,
        server_id: int | None,
        *,
        service_name: str,
        action: str,
        operator: str,
        result: str,
        duration_ms: int = 0,
        progress: list[dict[str, Any]] | None = None,
        error_text: str = "",
        started_at: str = "",
        completed_at: str = "",
    ) -> dict[str, Any]:
        normalized_action = action.strip().lower()
        if normalized_action not in LAB_OPERATION_ACTIONS:
            raise SimulatorValidationError(
                f"Unsupported lab operation action: {normalized_action or 'unknown'}."
            )
        normalized_result = result.strip() or "Unknown"
        normalized_operator = operator.strip() or "local-user"
        normalized_service_name = service_name.strip()
        if not normalized_service_name:
            raise SimulatorValidationError("Operation service name is required.")
        progress_steps = progress or []
        if not isinstance(progress_steps, list):
            raise SimulatorValidationError("Operation progress must be a list.")
        started = started_at or now_iso()
        completed = completed_at or now_iso()
        with self.lock, self.connect() as connection:
            if server_id is not None:
                row = connection.execute(
                    "SELECT id FROM lab_servers WHERE id = ?", (server_id,)
                ).fetchone()
                if not row:
                    raise KeyError(server_id)
            cursor = connection.execute(
                """
                INSERT INTO lab_operation_history (
                    server_id, service_name, action, operator, result, duration_ms,
                    progress_json, error_text, started_at, completed_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    server_id,
                    normalized_service_name,
                    normalized_action,
                    normalized_operator,
                    normalized_result,
                    max(0, int(duration_ms)),
                    json.dumps(progress_steps),
                    error_text,
                    started,
                    completed,
                ),
            )
            operation_id = cursor.lastrowid
        return self.get_lab_operation(operation_id)

    def get_lab_operation(self, operation_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM lab_operation_history WHERE id = ?", (operation_id,)
            ).fetchone()
            if not row:
                raise KeyError(operation_id)
        return self._lab_operation_dict(row)

    def list_lab_operations(
        self, server_id: int | None = None, *, limit: int = 20
    ) -> list[dict[str, Any]]:
        bounded_limit = min(200, max(1, int(limit)))
        with self.connect() as connection:
            if server_id is None:
                rows = connection.execute(
                    """
                    SELECT * FROM lab_operation_history
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (bounded_limit,),
                ).fetchall()
            else:
                rows = connection.execute(
                    """
                    SELECT * FROM lab_operation_history
                    WHERE server_id = ?
                    ORDER BY id DESC
                    LIMIT ?
                    """,
                    (server_id, bounded_limit),
                ).fetchall()
        return [self._lab_operation_dict(row) for row in rows]

    @staticmethod
    def _lab_operation_dict(row: sqlite3.Row) -> dict[str, Any]:
        return {
            "id": row["id"],
            "serverId": row["server_id"],
            "serviceName": row["service_name"],
            "action": row["action"],
            "operator": row["operator"],
            "result": row["result"],
            "durationMs": row["duration_ms"],
            "progress": json.loads(row["progress_json"] or "[]"),
            "error": row["error_text"],
            "startedAt": row["started_at"],
            "completedAt": row["completed_at"],
        }

    def list_gdt_orders(self) -> list[dict[str, Any]]:
        return [
            {
                "id": item["id"],
                "orderNumber": item["localGdtOrderNumber"],
                "status": item["status"],
                "updatedAt": item["updatedAt"],
            }
            for item in self.list_gdt_order_records()
        ]
