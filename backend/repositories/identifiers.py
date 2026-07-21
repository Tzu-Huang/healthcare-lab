"""Transaction-bound local identifier persistence."""

from __future__ import annotations

from sqlite3 import Connection

from backend.domain.patient import mrn


class PatientIdentifierRepository:
    """Owns MRN sequence SQL while using the caller's active transaction."""

    def allocate(self, connection: Connection) -> str:
        while True:
            row = connection.execute(
                "SELECT next_value FROM local_identifier_sequences WHERE name = 'patient_mrn'"
            ).fetchone()
            if not row:
                connection.execute(
                    "INSERT INTO local_identifier_sequences (name, next_value) VALUES ('patient_mrn', 1)"
                )
                continue
            value = int(row["next_value"])
            connection.execute(
                "UPDATE local_identifier_sequences SET next_value = ? WHERE name = 'patient_mrn'",
                (value + 1,),
            )
            candidate = mrn(value)
            if not connection.execute(
                "SELECT 1 FROM local_patient_records WHERE UPPER(TRIM(mrn)) = ? LIMIT 1",
                (candidate,),
            ).fetchone():
                return candidate
