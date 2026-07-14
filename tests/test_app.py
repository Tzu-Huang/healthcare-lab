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

from app import (
    DockerComposeLabOperationAdapter,
    DockerSocketLabOperationAdapter,
    OpenEMRProcedureOrderSource,
    SimulatorValidationError,
    collect_dashboard_resource_snapshot,
    create_app,
    dashboard_action_for_group,
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
from backend.lab_store import (
    DCM4CHEE_MWL_STATUS_CREATED,
    DCM4CHEE_MWL_STATUS_FAILED,
    DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
    DCM4CHEE_MWL_STATUS_PENDING,
    DCM4CHEE_RESULT_STATUS_DUPLICATE,
    DCM4CHEE_RESULT_STATUS_MATCHED,
    DCM4CHEE_RESULT_STATUS_NO_RESULT,
    DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
    DCM4CHEE_RESULT_SOURCE_SIMULATED_AP,
    DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
    render_gdt_message,
)


class FakeHttpResponse:
    def __init__(self, body, status=200):
        self.body = body
        self.status = status

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def read(self):
        return self.body


class FakeDockerSocketLabOperationAdapter(DockerSocketLabOperationAdapter):
    def __init__(self):
        super().__init__()
        self.requested_paths = []

    def is_available(self) -> bool:
        return True

    def containers_for_service(self, service_name):
        return [{"Id": "container-1", "Names": [f"/{service_name}-1"]}]

    def request(self, method, path):
        self.requested_paths.append(path)
        return 204, b""


class FakeDbCursor:
    def __init__(self, rows=None, execute_error=None):
        self.rows = rows or []
        self.execute_error = execute_error

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        return False

    def execute(self, query, params):
        if self.execute_error:
            raise self.execute_error

    def fetchall(self):
        return self.rows


class FakeDbConnection:
    def __init__(self, rows=None, execute_error=None):
        self.rows = rows or []
        self.execute_error = execute_error
        self.closed = False

    def cursor(self):
        return FakeDbCursor(self.rows, self.execute_error)

    def close(self):
        self.closed = True


class HealthcareLabApiTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        app = create_app(str(Path(self.temp_dir.name) / "app.db"))
        app.config.update(
            TESTING=True,
            GDT_BRIDGE_PATH=str(Path(self.temp_dir.name) / "gdt-bridge"),
            MEDPLUM_CLIENT_ID="demo-client",
            MEDPLUM_CLIENT_SECRET="demo-secret",
            MEDPLUM_SCOPE="openid",
            MEDPLUM_TOKEN_URL="",
            OIE_MLLP_ORDER_HOST="localhost",
            DCM4CHEE_DIMSE_HOST="127.0.0.1",
            DCM4CHEE_HL7_HOST="127.0.0.1",
            DCM4CHEE_DICOMWEB_BASE_URL="http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs",
            DCM4CHEE_QIDO_RS_URL="http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
            DCM4CHEE_WADO_RS_URL="http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
            DCM4CHEE_STOW_RS_URL="http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

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

    def test_index_serves_dashboard_only_ui(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<title>Healthcare Lab</title>", response.data)
        self.assertIn(b'data-project-mode="healthcare_lab"', response.data)
        self.assertIn(b"Server Health Dashboard", response.data)
        self.assertNotIn(b'id="protocol-mode"', response.data)
        self.assertIn(b'id="lab-console-view"', response.data)
        self.assertIn(b'id="patient-mode"', response.data)
        self.assertIn(b'class="table-wrap patient-local-table-wrap"', response.data)
        self.assertIn(b"<th>State</th><th>Created</th>", response.data)
        self.assertNotIn(b"<th>FHIR Sync</th>", response.data)
        self.assertNotIn(
            b"<th>ID</th><th>Mode</th><th>MRN</th><th>Name</th><th>DOB</th><th>Sex</th><th>Visit</th>"
            b"<th>FHIR Sync</th><th>Medplum</th><th>Created</th><th>Action</th>",
            response.data,
        )
        self.assertIn(b'id="order-view"', response.data)
        self.assertIn(b'id="order-payload-preview"', response.data)
        self.assertIn(b'class="table-wrap order-local-table-wrap"', response.data)
        self.assertIn(
            b"<th>Order ID</th><th>Mode</th><th>MRN</th><th>Visit Number</th><th>Name</th><th>Code</th><th>Status</th><th>Created At (Taipei)</th>",
            response.data,
        )
        self.assertNotIn(
            b"<th>Order</th><th>MRN</th><th>Name</th><th>Code</th><th>Status</th>"
            b"<th>Requested</th><th>Created</th><th>Actions</th>",
            response.data,
        )
        self.assertIn(b'<option value="fhir">FHIR</option>', response.data)
        self.assertIn(b'id="fhir-resource-type" value="ServiceRequest"', response.data)
        self.assertIn(b'id="fhir-service-request-id"', response.data)
        self.assertIn(b'id="fhir-status"', response.data)
        self.assertIn(b'id="fhir-intent"', response.data)
        self.assertIn(b'id="fhir-subject-reference"', response.data)
        self.assertIn(b'id="fhir-relevant-history"', response.data)
        self.assertIn(b'<option value="gdt">GDT ECG</option>', response.data)
        self.assertIn(b'id="create-gdt-patient"', response.data)
        self.assertIn(b'id="gdt-test-code" value="8402=EKG01"', response.data)
        self.assertIn(b'class="table-wrap oie-patient-table-wrap"', response.data)
        self.assertIn(b'class="lab-panel oie-transmission-panel"', response.data)
        self.assertIn(b'class="compact-output oie-preview-output"', response.data)
        self.assertIn(b'id="oie-selected-order-title"', response.data)
        self.assertIn(b'id="send-selected-oie-order"', response.data)
        self.assertIn(b'Host / IP<input id="oie-send-host"', response.data)
        self.assertNotIn(b'id="oie-order-list"', response.data)
        self.assertIn(b'id="gdt-view"', response.data)
        self.assertIn(b'id="gdt-inbox-list"', response.data)
        self.assertIn(b'id="gdt-patient-list"', response.data)
        self.assertIn(b'id="gdt-watcher-status"', response.data)
        self.assertIn(b'id="start-gdt-watcher"', response.data)
        self.assertIn(b'data-nav-target="medplum-view"', response.data)
        self.assertIn(b'id="medplum-view"', response.data)
        self.assertIn(b'<h2>Patient-Centered Console</h2>', response.data)
        self.assertIn(b'class="lab-panel medplum-patient-panel"', response.data)
        self.assertIn(b'class="medplum-context-column"', response.data)
        self.assertIn(b'class="lab-panel medplum-workflow-panel"', response.data)
        self.assertIn(b'id="medplum-patient-list"', response.data)
        self.assertIn(b'id="medplum-service-request-select"', response.data)
        self.assertIn(b'id="medplum-diagnostic-report-select"', response.data)
        self.assertIn(b'id="medplum-related-resources"', response.data)
        self.assertIn(b'id="medplum-json-preview"', response.data)
        self.assertIn(b"raw GDT-OUT or GDT-IN content", response.data)
        self.assertIn(b'id="oie-send-host" value="localhost"', response.data)
        self.assertIn(b'id="oie-listener-port" value="6665"', response.data)
        self.assertIn(b'id="oie-unmatched-result-list"', response.data)
        self.assertIn(b'id="dashboard-service-list"', response.data)
        self.assertNotIn(b'id="orders-workbench-view"', response.data)
        self.assertNotIn(b'id="hl7-v2-view"', response.data)
        self.assertNotIn(b'id="fhir-view"', response.data)
        self.assertNotIn(b'id="gdt-ap-view"', response.data)
        self.assertNotIn(b"GDT AP Simulator", response.data)
        self.assertNotIn(b"Submit to Medplum", response.data)

    def test_frontend_exposes_dashboard_gdt_order_action(self):
        app_js = Path(__file__).resolve().parents[1] / "frontend" / "static" / "app.js"
        script = app_js.read_text(encoding="utf-8")

        self.assertIn('const GENERATED_PATIENT_MRN_LABEL = "Generated on create";', script)
        self.assertIn('mrn: "",', script)
        self.assertIn("function patientPreviewMrn(payload)", script)
        self.assertNotIn('["MRN", payload.mrn],', script)
        self.assertIn("patientPreviewMrn(payload)", script)
        self.assertIn("function patientStateLabel(item)", script)
        self.assertIn('syncStatus === "Synced" && /^Patient\\/[^/]+$/.test(reference) ? "OK" : "Error"', script)
        self.assertIn('syncStatus === "Synced" && dcm4cheePatient.ack?.code === "AA" ? "OK" : "Error"', script)
        self.assertIn('return messages.length ? "Error" : "OK";', script)
        self.assertNotIn('return "Created";', script)
        self.assertIn("function orderStateLabel(item, mode)", script)
        self.assertIn("function orderModeLabel(item, mode)", script)
        self.assertIn("function orderRecordMode(item)", script)
        self.assertIn("function orderVisitNumber(item)", script)
        self.assertIn("let expandedOiePatientIds = new Set();", script)
        self.assertIn("function oiePatientSection(label, title, body)", script)
        self.assertIn("function renderOieTransmission(item)", script)
        self.assertIn('byId("send-selected-oie-order").addEventListener', script)
        self.assertIn("const ORDER_PATIENT_PROTOCOL_BY_MODE", script)
        self.assertIn("const ORDER_PATIENT_LABEL_BY_MODE", script)
        self.assertIn('"hl7-v251": "HL7 v2.5.1"', script)
        self.assertIn('"hl7-v251": "HL7 v2"', script)
        self.assertIn("function orderPatientRecordsForMode(mode = currentOrderMode())", script)
        self.assertIn("return patientRecords.filter((item) => item.protocolVersion === protocolVersion);", script)
        self.assertIn("const records = orderPatientRecordsForMode(mode);", script)
        self.assertIn("Create a ${orderPatientModeLabel(mode)} patient first", script)
        self.assertIn("const records = [...orderRecords, ...gdtOrderRecords]", script)
        self.assertIn('requestJson("/api/orders")', script)
        self.assertIn('requestJson("/api/gdt/orders")', script)
        self.assertIn('return "HL7 v2";', script)
        self.assertIn('rowCell(orderModeLabel(item, rowMode))', script)
        self.assertIn('rowCell(orderVisitNumber(item))', script)
        self.assertIn('rowCell(taipeiTimestamp(item.createdAt))', script)
        self.assertIn('"Order ID",', script)
        self.assertIn('"Visit Number",', script)
        self.assertIn('"Created At (Taipei)",', script)
        self.assertIn('statusLabel === "Accepted" ? "success" : "error"', script)
        self.assertIn('return status === "Created" ? "Accepted" : "Error";', script)
        self.assertIn('["error", "rejected", "transport error"].includes(status) ? "Error" : "Accepted"', script)
        self.assertIn('service.id === "openemr-gdt"', script)
        self.assertIn("ECG Order", script)
        self.assertIn('"/api/gdt/orders"', script)
        self.assertIn('"/api/gdt/workbench"', script)
        self.assertIn("Preview GDT-OUT", script)
        self.assertIn("Import GDT-IN", script)
        self.assertIn('"/api/gdt/bridge/watcher/start"', script)
        self.assertIn('"/api/gdt/bridge/watcher/stop"', script)
        self.assertIn("write-6302", script)
        self.assertIn('selector.value = "gdt"', script)
        self.assertIn('setActiveView("order-view")', script)
        self.assertIn('"/api/fhir/inventory"', script)
        self.assertIn('`/api/fhir/diagnostic-reports?${params.toString()}`', script)
        self.assertIn('`/api/fhir/resource-preview?${params.toString()}`', script)
        self.assertIn('`/api/fhir/records/${recordId}/preview`', script)
        self.assertIn('`/api/fhir/records/${recordId}/sync`', script)
        self.assertIn("Live fetch failed; local submitted JSON", script)
        self.assertIn("medplumDiagnosticReports", script)
        self.assertIn("fetchMedplumDiagnosticReportsForCurrentSelection", script)
        self.assertIn("renderMedplumDiagnosticReportRollup", script)
        self.assertIn("loadMedplumLiveReportPreview", script)
        self.assertIn("loadMedplumLiveReferencePreview", script)
        self.assertIn("resetMedplumDiagnosticReportState", script)
        self.assertIn("medplumDiagnosticReportKeyMatchesCurrent", script)
        self.assertIn("medplumDiagnosticReports.requestId + 1", script)
        self.assertIn("medplumDiagnosticReports.loading && medplumDiagnosticReports.key === key", script)
        self.assertIn("Patient-level result", script)
        self.assertIn("Live DiagnosticReport References", script)
        self.assertIn("medplumRecordMatchesPatient", script)
        self.assertIn("let expandedMedplumPatientIds = new Set();", script)
        self.assertIn("function medplumOrderRecordsForPatient(patient)", script)
        self.assertIn("function medplumResultRecordsForPatient(patient)", script)
        self.assertIn("function medplumResourceRollupTable(items, emptyText)", script)
        self.assertIn("function medplumPatientSection(label, title, body)", script)
        self.assertIn('toggleButton.setAttribute("aria-expanded"', script)
        self.assertIn('event.stopPropagation();\n      if (expandedMedplumPatientIds.has(patientId))', script)
        self.assertIn('"FHIR ORDERS"', script)
        self.assertIn('"FHIR RESULTS"', script)
        self.assertIn('medplumPreviewButton(item)', script)
        self.assertIn('retryButtonForMedplumRecord(item)', script)
        self.assertIn("renderMedplumPatientList", script)
        self.assertIn("renderMedplumPatientList();\n  const patient = selectedMedplumPatient();", script)
        self.assertIn('const serviceRequests = patient ? medplumRecordsForPatient(patient, "ServiceRequest") : [];', script)
        self.assertIn('item.resourceType === "ServiceRequest"', script)
        self.assertIn('"ServiceRequest",\n          medplumResourceRollupTable(orders', script)
        self.assertIn("clearMedplumPreview", script)
        self.assertIn("medplum-service-request-select", script)
        self.assertIn("medplum-diagnostic-report-select", script)
        self.assertIn("medplum-related-row", script)
        self.assertIn("buildFhirOrderPreviewPayload", script)
        self.assertIn("FHIR Order requires a synced FHIR Patient", script)
        self.assertIn('payload.mode === "hl7-v251"', script)
        self.assertIn("FHIR order code is required.", script)
        self.assertIn('payload.mode !== "fhir" && payload.requestedAt', script)
        self.assertIn("serviceRequest", script)
        self.assertIn('serviceRequest.sync?.status === "Synced"', script)
        self.assertIn('/^ServiceRequest\\/[^/]+$/.test(serviceRequestReference)', script)
        self.assertNotIn('"Task"', script)
        self.assertNotIn("item.fhir?.task", script)

        template = Path(__file__).resolve().parents[1] / "frontend" / "templates" / "index.html"
        html = template.read_text(encoding="utf-8")
        self.assertIn('id="medplum-diagnostic-report-rollup"', html)
        self.assertIn('id="medplum-diagnostic-report-status"', html)
        self.assertIn("Live Results", html)
        self.assertNotIn("Task", html)

        styles_path = Path(__file__).resolve().parents[1] / "frontend" / "static" / "styles.css"
        styles = styles_path.read_text(encoding="utf-8")
        self.assertIn(".medplum-patient-toggle", styles)
        self.assertIn(".medplum-patient-detail-row td", styles)
        self.assertIn(".medplum-patient-rollup-content", styles)
        self.assertIn(".medplum-nested-table-wrap", styles)
        self.assertIn(".medplum-context-column", styles)

    def test_sidebar_views_hide_inactive_pages(self):
        styles_path = Path(__file__).resolve().parents[1] / "frontend" / "static" / "styles.css"
        styles = styles_path.read_text(encoding="utf-8")
        self.assertIn(".app-view[hidden]", styles)
        self.assertIn("display: none", styles)
        self.assertIn(".patient-local-table-wrap", styles)
        self.assertIn(".order-local-table-wrap", styles)
        self.assertIn("max-height: 360px", styles)
        self.assertIn("overflow: auto", styles)

    def test_only_healthcare_lab_routes_are_registered(self):
        routes = {rule.rule for rule in self.client.application.url_map.iter_rules()}
        self.assertIn("/api/dashboard/services", routes)
        self.assertIn("/api/lab/servers", routes)
        self.assertIn("/api/orders", routes)
        self.assertIn("/api/oie/local-orders", routes)
        self.assertIn("/api/oie/settings", routes)
        self.assertIn("/api/oie/result-listener/start", routes)
        self.assertIn("/api/oie/workbench", routes)
        self.assertIn("/api/oie/results", routes)
        self.assertNotIn("/api/listener/start", routes)
        self.assertNotIn("/api/integration-records", routes)
        self.assertNotIn("/api/workbench/orders", routes)
        self.assertNotIn("/api/fhir/submit", routes)
        self.assertIn("/api/fhir/mappings", routes)
        self.assertIn("/api/fhir/inventory", routes)
        self.assertIn("/api/fhir/diagnostic-reports", routes)
        self.assertIn("/api/fhir/resource-preview", routes)
        self.assertIn("/api/fhir/records", routes)
        self.assertIn("/api/fhir/records/<int:record_id>", routes)
        self.assertIn("/api/fhir/records/<int:record_id>/preview", routes)
        self.assertIn("/api/fhir/records/<int:record_id>/sync", routes)
        self.assertIn("/api/fhir/records/<int:record_id>/attempts", routes)
        self.assertIn("/api/gdt/orders", routes)
        self.assertIn("/api/gdt/orders/<int:order_id>", routes)
        self.assertIn("/api/gdt/messages", routes)
        self.assertIn("/api/gdt/orders/<int:order_id>/events", routes)
        self.assertIn("/api/gdt/results", routes)
        self.assertIn("/api/gdt/workbench", routes)
        self.assertIn("/api/gdt/bridge/config", routes)
        self.assertIn("/api/gdt/bridge/watcher/status", routes)
        self.assertIn("/api/gdt/bridge/watcher/start", routes)
        self.assertIn("/api/gdt/bridge/watcher/stop", routes)
        self.assertIn("/api/gdt/orders/<int:order_id>/write-6302", routes)
        self.assertIn("/api/gdt/orders/<int:order_id>/demo-result", routes)
        self.assertIn("/api/gdt/bridge/inbox", routes)
        self.assertIn("/api/gdt/bridge/import", routes)
        self.assertIn("/api/orders/<int:order_id>/dcm4chee-mwl-verify", routes)
        self.assertIn("/api/dcm4chee/e2e-fixture", routes)
        self.assertIn("/api/orders/<int:order_id>/dcm4chee-e2e-evidence", routes)
        self.assertIn("/api/orders/<int:order_id>/dcm4chee-simulated-ap-return", routes)

    def test_gdt_bridge_config_api_updates_shared_folder_path(self):
        target = Path(self.temp_dir.name) / "custom-gdt-bridge"

        response = self.client.put("/api/gdt/bridge/config", json={"bridgePath": str(target)})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["item"]["bridgePath"], str(target))
        self.assertFalse(target.exists())
        self.assertEqual(body["item"]["inboxPath"], str(target / "inbox"))
        self.assertEqual(body["item"]["outboxPath"], str(target / "outbox"))
        current = self.client.get("/api/gdt/bridge/config").get_json()["item"]
        self.assertEqual(current["outboxPath"], str(target / "outbox"))
        self.assertIn("watcher", current)

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
                "mrn": "MRN-A04-001",
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

    def test_patient_api_allocates_blank_mrn_and_rejects_duplicate(self):
        payload = {
            "mrn": "",
            "firstName": "Avery",
            "lastName": "Morgan",
            "dob": "19850412",
            "sex": "F",
        }

        created = self.client.post("/api/patients", json=payload)

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["summary"]["mrn"], "MRN-000001")
        self.assertIn("PID|1||MRN-000001^^^HEALTHCARE_LAB^MR", item["payload"])

        duplicate = self.client.post("/api/patients", json={**payload, "mrn": "MRN-000001"})

        self.assertEqual(duplicate.status_code, 400)
        self.assertIn("Patient MRN MRN-000001 already exists", duplicate.get_json()["error"])
        self.assertEqual(len(self.client.get("/api/patients").get_json()["items"]), 1)

    def test_integration_patient_lists_filter_to_their_own_protocol(self):
        store = self.client.application.extensions["demo_store"]
        patients = {
            mode: store.create_patient_record(
                {
                    "mode": mode,
                    "mrn": f"MRN-{mode.upper()}",
                    "firstName": mode,
                    "lastName": "Patient",
                    "dob": "19850412",
                    "sex": "F",
                }
            )
            for mode in ("hl7-v2", "fhir", "gdt", "dicom")
        }
        store.create_patient_fhir_workflow_record(patients["fhir"])

        oie = self.client.get("/api/oie/workbench").get_json()["patients"]
        oie_local = self.client.get("/api/oie/local-adt-patients").get_json()["items"]
        gdt = self.client.get("/api/gdt/workbench").get_json()["patients"]
        medplum = self.client.get("/api/fhir/inventory").get_json()["patients"]
        dcm4chee = self.client.get("/api/patients?protocolVersion=DICOM").get_json()["items"]

        self.assertEqual([item["id"] for item in oie], [patients["hl7-v2"]["id"]])
        self.assertEqual([item["id"] for item in oie_local], [patients["hl7-v2"]["id"]])
        self.assertEqual([item["id"] for item in gdt], [patients["gdt"]["id"]])
        self.assertEqual([item["localSourceId"] for item in medplum], [str(patients["fhir"]["id"])])
        self.assertEqual([item["id"] for item in dcm4chee], [patients["dicom"]["id"]])

    def set_medplum_base_url(self, base_url):
        store = self.client.application.extensions["demo_store"]
        medplum = next(item for item in store.list_lab_servers() if item["name"] == "Medplum")
        store.update_lab_server(medplum["id"], {"baseUrl": base_url})

    def test_order_api_creates_and_lists_local_orm_order(self):
        patient = self.create_local_patient()

        created = self.client.post(
            "/api/orders",
            json={
                "patientRecordId": patient["id"],
                "priority": "R",
                "requestedAt": "20260703103000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Chest pain evaluation",
            },
        )

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["status"], "Ready to send")
        self.assertEqual(item["messageType"], "ORM^O01")
        self.assertEqual(item["visitNumber"], item["visitId"])
        self.assertEqual(item["summary"]["visitNumber"], item["summary"]["visitId"])
        self.assertIn("ORM^O01^ORM_O01", item["payload"])
        self.assertIn("|P|2.5.1||||||UNICODE UTF-8", item["payload"])
        self.assertIn("MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|", item["payload"])

        listed = self.client.get("/api/oie/local-orders")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"][0]["localOrderNumber"], item["localOrderNumber"])

    def test_patient_api_creates_fhir_local_patient_without_medplum_base(self):
        self.set_medplum_base_url("")

        response = self.client.post(
            "/api/patients",
            json={
                "mode": "fhir",
                "mrn": "MRN-FHIR-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "FHIR R4")
        self.assertEqual(item["messageType"], "Patient")
        self.assertIn('"resourceType": "Patient"', item["payload"])
        self.assertEqual(item["fhir"]["sync"]["status"], "Sync failed")
        self.assertIn("base URL", item["fhir"]["sync"]["error"])

    @patch("app.send_hl7_mllp_message")
    def test_patient_api_creates_dicom_patient_and_syncs_dcm4chee(self, send_hl7):
        send_hl7.return_value = (
            "MSH|^~\\&|DCM4CHEE|DCM4CHEE|HEALTHCARE_LAB|LAB_APP|20260709101010||ACK^A04^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8"
            "\rMSA|AA|DCMADT1|OK"
        )

        response = self.client.post(
            "/api/patients",
            json={
                "mode": "dicom",
                "mrn": "MRN-DCM-001",
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
        item = response.get_json()["item"]
        dcm4chee_patient = item["dcm4chee"]["patient"]
        self.assertEqual(dcm4chee_patient["status"], "Synced")
        self.assertEqual(dcm4chee_patient["patientId"], "MRN-DCM-001")
        self.assertEqual(dcm4chee_patient["issuerOfPatientId"], "local-dcm4chee")
        self.assertEqual(dcm4chee_patient["ack"]["code"], "AA")
        sent_payload = send_hl7.call_args.args[0]
        self.assertIn("ADT^A04^ADT_A01", sent_payload)
        self.assertIn("|P|2.5.1||||||UNICODE UTF-8", sent_payload)
        self.assertIn("PID|1||MRN-DCM-001^^^local-dcm4chee^MR", sent_payload)
        self.assertEqual(send_hl7.call_args.kwargs["host"], "127.0.0.1")
        self.assertEqual(send_hl7.call_args.kwargs["port"], 2575)

    @patch("app.send_hl7_mllp_message", side_effect=OSError("connection refused"))
    def test_patient_api_preserves_dicom_patient_when_dcm4chee_sync_fails(self, _send_hl7):
        response = self.client.post(
            "/api/patients",
            json={
                "mode": "dicom",
                "mrn": "MRN-DCM-002",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "DICOM")
        dcm4chee_patient = item["dcm4chee"]["patient"]
        self.assertEqual(dcm4chee_patient["status"], "Sync failed")
        self.assertTrue(dcm4chee_patient["retryable"])
        self.assertEqual(dcm4chee_patient["lastErrorType"], "dcm4chee_hl7_unreachable")
        self.assertIn("connection refused", dcm4chee_patient["lastError"])

    @patch("app.urllib.request.urlopen")
    def test_patient_api_creates_fhir_patient_and_syncs_medplum(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        calls = []
        create_payloads = []

        def fake_urlopen(request, timeout):
            calls.append((request.get_method(), request.full_url))
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            self.assertEqual(request.get_method(), "POST")
            create_payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeHttpResponse(
                json.dumps({"resourceType": "Patient", "id": "patient-created"}).encode("utf-8"),
                status=201,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.post(
            "/api/patients",
            json={
                "mode": "fhir",
                "mrn": "MRN-FHIR-002",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
                "email": "avery@example.org",
                "addressLine": "100 Main St",
                "addressCity": "Boston",
                "addressPostalCode": "02110",
                "managingOrganizationReference": "Organization/healthcare-lab",
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["fhir"]["sync"]["status"], "Synced")
        self.assertEqual(item["fhir"]["medplum"]["reference"], "Patient/patient-created")
        self.assertEqual(create_payloads[0]["telecom"][0], {"system": "email", "value": "avery@example.org"})
        self.assertEqual(create_payloads[0]["address"][0]["city"], "Boston")
        self.assertEqual(create_payloads[0]["managingOrganization"]["reference"], "Organization/healthcare-lab")
        methods = [method for method, url in calls if not url.endswith("/oauth2/token")]
        self.assertEqual(methods, ["GET", "POST"])

        listed = self.client.get("/api/patients").get_json()["items"]
        self.assertEqual(listed[0]["fhir"]["medplum"]["reference"], "Patient/patient-created")

    @patch("app.urllib.request.urlopen")
    def test_patient_api_preserves_fhir_patient_when_sync_fails_and_retry_succeeds(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "temporary failure"}],
        }
        retry_mode = {"enabled": False}

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if not retry_mode["enabled"]:
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    hdrs=None,
                    fp=FakeHttpResponse(json.dumps(outcome).encode("utf-8"), status=400),
                )
            self.assertEqual(request.get_method(), "GET")
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Bundle",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Patient",
                                    "id": "patient-existing",
                                }
                            }
                        ],
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        created = self.client.post(
            "/api/patients",
            json={
                "mode": "fhir",
                "mrn": "MRN-FHIR-003",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        )

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["fhir"]["sync"]["status"], "Sync failed")
        self.assertEqual(item["fhir"]["sync"]["operationOutcome"], outcome)
        self.assertTrue(self.client.get("/api/patients").get_json()["items"][0]["fhir"]["recordId"])

        retry_mode["enabled"] = True
        retried = self.client.post(f"/api/patients/{item['id']}/fhir-sync", json={})

        self.assertEqual(retried.status_code, 200)
        self.assertTrue(retried.get_json()["success"])
        self.assertEqual(retried.get_json()["item"]["fhir"]["sync"]["status"], "Synced")
        self.assertEqual(retried.get_json()["item"]["fhir"]["medplum"]["reference"], "Patient/patient-existing")

    def test_fhir_mapping_and_record_apis_expose_local_sync_status(self):
        mappings = self.client.get("/api/fhir/mappings")
        self.assertEqual(mappings.status_code, 200)
        by_type = {item["resourceType"]: item for item in mappings.get_json()["items"]}
        self.assertIn("Patient", by_type)
        self.assertIn("DiagnosticReport", by_type)
        self.assertIn("DocumentReference", by_type["DiagnosticReport"]["dependsOn"])

        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            },
        )

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["sync"]["status"], "Pending sync")
        self.assertEqual(item["resource"]["identifier"][0]["value"], "local-patient-records-1")
        listed = self.client.get("/api/fhir/records")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"][0]["id"], item["id"])

    def test_fhir_inventory_exposes_patient_relations_and_local_preview(self):
        patient = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]
        observation = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_fhir_results",
                "localSourceId": "obs-1",
                "resource": {
                    "resourceType": "Observation",
                    "status": "final",
                    "subject": {"reference": "Patient/patient-created"},
                },
            },
        ).get_json()["item"]
        store = self.client.application.extensions["demo_store"]
        store.mark_fhir_sync_success(
            patient["id"],
            medplum_resource_id="patient-created",
            medplum_resource_reference="Patient/patient-created",
        )

        inventory = self.client.get("/api/fhir/inventory")

        self.assertEqual(inventory.status_code, 200)
        body = inventory.get_json()
        by_id = {item["id"]: item for item in body["items"]}
        self.assertEqual(by_id[patient["id"]]["previewSource"], "medplum-live")
        self.assertEqual(by_id[observation["id"]]["patientReferences"], ["Patient/patient-created"])
        self.assertEqual(by_id[observation["id"]]["references"], ["Patient/patient-created"])
        self.assertEqual(by_id[observation["id"]]["summary"]["primary"], "Observation")
        self.assertEqual(by_id[observation["id"]]["summary"]["status"], "final")
        self.assertTrue(by_id[observation["id"]]["retryable"])
        self.assertEqual(body["patients"][0]["reference"], "Patient/patient-created")

        preview = self.client.get(f"/api/fhir/records/{observation['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["source"], "local-submitted")
        self.assertEqual(preview.get_json()["resource"]["subject"]["reference"], "Patient/patient-created")

    @patch("app.urllib.request.urlopen")
    def test_fhir_record_preview_uses_medplum_live_json_for_synced_resource(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]
        store = self.client.application.extensions["demo_store"]
        store.mark_fhir_sync_success(
            created["id"],
            medplum_resource_id="patient-created",
            medplum_resource_reference="Patient/patient-created",
        )

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertEqual(request.full_url, "http://medplum.test/fhir/R4/Patient/patient-created")
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Patient",
                        "id": "patient-created",
                        "active": False,
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        preview = self.client.get(f"/api/fhir/records/{created['id']}/preview")

        self.assertEqual(preview.status_code, 200)
        body = preview.get_json()
        self.assertEqual(body["source"], "medplum-live")
        self.assertTrue(body["live"]["fetched"])
        self.assertFalse(body["resource"]["active"])

    @patch("app.urllib.request.urlopen")
    def test_fhir_record_preview_falls_back_to_local_json_when_live_fetch_fails(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]
        store = self.client.application.extensions["demo_store"]
        store.mark_fhir_sync_success(
            created["id"],
            medplum_resource_id="patient-created",
            medplum_resource_reference="Patient/patient-created",
        )

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            raise urllib.error.URLError("medplum down")

        urlopen.side_effect = fake_urlopen

        preview = self.client.get(f"/api/fhir/records/{created['id']}/preview")

        self.assertEqual(preview.status_code, 200)
        body = preview.get_json()
        self.assertEqual(body["source"], "local-submitted-fallback")
        self.assertFalse(body["live"]["fetched"])
        self.assertIn("medplum down", body["live"]["error"])
        self.assertTrue(body["resource"]["active"])

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_fetches_patient_bundle_and_summaries(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request.get_method(), request.full_url))
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertIn("/DiagnosticReport?", request.full_url)
            self.assertIn("subject=Patient%2Fpatient-1", request.full_url)
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Bundle",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "DiagnosticReport",
                                    "id": "report-1",
                                    "status": "final",
                                    "code": {"text": "ECG report"},
                                    "subject": {"reference": "Patient/patient-1"},
                                    "effectiveDateTime": "2026-07-08T01:02:03Z",
                                    "result": [{"reference": "Observation/obs-1"}],
                                    "media": [
                                        {
                                            "comment": "PDF",
                                            "link": {"reference": "DocumentReference/doc-1"},
                                        }
                                    ],
                                    "presentedForm": [{"url": "Binary/bin-1"}],
                                }
                            }
                        ],
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get("/api/fhir/diagnostic-reports?patient=Patient/patient-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertFalse(body["empty"])
        self.assertEqual(body["strategy"], "patient")
        self.assertEqual(body["patientReference"], "Patient/patient-1")
        self.assertEqual(body["bundle"]["resourceType"], "Bundle")
        report = body["reports"][0]
        self.assertEqual(report["reference"], "DiagnosticReport/report-1")
        self.assertEqual(report["display"], "ECG report")
        self.assertEqual(report["status"], "final")
        self.assertEqual(report["date"], "2026-07-08T01:02:03Z")
        self.assertEqual(report["relationshipType"], "patient-level")
        self.assertEqual(report["resultCount"], 1)
        self.assertEqual(report["attachmentCount"], 2)
        self.assertEqual(
            report["relationships"]["related"],
            [
                {"resourceType": "Observation", "reference": "Observation/obs-1"},
                {"resourceType": "DocumentReference", "reference": "DocumentReference/doc-1"},
                {"resourceType": "Binary", "reference": "Binary/bin-1"},
            ],
        )
        self.assertTrue(any("subject=Patient%2Fpatient-1" in url for _method, url in calls))

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_empty_bundle_is_successful(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get("/api/fhir/diagnostic-reports?patient=Patient/patient-empty")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertTrue(body["empty"])
        self.assertEqual(body["reports"], [])

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_falls_back_when_based_on_search_is_unsupported(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if "based-on=ServiceRequest%2Fsr-1" in request.full_url:
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Unsupported search parameter",
                    hdrs=None,
                    fp=io.BytesIO(
                        json.dumps(
                            {
                                "resourceType": "OperationOutcome",
                                "issue": [{"diagnostics": "Unknown search parameter based-on"}],
                            }
                        ).encode("utf-8")
                    ),
                )
            self.assertIn("subject=Patient%2Fpatient-1", request.full_url)
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Bundle",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "DiagnosticReport",
                                    "id": "linked",
                                    "subject": {"reference": "Patient/patient-1"},
                                    "basedOn": [{"reference": "ServiceRequest/sr-1"}],
                                }
                            },
                            {
                                "resource": {
                                    "resourceType": "DiagnosticReport",
                                    "id": "other-order",
                                    "subject": {"reference": "Patient/patient-1"},
                                    "basedOn": [{"reference": "ServiceRequest/sr-2"}],
                                }
                            },
                            {
                                "resource": {
                                    "resourceType": "DiagnosticReport",
                                    "id": "patient-level",
                                    "subject": {"reference": "Patient/patient-1"},
                                }
                            },
                        ],
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get(
            "/api/fhir/diagnostic-reports"
            "?patient=Patient/patient-1&serviceRequest=ServiceRequest/sr-1"
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["strategy"], "patient-filter")
        self.assertIn("based-on", body["fallbackReason"])
        self.assertEqual([item["id"] for item in body["reports"]], ["linked", "patient-level"])
        self.assertEqual(body["reports"][0]["relationshipType"], "order-linked")
        self.assertEqual(body["reports"][1]["relationshipType"], "patient-level")

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_prefers_based_on_when_subject_search_fails(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if "based-on=ServiceRequest%2Fsr-1" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "resourceType": "Bundle",
                            "entry": [
                                {
                                    "resource": {
                                        "resourceType": "DiagnosticReport",
                                        "id": "linked",
                                        "subject": {"reference": "Patient/patient-1"},
                                        "basedOn": [{"reference": "ServiceRequest/sr-1"}],
                                    }
                                }
                            ],
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertIn("subject=Patient%2Fpatient-1", request.full_url)
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Unsupported subject search",
                hdrs=None,
                fp=io.BytesIO(b'{"resourceType":"OperationOutcome"}'),
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get(
            "/api/fhir/diagnostic-reports"
            "?patient=Patient/patient-1&serviceRequest=ServiceRequest/sr-1"
        )

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["strategy"], "based-on")
        self.assertIn("HTTP 400", body["fallbackReason"])
        self.assertEqual([item["id"] for item in body["reports"]], ["linked"])
        self.assertEqual(body["reports"][0]["relationshipType"], "order-linked")

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_surfaces_unauthorized_fetch(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            raise urllib.error.HTTPError(
                request.full_url,
                401,
                "Unauthorized",
                hdrs=None,
                fp=io.BytesIO(b'{"resourceType":"OperationOutcome"}'),
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get("/api/fhir/diagnostic-reports?patient=Patient/patient-1")

        self.assertEqual(response.status_code, 401)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["statusCode"], 401)
        self.assertEqual(body["operationOutcome"]["resourceType"], "OperationOutcome")

    @patch("app.urllib.request.urlopen")
    def test_fhir_diagnostic_reports_rejects_malformed_bundle(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps({"resourceType": "OperationOutcome"}).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get("/api/fhir/diagnostic-reports?patient=Patient/patient-1")

        self.assertEqual(response.status_code, 502)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertIn("non-Bundle", body["error"])

    @patch("app.urllib.request.urlopen")
    def test_fhir_resource_preview_fetches_live_binary_reference(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertEqual(request.full_url, "http://medplum.test/fhir/R4/Binary/bin-1")
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Binary",
                        "id": "bin-1",
                        "contentType": "application/pdf",
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.get("/api/fhir/resource-preview?reference=Binary/bin-1")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["source"], "medplum-live")
        self.assertEqual(body["reference"], "Binary/bin-1")
        self.assertEqual(body["resource"]["resourceType"], "Binary")

    @patch("app.urllib.request.urlopen")
    def test_fhir_sync_reuses_existing_medplum_resource_by_identifier(self, urlopen):
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "1",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertIn("/Patient?", request.full_url)
            self.assertEqual(request.get_method(), "GET")
            return FakeHttpResponse(
                json.dumps(
                    {
                        "resourceType": "Bundle",
                        "entry": [
                            {
                                "resource": {
                                    "resourceType": "Patient",
                                    "id": "patient-existing",
                                }
                            }
                        ],
                    }
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        synced = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(synced.status_code, 200)
        item = synced.get_json()["item"]
        self.assertTrue(synced.get_json()["success"])
        self.assertEqual(item["sync"]["status"], "Synced")
        self.assertEqual(item["medplum"]["reference"], "Patient/patient-existing")
        attempts = self.client.get(f"/api/fhir/records/{created['id']}/attempts").get_json()["items"]
        self.assertEqual(len(attempts), 1)
        self.assertEqual(attempts[0]["method"], "GET")

    @patch("app.urllib.request.urlopen")
    def test_fhir_sync_creates_once_when_identifier_is_missing(self, urlopen):
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "2",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]
        calls = []

        def fake_urlopen(request, timeout):
            calls.append((request.get_method(), request.full_url))
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            self.assertEqual(request.get_method(), "POST")
            self.assertTrue(request.data)
            return FakeHttpResponse(
                json.dumps({"resourceType": "Patient", "id": "patient-created"}).encode("utf-8"),
                status=201,
            )

        urlopen.side_effect = fake_urlopen

        synced = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(synced.status_code, 200)
        self.assertEqual(synced.get_json()["item"]["medplum"]["id"], "patient-created")
        methods = [method for method, _url in calls if not _url.endswith("/oauth2/token")]
        self.assertEqual(methods, ["GET", "POST"])
        attempts = self.client.get(f"/api/fhir/records/{created['id']}/attempts").get_json()["items"]
        self.assertEqual([item["method"] for item in attempts], ["POST", "GET"])

        retried = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(retried.status_code, 200)
        self.assertEqual(retried.get_json()["item"]["medplum"]["id"], "patient-created")
        retry_methods = [method for method, _url in calls if not _url.endswith("/oauth2/token")]
        self.assertEqual(retry_methods, ["GET", "POST", "GET"])

    @patch("app.urllib.request.urlopen")
    def test_fhir_sync_updates_existing_medplum_resource_after_local_change(self, urlopen):
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "22",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]
        calls = []
        put_payloads = []

        def fake_urlopen(request, timeout):
            calls.append((request.get_method(), request.full_url))
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "POST":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Patient", "id": "patient-created"}).encode("utf-8"),
                    status=201,
                )
            self.assertEqual(request.get_method(), "PUT")
            put_payloads.append(json.loads(request.data.decode("utf-8")))
            return FakeHttpResponse(
                json.dumps({"resourceType": "Patient", "id": "patient-created"}).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        first_sync = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})
        changed = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "22",
                "resource": {"resourceType": "Patient", "active": False},
            },
        ).get_json()["item"]
        second_sync = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(first_sync.status_code, 200)
        self.assertEqual(changed["sync"]["status"], "Pending sync")
        self.assertEqual(second_sync.status_code, 200)
        self.assertEqual(second_sync.get_json()["item"]["sync"]["status"], "Synced")
        methods = [method for method, _url in calls if not _url.endswith("/oauth2/token")]
        self.assertEqual(methods, ["GET", "POST", "GET", "PUT"])
        self.assertEqual(put_payloads[0]["id"], "patient-created")
        self.assertFalse(put_payloads[0]["active"])

    @patch("app.urllib.request.urlopen")
    def test_fhir_sync_failure_preserves_operation_outcome(self, urlopen):
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_order_records",
                "localSourceId": "7",
                "resource": {
                    "resourceType": "ServiceRequest",
                    "status": "active",
                    "intent": "order",
                },
            },
        ).get_json()["item"]
        outcome = {
            "resourceType": "OperationOutcome",
            "issue": [{"severity": "error", "diagnostics": "bad identifier"}],
        }

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            raise urllib.error.HTTPError(
                request.full_url,
                400,
                "Bad Request",
                hdrs=None,
                fp=FakeHttpResponse(json.dumps(outcome).encode("utf-8"), status=400),
            )

        urlopen.side_effect = fake_urlopen

        synced = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(synced.status_code, 200)
        body = synced.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["item"]["sync"]["status"], "Sync failed")
        self.assertEqual(body["item"]["sync"]["operationOutcome"], outcome)
        attempts = self.client.get(f"/api/fhir/records/{created['id']}/attempts").get_json()["items"]
        self.assertEqual(attempts[0]["method"], "GET")
        self.assertEqual(attempts[0]["httpStatus"], 400)
        self.assertEqual(attempts[0]["responsePayload"], outcome)
        self.assertEqual(attempts[0]["operationOutcome"], outcome)

    def test_fhir_sync_validation_failure_marks_record_failed(self):
        self.client.application.config["MEDPLUM_CLIENT_ID"] = ""
        self.client.application.config["MEDPLUM_CLIENT_SECRET"] = ""
        created = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_patient_records",
                "localSourceId": "3",
                "resource": {"resourceType": "Patient", "active": True},
            },
        ).get_json()["item"]

        synced = self.client.post(f"/api/fhir/records/{created['id']}/sync", json={})

        self.assertEqual(synced.status_code, 200)
        body = synced.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["item"]["sync"]["status"], "Sync failed")
        self.assertIn("client credentials", body["item"]["sync"]["error"])
        attempts = self.client.get(f"/api/fhir/records/{created['id']}/attempts").get_json()["items"]
        self.assertEqual(attempts[0]["method"], "GET")
        self.assertIn("client credentials", attempts[0]["error"])

    def create_synced_fhir_patient(self):
        store = self.client.application.extensions["demo_store"]
        patient = store.create_patient_record(
            {
                "mode": "fhir",
                "mrn": "MRN-FHIR-ORDER-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            }
        )
        fhir = store.create_patient_fhir_workflow_record(patient)
        store.mark_fhir_sync_success(
            fhir["id"],
            medplum_resource_id="patient-order",
            medplum_resource_reference="Patient/patient-order",
        )
        return store.get_patient_record(patient["id"])

    @patch("app.urllib.request.urlopen")
    def test_order_api_creates_only_fhir_service_request(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        patient = self.create_synced_fhir_patient()
        created_payloads = []

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            payload = json.loads(request.data.decode("utf-8"))
            created_payloads.append(payload)
            if payload["resourceType"] == "ServiceRequest":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "ServiceRequest", "id": "sr-created"}).encode("utf-8"),
                    status=201,
                )
            self.fail(f"Unexpected payload: {payload}")

        urlopen.side_effect = fake_urlopen

        response = self.client.post(
            "/api/orders",
            json={
                "mode": "fhir",
                "patientRecordId": patient["id"],
                "fhir": {
                    "status": "active",
                    "intent": "order",
                    "priority": "stat",
                    "codeCode": "ECG12",
                    "codeDisplay": "12 Lead ECG",
                    "occurrenceDateTime": "2026-07-08T10:30",
                    "authoredOn": "2026-07-08T09:00",
                    "requester": "Practitioner/prac-1",
                    "reasonCodeText": "Chest pain evaluation",
                },
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "FHIR R4")
        self.assertEqual(item["fhir"]["serviceRequest"]["sync"]["status"], "Synced")
        self.assertEqual(item["fhir"]["serviceRequest"]["medplum"]["reference"], "ServiceRequest/sr-created")
        self.assertEqual(set(item["fhir"]), {"serviceRequest"})
        self.assertEqual(len(created_payloads), 1)
        service_request = next(payload for payload in created_payloads if payload["resourceType"] == "ServiceRequest")
        self.assertEqual(service_request["subject"]["reference"], "Patient/patient-order")
        self.assertRegex(service_request["occurrenceDateTime"], r"^2026-07-08T10:30:00[+-]\d{2}:\d{2}$")
        self.assertRegex(service_request["authoredOn"], r"^2026-07-08T09:00:00[+-]\d{2}:\d{2}$")

    @patch("app.urllib.request.urlopen")
    def test_order_api_preserves_fhir_service_request_sync_failure(self, urlopen):
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        patient = self.create_synced_fhir_patient()

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() != "GET" and "ServiceRequest" in request.full_url:
                raise urllib.error.HTTPError(
                    request.full_url,
                    400,
                    "Bad Request",
                    hdrs=None,
                    fp=FakeHttpResponse(
                        json.dumps(
                            {
                                "resourceType": "OperationOutcome",
                                "issue": [{"severity": "error", "diagnostics": "service request rejected"}],
                            }
                        ).encode("utf-8"),
                        status=400,
                    ),
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps({"resourceType": "ServiceRequest", "id": "sr-created"}).encode("utf-8"),
                status=201,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.post(
            "/api/orders",
            json={
                "mode": "fhir",
                "patientRecordId": patient["id"],
                "fhir": {"status": "active", "intent": "order", "codeCode": "ECG12"},
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["fhir"]["serviceRequest"]["sync"]["status"], "Sync failed")
        self.assertIn("service request rejected", item["fhir"]["serviceRequest"]["sync"]["error"])
        self.assertEqual(set(item["fhir"]), {"serviceRequest"})

    def test_historical_fhir_task_is_excluded_from_active_api_contracts(self):
        store = self.client.application.extensions["demo_store"]
        record = store.create_fhir_workflow_record(
            {
                "localSourceType": "local_order_records",
                "localSourceId": "historical-task",
                "resourceType": "ServiceRequest",
                "resource": {
                    "resourceType": "ServiceRequest",
                    "status": "active",
                    "intent": "order",
                    "subject": {"reference": "Patient/historical"},
                },
            }
        )
        with store.connect() as connection:
            connection.execute(
                """
                UPDATE local_fhir_workflow_records
                SET resource_type = 'Task', resource_json = ?, medplum_resource_reference = 'Task/historical'
                WHERE id = ?
                """,
                (json.dumps({"resourceType": "Task", "status": "completed", "intent": "order"}), record["id"]),
            )

        listed = self.client.get("/api/fhir/records").get_json()["items"]
        self.assertNotIn(record["id"], [item["id"] for item in listed])
        inventory = self.client.get("/api/fhir/inventory").get_json()["items"]
        self.assertNotIn(record["id"], [item["id"] for item in inventory])
        self.assertEqual(self.client.get(f"/api/fhir/records/{record['id']}").status_code, 400)
        self.assertEqual(self.client.get(f"/api/fhir/records/{record['id']}/preview").status_code, 400)
        self.set_medplum_base_url("http://medplum.test/fhir/R4")
        self.assertEqual(self.client.post(f"/api/fhir/records/{record['id']}/sync", json={}).status_code, 400)

        create = self.client.post(
            "/api/fhir/records",
            json={
                "localSourceType": "local_order_records",
                "localSourceId": "new-task",
                "resourceType": "Task",
                "resource": {"resourceType": "Task", "status": "requested", "intent": "order"},
            },
        )
        self.assertEqual(create.status_code, 400)

    def test_order_api_rejects_missing_patient(self):
        response = self.client.post("/api/orders", json={"patientRecordId": 404})

        self.assertEqual(response.status_code, 404)

    def test_dcm4chee_mwl_payload_uses_profile_and_generated_identifiers(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        order = store.create_dcm4chee_order_record(
            {
                "patientRecordId": patient["id"],
                "requestedAt": "20260708103000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Chest pain evaluation",
            }
        )
        payload = store.build_dcm4chee_mwl_payload(
            order,
            dcm4chee_profile_from_config(self.client.application.config),
            uid_root="1.2.826.0.1.3680043.10.543",
        )

        self.assertEqual(payload["00100010"]["Value"][0]["Alphabetic"], "Morgan^Avery^Lee")
        self.assertEqual(payload["00100020"]["Value"], ["MRN-A04-001"])
        self.assertEqual(payload["00100021"]["Value"], ["local-dcm4chee"])
        self.assertEqual(payload["00080050"]["Value"], ["ACC-000001"])
        self.assertEqual(payload["00401001"]["Value"], ["RP-000001"])
        self.assertRegex(payload["0020000D"]["Value"][0], r"^1\.2\.826\.0\.1\.3680043\.10\.543\.\d+\.\d+$")
        sps = payload["00400100"]["Value"][0]
        self.assertEqual(sps["00400001"]["Value"], ["ECG_AP"])
        self.assertEqual(sps["00400009"]["Value"], ["SPS-000001"])
        self.assertEqual(sps["00400020"]["Value"], ["SCHEDULED"])

    @patch("app.urllib.request.urlopen")
    def test_order_api_creates_dcm4chee_mwl_attempt(self, urlopen):
        patient = self.create_local_patient()
        captured = []

        def fake_urlopen(request, timeout):
            method = request.get_method()
            captured.append(
                {
                    "url": request.full_url,
                    "method": method,
                    "payload": json.loads(request.data.decode("utf-8")) if request.data else None,
                    "headers": dict(request.header_items()),
                }
            )
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            if method == "GET":
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                                "00080050": {"vr": "SH", "Value": ["ACC-DCM-000001"]},
                                "00401001": {"vr": "SH", "Value": ["RP-DCM-000001"]},
                                "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                                "00741202": {"vr": "LO", "Value": ["12 Lead ECG"]},
                                "00400100": {
                                    "vr": "SQ",
                                    "Value": [
                                        {
                                            "00400001": {"vr": "AE", "Value": ["ECG_AP"]},
                                            "00400009": {"vr": "SH", "Value": ["SPS-DCM-000001"]},
                                        }
                                    ],
                                },
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps({"created": True, "id": "mwl-1"}).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.post(
            "/api/orders",
            json={
                "mode": "dicom",
                "patientRecordId": patient["id"],
                "requestedAt": "20260708103000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Chest pain evaluation",
            },
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "DICOM")
        self.assertEqual(item["messageType"], "MWL")
        mwl = item["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_CREATED)
        self.assertEqual(mwl["httpStatus"], 200)
        self.assertEqual(mwl["accessionNumber"], "ACC-000001")
        self.assertEqual(mwl["mapping"]["status"], DCM4CHEE_MWL_STATUS_CREATED)
        self.assertEqual(mwl["mapping"]["accessionNumber"], "ACC-DCM-000001")
        self.assertEqual(mwl["mapping"]["requestedProcedureId"], "RP-DCM-000001")
        self.assertEqual(mwl["mapping"]["scheduledProcedureStepId"], "SPS-DCM-000001")
        self.assertEqual(mwl["mapping"]["patientId"], "MRN-A04-001")
        self.assertEqual(captured[0]["method"], "GET")
        self.assertIn("/aets/DCM4CHEE/rs/patients?", captured[0]["url"])
        self.assertEqual(captured[1]["method"], "POST")
        self.assertEqual(
            captured[1]["url"],
            "http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs/mwlitems",
        )
        self.assertEqual(captured[1]["headers"]["Content-type"], "application/dicom+json")
        self.assertEqual(captured[1]["payload"]["00400100"]["Value"][0]["00400001"]["Value"], ["ECG_AP"])
        self.assertEqual(captured[2]["method"], "GET")
        self.assertIn("AccessionNumber=ACC-000001", captured[2]["url"])

    @patch("app.urllib.request.urlopen")
    @patch("app.send_hl7_mllp_message")
    def test_order_api_creates_dcm4chee_mwl_after_dicom_patient_sync(self, send_hl7, urlopen):
        send_hl7.return_value = "MSH|^~\\&|DCM4CHEE|DCM4CHEE|HEALTHCARE_LAB|LAB_APP|20260709101010||ACK^A04^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8\rMSA|AA|DCMADT1|OK"
        captured = []

        def fake_urlopen(request, timeout):
            captured.append(request.get_method())
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-DCM-MWL-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                                "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                                "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                                "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                                "00400100": {
                                    "vr": "SQ",
                                    "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                                },
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(json.dumps({"created": True}).encode("utf-8"), status=200)

        urlopen.side_effect = fake_urlopen
        patient = self.client.post(
            "/api/patients",
            json={
                "mode": "dicom",
                "mrn": "MRN-DCM-MWL-001",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        ).get_json()["item"]

        created = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(created.status_code, 201)
        mwl = created.get_json()["item"]["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_CREATED)
        self.assertEqual(captured, ["POST", "GET"])
        self.assertEqual(send_hl7.call_count, 1)

    @patch("app.urllib.request.urlopen")
    @patch("app.send_hl7_mllp_message", side_effect=OSError("connection refused"))
    def test_order_api_blocks_dcm4chee_mwl_when_dicom_patient_sync_fails(self, send_hl7, urlopen):
        patient = self.client.post(
            "/api/patients",
            json={
                "mode": "dicom",
                "mrn": "MRN-DCM-MWL-002",
                "firstName": "Avery",
                "lastName": "Morgan",
                "dob": "19850412",
                "sex": "F",
            },
        ).get_json()["item"]

        created = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["protocolVersion"], "DICOM")
        mwl = item["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_PATIENT_MISSING)
        self.assertEqual(mwl["errorType"], "patient_sync_failed")
        self.assertFalse(mwl["retryable"])
        self.assertIn("connection refused", mwl["error"])
        self.assertEqual(send_hl7.call_count, 2)
        urlopen.assert_not_called()

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_sync_reuses_successful_mapping_without_duplicate_post(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})

        def fake_urlopen(request, timeout):
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                                "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                                "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                                "00400100": {
                                    "vr": "SQ",
                                    "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                                },
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(json.dumps({"created": True}).encode("utf-8"), status=200)

        urlopen.side_effect = fake_urlopen

        sync_order_to_dcm4chee_mwl(
            store,
            order,
            dcm4chee_profile_from_config(self.client.application.config),
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        self.assertEqual(urlopen.call_count, 3)

        urlopen.reset_mock()
        mapping = sync_order_to_dcm4chee_mwl(
            store,
            store.get_order_record(int(order["id"])),
            dcm4chee_profile_from_config(self.client.application.config),
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )

        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)
        urlopen.assert_not_called()

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_sync_endpoint_retries_failed_order_and_reuses_successful_mapping(self, urlopen):
        patient = self.create_local_patient()
        phase = {"name": "fail-create"}
        calls = []
        mwl_gets = {"count": 0}

        def fake_urlopen(request, timeout):
            calls.append(request.get_method())
            if phase["name"] == "fail-create":
                raise urllib.error.URLError("connection refused")
            if phase["name"] == "retry-success":
                if "/patients?" in request.full_url:
                    return FakeHttpResponse(b"", status=204)
                if request.full_url.endswith("/patients"):
                    return FakeHttpResponse(b'{"PatientIdentifiers":"[MRN-A04-001^^^local-dcm4chee]"}', status=200)
                if request.get_method() == "GET":
                    mwl_gets["count"] += 1
                    body = [] if mwl_gets["count"] == 1 else [
                        {
                            "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                            "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                            "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                            "00400100": {
                                "vr": "SQ",
                                "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                            },
                        }
                    ]
                    return FakeHttpResponse(json.dumps(body).encode("utf-8"), status=200)
                return FakeHttpResponse(json.dumps({"created": True}).encode("utf-8"), status=200)
            raise AssertionError("Unexpected dcm4chee request")

        urlopen.side_effect = fake_urlopen
        created = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(created.status_code, 201)
        order_id = created.get_json()["item"]["id"]
        mwl = created.get_json()["item"]["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_FAILED)
        self.assertTrue(mwl["retryable"])
        self.assertEqual(mwl["displayStatus"], "Retry needed")

        phase["name"] = "retry-success"
        calls.clear()
        mwl_gets["count"] = 0
        retry = self.client.post(f"/api/orders/{order_id}/dcm4chee-sync")

        self.assertEqual(retry.status_code, 200)
        body = retry.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["item"]["dcm4chee"]["mwl"]["displayStatus"], "Synced")
        self.assertFalse(body["item"]["dcm4chee"]["mwl"]["retryable"])
        self.assertEqual(calls, ["GET", "POST", "GET", "POST", "GET"])

        calls.clear()
        duplicate_retry = self.client.post(f"/api/orders/{order_id}/dcm4chee-sync")

        self.assertEqual(duplicate_retry.status_code, 200)
        self.assertTrue(duplicate_retry.get_json()["success"])
        self.assertEqual(calls, [])

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_sync_endpoint_preserves_order_when_retry_fails(self, urlopen):
        patient = self.create_local_patient()
        urlopen.side_effect = urllib.error.URLError("connection refused")

        created = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(created.status_code, 201)
        order_id = created.get_json()["item"]["id"]
        retry = self.client.post(f"/api/orders/{order_id}/dcm4chee-sync")

        self.assertEqual(retry.status_code, 200)
        body = retry.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["item"]["id"], order_id)
        mwl = body["item"]["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_FAILED)
        self.assertTrue(mwl["retryable"])
        self.assertIn("connection refused", mwl["latest"]["error"])
        self.assertGreaterEqual(mwl["mapping"]["retryCount"], 1)

    def test_dcm4chee_sync_endpoint_rejects_unknown_and_non_dicom_orders(self):
        missing = self.client.post("/api/orders/404/dcm4chee-sync")
        self.assertEqual(missing.status_code, 404)

        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        retry = self.client.post(f"/api/orders/{order['id']}/dcm4chee-sync")

        self.assertEqual(retry.status_code, 400)
        self.assertIn("not DICOM", retry.get_json()["error"])

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_attempt_history_endpoint_lists_newest_first(self, urlopen):
        patient = self.create_local_patient()
        urlopen.side_effect = urllib.error.URLError("connection refused")
        created = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})
        order_id = created.get_json()["item"]["id"]
        self.client.post(f"/api/orders/{order_id}/dcm4chee-sync")

        response = self.client.get(f"/api/orders/{order_id}/dcm4chee-attempts")

        self.assertEqual(response.status_code, 200)
        attempts = response.get_json()["items"]
        self.assertEqual(len(attempts), 2)
        self.assertEqual([item["operationType"] for item in attempts], ["create", "create"])
        self.assertTrue(all(item["error"] for item in attempts))

    def test_dcm4chee_mapping_retry_reuses_stable_identifiers(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )

        first = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
        )
        second = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_PENDING,
            increment_retry=True,
        )

        self.assertEqual(first["id"], second["id"])
        self.assertEqual(second["retryCount"], 1)
        self.assertEqual(second["accessionNumber"], first["accessionNumber"])
        self.assertEqual(second["requestedProcedureId"], first["requestedProcedureId"])
        self.assertEqual(second["scheduledProcedureStepId"], first["scheduledProcedureStepId"])
        self.assertEqual(second["studyInstanceUid"], first["studyInstanceUid"])

    def test_dcm4chee_mapping_lookup_uses_reconciliation_identifiers(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        by_study = store.find_dcm4chee_mwl_mapping_for_reconciliation(
            study_instance_uid=mapping["studyInstanceUid"]
        )
        by_accession = store.find_dcm4chee_mwl_mapping_for_reconciliation(
            accession_number=mapping["accessionNumber"],
            profile_name=mapping["profileName"],
            server_identity=mapping["serverIdentity"],
        )
        by_procedure = store.find_dcm4chee_mwl_mapping_for_reconciliation(
            requested_procedure_id=mapping["requestedProcedureId"],
            scheduled_procedure_step_id=mapping["scheduledProcedureStepId"],
            profile_name=mapping["profileName"],
            server_identity=mapping["serverIdentity"],
        )

        self.assertEqual(by_study["orderRecordId"], order["id"])
        self.assertEqual(by_accession["orderRecordId"], order["id"])
        self.assertEqual(by_procedure["orderRecordId"], order["id"])

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_failed_retry_reads_back_before_duplicate_post(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_FAILED,
        )
        methods = []

        def fake_urlopen(request, timeout):
            methods.append(request.get_method())
            self.assertEqual(request.get_method(), "GET")
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps(
                    [
                        {
                            "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                            "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                            "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                            "00400100": {
                                "vr": "SQ",
                                "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                            },
                        }
                    ]
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        result = sync_order_to_dcm4chee_mwl(
            store,
            store.get_order_record(int(order["id"])),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )

        self.assertEqual(result["operationType"], "read-back")
        self.assertEqual(methods, ["GET", "GET"])
        mapping = store.get_dcm4chee_mwl_mapping_for_order(int(order["id"]))
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_create_with_readback_failure_retries_readback_without_post(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        methods = []

        def first_urlopen(request, timeout):
            methods.append(request.get_method())
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                raise urllib.error.URLError("read-back unavailable")
            return FakeHttpResponse(json.dumps({"created": True}).encode("utf-8"), status=200)

        urlopen.side_effect = first_urlopen
        response = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(methods, ["GET", "POST", "GET"])
        item = response.get_json()["item"]
        mapping = item["dcm4chee"]["mwl"]["mapping"]
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_PENDING)
        self.assertEqual(mapping["lastErrorType"], "dcm4chee_readback_failed")

        methods.clear()

        def retry_urlopen(request, timeout):
            methods.append(request.get_method())
            self.assertEqual(request.get_method(), "GET")
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps(
                    [
                        {
                            "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                            "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                            "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                            "00400100": {
                                "vr": "SQ",
                                "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                            },
                        }
                    ]
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = retry_urlopen
        result = sync_order_to_dcm4chee_mwl(
            store,
            store.get_order_record(int(item["id"])),
            dcm4chee_profile_from_config(self.client.application.config),
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )

        self.assertEqual(result["operationType"], "read-back")
        self.assertEqual(methods, ["GET", "GET"])
        mapping = store.get_dcm4chee_mwl_mapping_for_order(int(item["id"]))
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_create_with_empty_readback_retries_readback_without_post(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        methods = []

        def first_urlopen(request, timeout):
            methods.append(request.get_method())
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            if request.get_method() == "GET":
                return FakeHttpResponse(b"[]", status=200)
            return FakeHttpResponse(json.dumps({"created": True}).encode("utf-8"), status=200)

        urlopen.side_effect = first_urlopen
        response = self.client.post("/api/orders", json={"mode": "dicom", "patientRecordId": patient["id"]})

        self.assertEqual(response.status_code, 201)
        self.assertEqual(methods, ["GET", "POST", "GET"])
        item = response.get_json()["item"]
        mapping = item["dcm4chee"]["mwl"]["mapping"]
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_PENDING)
        self.assertEqual(mapping["lastErrorType"], "dcm4chee_readback_empty")

        methods.clear()

        def retry_urlopen(request, timeout):
            methods.append(request.get_method())
            self.assertEqual(request.get_method(), "GET")
            if "/patients?" in request.full_url:
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "00100020": {"vr": "LO", "Value": ["MRN-A04-001"]},
                                "00100021": {"vr": "LO", "Value": ["local-dcm4chee"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(
                json.dumps(
                    [
                        {
                            "00080050": {"vr": "SH", "Value": ["ACC-000001"]},
                            "00401001": {"vr": "SH", "Value": ["RP-000001"]},
                            "0020000D": {"vr": "UI", "Value": ["1.2.826.0.1.3680043.10.543.20260708103000.1"]},
                            "00400100": {
                                "vr": "SQ",
                                "Value": [{"00400009": {"vr": "SH", "Value": ["SPS-000001"]}}],
                            },
                        }
                    ]
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = retry_urlopen
        result = sync_order_to_dcm4chee_mwl(
            store,
            store.get_order_record(int(item["id"])),
            dcm4chee_profile_from_config(self.client.application.config),
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )

        self.assertEqual(result["operationType"], "read-back")
        self.assertEqual(methods, ["GET", "GET"])
        mapping = store.get_dcm4chee_mwl_mapping_for_order(int(item["id"]))
        self.assertEqual(mapping["status"], DCM4CHEE_MWL_STATUS_CREATED)

    @patch("app.urllib.request.urlopen")
    def test_order_api_records_dcm4chee_patient_missing_without_deleting_order(self, urlopen):
        patient = self.create_local_patient()

        def fake_urlopen(request, timeout):
            if "/patients?" in request.full_url:
                return FakeHttpResponse(b"", status=204)
            if request.full_url.endswith("/patients"):
                return FakeHttpResponse(b'{"PatientIdentifiers":"[MRN-A04-001^^^local-dcm4chee]"}', status=200)
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=FakeHttpResponse(b'{"errorMessage":"Patient[id=MRN-001] does not exist."}', status=404),
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.post(
            "/api/orders",
            json={"mode": "dicom", "patientRecordId": patient["id"]},
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        self.assertEqual(item["dcm4chee"]["mwl"]["status"], DCM4CHEE_MWL_STATUS_PATIENT_MISSING)
        self.assertEqual(item["dcm4chee"]["mwl"]["errorType"], "patient_missing")
        self.assertIn("does not exist", item["dcm4chee"]["mwl"]["responseBody"])
        detail = self.client.get(f"/api/orders").get_json()["items"][0]
        self.assertEqual(detail["id"], item["id"])
        self.assertEqual(detail["dcm4chee"]["mwl"]["status"], DCM4CHEE_MWL_STATUS_PATIENT_MISSING)

    @patch("app.urllib.request.urlopen")
    def test_order_api_records_dcm4chee_profile_validation_failure(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_DICOMWEB_BASE_URL"] = "not-a-url"

        response = self.client.post(
            "/api/orders",
            json={"mode": "dicom", "patientRecordId": patient["id"]},
        )

        self.assertEqual(response.status_code, 201)
        mwl = response.get_json()["item"]["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_FAILED)
        self.assertEqual(mwl["errorType"], "profile_invalid")
        self.assertIn("profile is incomplete", mwl["error"])
        urlopen.assert_not_called()

    @patch("app.urllib.request.urlopen")
    def test_order_api_records_dcm4chee_missing_station_profile_failure(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_DEFAULT_SCHEDULED_STATION_AE_TITLE"] = ""

        response = self.client.post(
            "/api/orders",
            json={"mode": "dicom", "patientRecordId": patient["id"]},
        )

        self.assertEqual(response.status_code, 201)
        item = response.get_json()["item"]
        mwl = item["dcm4chee"]["mwl"]
        self.assertEqual(mwl["status"], DCM4CHEE_MWL_STATUS_FAILED)
        self.assertEqual(mwl["errorType"], "profile_invalid")
        self.assertIn("profile is incomplete", mwl["error"])
        self.assertEqual(mwl["scheduledStationAETitle"], "")
        self.assertEqual(mwl["requestPayload"], {})
        detail = self.client.get("/api/orders").get_json()["items"][0]
        self.assertEqual(detail["id"], item["id"])
        self.assertEqual(detail["dcm4chee"]["mwl"]["errorType"], "profile_invalid")
        urlopen.assert_not_called()

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_mwl_verify_endpoint_records_matching_order(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        urlopen.return_value = FakeHttpResponse(
            json.dumps(
                [
                    {
                        "00100020": {"vr": "LO", "Value": [mapping["patientId"]]},
                        "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
                        "00080050": {"vr": "SH", "Value": [mapping["accessionNumber"]]},
                        "00401001": {"vr": "SH", "Value": [mapping["requestedProcedureId"]]},
                        "00741202": {"vr": "LO", "Value": [mapping["worklistLabel"]]},
                        "00400100": {
                            "vr": "SQ",
                            "Value": [
                                {
                                    "00400001": {"vr": "AE", "Value": [mapping["scheduledStationAETitle"]]},
                                    "00400009": {"vr": "SH", "Value": [mapping["scheduledProcedureStepId"]]},
                                }
                            ],
                        },
                    }
                ]
            ).encode("utf-8"),
            status=200,
        )

        response = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["latestAttempt"]["operationType"], "verify-mwl")
        verification = body["verification"]
        self.assertEqual(verification["status"], "verified")
        self.assertEqual(verification["method"], "dcm4chee-mwl-rest")
        self.assertEqual(verification["match"]["identifiers"]["accession_number"], mapping["accessionNumber"])
        self.assertIn("AccessionNumber=ACC-000001", urlopen.call_args[0][0].full_url)
        attempts = self.client.get(f"/api/orders/{order['id']}/dcm4chee-attempts").get_json()["items"]
        self.assertEqual(attempts[0]["operationType"], "verify-mwl")

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_mwl_verify_endpoint_records_empty_response(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )
        urlopen.return_value = FakeHttpResponse(b"[]", status=200)

        response = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["success"])
        verification = body["verification"]
        self.assertEqual(verification["status"], "verification_failed")
        self.assertEqual(verification["errorType"], "mwl_empty")
        self.assertEqual(body["latestAttempt"]["errorType"], "mwl_empty")

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_mwl_verify_keeps_patient_missing_precondition(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
        )
        store.update_dcm4chee_mwl_mapping_from_attempt(
            int(order["id"]),
            attempt_id=None,
            sync_status=DCM4CHEE_MWL_STATUS_PATIENT_MISSING,
            http_status=404,
            response_body='{"errorMessage":"Patient[id=MRN-A04-001] does not exist."}',
            error_type="patient_missing",
            error_text="dcm4chee returned HTTP 404: Patient does not exist.",
        )

        response = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertEqual(body["verification"]["errorType"], "patient_missing")
        self.assertEqual(body["latestAttempt"]["status"], DCM4CHEE_MWL_STATUS_PATIENT_MISSING)
        urlopen.assert_not_called()

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_mwl_verify_endpoint_records_mismatch_and_ambiguity(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        def item(accession, patient_id="MRN-A04-001"):
            return {
                "00100020": {"vr": "LO", "Value": [patient_id]},
                "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
                "00080050": {"vr": "SH", "Value": [accession]},
                "00401001": {"vr": "SH", "Value": [mapping["requestedProcedureId"]]},
                "00400100": {
                    "vr": "SQ",
                    "Value": [
                        {
                            "00400001": {"vr": "AE", "Value": [mapping["scheduledStationAETitle"]]},
                            "00400009": {"vr": "SH", "Value": [mapping["scheduledProcedureStepId"]]},
                        }
                    ],
                },
            }

        urlopen.return_value = FakeHttpResponse(json.dumps([item("OTHER")]).encode("utf-8"), status=200)
        mismatch = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")
        self.assertEqual(mismatch.get_json()["verification"]["errorType"], "mwl_mismatch")

        urlopen.return_value = FakeHttpResponse(
            json.dumps([item(mapping["accessionNumber"]), item(mapping["accessionNumber"])]).encode("utf-8"),
            status=200,
        )
        ambiguous = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")
        verification = ambiguous.get_json()["verification"]
        self.assertEqual(verification["status"], "verification_ambiguous")
        self.assertEqual(verification["errorType"], "mwl_ambiguous")

    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_mwl_verify_endpoint_records_patient_missing_and_profile_failure(self, urlopen):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        def missing_patient(request, timeout):
            raise urllib.error.HTTPError(
                request.full_url,
                404,
                "Not Found",
                hdrs=None,
                fp=FakeHttpResponse(b'{"errorMessage":"Patient[id=MRN-A04-001] does not exist."}', status=404),
            )

        urlopen.side_effect = missing_patient
        response = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")
        self.assertEqual(response.get_json()["verification"]["errorType"], "patient_missing")
        self.assertEqual(response.get_json()["latestAttempt"]["status"], DCM4CHEE_MWL_STATUS_PATIENT_MISSING)

        self.client.application.config["DCM4CHEE_DICOMWEB_BASE_URL"] = "not-a-url"
        urlopen.reset_mock()
        response = self.client.post(f"/api/orders/{order['id']}/dcm4chee-mwl-verify")
        self.assertEqual(response.get_json()["verification"]["errorType"], "mwl_profile_invalid")

    def test_patient_dcm4chee_result_ui_hooks_are_present(self):
        template = Path("frontend/templates/index.html").read_text(encoding="utf-8")
        script = Path("frontend/static/app.js").read_text(encoding="utf-8")

        self.assertIn('data-nav-target="dcm4chee-view"', template)
        self.assertIn('id="dcm4chee-view"', template)
        self.assertNotIn('type="button" disabled>\n          <span class="nav-icon">DC</span>dcm4chee', template)
        self.assertIn('class="app-view dcm4chee-workspace"', template)
        self.assertIn('class="lab-panel dcm4chee-patient-panel"', template)
        self.assertIn('class="lab-panel dcm4chee-workflow-panel"', template)
        self.assertIn("Patient-Centered Console", template)
        self.assertNotIn('class="dcm4chee-console-grid lower-grid"', template)
        self.assertIn("dcm4chee-patient-list", template)
        self.assertNotIn("dcm4chee-order-list", template)
        self.assertNotIn("Selected Patient Orders", template)
        self.assertEqual(template.count('id="dcm4chee-selected-patient-summary"'), 1)
        self.assertLess(
            template.index('id="dcm4chee-patient-list"'),
            template.index('id="dcm4chee-selected-patient-summary"'),
        )
        self.assertIn("dcm4chee-patient-select", template)
        self.assertIn("dcm4chee-order-select", template)
        self.assertIn("dcm4chee-payload-preview", template)
        self.assertIn("send-dcm4chee-order", template)
        self.assertIn("dcm4chee-profile-summary", template)
        self.assertIn("refreshPatientDcm4cheeResults", script)
        self.assertIn("/api/patients/${patientId}/dcm4chee-results-refresh", script)
        self.assertIn("refreshDcm4cheeConsole", script)
        self.assertIn("/api/dcm4chee/profile/diagnostics", script)
        self.assertIn("renderDcm4cheeConsole", script)
        self.assertIn("renderDcm4cheeSelectors", script)
        self.assertIn("renderDcm4cheePreview", script)
        self.assertIn("sendDcm4cheeOrder", script)
        self.assertIn("let expandedDcm4cheePatientIds = new Set();", script)
        self.assertIn('createElement("button", "V", "dcm4chee-patient-toggle")', script)
        self.assertIn("renderDcm4cheeExpandedOrders", script)
        self.assertIn("renderDcm4cheeExpandedResults", script)
        self.assertIn("renderDcm4cheeResultTable", script)
        self.assertIn("function dcm4cheeFirstArtifact(records)", script)
        self.assertIn("const artifact = dcm4cheeFirstArtifact(study.records);", script)
        self.assertIn('"Artifact", "Artifact Type", "Artifact Location"', script)
        self.assertIn('dcm4cheeActionsForResult({ ...representative, artifact }, "study")', script)
        self.assertIn('"dcm4chee-study-table-wrap"', script)
        self.assertIn('"dcm4chee-series-table-wrap"', script)
        self.assertNotIn('section.className = "detail-block raw-details dcm4chee-result-browser"', script)
        toggle_start = script.index('toggleButton.addEventListener("click"')
        toggle_end = script.index("renderDcm4cheeConsole();", toggle_start)
        toggle_handler = script[toggle_start:toggle_end]
        self.assertNotIn("selectedDcm4cheePatientId", toggle_handler)
        self.assertIn('row.addEventListener("click", () => selectDcm4cheePatient(patient.id))', script)
        self.assertIn('byId("send-dcm4chee-order").addEventListener', script)
        self.assertIn("patientIdsWithDicomOrders", script)
        self.assertIn("renderDcm4cheeSelectedPatient", script)
        self.assertIn("renderDcm4cheeSelectedOrder", script)
        self.assertIn("renderPatientDcm4cheeResults", script)
        self.assertIn("DICOM Results", script)
        self.assertIn("dicomResults", script)
        self.assertIn("groupDcm4cheeResultsForBrowser", script)
        self.assertIn("renderDcm4cheeStudyDetails", script)
        self.assertIn("renderDcm4cheeSeriesDetails", script)
        self.assertIn("renderDcm4cheeInstanceTable", script)
        self.assertIn("Study Instance UID", script)
        self.assertIn("Series Instance UID", script)
        self.assertIn("SOP Instance UID", script)
        self.assertIn("Accession Number", script)
        self.assertIn("Issuer of Patient ID", script)
        self.assertIn("Open Viewer", script)
        self.assertIn("Copy Retrieve", script)
        self.assertIn("Refresh PACS Results", script)
        self.assertIn("Simulate AP PDF", script)
        self.assertIn("Simulate AP DICOM", script)
        self.assertIn("/api/orders/${orderId}/dcm4chee-simulated-ap-return", script)
        self.assertIn("Open Artifact", script)
        self.assertIn("Copy Artifact", script)
        self.assertIn("MWL Sync", script)
        self.assertIn("MWL Queryable", script)
        self.assertIn("AP C-STORE Result", script)
        self.assertIn("Reconciliation", script)

        styles = Path("frontend/static/styles.css").read_text(encoding="utf-8")
        self.assertIn(".dcm4chee-workflow-strip", styles)
        self.assertIn(".dcm4chee-console-grid", styles)
        self.assertIn(".dcm4chee-workflow-panel", styles)
        self.assertIn(".dcm4chee-selected-order-bar", styles)
        self.assertIn(".dcm4chee-patient-toggle", styles)
        self.assertIn(".dcm4chee-patient-detail-row", styles)
        self.assertIn(".dcm4chee-patient-rollup-content", styles)
        self.assertIn(".dcm4chee-patient-preview", styles)
        self.assertIn(".dcm4chee-patient-sync-card dd", styles)
        self.assertIn("overflow-wrap: anywhere", styles)
        self.assertIn("height: 560px", styles)
        self.assertIn(".dcm4chee-result-browser", styles)
        self.assertIn(".dcm4chee-result-table-wrap", styles)
        self.assertIn(".dcm4chee-study-table-wrap table", styles)
        self.assertIn(".dcm4chee-browser-row", styles)
        self.assertIn(".dcm4chee-nested-table-wrap", styles)

    def test_dcm4chee_e2e_fixture_api_creates_demo_patient_order_and_evidence(self):
        response = self.client.post("/api/dcm4chee/e2e-fixture", json={})

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["patient"]["summary"]["mrn"], "MRN-DCM-E2E-001")
        self.assertEqual(body["order"]["protocolVersion"], "DICOM")
        evidence = body["evidence"]
        self.assertEqual(evidence["mode"], "dcm4chee-production-like-e2e")
        self.assertEqual(evidence["identifiers"]["patientId"], "MRN-DCM-E2E-001")
        self.assertEqual(evidence["identifiers"]["issuerOfPatientId"], "local-dcm4chee")
        self.assertEqual(evidence["aeTitles"]["mwlAETitle"], "WORKLIST")
        self.assertIn("/mwlitems", evidence["endpoints"]["mwlRestUrl"])
        self.assertEqual(evidence["steps"]["apReturn"], "not_recorded")

    def test_dcm4chee_simulated_ap_return_records_pdf_and_dicom_results(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        response = self.client.post(
            f"/api/orders/{order['id']}/dcm4chee-simulated-ap-return",
            json={"type": "both", "artifactUrl": "http://localhost/reports/zac-42.pdf"},
        )

        self.assertEqual(response.status_code, 201)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertEqual(body["evidence"]["steps"]["apReturn"], "recorded")
        self.assertTrue(body["evidence"]["steps"]["uiVisibleResult"])
        self.assertEqual(body["evidence"]["identifiers"]["studyInstanceUid"], mapping["studyInstanceUid"])
        items = body["items"]
        self.assertEqual(len(items), 2)
        self.assertEqual({item["source"] for item in items}, {DCM4CHEE_RESULT_SOURCE_SIMULATED_AP})
        self.assertIn(DCM4CHEE_RESULT_STATUS_MATCHED, {item["reconciliationStatus"] for item in items})
        pdf = next(item for item in items if item["sourceType"] == "pdf")
        self.assertEqual(pdf["artifact"]["url"], "http://localhost/reports/zac-42.pdf")
        self.assertEqual(pdf["artifact"]["mediaType"], "application/pdf")

        patient_detail = self.client.get("/api/patients").get_json()["items"][0]
        self.assertEqual(patient_detail["dcm4chee"]["resultCount"], 2)
        self.assertEqual(
            {item["source"] for item in patient_detail["dcm4chee"]["dicomResults"]},
            {DCM4CHEE_RESULT_SOURCE_SIMULATED_AP},
        )

        evidence = self.client.get(f"/api/orders/{order['id']}/dcm4chee-e2e-evidence")
        self.assertEqual(evidence.status_code, 200)
        self.assertEqual(evidence.get_json()["evidence"]["steps"]["resultReconciliation"], DCM4CHEE_RESULT_STATUS_MATCHED)

    def test_dcm4chee_simulated_ap_return_sequence_keeps_pdf_and_dicom_visible(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        pdf = self.client.post(
            f"/api/orders/{order['id']}/dcm4chee-simulated-ap-return",
            json={"type": "pdf", "artifactUrl": "http://localhost/reports/zac-42.pdf"},
        )
        store.begin_dcm4chee_result_refresh(patient["id"], "intervening-refresh")
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="intervening-refresh",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "intervening-refresh")
        dicom = self.client.post(
            f"/api/orders/{order['id']}/dcm4chee-simulated-ap-return",
            json={"type": "dicom"},
        )

        self.assertEqual(pdf.status_code, 201)
        self.assertEqual(dicom.status_code, 201)
        self.assertEqual(pdf.get_json()["refreshGeneration"], dicom.get_json()["refreshGeneration"])
        patient_detail = self.client.get("/api/patients").get_json()["items"][0]
        results = patient_detail["dcm4chee"]["dicomResults"]
        self.assertEqual(patient_detail["dcm4chee"]["resultCount"], 2)
        self.assertEqual({item["sourceType"] for item in results}, {"pdf", "dicom"})
        self.assertTrue(any(item["artifact"].get("mediaType") == "application/pdf" for item in results))

    @patch("app.urllib.request.urlopen")
    def test_patient_dcm4chee_result_refresh_reconciles_study_series_and_instance(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_QIDO_RS_URL"] = (
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
        )
        self.client.application.config["DCM4CHEE_WADO_RS_URL"] = (
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
        )
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )
        calls = []

        def fake_urlopen(request, timeout):
            calls.append(request.full_url)
            if request.full_url.endswith("/series"):
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "0020000D": {"vr": "UI", "Value": [mapping["studyInstanceUid"]]},
                                "0020000E": {"vr": "UI", "Value": ["1.2.3.series"]},
                                "00080060": {"vr": "CS", "Value": ["ECG"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            if request.full_url.endswith("/instances"):
                return FakeHttpResponse(
                    json.dumps(
                        [
                            {
                                "0020000D": {"vr": "UI", "Value": [mapping["studyInstanceUid"]]},
                                "0020000E": {"vr": "UI", "Value": ["1.2.3.series"]},
                                "00080018": {"vr": "UI", "Value": ["1.2.3.instance"]},
                                "00080060": {"vr": "CS", "Value": ["ECG"]},
                            }
                        ]
                    ).encode("utf-8"),
                    status=200,
                )
            self.assertIn("/studies?", request.full_url)
            return FakeHttpResponse(
                json.dumps(
                    [
                        {
                            "00100020": {"vr": "LO", "Value": [mapping["patientId"]]},
                            "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
                            "00080050": {"vr": "SH", "Value": [mapping["accessionNumber"]]},
                            "00401001": {"vr": "SH", "Value": [mapping["requestedProcedureId"]]},
                            "0020000D": {"vr": "UI", "Value": [mapping["studyInstanceUid"]]},
                            "00080060": {"vr": "CS", "Value": ["ECG"]},
                            "00080020": {"vr": "DA", "Value": ["20260709"]},
                            "00080030": {"vr": "TM", "Value": ["101500"]},
                            "00400100": {
                                "vr": "SQ",
                                "Value": [{"00400009": {"vr": "SH", "Value": [mapping["scheduledProcedureStepId"]]}}],
                            },
                        }
                    ]
                ).encode("utf-8"),
                status=200,
            )

        urlopen.side_effect = fake_urlopen

        response = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        self.assertGreaterEqual(len(body["items"]), 3)
        matched = [item for item in body["items"] if item["reconciliationStatus"] == DCM4CHEE_RESULT_STATUS_MATCHED]
        self.assertTrue(matched)
        self.assertEqual(matched[0]["orderRecordId"], order["id"])
        self.assertIn(mapping["studyInstanceUid"], matched[0]["viewerUrl"])
        self.assertTrue(any("/studies?" in url and "StudyInstanceUID=" in url for url in calls))
        patient_detail = self.client.get("/api/patients").get_json()["items"][0]
        self.assertGreaterEqual(patient_detail["dcm4chee"]["resultCount"], 3)

    @patch("app.urllib.request.urlopen")
    def test_patient_dcm4chee_result_refresh_records_diagnostics(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_QIDO_RS_URL"] = (
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
        )
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        urlopen.return_value = FakeHttpResponse(b"[]", status=200)
        empty = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")
        self.assertEqual(empty.status_code, 200)
        self.assertIn(
            DCM4CHEE_RESULT_STATUS_NO_RESULT,
            {item["reconciliationStatus"] for item in empty.get_json()["items"]},
        )

        urlopen.return_value = FakeHttpResponse(
            json.dumps(
                [
                    {
                        "00100020": {"vr": "LO", "Value": ["OTHER-MRN"]},
                        "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
                        "00080050": {"vr": "SH", "Value": [mapping["accessionNumber"]]},
                        "0020000D": {"vr": "UI", "Value": ["9.9.9"]},
                    }
                ]
            ).encode("utf-8"),
            status=200,
        )
        wrong_patient = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")
        self.assertIn(
            DCM4CHEE_RESULT_STATUS_WRONG_PATIENT,
            {item["reconciliationStatus"] for item in wrong_patient.get_json()["items"]},
        )

        def query_failure(request, timeout):
            raise urllib.error.URLError("connection refused")

        urlopen.side_effect = query_failure
        failed = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")
        self.assertEqual(failed.status_code, 200)
        self.assertFalse(failed.get_json()["success"])
        self.assertIn(
            DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
            {item["reconciliationStatus"] for item in failed.get_json()["items"]},
        )

    @patch("app.uuid.uuid4")
    @patch("app.datetime")
    def test_dcm4chee_result_refresh_generation_is_unique_when_clock_does_not_advance(
        self,
        datetime_mock,
        uuid4_mock,
    ):
        datetime_mock.now.return_value.isoformat.return_value = "2026-07-13T06:44:12.000000+00:00"
        uuid4_mock.side_effect = [
            SimpleNamespace(hex="generation-a"),
            SimpleNamespace(hex="generation-b"),
        ]

        first = dcm4chee_result_refresh_generation()
        second = dcm4chee_result_refresh_generation()

        self.assertEqual(first, "2026-07-13T06:44:12.000000+00:00-generation-a")
        self.assertEqual(second, "2026-07-13T06:44:12.000000+00:00-generation-b")
        self.assertNotEqual(first, second)

    @patch("backend.lab_store.now_iso", return_value="2026-07-13T15:30:00+08:00")
    def test_dcm4chee_result_refresh_run_order_supersedes_updated_lower_id_row(self, _now_iso):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)

        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="generation-1",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "generation-1")
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_QUERY_FAILED,
            refresh_generation="generation-2",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "generation-2")
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="generation-3",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "generation-3")

        direct_results = store.list_dcm4chee_results_for_patient(patient["id"])
        aggregated_results = store.get_patient_record(patient["id"])["dcm4chee"]["dicomResults"]

        for results in (direct_results, aggregated_results):
            self.assertEqual(
                [(item["reconciliationStatus"], item["refreshGeneration"]) for item in results],
                [(DCM4CHEE_RESULT_STATUS_NO_RESULT, "generation-3")],
            )

    def test_dcm4chee_result_refresh_publishes_only_completed_snapshots(self):
        patient = self.create_local_patient()
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)

        store.begin_dcm4chee_result_refresh(patient["id"], "generation-0")
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="generation-0",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "generation-0")

        store.begin_dcm4chee_result_refresh(patient["id"], "generation-1")
        for results in (
            store.list_dcm4chee_results_for_patient(patient["id"]),
            store.get_patient_record(patient["id"])["dcm4chee"]["dicomResults"],
        ):
            self.assertEqual([item["refreshGeneration"] for item in results], ["generation-0"])

        store.begin_dcm4chee_result_refresh(patient["id"], "generation-2")
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="generation-2",
        )
        store.record_dcm4chee_result_refresh_diagnostic(
            patient_record_id=patient["id"],
            profile=profile,
            status=DCM4CHEE_RESULT_STATUS_NO_RESULT,
            refresh_generation="generation-1",
        )
        store.complete_dcm4chee_result_refresh(patient["id"], "generation-1")

        self.assertEqual(
            [item["refreshGeneration"] for item in store.list_dcm4chee_results_for_patient(patient["id"])],
            ["generation-0"],
        )

        store.complete_dcm4chee_result_refresh(patient["id"], "generation-2")

        for results in (
            store.list_dcm4chee_results_for_patient(patient["id"]),
            store.get_patient_record(patient["id"])["dcm4chee"]["dicomResults"],
        ):
            self.assertEqual(
                [(item["reconciliationStatus"], item["refreshGeneration"]) for item in results],
                [(DCM4CHEE_RESULT_STATUS_NO_RESULT, "generation-2")],
            )

    @patch("app.urllib.request.urlopen")
    def test_patient_dcm4chee_result_refresh_supersedes_stale_diagnostics(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_QIDO_RS_URL"] = (
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
        )
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )

        urlopen.return_value = FakeHttpResponse(b"[]", status=200)
        empty = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")
        empty_body = empty.get_json()
        self.assertIn(
            DCM4CHEE_RESULT_STATUS_NO_RESULT,
            {item["reconciliationStatus"] for item in empty_body["items"]},
        )

        urlopen.return_value = FakeHttpResponse(
            json.dumps(
                [
                    {
                        "00100020": {"vr": "LO", "Value": [mapping["patientId"]]},
                        "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
                        "00080050": {"vr": "SH", "Value": [mapping["accessionNumber"]]},
                        "0020000D": {"vr": "UI", "Value": [mapping["studyInstanceUid"]]},
                    }
                ]
            ).encode("utf-8"),
            status=200,
        )
        matched = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")
        matched_body = matched.get_json()
        statuses = {item["reconciliationStatus"] for item in matched_body["items"]}

        self.assertNotEqual(empty_body["refreshGeneration"], matched_body["refreshGeneration"])
        self.assertIn(DCM4CHEE_RESULT_STATUS_MATCHED, statuses)
        self.assertNotIn(DCM4CHEE_RESULT_STATUS_NO_RESULT, statuses)

    @patch("app.urllib.request.urlopen")
    def test_patient_dcm4chee_result_refresh_records_duplicate_study_candidates(self, urlopen):
        patient = self.create_local_patient()
        self.client.application.config["DCM4CHEE_QIDO_RS_URL"] = (
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs"
        )
        store = self.client.application.extensions["demo_store"]
        profile = dcm4chee_profile_from_config(self.client.application.config)
        order = store.create_dcm4chee_order_record({"patientRecordId": patient["id"]})
        payload = store.build_dcm4chee_mwl_payload(
            order,
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
        )
        mapping = store.upsert_dcm4chee_mwl_mapping(
            int(order["id"]),
            profile,
            uid_root=self.client.application.config["DCM4CHEE_UID_ROOT"],
            request_payload=payload,
            sync_status=DCM4CHEE_MWL_STATUS_CREATED,
        )
        study = {
            "00100020": {"vr": "LO", "Value": [mapping["patientId"]]},
            "00100021": {"vr": "LO", "Value": [mapping["issuerOfPatientId"]]},
            "00080050": {"vr": "SH", "Value": [mapping["accessionNumber"]]},
            "0020000D": {"vr": "UI", "Value": [mapping["studyInstanceUid"]]},
        }

        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/series") or request.full_url.endswith("/instances"):
                return FakeHttpResponse(b"[]", status=200)
            return FakeHttpResponse(json.dumps([study, study]).encode("utf-8"), status=200)

        urlopen.side_effect = fake_urlopen
        response = self.client.post(f"/api/patients/{patient['id']}/dcm4chee-results-refresh")

        self.assertIn(
            DCM4CHEE_RESULT_STATUS_DUPLICATE,
            {item["reconciliationStatus"] for item in response.get_json()["items"]},
        )

    def test_gdt_order_api_creates_and_lists_local_ecg_order_without_openemr(self):
        self.client.application.config["OPENEMR_DB_HOST"] = ""
        patient = self.create_local_patient()

        created = self.client.post(
            "/api/gdt/orders",
            json={
                "patientRecordId": patient["id"],
                "requestedAt": "20260706110000",
                "orderingProvider": "1001^WANG^AMY",
                "clinicalIndication": "Resting ECG baseline",
                "attachmentUrl": "http://localhost/reports/demo.pdf",
            },
        )

        self.assertEqual(created.status_code, 201)
        item = created.get_json()["item"]
        self.assertEqual(item["status"], "Created")
        self.assertEqual(item["messageType"], "6302")
        self.assertEqual(item["gdtTestField"], "8402")
        self.assertEqual(item["gdtTestCode"], "EKG01")
        self.assertEqual(item["gdtPatientNumber"], f"GDT-PAT-{patient['id']:06d}")
        self.assertEqual(item["messages"][0]["parsedFields"]["8402"], ["EKG01"])
        self.assertEqual(item["messages"][0]["parsedFields"]["6200"], ["06072026"])
        self.assertEqual(item["messages"][0]["parsedFields"]["6330"], [item["localGdtOrderNumber"]])
        self.assertNotIn("6220", item["messages"][0]["parsedFields"])
        self.assertNotIn("6228", item["messages"][0]["parsedFields"])
        self.assertEqual(item["attachments"][0]["url"], "http://localhost/reports/demo.pdf")
        self.assertIn("8402EKG01", item["payload"])

        listed = self.client.get("/api/gdt/orders")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"][0]["localGdtOrderNumber"], item["localGdtOrderNumber"])

        detail = self.client.get(f"/api/gdt/orders/{item['id']}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["item"]["gdtPatientNumber"], item["gdtPatientNumber"])

    def test_gdt_result_api_imports_and_matches_local_order(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        result_payload = render_gdt_message(
            [
                ("3000", order["gdtPatientNumber"]),
                ("8402", "EKG01"),
                ("6200", order["localGdtOrderNumber"]),
                ("8410", "HR"),
                ("8420", "75"),
                ("8421", "/min"),
                ("6220", "Normal sinus rhythm"),
                ("8401", "72 bpm"),
                ("8402", "160 ms"),
                ("8403", "92 ms"),
                ("8404", "390 ms"),
                ("8405", "427 ms"),
                ("6302", "report"),
                ("6303", "PDF"),
                ("6304", "ECG report"),
                ("6305", "reports/ecg-result.pdf"),
            ],
            set_type="6310",
        )

        imported = self.client.post("/api/gdt/results", json={"rawGdtText": result_payload})

        self.assertEqual(imported.status_code, 201)
        item = imported.get_json()["item"]
        self.assertEqual(item["messageType"], "6310")
        self.assertEqual(item["matchStatus"], "order-matched")
        self.assertEqual(item["canonical"]["result"]["measurements"]["HR"]["value"], 75)
        self.assertEqual(item["canonical"]["validation"], {"errors": [], "warnings": []})
        messages = self.client.get("/api/gdt/messages")
        self.assertEqual(messages.status_code, 200)
        self.assertTrue(any(message["messageType"] == "6310" for message in messages.get_json()["items"]))
        events = self.client.get(f"/api/gdt/orders/{order['id']}/events")
        self.assertEqual(events.status_code, 200)
        self.assertIn("result-matched", {event["eventType"] for event in events.get_json()["items"]})

    def test_gdt_bridge_write_import_demo_and_workbench(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        (bridge_root / "inbox").mkdir(parents=True, exist_ok=True)

        written = self.client.post(f"/api/gdt/orders/{order['id']}/write-6302", json={})
        self.assertEqual(written.status_code, 200)
        inbound_path = Path(written.get_json()["path"])
        self.assertEqual(inbound_path.parent, bridge_root / "inbox")
        self.assertTrue(inbound_path.exists())
        self.assertIn(order["localGdtOrderNumber"], inbound_path.read_text(encoding="cp1252"))
        inbound_path.unlink()

        demo = self.client.post(f"/api/gdt/orders/{order['id']}/demo-result", json={})
        self.assertEqual(demo.status_code, 201)
        self.assertEqual(
            demo.get_json()["item"]["canonical"]["result"]["measurements"]["QTC"],
            {"value": 427, "unit": "ms", "sourceTestId": "QTC"},
        )

        inbound = self.write_gdt_result_file(order)

        inbox = self.client.get("/api/gdt/bridge/inbox")
        self.assertEqual(inbox.status_code, 200)
        self.assertEqual(inbox.get_json()["items"][0]["name"], "device-result.gdt")

        imported = self.client.post("/api/gdt/bridge/import", json={"filename": "device-result.gdt"})
        self.assertEqual(imported.status_code, 201)
        self.assertFalse(inbound.exists())
        self.assertTrue((bridge_root / "archive" / "device-result.gdt").exists())

        workbench = self.client.get("/api/gdt/workbench")
        self.assertEqual(workbench.status_code, 200)
        body = workbench.get_json()
        self.assertEqual(body["patients"][0]["orderCount"], 1)
        self.assertGreaterEqual(body["patients"][0]["resultCount"], 2)
        warning_artifacts = [
            item for item in body["attachments"]
            if item["reference"] == "reports/missing.pdf"
        ]
        self.assertEqual(warning_artifacts[0]["status"], "warning")

    def test_gdt_bridge_batch_import_delete_mode_removes_successful_exchange_file(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        inbound = self.write_gdt_result_file(order, "delete-result.gdt")
        self.client.application.config["GDT_BRIDGE_IMPORT_SUCCESS_MODE"] = "delete"

        imported = self.client.post("/api/gdt/bridge/import", json={"filename": inbound.name})

        self.assertEqual(imported.status_code, 201)
        self.assertFalse(inbound.exists())
        self.assertFalse((inbound.parents[1] / "archive" / inbound.name).exists())
        self.assertEqual(imported.get_json()["result"]["imported"][0]["status"], "deleted")

    def test_gdt_bridge_batch_import_reports_disposition_warning_after_successful_persistence(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        inbound = self.write_gdt_result_file(order, "cleanup-warning.gdt")
        original_replace = Path.replace

        def replace_with_archive_failure(path, target):
            if Path(target).parent.name == "archive" and Path(target).name == inbound.name:
                raise OSError("archive unavailable")
            return original_replace(path, target)

        with patch.object(Path, "replace", replace_with_archive_failure):
            result = import_gdt_bridge_files(
                self.client.application.extensions["demo_store"],
                self.client.application.config["GDT_BRIDGE_PATH"],
                stable_seconds=0,
            )

        self.assertEqual(result["failures"], [])
        self.assertEqual(result["imported"][0]["status"], "imported-warning")
        self.assertIn("archive unavailable", result["imported"][0]["dispositionError"])
        self.assertTrue(Path(result["imported"][0]["path"]).exists())
        messages = self.client.get("/api/gdt/messages").get_json()["items"]
        self.assertTrue(any(message["messageType"] == "6310" for message in messages))

    def test_gdt_bridge_batch_import_skips_temp_files_and_moves_parse_failures_to_error(self):
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        inbound_dir = bridge_root / "outbox"
        for folder_name in ("outbox", "processing", "archive", "error"):
            (bridge_root / folder_name).mkdir(parents=True, exist_ok=True)
        (inbound_dir / "partial.gdt.tmp").write_text("not ready", encoding="utf-8")
        bad_file = inbound_dir / "bad-result.gdt"
        bad_file.write_text("8000|NOT-GDT\n", encoding="utf-8")

        result = import_gdt_bridge_files(
            self.client.application.extensions["demo_store"],
            bridge_root,
            stable_seconds=0,
        )

        self.assertEqual(len(result["failures"]), 1)
        self.assertEqual(result["failures"][0]["name"], "bad-result.gdt")
        self.assertTrue((bridge_root / "error" / "bad-result.gdt").exists())
        self.assertTrue((inbound_dir / "partial.gdt.tmp").exists())
        self.assertTrue(any(item["name"] == "partial.gdt.tmp" for item in result["skipped"]))

    def test_gdt_bridge_batch_import_applies_gdt35_filename_binding(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        rejected = self.write_gdt_result_file(order, "OTHER_GER_0001.GDT", text="Wrong receiver")
        accepted = self.write_gdt_result_file(order, "AIS_GER_0002.GDT", text="Right receiver")

        result = import_gdt_bridge_files(
            self.client.application.extensions["demo_store"],
            self.client.application.config["GDT_BRIDGE_PATH"],
            filename_profile="gdt35",
            receiver_id="AIS",
            sender_id="GER",
            stable_seconds=0,
        )

        self.assertEqual([item["name"] for item in result["imported"]], [accepted.name])
        self.assertTrue(rejected.exists())
        self.assertTrue(any(item["name"] == rejected.name for item in result["skipped"]))

    def test_gdt_bridge_inbox_lists_gdt21_sequence_extension_files(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        inbound = self.write_gdt_result_file(order, "EDV1EKG1.001")
        self.client.application.config["GDT_BRIDGE_FILENAME_PROFILE"] = "gdt21"
        self.client.application.config["GDT_BRIDGE_RECEIVER_ID"] = "EDV1"
        self.client.application.config["GDT_BRIDGE_SENDER_ID"] = "EKG1"

        inbox = self.client.get("/api/gdt/bridge/inbox")

        self.assertEqual(inbox.status_code, 200)
        self.assertIn(inbound.name, [item["name"] for item in inbox.get_json()["items"]])

    def test_gdt_bridge_batch_import_requires_stable_observation_before_processing(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        inbound = self.write_gdt_result_file(order, "stable-result.gdt")
        observations = {}

        first = import_gdt_bridge_files(
            self.client.application.extensions["demo_store"],
            self.client.application.config["GDT_BRIDGE_PATH"],
            require_stable=True,
            stable_seconds=0,
            observations=observations,
        )
        self.assertEqual(first["imported"], [])
        self.assertTrue(inbound.exists())

        second = import_gdt_bridge_files(
            self.client.application.extensions["demo_store"],
            self.client.application.config["GDT_BRIDGE_PATH"],
            require_stable=True,
            stable_seconds=0,
            observations=observations,
        )

        self.assertEqual([item["name"] for item in second["imported"]], [inbound.name])

    def test_gdt_bridge_batch_import_uses_fifo_candidate_order(self):
        patient = self.create_local_patient()
        first_order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        second_order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        first = self.write_gdt_result_file(first_order, "a-first.gdt", text="First")
        time.sleep(0.02)
        second = self.write_gdt_result_file(second_order, "b-second.gdt", text="Second")
        old = time.time() - 10
        os.utime(first, (old, old))
        os.utime(second, (old + 5, old + 5))

        result = import_gdt_bridge_files(
            self.client.application.extensions["demo_store"],
            self.client.application.config["GDT_BRIDGE_PATH"],
            stable_seconds=0,
        )

        self.assertEqual([item["name"] for item in result["imported"]], [first.name, second.name])

    def test_gdt_bridge_watcher_api_lifecycle_and_path_change_guard(self):
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        (bridge_root / "inbox").mkdir(parents=True, exist_ok=True)
        (bridge_root / "outbox").mkdir(parents=True, exist_ok=True)
        self.client.application.extensions["gdt_bridge_watcher"].configure(
            bridge_root=bridge_root
        )
        started = self.client.post("/api/gdt/bridge/watcher/start", json={})
        self.assertEqual(started.status_code, 200)
        self.assertTrue(started.get_json()["item"]["running"])

        blocked = self.client.put(
            "/api/gdt/bridge/config",
            json={"bridgePath": str(Path(self.temp_dir.name) / "blocked-gdt-bridge")},
        )
        self.assertEqual(blocked.status_code, 409)

        status = self.client.get("/api/gdt/bridge/watcher/status")
        self.assertEqual(status.status_code, 200)
        self.assertTrue(status.get_json()["item"]["running"])

        stopped = self.client.post("/api/gdt/bridge/watcher/stop", json={})
        self.assertEqual(stopped.status_code, 200)
        self.assertFalse(stopped.get_json()["item"]["running"])

    def test_gdt_order_api_rejects_non_mvp_test_codes(self):
        patient = self.create_local_patient()

        response = self.client.post(
            "/api/gdt/orders",
            json={"patientRecordId": patient["id"], "gdtTestCode": "EKG04"},
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("EKG01", response.get_json()["error"])

    def test_parse_hl7_ack_extracts_msa_fields(self):
        ack = parse_hl7_ack(
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8\r"
            "MSA|AE|ORM123|Application error"
        )

        self.assertEqual(ack["code"], "AE")
        self.assertEqual(ack["controlId"], "ORM123")
        self.assertEqual(ack["text"], "Application error")

    def test_parse_oru_summary_extracts_matching_fields(self):
        parsed = parse_oru_summary(
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01^ORU_R01|ORU1|P|2.5.1||||||UNICODE UTF-8\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR||Morgan^Avery\r"
            "OBR|1|ORD-000001|FILL-1|ECG12^12 Lead ECG"
        )

        self.assertEqual(parsed["messageType"], "ORU^R01")
        self.assertEqual(parsed["messageControlId"], "ORU1")
        self.assertEqual(parsed["patientMrn"], "MRN-A04-001")
        self.assertEqual(parsed["placerOrderNumber"], "ORD-000001")
        self.assertEqual(parsed["fillerOrderNumber"], "FILL-1")

    def test_oie_settings_api_returns_secret_safe_local_defaults(self):
        response = self.client.get("/api/oie/settings")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["success"])
        item = body["item"]
        self.assertEqual(item["managementApi"]["baseUrl"], "http://oie:8080")
        self.assertEqual(item["managementApi"]["username"], "admin")
        self.assertTrue(item["managementApi"]["passwordConfigured"])
        self.assertNotIn("password", item["managementApi"])
        self.assertNotIn("Admin", response.get_data(as_text=True))
        self.assertEqual(item["resultListener"]["port"], 6665)
        self.assertTrue(item["resultListener"]["autoStart"])

    def test_oie_settings_api_updates_profile_without_changing_listener_runtime(self):
        listener_before = self.client.get("/api/oie/result-listener/status").get_json()["item"]
        payload = self.oie_settings_payload(
            managementApi={
                "baseUrl": "https://oie.example.test/api",
                "username": "operator",
                "tlsVerify": True,
                "timeoutSeconds": 15,
            },
            resultListener={
                "host": "127.0.0.1",
                "port": 7777,
                "mllpFraming": False,
                "autoStart": True,
            },
            managedChannels=[
                {
                    "logicalType": "result",
                    "channelId": "channel-result",
                    "channelName": "HLAB Result",
                    "templateVersion": "2.0",
                    "lastKnownRevision": "revision-7",
                }
            ],
        )

        response = self.client.put("/api/oie/settings", json=payload)

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertEqual(item["managementApi"]["baseUrl"], "https://oie.example.test/api")
        self.assertEqual(item["resultListener"]["port"], 7777)
        self.assertEqual(item["managedChannels"][0]["channelId"], "channel-result")
        self.assertEqual(self.client.get("/api/oie/settings").get_json()["item"], item)

        listener_after = self.client.get("/api/oie/result-listener/status").get_json()["item"]
        self.assertFalse(listener_before["running"])
        self.assertFalse(listener_after["running"])
        self.assertEqual(listener_before["port"], 6665)
        self.assertEqual(listener_after["port"], 6665)

    def test_oie_settings_api_validates_fields_and_rejects_atomically(self):
        original = self.client.get("/api/oie/settings").get_json()["item"]
        invalid_payloads = []

        invalid_url = self.oie_settings_payload()
        invalid_url["managementApi"]["baseUrl"] = "ftp://oie.example.test"
        invalid_payloads.append((invalid_url, "baseUrl"))

        malformed_url = self.oie_settings_payload()
        malformed_url["managementApi"]["baseUrl"] = "http://[bad"
        invalid_payloads.append((malformed_url, "baseUrl"))

        invalid_host = self.oie_settings_payload()
        invalid_host["resultListener"]["host"] = ""
        invalid_payloads.append((invalid_host, "host"))

        invalid_timeout = self.oie_settings_payload()
        invalid_timeout["managementApi"]["timeoutSeconds"] = "slow"
        invalid_payloads.append((invalid_timeout, "timeoutSeconds"))

        invalid_port = self.oie_settings_payload()
        invalid_port["resultListener"]["port"] = 70000
        invalid_payloads.append((invalid_port, "between 1 and 65535"))

        for payload, message in invalid_payloads:
            with self.subTest(message=message):
                response = self.client.put("/api/oie/settings", json=payload)
                self.assertEqual(response.status_code, 400)
                self.assertIn(message, response.get_json()["error"])
                self.assertEqual(
                    self.client.get("/api/oie/settings").get_json()["item"],
                    original,
                )

    def test_oie_settings_api_preserves_replaces_and_never_exposes_password(self):
        secret = "  new-write-only-secret  "
        payload = self.oie_settings_payload()
        payload["managementApi"]["password"] = secret
        logger = self.client.application.logger

        with patch.object(logger, "_log") as log_call:
            response = self.client.put("/api/oie/settings", json=payload)

        self.assertEqual(response.status_code, 200)
        self.assertNotIn(secret, response.get_data(as_text=True))
        self.assertNotIn(secret, str(log_call.call_args_list))
        self.assertNotIn("password", response.get_json()["item"]["managementApi"])

        omitted = self.oie_settings_payload()
        omitted["managementApi"]["username"] = "updated-user"
        self.assertEqual(self.client.put("/api/oie/settings", json=omitted).status_code, 200)
        store = self.client.application.extensions["demo_store"]
        with store.connect() as connection:
            stored_password = connection.execute(
                "SELECT management_api_password FROM oie_settings_profiles"
            ).fetchone()[0]
        self.assertEqual(stored_password, secret)

        for invalid_password in ("", None, 123):
            with self.subTest(invalid_password=invalid_password):
                invalid = self.oie_settings_payload()
                invalid["managementApi"]["password"] = invalid_password
                rejected = self.client.put("/api/oie/settings", json=invalid)
                self.assertEqual(rejected.status_code, 400)
                self.assertIn("non-empty string", rejected.get_json()["error"])
                self.assertNotIn(secret, rejected.get_data(as_text=True))
        with store.connect() as connection:
            preserved_password = connection.execute(
                "SELECT management_api_password FROM oie_settings_profiles"
            ).fetchone()[0]
        self.assertEqual(preserved_password, secret)

    def test_oie_result_api_persists_and_matches_order_result(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01^ORU_R01|ORU1|P|2.5.1||||||UNICODE UTF-8\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR||Morgan^Avery\r"
            f"OBR|1|{order['localOrderNumber']}||ECG12^12 Lead ECG"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("MSA|AA|ORU1", body["ack"])
        self.assertIn("ACK^R01^ACK", body["ack"])
        self.assertIn("|P|2.5.1||||||UNICODE UTF-8", body["ack"])
        self.assertEqual(body["item"]["matchStatus"], "order-matched")
        self.assertEqual(body["item"]["matchedOrderRecordId"], order["id"])

        workbench = self.client.get("/api/oie/workbench").get_json()
        self.assertEqual(workbench["patients"][0]["orderCount"], 1)
        self.assertEqual(workbench["patients"][0]["resultCount"], 1)
        self.assertEqual(workbench["patients"][0]["results"][0]["messageControlId"], "ORU1")

    def test_oie_result_api_keeps_unknown_patient_unmatched(self):
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^W01^ORU_W01|ORU2|P|2.5.1||||||UNICODE UTF-8\r"
            "PID|1||UNKNOWN^^^HEALTHCARE_LAB^MR||Patient^Unknown\r"
            "OBR|1|ORD-404||ECG12^12 Lead ECG"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertEqual(item["matchStatus"], "unmatched-patient")
        workbench = self.client.get("/api/oie/workbench").get_json()
        self.assertEqual(workbench["unmatchedResults"][0]["messageControlId"], "ORU2")

    def test_oie_result_api_rejects_unsupported_message_with_failure_ack(self):
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ADT^A04^ADT_A01|BAD1|P|2.5.1||||||UNICODE UTF-8\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertIn("MSA|AR|BAD1", body["ack"])
        self.assertIn("ACK^A04^ACK", body["ack"])
        self.assertIn("ERR||MSH^1^9^1^1|200^Unsupported message type^HL70357|E", body["ack"])

    def test_oie_result_listener_status_defaults_to_port_6665(self):
        response = self.client.get("/api/oie/result-listener/status")

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertFalse(item["running"])
        self.assertEqual(item["port"], 6665)

    def test_oie_result_listener_start_reports_bind_failure(self):
        occupied = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        occupied.bind(("127.0.0.1", 0))
        occupied.listen(1)
        port = occupied.getsockname()[1]
        try:
            response = self.client.post(
                "/api/oie/result-listener/start",
                json={"host": "127.0.0.1", "port": port, "mllpFraming": True},
            )
        finally:
            occupied.close()

        self.assertEqual(response.status_code, 400)
        self.assertIn("Listener could not start", response.get_json()["error"])
        status = self.client.get("/api/oie/result-listener/status").get_json()["item"]
        self.assertFalse(status["running"])

    @patch("app.send_hl7_mllp_message")
    def test_oie_send_order_records_ack_acceptance(self, send_message):
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        send_message.return_value = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8\r"
            "MSA|AA|ORM123|OK"
        )

        response = self.client.post(
            f"/api/oie/local-orders/{order['id']}/send",
            json={"host": "localhost", "port": 6663, "timeoutSeconds": 1, "mllpFraming": True},
        )

        self.assertEqual(response.status_code, 200)
        item = response.get_json()["item"]
        self.assertEqual(item["status"], "Accepted")
        self.assertEqual(item["ack"]["code"], "AA")
        self.assertEqual(item["ack"]["text"], "OK")
        send_message.assert_called_once()

    @patch("app.send_hl7_mllp_message")
    def test_oie_send_order_uses_configured_default_endpoint(self, send_message):
        self.client.application.config.update(
            OIE_MLLP_ORDER_HOST="oie",
            OIE_MLLP_ORDER_PORT=6600,
        )
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        send_message.return_value = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01^ACK|ACK1|P|2.5.1||||||UNICODE UTF-8\r"
            "MSA|AA|ORM123|OK"
        )

        response = self.client.post(
            f"/api/oie/local-orders/{order['id']}/send",
            json={"timeoutSeconds": 1, "mllpFraming": True},
        )

        self.assertEqual(response.status_code, 200)
        send_message.assert_called_once()
        self.assertEqual(send_message.call_args.kwargs["host"], "oie")
        self.assertEqual(send_message.call_args.kwargs["port"], 6600)

    @patch("app.send_hl7_mllp_message", side_effect=OSError("connection refused"))
    def test_oie_send_order_records_transport_error(self, _send_message):
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]

        response = self.client.post(
            f"/api/oie/local-orders/{order['id']}/send",
            json={"host": "localhost", "port": 6663, "timeoutSeconds": 1, "mllpFraming": True},
        )

        self.assertEqual(response.status_code, 502)
        item = response.get_json()["item"]
        self.assertEqual(item["status"], "Transport error")
        self.assertIn("connection refused", item["transportError"])

    def test_dashboard_services_exposes_four_allowlisted_groups(self):
        response = self.client.get("/api/dashboard/services")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(
            [item["id"] for item in body["items"]],
            ["hl7-v2-oie", "fhir-medplum", "openemr-gdt", "dicom-dcm4chee"],
        )
        self.assertEqual(body["summary"]["total"], 4)
        self.assertIn("resources", body)
        self.assertIn("events", body)

    def test_dashboard_rejects_unsupported_service_ids(self):
        preview = self.client.get("/api/dashboard/services/raw-container/restart-preview")
        self.assertEqual(preview.status_code, 404)
        action = self.client.post("/api/dashboard/services/raw-container/restart", json={})
        self.assertEqual(action.status_code, 404)

    @patch("app.run_lab_operation")
    def test_dashboard_action_mapping_and_restart_preview(self, run_operation):
        run_operation.return_value = {
            "operation": {"action": "start", "result": "success"},
            "output": "started",
        }
        response = self.client.post("/api/dashboard/services/fhir-medplum/enable", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(run_operation.call_args.kwargs["action"], "start")
        self.assertIn("service", response.get_json())

        preview = self.client.get("/api/dashboard/services/fhir-medplum/restart-preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["item"]["risk"], "high")
        self.assertIn("Medplum", preview.get_json()["item"]["affectedServices"])

    def test_dashboard_action_mapping_helper(self):
        self.assertEqual(dashboard_action_for_group({}, "enable"), "start")
        self.assertEqual(dashboard_action_for_group({}, "disable"), "stop")
        self.assertEqual(dashboard_action_for_group({}, "restart"), "restart")
        with self.assertRaises(SimulatorValidationError):
            dashboard_action_for_group({}, "check")
        with self.assertRaises(SimulatorValidationError):
            dashboard_action_for_group({}, "logs")

    @patch("app.run_lab_operation")
    @patch("app.run_lab_server_health_check")
    def test_dashboard_check_runs_health_check_for_every_group_component(
        self, run_health_check, run_operation
    ):
        store = self.client.application.extensions["demo_store"]

        def mark_healthy(store_arg, server_id):
            self.assertIs(store_arg, store)
            return store_arg.update_lab_server_health(
                server_id,
                overall_status="Healthy",
                process_status="Healthy",
                application_status="Healthy",
                protocol_status="Healthy",
            )

        run_health_check.side_effect = mark_healthy

        response = self.client.post("/api/dashboard/services/openemr-gdt/check", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(run_operation.called)
        self.assertEqual(run_health_check.call_count, 3)
        body = response.get_json()
        self.assertEqual(body["service"]["status"], "Healthy")
        self.assertEqual(body["service"]["checks"]["process"], "Healthy")
        self.assertEqual(
            [item["name"] for item in body["servers"]],
            ["OpenEMR", "GDT Bridge", "GDT Hospital"],
        )

    @patch("app.urllib.request.urlopen")
    def test_openemr_gdt_check_treats_file_based_gdt_services_as_healthy(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)

        response = self.client.post("/api/dashboard/services/openemr-gdt/check", json={})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["service"]["status"], "Healthy")
        by_name = {item["name"]: item for item in body["servers"]}
        self.assertEqual(by_name["OpenEMR"]["overallStatus"], "Healthy")
        self.assertEqual(by_name["GDT Bridge"]["overallStatus"], "Healthy")
        self.assertEqual(by_name["GDT Bridge"]["checks"]["application"], "Healthy")
        self.assertEqual(by_name["GDT Bridge"]["checks"]["protocol"], "Healthy")
        self.assertEqual(by_name["GDT Hospital"]["overallStatus"], "Healthy")

    @patch("backend.dashboard_services.Path.exists", return_value=False)
    @patch("backend.dashboard_services.subprocess.run", side_effect=OSError("docker missing"))
    def test_dashboard_resource_snapshot_falls_back_when_docker_stats_unavailable(
        self, _run, _exists
    ):
        snapshot = collect_dashboard_resource_snapshot()
        self.assertEqual(snapshot["status"], "unavailable")
        self.assertEqual(snapshot["totals"]["cpuPercent"], 0.0)
        self.assertIn("docker missing", snapshot["message"])

    @patch("backend.dashboard_services.docker_socket_available", return_value=True)
    @patch("backend.dashboard_services.subprocess.run")
    @patch("backend.dashboard_services.collect_dashboard_resource_snapshot_from_socket")
    def test_dashboard_resource_snapshot_prefers_docker_socket(
        self, socket_snapshot, docker_run, _socket_available
    ):
        socket_snapshot.return_value = {
            "status": "ok",
            "message": "",
            "totals": {
                "cpuPercent": 2.5,
                "memoryUsedMiB": 128.0,
                "memoryLimitMiB": 1024.0,
                "memoryPercent": 12.5,
            },
            "containers": [{"name": "interoperability-lab-oie-1"}],
            "collectedAt": "2026-07-02T00:00:00Z",
        }

        snapshot = collect_dashboard_resource_snapshot()

        self.assertEqual(snapshot["status"], "ok")
        self.assertEqual(snapshot["containers"][0]["name"], "interoperability-lab-oie-1")
        socket_snapshot.assert_called_once()
        docker_run.assert_not_called()

    def test_lab_server_registry_seeds_default_services(self):
        response = self.client.get("/api/lab/servers")
        self.assertEqual(response.status_code, 200)
        items = response.get_json()["items"]
        by_name = {item["name"]: item for item in items}
        self.assertEqual(by_name["OIE"]["serverType"], "HL7 Engine")
        self.assertEqual(by_name["Medplum"]["serverType"], "FHIR Server")
        self.assertEqual(by_name["OpenEMR"]["serverType"], "EMR")
        self.assertEqual(by_name["GDT Bridge"]["serverType"], "GDT Bridge")
        self.assertEqual(by_name["dcm4chee"]["serverType"], "DICOM Archive")
        self.assertTrue(all(item["overallStatus"] == "Unknown" for item in items))

    def test_dcm4chee_profile_api_returns_local_defaults(self):
        response = self.client.get("/api/dcm4chee/profile")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        profile = body["item"]

        self.assertEqual(profile["profileName"], "local-dcm4chee")
        self.assertEqual(profile["displayName"], "dcm4chee Local Archive")
        self.assertEqual(profile["environmentName"], "local-docker")
        self.assertEqual(profile["webUiUrl"], "http://127.0.0.1:8082/dcm4chee-arc/ui2")
        self.assertEqual(profile["dimse"]["host"], "127.0.0.1")
        self.assertEqual(profile["dimse"]["port"], 11112)
        self.assertEqual(profile["dimse"]["calledAETitle"], "DCM4CHEE")
        self.assertEqual(profile["dimse"]["callingAETitle"], "HEALTHCARE_LAB")
        self.assertEqual(profile["mwl"]["aeTitle"], "WORKLIST")
        self.assertEqual(profile["mwl"]["defaultScheduledStationAETitle"], "ECG_AP")
        self.assertEqual(profile["hl7"]["host"], "127.0.0.1")
        self.assertEqual(profile["hl7"]["port"], 2575)
        self.assertEqual(profile["hl7"]["sendingApplication"], "HEALTHCARE_LAB")
        self.assertEqual(profile["hl7"]["sendingFacility"], "LAB_APP")
        self.assertEqual(profile["hl7"]["receivingApplication"], "DCM4CHEE")
        self.assertEqual(profile["hl7"]["receivingFacility"], "DCM4CHEE")
        self.assertEqual(profile["hl7"]["patientAssigningAuthority"], "local-dcm4chee")
        self.assertEqual(
            profile["dicomweb"]["baseUrl"],
            "http://127.0.0.1:8082/dcm4chee-arc/aets/WORKLIST/rs",
        )
        self.assertEqual(
            profile["dicomweb"]["qidoRsUrl"],
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        self.assertEqual(
            profile["dicomweb"]["wadoRsUrl"],
            "http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        self.assertEqual(profile["security"]["authMode"], "none")
        self.assertFalse(profile["security"]["tlsEnabled"])
        self.assertTrue(body["diagnostics"]["valid"])

    def test_dcm4chee_profile_archive_defaults_preserve_configured_host(self):
        self.client.application.config["DCM4CHEE_DICOMWEB_BASE_URL"] = (
            "http://pacs.example.test:8082/dcm4chee-arc/aets/WORKLIST/rs"
        )
        self.client.application.config["DCM4CHEE_QIDO_RS_URL"] = ""
        self.client.application.config["DCM4CHEE_WADO_RS_URL"] = ""
        self.client.application.config["DCM4CHEE_STOW_RS_URL"] = ""

        profile = dcm4chee_profile_from_config(self.client.application.config)

        self.assertEqual(
            profile["dicomweb"]["baseUrl"],
            "http://pacs.example.test:8082/dcm4chee-arc/aets/WORKLIST/rs",
        )
        self.assertEqual(
            profile["dicomweb"]["qidoRsUrl"],
            "http://pacs.example.test:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        self.assertEqual(
            profile["dicomweb"]["wadoRsUrl"],
            "http://pacs.example.test:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )
        self.assertEqual(
            profile["dicomweb"]["stowRsUrl"],
            "http://pacs.example.test:8082/dcm4chee-arc/aets/DCM4CHEE/rs",
        )

    def test_dcm4chee_profile_diagnostics_report_missing_values(self):
        profile = dcm4chee_profile_from_config(self.client.application.config)
        profile["dimse"]["calledAETitle"] = ""
        profile["hl7"]["patientAssigningAuthority"] = ""
        profile["dicomweb"]["baseUrl"] = "not-a-url"
        profile["security"]["certificatePath"] = "cert.pem"

        diagnostics = validate_dcm4chee_profile(profile)

        self.assertFalse(diagnostics["valid"])
        messages = {check["field"]: check["message"] for check in diagnostics["checks"]}
        self.assertEqual(messages["dimse.calledAETitle"], "Called AE title is required.")
        self.assertEqual(messages["hl7.patientAssigningAuthority"], "HL7 Patient assigning authority is required.")
        self.assertEqual(
            messages["dicomweb.baseUrl"],
            "dicomweb.baseUrl must start with http:// or https://.",
        )
        self.assertEqual(
            messages["security.certificatePath"],
            "Certificate or key paths require TLS to be enabled.",
        )

    def test_dcm4chee_profile_named_route_rejects_unknown_profile(self):
        response = self.client.get("/api/dcm4chee/profiles/remote")
        self.assertEqual(response.status_code, 404)

    def test_dcm4chee_profile_diagnostics_handles_malformed_env_values(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            with patch.dict(
                os.environ,
                {
                    "DCM4CHEE_DIMSE_PORT": "abc",
                    "DCM4CHEE_HL7_PORT": "bad",
                    "DCM4CHEE_TLS_ENABLED": "maybe",
                    "DCM4CHEE_TLS_VERIFY": "sometimes",
                },
            ):
                app = create_app(str(Path(temp_dir) / "malformed.db"))
            app.config.update(TESTING=True, GDT_BRIDGE_PATH=str(Path(temp_dir) / "gdt-bridge"))
            response = app.test_client().get("/api/dcm4chee/profile/diagnostics")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertFalse(body["valid"])
        messages = {check["field"]: check["message"] for check in body["checks"]}
        self.assertEqual(
            messages["dimse.port"],
            "DIMSE port must be an integer between 1 and 65535.",
        )
        self.assertEqual(
            messages["hl7.port"],
            "HL7 port must be an integer between 1 and 65535.",
        )
        self.assertEqual(messages["security.tlsEnabled"], "TLS enabled must be true or false.")
        self.assertEqual(messages["security.tlsVerify"], "TLS verify must be true or false.")

    @patch("app.socket.create_connection")
    @patch("app.urllib.request.urlopen")
    def test_dcm4chee_smoke_reports_out_of_range_dimse_port(self, urlopen, create_connection):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.client.application.config["DCM4CHEE_DIMSE_PORT"] = "99999"
        store = self.client.application.extensions["demo_store"]
        dcm4chee = next(item for item in store.list_lab_servers() if item["name"] == "dcm4chee")

        result = run_lab_smoke_check(self.client.application, store, dcm4chee)

        self.assertEqual(result["status"], "Down")
        dimse_step = next(step for step in result["steps"] if step["name"] == "dicom_dimse")
        self.assertEqual(dimse_step["status"], "Down")
        self.assertEqual(dimse_step["message"], "Port must be an integer between 1 and 65535.")
        create_connection.assert_not_called()

    def test_lab_server_create_update_and_detail_api(self):
        created = self.client.post(
            "/api/lab/servers",
            json={
                "name": "Custom Monitor",
                "serverType": "Test Tool",
                "protocol": "HTTP",
                "baseUrl": "http://127.0.0.1:9000",
            },
        )
        self.assertEqual(created.status_code, 201)
        server_id = created.get_json()["item"]["id"]

        updated = self.client.put(
            f"/api/lab/servers/{server_id}",
            json={"host": "127.0.0.1", "baseUrl": "http://127.0.0.1:9001"},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["item"]["overallStatus"], "Unknown")
        self.assertEqual(updated.get_json()["item"]["baseUrl"], "http://127.0.0.1:9001")

        detail = self.client.get(f"/api/lab/servers/{server_id}")
        self.assertEqual(detail.status_code, 200)
        self.assertEqual(detail.get_json()["item"]["name"], "Custom Monitor")

    def test_lab_server_validation_rejects_invalid_payload(self):
        response = self.client.post(
            "/api/lab/servers",
            json={"name": "", "serverType": "Unknown", "protocol": "BAD"},
        )
        self.assertEqual(response.status_code, 400)

    def test_lab_operation_history_exposes_internal_logs_operation(self):
        created = self.client.post(
            "/api/lab/servers",
            json={
                "name": "External Tool",
                "serverType": "Test Tool",
                "protocol": "HTTP",
                "baseUrl": "http://127.0.0.1:9000",
                "operation": {
                    "controlType": "external",
                    "supportedActions": ["logs"],
                    "backingService": "external-tool",
                },
            },
        )
        server_id = created.get_json()["item"]["id"]
        response = self.client.post(f"/api/lab/servers/{server_id}/logs", json={})
        self.assertEqual(response.status_code, 200)
        self.assertIn("No internal operation adapter", response.get_json()["output"])

    @patch("app.urllib.request.urlopen")
    def test_lab_application_check_uses_tcp_when_host_and_port_are_configured(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        result = run_lab_application_check(
            {"name": "Demo", "host": "127.0.0.1", "port": 65535, "baseUrl": ""}
        )
        self.assertIn(result[0], {"Down", "Healthy"})

    def test_internal_lab_tool_application_check_ignores_host_mapped_port(self):
        result = run_lab_application_check(
            {
                "name": "HL7Tester",
                "host": "127.0.0.1",
                "port": 6671,
                "baseUrl": "",
                "protocol": "MLLP",
                "operation": {"controlType": "internal-tool", "backingService": "lab-app"},
            }
        )

        self.assertEqual(result[0], "Healthy")
        self.assertIn("lab-app", result[1])

    @patch("app.socket.create_connection")
    @patch("app.urllib.request.urlopen")
    def test_oie_smoke_uses_compose_network_endpoints(self, urlopen, create_connection):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        create_connection.return_value.__enter__.return_value = object()
        store = self.client.application.extensions["demo_store"]
        oie = next(item for item in store.list_lab_servers() if item["name"] == "OIE")

        result = run_lab_smoke_check(self.client.application, store, oie)

        self.assertEqual(result["status"], "Healthy")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://oie:8080")
        create_connection.assert_called_with(("oie", 6661), 3)

    @patch("app.urllib.request.urlopen")
    def test_medplum_smoke_distinguishes_service_request_unauthorized(self, urlopen):
        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if "ServiceRequest" in request.full_url:
                raise urllib.error.HTTPError(
                    request.full_url,
                    401,
                    "Unauthorized",
                    hdrs=None,
                    fp=None,
                )
            return FakeHttpResponse(b"{}", status=200)

        urlopen.side_effect = fake_urlopen
        store = self.client.application.extensions["demo_store"]
        medplum = next(item for item in store.list_lab_servers() if item["name"] == "Medplum")

        result = run_lab_smoke_check(self.client.application, store, medplum)

        self.assertEqual(result["status"], "Degraded")
        service_request_step = next(
            step for step in result["steps"] if step["name"] == "service_request_fetch"
        )
        self.assertIn("FHIR data fetch unauthorized", service_request_step["message"])

    @patch("app.urllib.request.urlopen")
    def test_medplum_smoke_treats_empty_diagnostic_report_bundle_as_healthy(self, urlopen):
        def fake_urlopen(request, timeout):
            if request.full_url.endswith("/oauth2/token"):
                return FakeHttpResponse(
                    json.dumps(
                        {
                            "access_token": "server-token",
                            "token_type": "Bearer",
                            "expires_in": 3600,
                        }
                    ).encode("utf-8"),
                    status=200,
                )
            if "ServiceRequest" in request.full_url:
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            if "DiagnosticReport" in request.full_url:
                return FakeHttpResponse(
                    json.dumps({"resourceType": "Bundle", "entry": []}).encode("utf-8"),
                    status=200,
                )
            return FakeHttpResponse(b"{}", status=200)

        urlopen.side_effect = fake_urlopen
        store = self.client.application.extensions["demo_store"]
        medplum = next(item for item in store.list_lab_servers() if item["name"] == "Medplum")

        result = run_lab_smoke_check(self.client.application, store, medplum)

        diagnostic_step = next(
            step for step in result["steps"] if step["name"] == "diagnostic_report_fetch"
        )
        self.assertEqual(diagnostic_step["status"], "Healthy")
        self.assertIn("0 report(s)", diagnostic_step["message"])

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
        store = self.client.application.extensions["demo_store"]
        openemr = next(item for item in store.list_lab_servers() if item["name"] == "OpenEMR")
        return run_lab_smoke_check(self.client.application, store, openemr)

    @patch("app.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_reports_healthy_steps(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.install_openemr_source(lambda: FakeDbConnection(rows=[{"procedure_order_id": 1}]))
        Path(self.client.application.config["GDT_BRIDGE_PATH"]).mkdir(parents=True, exist_ok=True)

        result = self.run_openemr_smoke()

        self.assertEqual(result["status"], "Healthy")
        by_name = {step["name"]: step for step in result["steps"]}
        self.assertEqual(by_name["openemr_http"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_db_connection"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_order_schema"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_ecg_orders"]["status"], "Healthy")
        self.assertFalse(by_name["openemr_ecg_orders"]["required"])
        self.assertEqual(by_name["gdt_folder_contract"]["status"], "Healthy")

    @patch("app.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_reports_mariadb_connection_failure(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)

        def fail_connection():
            raise OSError("mariadb unavailable")

        self.install_openemr_source(fail_connection)

        result = self.run_openemr_smoke()

        self.assertEqual(result["status"], "Down")
        by_name = {step["name"]: step for step in result["steps"]}
        self.assertEqual(by_name["openemr_db_connection"]["status"], "Down")
        self.assertIn("mariadb unavailable", by_name["openemr_db_connection"]["message"])
        self.assertIn(by_name["openemr_db_connection"], result["requiredFailures"])

    @patch("app.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_reports_missing_order_schema_failure(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        missing_schema = Exception(1146, "Table 'openemr.procedure_order' doesn't exist")
        self.install_openemr_source(lambda: FakeDbConnection(execute_error=missing_schema))

        result = self.run_openemr_smoke()

        self.assertEqual(result["status"], "Down")
        by_name = {step["name"]: step for step in result["steps"]}
        self.assertEqual(by_name["openemr_db_connection"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_order_schema"]["status"], "Down")
        self.assertIn("Required OpenEMR procedure-order schema", by_name["openemr_order_schema"]["message"])
        self.assertIn(by_name["openemr_order_schema"], result["requiredFailures"])

    @patch("app.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_degrades_when_no_ecg_orders_exist(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.install_openemr_source(lambda: FakeDbConnection(rows=[]))
        Path(self.client.application.config["GDT_BRIDGE_PATH"]).mkdir(parents=True, exist_ok=True)

        result = self.run_openemr_smoke()

        self.assertEqual(result["status"], "Degraded")
        by_name = {step["name"]: step for step in result["steps"]}
        self.assertEqual(by_name["openemr_order_schema"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_ecg_orders"]["status"], "Degraded")
        self.assertFalse(by_name["openemr_ecg_orders"]["required"])

    @patch("backend.lab_operations.shutil.which", return_value="tool")
    def test_lab_compose_operation_adapter_builds_allowlisted_command(self, _which):
        adapter = DockerComposeLabOperationAdapter("deploy/lab.ps1")
        command = adapter.build_command("restart", "oie")
        self.assertEqual(command[:4], ["powershell", "-NoProfile", "-ExecutionPolicy", "Bypass"])
        self.assertIn("restart", command)
        self.assertIn("oie", command)

    def test_docker_socket_stop_uses_short_grace_period(self):
        adapter = FakeDockerSocketLabOperationAdapter()

        result = adapter.run("stop", "openemr", timeout_seconds=240)

        self.assertEqual(result["returnCode"], 0)
        self.assertIn("/containers/container-1/stop?t=10", adapter.requested_paths)

    def test_lab_health_status_derivation(self):
        self.assertEqual(
            derive_lab_overall_status(
                {"process": "Healthy", "application": "Healthy", "protocol": "Healthy"}
            ),
            "Healthy",
        )
        self.assertEqual(
            derive_lab_overall_status(
                {"process": "Healthy", "application": "Down", "protocol": "Healthy"}
            ),
            "Down",
        )


if __name__ == "__main__":
    unittest.main()
