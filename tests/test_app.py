import json
import os
import socket
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
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
    import_gdt_bridge_files,
    parse_hl7_ack,
    parse_oru_summary,
    run_lab_application_check,
    run_lab_smoke_check,
)
from backend.lab_store import render_gdt_message


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
        )
        self.client = app.test_client()

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_index_serves_dashboard_only_ui(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<title>Healthcare Lab</title>", response.data)
        self.assertIn(b'data-project-mode="healthcare_lab"', response.data)
        self.assertIn(b"Server Health Dashboard", response.data)
        self.assertNotIn(b'id="protocol-mode"', response.data)
        self.assertIn(b'id="lab-console-view"', response.data)
        self.assertIn(b'id="patient-mode"', response.data)
        self.assertIn(b'id="order-view"', response.data)
        self.assertIn(b'id="order-payload-preview"', response.data)
        self.assertIn(b'<option value="gdt">GDT ECG</option>', response.data)
        self.assertIn(b'id="create-gdt-patient"', response.data)
        self.assertIn(b'id="gdt-test-code" value="8402=EKG01"', response.data)
        self.assertIn(b'id="oie-order-list"', response.data)
        self.assertIn(b'id="gdt-view"', response.data)
        self.assertIn(b'id="gdt-inbox-list"', response.data)
        self.assertIn(b'id="gdt-patient-list"', response.data)
        self.assertIn(b'id="gdt-watcher-status"', response.data)
        self.assertIn(b'id="start-gdt-watcher"', response.data)
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

    def test_sidebar_views_hide_inactive_pages(self):
        styles_path = Path(__file__).resolve().parents[1] / "frontend" / "static" / "styles.css"
        styles = styles_path.read_text(encoding="utf-8")
        self.assertIn(".app-view[hidden]", styles)
        self.assertIn("display: none", styles)

    def test_only_healthcare_lab_routes_are_registered(self):
        routes = {rule.rule for rule in self.client.application.url_map.iter_rules()}
        self.assertIn("/api/dashboard/services", routes)
        self.assertIn("/api/lab/servers", routes)
        self.assertIn("/api/orders", routes)
        self.assertIn("/api/oie/local-orders", routes)
        self.assertIn("/api/oie/result-listener/start", routes)
        self.assertIn("/api/oie/workbench", routes)
        self.assertIn("/api/oie/results", routes)
        self.assertNotIn("/api/listener/start", routes)
        self.assertNotIn("/api/integration-records", routes)
        self.assertNotIn("/api/workbench/orders", routes)
        self.assertNotIn("/api/fhir/submit", routes)
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

    def test_gdt_bridge_config_api_updates_shared_folder_path(self):
        target = Path(self.temp_dir.name) / "custom-gdt-bridge"

        response = self.client.put("/api/gdt/bridge/config", json={"bridgePath": str(target)})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(body["item"]["bridgePath"], str(target))
        self.assertTrue((target / "outbox").is_dir())
        self.assertTrue((target / "inbound").is_dir())
        current = self.client.get("/api/gdt/bridge/config").get_json()["item"]
        self.assertEqual(current["outboxPath"], str(target / "outbox"))
        self.assertIn("watcher", current)

    def gdt_result_payload_for_order(self, order, text="Imported from bridge file"):
        return render_gdt_message(
            [
                ("3000", order["gdtPatientNumber"]),
                ("6200", order["localGdtOrderNumber"]),
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
        inbound = bridge_root / "inbound" / filename
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
        self.assertIn("ORM^O01", item["payload"])
        self.assertIn("MSH|^~\\&|HEALTHCARE_LAB|DASHBOARD|OIE|HL7LAB|", item["payload"])

        listed = self.client.get("/api/oie/local-orders")
        self.assertEqual(listed.status_code, 200)
        self.assertEqual(listed.get_json()["items"][0]["localOrderNumber"], item["localOrderNumber"])

    def test_patient_api_creates_fhir_local_patient(self):
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

    def test_order_api_rejects_missing_patient(self):
        response = self.client.post("/api/orders", json={"patientRecordId": 404})

        self.assertEqual(response.status_code, 404)

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
                ("6200", order["localGdtOrderNumber"]),
                ("8410", order["localGdtOrderNumber"]),
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
        self.assertEqual(item["canonical"]["result"]["measurements"]["HR"], "72 bpm")
        self.assertEqual(item["canonical"]["attachments"][0]["reference"], "reports/ecg-result.pdf")
        messages = self.client.get("/api/gdt/messages")
        self.assertEqual(messages.status_code, 200)
        self.assertTrue(any(message["messageType"] == "6310" for message in messages.get_json()["items"]))
        events = self.client.get(f"/api/gdt/orders/{order['id']}/events")
        self.assertEqual(events.status_code, 200)
        self.assertIn("result-matched", {event["eventType"] for event in events.get_json()["items"]})

    def test_gdt_bridge_write_import_demo_and_workbench(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/gdt/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]

        written = self.client.post(f"/api/gdt/orders/{order['id']}/write-6302", json={})
        self.assertEqual(written.status_code, 200)
        outbox_path = Path(written.get_json()["path"])
        self.assertTrue(outbox_path.exists())
        self.assertIn(order["localGdtOrderNumber"], outbox_path.read_text(encoding="cp1252"))

        demo = self.client.post(f"/api/gdt/orders/{order['id']}/demo-result", json={})
        self.assertEqual(demo.status_code, 201)
        self.assertEqual(demo.get_json()["item"]["canonical"]["result"]["measurements"]["QTC"], "427 ms")

        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
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
        inbound_dir = bridge_root / "inbound"
        inbound_dir.mkdir(parents=True, exist_ok=True)
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
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01|ACK1|P|2.3.1\r"
            "MSA|AE|ORM123|Application error"
        )

        self.assertEqual(ack["code"], "AE")
        self.assertEqual(ack["controlId"], "ORM123")
        self.assertEqual(ack["text"], "Application error")

    def test_parse_oru_summary_extracts_matching_fields(self):
        parsed = parse_oru_summary(
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01|ORU1|P|2.3.1\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR||Morgan^Avery\r"
            "OBR|1|ORD-000001|FILL-1|ECG12^12 Lead ECG"
        )

        self.assertEqual(parsed["messageType"], "ORU^R01")
        self.assertEqual(parsed["messageControlId"], "ORU1")
        self.assertEqual(parsed["patientMrn"], "MRN-A04-001")
        self.assertEqual(parsed["placerOrderNumber"], "ORD-000001")
        self.assertEqual(parsed["fillerOrderNumber"], "FILL-1")

    def test_oie_result_api_persists_and_matches_order_result(self):
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01|ORU1|P|2.3.1\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR||Morgan^Avery\r"
            f"OBR|1|{order['localOrderNumber']}||ECG12^12 Lead ECG"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertIn("MSA|AA|ORU1", body["ack"])
        self.assertEqual(body["item"]["matchStatus"], "order-matched")
        self.assertEqual(body["item"]["matchedOrderRecordId"], order["id"])

        workbench = self.client.get("/api/oie/workbench").get_json()
        self.assertEqual(workbench["patients"][0]["orderCount"], 1)
        self.assertEqual(workbench["patients"][0]["resultCount"], 1)
        self.assertEqual(workbench["patients"][0]["results"][0]["messageControlId"], "ORU1")

    def test_oie_result_api_keeps_unknown_patient_unmatched(self):
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^W01|ORU2|P|2.3.1\r"
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
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ADT^A04|BAD1|P|2.3.1\r"
            "PID|1||MRN-A04-001^^^HEALTHCARE_LAB^MR"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertIn("MSA|AR|BAD1", body["ack"])

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
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01|ACK1|P|2.3.1\r"
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
            OIE_MLLP_ORDER_PORT=6663,
        )
        patient = self.create_local_patient()
        order = self.client.post("/api/orders", json={"patientRecordId": patient["id"]}).get_json()["item"]
        send_message.return_value = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD||ACK^O01|ACK1|P|2.3.1\r"
            "MSA|AA|ORM123|OK"
        )

        response = self.client.post(
            f"/api/oie/local-orders/{order['id']}/send",
            json={"timeoutSeconds": 1, "mllpFraming": True},
        )

        self.assertEqual(response.status_code, 200)
        send_message.assert_called_once()
        self.assertEqual(send_message.call_args.kwargs["host"], "oie")
        self.assertEqual(send_message.call_args.kwargs["port"], 6663)

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
