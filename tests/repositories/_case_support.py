import unittest
import json
import sqlite3
from pathlib import Path

from backend.application_composition import assemble_application_dependencies

from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
)
from backend.domain.errors import SimulatorValidationError
from backend.domain.gdt_protocol import render_gdt_message
from backend.services.oie_workflow import compose_oie_workbench
from backend.services.protocol_compatibility import list_fhir_resource_mappings
from backend.templates import dicom as dicom_templates
from tests.support import DisposableStoreCase


def parse_gdt_records(payload):
    raw = payload.encode("cp1252")
    records = {}
    offset = 0
    while offset < len(raw):
        length = int(raw[offset : offset + 3].decode("ascii"))
        record = raw[offset : offset + length]
        assert record.endswith(b"\r\n")
        assert len(record) == length
        code = record[3:7].decode("ascii")
        value = record[7:-2].decode("cp1252")
        records[code] = value
        offset += length
    assert offset == len(raw)
    return records

class StoreCaseSupport(DisposableStoreCase):
    """Shared setup and factories for focused repository assertion owners."""

    @staticmethod
    def patient_payload(**overrides):
        payload = {
            "firstName": "Avery",
            "middleName": "Lee",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }
        payload.update(overrides)
        return payload

    def oie_workbench(self):
        return compose_oie_workbench(
            self.oie_coordination.list_oie_local_adt_inventory(),
            self.oie_coordination.list_oie_local_order_inventory(),
            self.dependencies.oie_repository.list_oie_results(),
        )



def build_dcm4chee_mwl_payload(order, profile, *, uid_root="1.2.826.0.1.3680043.10.543"):
    return dicom_templates.build_mwl_payload(
        order,
        profile,
        uid_root=uid_root,
        timestamp_factory=lambda: "20260720120000",
    )

__all__ = [name for name in globals() if not name.startswith("_")]
