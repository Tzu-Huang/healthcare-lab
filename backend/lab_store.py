from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
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
PATIENT_PROTOCOL_VERSION = "2.3.1"
PATIENT_MESSAGE_TYPE = "ADT^A04"
PATIENT_MODES = {
    "hl7-v2": {"protocol": "HL7 v2.3.1", "message_type": "ADT^A04"},
    "fhir": {"protocol": "FHIR R4", "message_type": "Patient"},
    "gdt": {"protocol": "GDT 2.1", "message_type": "6301"},
    "dicom": {"protocol": "DICOM", "message_type": "Patient Module"},
}
PATIENT_CLASS_DEFAULT = "O"
GDT_PATIENT_SEX_CODES = {"M": "1", "F": "2"}
ORDER_PROTOCOL_VERSION = "2.3.1"
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
    "Task",
    "Binary",
    "Observation",
    "DocumentReference",
    "DiagnosticReport",
    "Provenance",
)
FHIR_RESOURCE_DEPENDENCY_ORDER = {
    "Patient": 10,
    "ServiceRequest": 20,
    "Task": 30,
    "Binary": 40,
    "Observation": 50,
    "DocumentReference": 60,
    "DiagnosticReport": 70,
    "Provenance": 80,
}
FHIR_IDENTIFIER_SYSTEMS = {
    "Patient": "https://healthcare-lab.local/fhir/identifier/patient",
    "ServiceRequest": "https://healthcare-lab.local/fhir/identifier/service-request",
    "Task": "https://healthcare-lab.local/fhir/identifier/task",
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
    "Task": {
        "local_source_type": "local_order_records",
        "depends_on": ("Patient", "ServiceRequest"),
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
            "Task",
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
    root = Path(base_path)
    directories = {
        "root": root,
        "outbox": root / "outbox",
        "processed": root / "processed",
        "processing": root / "processing",
        "error": root / "error",
        "outbound": root / "outbound",
        "inbound": root / "inbound",
        "reports": root / "reports",
        "archive": root / "archive",
    }
    for path in directories.values():
        path.mkdir(parents=True, exist_ok=True)
    return directories


def validate_gdt_bridge_dirs(base_path: str | Path) -> dict[str, Path]:
    directories = ensure_gdt_bridge_dirs(base_path)
    probe_name = f".write-test-{datetime.now().strftime('%Y%m%d%H%M%S%f')}"
    for name in ("outbox", "processed", "processing", "error", "inbound", "archive", "reports"):
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
                CREATE UNIQUE INDEX IF NOT EXISTS idx_oie_result_control_id
                ON oie_result_records(message_control_id)
                WHERE message_control_id != '';
                CREATE UNIQUE INDEX IF NOT EXISTS idx_fhir_record_identifier
                ON local_fhir_workflow_records(resource_type, identifier_system, identifier_value);
                CREATE INDEX IF NOT EXISTS idx_fhir_record_source
                ON local_fhir_workflow_records(local_source_type, local_source_id);
                CREATE INDEX IF NOT EXISTS idx_fhir_record_sync_status
                ON local_fhir_workflow_records(sync_status);
                CREATE INDEX IF NOT EXISTS idx_fhir_attempt_record
                ON local_fhir_sync_attempts(fhir_record_id, attempted_at);
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
            self._seed_lab_servers(connection)

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
    def _normalize_patient_mode(payload: dict[str, Any]) -> str:
        mode = str(payload.get("mode", payload.get("protocolMode", "hl7-v2"))).strip().lower()
        aliases = {
            "hl7": "hl7-v2",
            "hl7v2": "hl7-v2",
            "hl7-v2.3.1": "hl7-v2",
            "hl7-v231": "hl7-v2",
            "fhir-r4": "fhir",
            "gdt-2.1": "gdt",
            "dicom-patient": "dicom",
        }
        normalized = aliases.get(mode, mode)
        if normalized not in PATIENT_MODES:
            raise SimulatorValidationError("Patient mode must be HL7 v2, FHIR, GDT, or DICOM.")
        return normalized

    def _validate_patient_payload(self, payload: dict[str, Any]) -> dict[str, str]:
        if not isinstance(payload, dict):
            raise SimulatorValidationError("Patient payload must be a JSON object.")
        return {
            "mode": self._normalize_patient_mode(payload),
            "mrn": self._clean_patient_text(payload.get("mrn"), "mrn", required=True),
            "first_name": self._clean_patient_text(payload.get("firstName"), "firstName", required=True),
            "last_name": self._clean_patient_text(payload.get("lastName"), "lastName", required=True),
            "middle_name": self._clean_patient_text(payload.get("middleName"), "middleName"),
            "dob": self._normalize_patient_dob(payload.get("dob")),
            "sex": self._normalize_patient_sex(payload.get("sex")),
            "address": self._clean_patient_text(payload.get("address"), "address"),
            "phone": self._clean_patient_text(payload.get("phone"), "phone"),
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
            f"MSH|^~\\&|HEALTHCARE_LAB|LAB_DEMO|OIE|ADT|{timestamp}||ADT^A04|{control_id}|P|2.3.1",
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
        resource = {
            "resourceType": "Patient",
            "id": DemoStore._patient_record_number(record_id),
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
            "telecom": [{"system": "phone", "value": values["phone"]}] if values["phone"] else [],
            "address": [{"text": values["address"]}] if values["address"] else [],
            "extension": [
                {
                    "url": "urn:healthcare-lab:visit-number",
                    "valueString": visit_number,
                }
            ],
        }
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
            cursor = connection.execute(
                """
                INSERT INTO local_patient_records (
                    local_patient_number, protocol_version, message_type, mrn,
                    first_name, last_name, middle_name, dob, sex, address, phone,
                    visit_number, patient_class, assigned_location, attending_provider,
                    account_number, validation_status, validation_messages_json,
                    payload_hl7, created_at, updated_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    def list_patient_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_patient_records
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._patient_record_dict(row) for row in rows]

    def get_patient_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_patient_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._patient_record_dict(row)

    def list_oie_local_adt_inventory(self) -> list[dict[str, Any]]:
        return self.list_patient_records()

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
            f"MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|{timestamp}||ORM^O01|{control_id}|P|2.3.1",
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

    def list_order_records(self) -> list[dict[str, Any]]:
        with self.connect() as connection:
            rows = connection.execute(
                """
                SELECT * FROM local_order_records
                ORDER BY created_at DESC, id DESC
                """
            ).fetchall()
        return [self._order_record_dict(row) for row in rows]

    def get_order_record(self, record_id: int) -> dict[str, Any]:
        with self.connect() as connection:
            row = connection.execute(
                "SELECT * FROM local_order_records WHERE id = ?",
                (record_id,),
            ).fetchone()
            if not row:
                raise KeyError(record_id)
        return self._order_record_dict(row)

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
        return self.list_order_records()

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
            for code in ("6200", "8410")
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
                    WHERE mrn = ?
                    ORDER BY id DESC
                    LIMIT 1
                    """,
                    (patient_mrn,),
                ).fetchone()
            order_row = None
            if patient_row and (placer_order_number or filler_order_number):
                order_row = connection.execute(
                    """
                    SELECT * FROM local_order_records
                    WHERE patient_record_id = ?
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
        patients = self.list_patient_records()
        orders = self.list_order_records()
        results = self.list_oie_results()
        orders_by_patient: dict[int, list[dict[str, Any]]] = {}
        results_by_patient: dict[int, list[dict[str, Any]]] = {}
        unmatched_results: list[dict[str, Any]] = []
        for order in orders:
            orders_by_patient.setdefault(int(order["patientRecordId"]), []).append(order)
        for result in results:
            patient_id = result.get("matchedPatientRecordId")
            if patient_id:
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

    @staticmethod
    def _order_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        validation_messages = json.loads(row["validation_messages_json"] or "[]")
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
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
                "visitId": row["visit_id"],
                "orderCode": row["order_code"],
                "orderText": row["order_code_text"],
            },
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
            "mapping": self.fhir_mapping_for_resource_type(row["resource_type"]),
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

    @staticmethod
    def _patient_record_dict(row: sqlite3.Row) -> dict[str, Any]:
        validation_messages = json.loads(row["validation_messages_json"] or "[]")
        patient = {
            "mrn": row["mrn"],
            "firstName": row["first_name"],
            "lastName": row["last_name"],
            "middleName": row["middle_name"],
            "dob": row["dob"],
            "sex": row["sex"],
            "address": row["address"],
            "phone": row["phone"],
        }
        summary_name = " ".join(
            part for part in (row["first_name"], row["middle_name"], row["last_name"]) if part
        )
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
            "createdAt": row["created_at"],
            "updatedAt": row["updated_at"],
            "localOnly": True,
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
