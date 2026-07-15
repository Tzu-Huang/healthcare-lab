"""External OpenEMR MariaDB procedure-order client."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

try:
    import pymysql
    import pymysql.cursors
except ImportError:  # pragma: no cover - optional integration dependency
    pymysql = None

from backend.domain.errors import SimulatorValidationError
from backend.domain.openemr import (
    OPENEMR_DEFAULT_ALLOWED_PROCEDURE_CODES,
    map_openemr_procedure_order_to_gdt_order,
)


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

