import unittest

from ._case_support import *

class FhirApiTests(ApiCaseSupport):
    """Focused assertion owner for FhirApiTests."""

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
                "resource": {
                    "resourceType": "Patient",
                    "active": True,
                    "identifier": [
                        {"system": "urn:healthcare-lab:mrn", "value": "MRN-000701"}
                    ],
                },
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
                "resource": {
                    "resourceType": "Patient",
                    "active": True,
                    "identifier": [
                        {"system": "urn:healthcare-lab:mrn", "value": "MRN-000701"}
                    ],
                },
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
        store = self.dependencies
        store.fhir_ledger.mark_fhir_sync_success(
            patient["id"],
            medplum_resource_id="patient-created",
            medplum_resource_reference="Patient/patient-created",
        )

        inventory = self.client.get("/api/fhir/inventory")

        self.assertEqual(inventory.status_code, 200)
        body = inventory.get_json()
        by_id = {item["id"]: item for item in body["items"]}
        self.assertEqual(by_id[patient["id"]]["previewSource"], "medplum-live")
        self.assertEqual(by_id[patient["id"]]["summary"]["secondary"], "MRN-000701")
        self.assertNotEqual(
            by_id[patient["id"]]["summary"]["secondary"],
            by_id[patient["id"]]["identifier"]["value"],
        )
        self.assertEqual(by_id[observation["id"]]["patientReferences"], ["Patient/patient-created"])
        self.assertEqual(by_id[observation["id"]]["references"], ["Patient/patient-created"])
        self.assertEqual(by_id[observation["id"]]["summary"]["primary"], "Observation")
        self.assertEqual(by_id[observation["id"]]["summary"]["status"], "final")
        self.assertTrue(by_id[observation["id"]]["retryable"])
        self.assertEqual(body["patients"][0]["reference"], "Patient/patient-created")
        self.assertEqual(body["patients"][0]["createdAt"], body["items"][0]["createdAt"])

        preview = self.client.get(f"/api/fhir/records/{observation['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        self.assertEqual(preview.get_json()["source"], "local-submitted")
        self.assertEqual(preview.get_json()["resource"]["subject"]["reference"], "Patient/patient-created")

    @patch("backend.app_factory.urllib.request.urlopen")
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
        store = self.dependencies
        store.fhir_ledger.mark_fhir_sync_success(
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

    @patch("backend.app_factory.urllib.request.urlopen")
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
        store = self.dependencies
        store.fhir_ledger.mark_fhir_sync_success(
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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


if __name__ == "__main__":
    unittest.main()
