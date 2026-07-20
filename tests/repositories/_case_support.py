import unittest
import json
from pathlib import Path

from backend.lab_store import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_PATIENT_SYNC_OPERATION_ADT_CREATE,
    DCM4CHEE_PATIENT_SYNC_STATUS_FAILED,
    DCM4CHEE_PATIENT_SYNC_STATUS_PENDING,
    DCM4CHEE_PATIENT_SYNC_STATUS_SYNCED,
    DemoStore,
    SimulatorValidationError,
    render_gdt_message,
)
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

__all__ = [name for name in globals() if not name.startswith("_")]
