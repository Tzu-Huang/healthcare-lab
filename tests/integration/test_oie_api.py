import unittest

from ._case_support import *

class OieApiTests(ApiCaseSupport):
    """Focused assertion owner for OieApiTests."""

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
        body = response.get_json()
        self.assertTrue(body["runtimeReloadRequired"])
        item = body["item"]
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
        self.assertFalse(response.get_json()["runtimeReloadRequired"])

        omitted = self.oie_settings_payload()
        omitted["managementApi"]["username"] = "updated-user"
        self.assertEqual(self.client.put("/api/oie/settings", json=omitted).status_code, 200)
        store = self.dependencies
        with store.database.connect() as connection:
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
        with store.database.connect() as connection:
            preserved_password = connection.execute(
                "SELECT management_api_password FROM oie_settings_profiles"
            ).fetchone()[0]
        self.assertEqual(preserved_password, secret)

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

    def test_oie_result_api_requires_msh_10_without_accepting_a_result(self):
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01^ORU_R01||P|2.5.1\r"
            "PID|1||MRN-MISSING-ID^^^HEALTHCARE_LAB^MR"
        )

        response = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(response.status_code, 400)
        body = response.get_json()
        self.assertFalse(body["success"])
        self.assertIn("MSA|AE||HL7 MSH-10 message control ID is required.", body["ack"])
        results = self.client.get("/api/oie/workbench").get_json()["unmatchedResults"]
        self.assertEqual(1, len(results))
        self.assertEqual("error", results[0]["parseStatus"])

    def test_oie_result_redelivery_is_acknowledged_without_duplicate_insert(self):
        payload = (
            "MSH|^~\\&|OIE|HL7LAB|HEALTHCARE_LAB|DASHBOARD|20260706100000||ORU^R01^ORU_R01|ORU-RETRY|P|2.5.1\r"
            "PID|1||UNKNOWN^^^HEALTHCARE_LAB^MR"
        )

        first = self.client.post("/api/oie/results", json={"payload": payload})
        duplicate = self.client.post("/api/oie/results", json={"payload": payload})

        self.assertEqual(200, first.status_code)
        self.assertEqual(200, duplicate.status_code)
        self.assertIn("MSA|AA|ORU-RETRY|Duplicate result ignored.", duplicate.get_json()["ack"])
        self.assertTrue(duplicate.get_json()["item"]["duplicate"])
        results = self.client.get("/api/oie/workbench").get_json()["unmatchedResults"]
        self.assertEqual(1, len(results))

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
            payload = self.oie_settings_payload(resultListener={
                "host": "127.0.0.1", "port": port,
                "mllpFraming": True, "autoStart": True,
            })
            self.assertEqual(200, self.client.put("/api/oie/settings", json=payload).status_code)
            response = self.client.post("/api/oie/result-listener/start", json={
                "host": "ignored.example", "port": 1, "mllpFraming": False,
            })
        finally:
            occupied.close()

        self.assertEqual(response.status_code, 400)
        self.assertIn("Listener could not start", response.get_json()["error"])
        status = self.client.get("/api/oie/result-listener/status").get_json()["item"]
        self.assertFalse(status["running"])
        self.assertEqual("degraded", status["state"])
        self.assertEqual(port, status["port"])

    @patch("backend.app_factory.send_hl7_mllp_message")
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

    @patch("backend.app_factory.send_hl7_mllp_message")
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

    @patch("backend.app_factory.send_hl7_mllp_message", side_effect=OSError("connection refused"))
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


if __name__ == "__main__":
    unittest.main()
