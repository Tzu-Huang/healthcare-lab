import unittest

from ._case_support import *

class GdtApiTests(ApiCaseSupport):
    """Focused assertion owner for GdtApiTests."""

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
                self.dependencies.gdt_workflow,
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
            self.dependencies.gdt_workflow,
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
            self.dependencies.gdt_workflow,
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
            self.dependencies.gdt_workflow,
            self.client.application.config["GDT_BRIDGE_PATH"],
            require_stable=True,
            stable_seconds=0,
            observations=observations,
        )
        self.assertEqual(first["imported"], [])
        self.assertTrue(inbound.exists())

        second = import_gdt_bridge_files(
            self.dependencies.gdt_workflow,
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
            self.dependencies.gdt_workflow,
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


if __name__ == "__main__":
    unittest.main()
