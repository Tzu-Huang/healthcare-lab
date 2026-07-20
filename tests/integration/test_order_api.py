import unittest

from ._case_support import *

class OrderApiTests(ApiCaseSupport):
    """Focused assertion owner for OrderApiTests."""

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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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
        store = self.dependencies
        record = store.fhir_ledger.create_fhir_workflow_record(
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
        with store.database.connect() as connection:
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


if __name__ == "__main__":
    unittest.main()
