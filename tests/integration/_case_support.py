import json
import io
import os
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from backend.app_factory import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
    OpenEMRProcedureOrderSource,
    SimulatorValidationError,
    collect_dashboard_resource_snapshot,
    create_app,
    dashboard_action_for_group,
    dashboard_summary,
    derive_lab_overall_status,
    dcm4chee_profile_from_config,
    dcm4chee_result_refresh_generation,
    import_gdt_bridge_files,
    parse_hl7_ack,
    parse_oru_summary,
    run_lab_application_check,
    run_lab_smoke_check,
    sync_order_to_dcm4chee_mwl,
    validate_dcm4chee_profile,
)
from backend.domain.statuses import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
)
from backend.domain.dicom import DCM4CHEE_RESULT_SOURCE_SIMULATED_AP
from backend.domain.gdt_protocol import render_gdt_message
from backend.domain.timestamps import hl7_timestamp
from backend.templates import dicom as dicom_templates
from tests.support import (
    DisposableAppCase,
    FakeDbConnection,
    FakeDockerSocketLabOperationAdapter,
    FakeHttpResponse,
)


def frontend_styles() -> str:
    root = Path(__file__).resolve().parents[2] / "frontend" / "static" / "css"
    return "\n".join(
        (root / path).read_text(encoding="utf-8")
        for path in (
            "base.css",
            "layout.css",
            "components.css",
            "views/application.css",
            "views/dashboard.css",
            "views/patient.css",
            "views/order.css",
            "views/fhir.css",
            "views/dcm4chee.css",
            "views/oie.css",
            "views/gdt.css",
            "views/settings.css",
        )
    )

class ApiCaseSupport(DisposableAppCase):
    """Shared setup and fakes for focused API assertion owners."""

    @staticmethod
    def oie_settings_payload(**overrides):
        payload = {
            "managementApi": {
                "baseUrl": "http://oie:8080",
                "username": "admin",
                "tlsVerify": False,
                "timeoutSeconds": 10,
            },
            "resultListener": {
                "host": "0.0.0.0",
                "port": 6665,
                "mllpFraming": True,
                "autoStart": True,
            },
            "managedChannels": [],
        }
        payload.update(overrides)
        return payload
    def install_openemr_source(self, connection_factory):
        self.client.application.extensions["openemr_procedure_order_source"] = OpenEMRProcedureOrderSource(
            host="openemr-mariadb",
            port=3306,
            user="openemr",
            password="openemr",
            database="openemr",
            allowed_procedure_codes=("1001",),
            connection_factory=connection_factory,
        )
    def run_openemr_smoke(self):
        store = self.lab_repository_view
        openemr = next(item for item in store.list_lab_servers() if item["name"] == "OpenEMR")
        return run_lab_smoke_check(self.client.application, store, openemr)

    def gdt_result_payload_for_order(self, order, text="Imported from bridge file"):
        return render_gdt_message(
            [
                ("3000", order["gdtPatientNumber"]),
                ("6200", order["localGdtOrderNumber"]),
                ("8402", "EKG01"),
                ("8410", order["localGdtOrderNumber"]),
                ("6220", text),
                ("6302", "report"),
                ("6303", "PDF"),
                ("6304", "Bridge PDF"),
                ("6305", "reports/missing.pdf"),
            ],
            set_type="6310",
        )

    def write_gdt_result_file(self, order, filename="device-result.gdt", text="Imported from bridge file"):
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        for folder_name in ("inbox", "outbox", "processing", "archive", "error"):
            (bridge_root / folder_name).mkdir(parents=True, exist_ok=True)
        inbound = bridge_root / "outbox" / filename
        inbound.parent.mkdir(parents=True, exist_ok=True)
        inbound.write_bytes(self.gdt_result_payload_for_order(order, text=text).encode("cp1252"))
        return inbound

    def create_local_patient(self):
        response = self.client.post(
            "/api/patients",
            json={
                "mrn": "MRN-100001",
                "firstName": "Avery",
                "middleName": "Lee",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
                "patientClass": "O",
                "assignedLocation": "CARDIOLOGY^ROOM1",
            },
        )
        self.assertEqual(response.status_code, 201)
        return response.get_json()["item"]

    def set_medplum_base_url(self, base_url):
        settings = self.app.extensions["integration_settings_service"]
        fields = dict(settings.get_public("medplum")["fields"])
        fields["baseUrl"] = base_url
        settings.replace("medplum", fields)

    def create_synced_fhir_patient(self):
        store = self.dependencies
        patient = store.patient_repository.create_patient_record(
            {
                "mode": "fhir",
                "mrn": "MRN-100002",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        fhir = store.patient_fhir.create_patient_fhir_workflow_record(patient)
        store.fhir_ledger.mark_fhir_sync_success(
            fhir["id"],
            medplum_resource_id="patient-order",
            medplum_resource_reference="Patient/patient-order",
        )
        return store.patient_repository.get_patient_record(patient["id"])


def build_dcm4chee_mwl_payload(order, profile, *, uid_root):
    return dicom_templates.build_mwl_payload(
        order,
        profile,
        uid_root=uid_root,
        timestamp_factory=hl7_timestamp,
    )

__all__ = [name for name in globals() if not name.startswith("_")]
