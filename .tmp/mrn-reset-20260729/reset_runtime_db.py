import shutil
import sqlite3
from pathlib import Path


backup = Path(__file__).with_name("healthcare-lab.before-reset.db")
database = Path(__file__).with_name("healthcare-lab.reset.db")
shutil.copy2(backup, database)

tables = (
    "local_gdt_workflow_events",
    "local_gdt_attachment_records",
    "local_gdt_message_records",
    "local_gdt_order_records",
    "local_gdt_patient_contexts",
    "local_fhir_sync_attempts",
    "local_fhir_workflow_records",
    "local_dcm4chee_result_records",
    "local_dcm4chee_result_refresh_runs",
    "local_dcm4chee_mwl_attempts",
    "local_dcm4chee_mwl_mappings",
    "local_dcm4chee_patient_sync_attempts",
    "local_dcm4chee_patient_syncs",
    "oie_result_records",
    "ap_device_observations",
    "local_order_records",
    "local_patient_records",
)

with sqlite3.connect(database) as connection:
    before = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in tables
    }
    connection.execute("PRAGMA foreign_keys = OFF")
    connection.execute("BEGIN IMMEDIATE")
    for table in tables:
        connection.execute(f'DELETE FROM "{table}"')
    placeholders = ",".join("?" for _ in tables)
    connection.execute(
        f"DELETE FROM sqlite_sequence WHERE name IN ({placeholders})",
        tables,
    )
    connection.execute(
        """
        INSERT INTO local_identifier_sequences (name, next_value)
        VALUES ('patient_mrn', 100)
        ON CONFLICT(name) DO UPDATE SET next_value = 100
        """
    )
    connection.commit()
    connection.execute("PRAGMA foreign_keys = ON")
    violations = connection.execute("PRAGMA foreign_key_check").fetchall()
    integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
    after = {
        table: connection.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()[0]
        for table in tables
    }
    next_mrn = connection.execute(
        "SELECT next_value FROM local_identifier_sequences WHERE name = 'patient_mrn'"
    ).fetchone()[0]

print("before:", before)
print("after:", after)
print("patient_mrn.next_value:", next_mrn)
print("foreign_key_violations:", violations)
print("integrity_check:", integrity)
