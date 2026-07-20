import unittest

from ._case_support import *

class Dcm4cheeApiTests(ApiCaseSupport):
    """Focused assertion owner for Dcm4cheeApiTests."""

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
        template = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (
                Path("frontend/templates/shell/sidebar.html"),
                Path("frontend/templates/views/dcm4chee.html"),
            )
        )
        script = Path("frontend/static/js/views/application.js").read_text(encoding="utf-8")
        order_api = Path("frontend/static/js/api/order.js").read_text(encoding="utf-8")
        dcm4chee_view = Path("frontend/static/js/views/dcm4chee.js").read_text(encoding="utf-8")
        dcm4chee_ownership = script + dcm4chee_view

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
        self.assertIn("refreshPatientDcm4cheeResults", dcm4chee_ownership)
        patient_api = Path("frontend/static/js/api/patient.js").read_text(encoding="utf-8")
        self.assertIn("/api/patients/${patientId}/dcm4chee-results-refresh", patient_api)
        dcm4chee_api = Path("frontend/static/js/api/dcm4chee.js").read_text(encoding="utf-8")
        self.assertIn("refreshDcm4cheeConsole", dcm4chee_view)
        self.assertIn("/api/dcm4chee/profile/diagnostics", dcm4chee_api)
        self.assertIn("renderDcm4cheeConsole", dcm4chee_view)
        self.assertIn("renderDcm4cheeSelectors", dcm4chee_view)
        self.assertIn("renderDcm4cheePreview", dcm4chee_view)
        self.assertIn("sendDcm4cheeOrder", dcm4chee_ownership)
        dcm4chee_state = Path("frontend/static/js/state/dcm4chee.js").read_text(encoding="utf-8")
        self.assertIn("const expandedPatientIds = new Set();", dcm4chee_state)
        self.assertIn("toggleDcm4cheePatientExpanded", dcm4chee_view)
        self.assertIn('createElement("button", "V", "dcm4chee-patient-toggle")', dcm4chee_view)
        self.assertIn("renderDcm4cheeExpandedOrders", dcm4chee_view)
        self.assertIn("renderDcm4cheeExpandedResults", dcm4chee_view)
        self.assertIn("renderDcm4cheeResultTable", dcm4chee_view)
        self.assertIn("function dcm4cheeFirstArtifact(records)", dcm4chee_view)
        self.assertIn("const artifact = dcm4cheeFirstArtifact(study.records);", dcm4chee_view)
        self.assertIn('"Artifact", "Artifact Type", "Artifact Location"', dcm4chee_view)
        self.assertIn('dcm4cheeActionsForResult({ ...representative, artifact }, "study")', dcm4chee_view)
        self.assertIn('"dcm4chee-study-table-wrap"', dcm4chee_view)
        self.assertIn('"dcm4chee-series-table-wrap"', dcm4chee_view)
        self.assertNotIn('section.className = "detail-block raw-details dcm4chee-result-browser"', dcm4chee_ownership)
        toggle_start = dcm4chee_view.index('toggleButton.addEventListener("click"')
        toggle_end = dcm4chee_view.index("renderDcm4cheeConsole();", toggle_start)
        toggle_handler = dcm4chee_view[toggle_start:toggle_end]
        self.assertNotIn("selectedDcm4cheePatientId", toggle_handler)
        self.assertIn('row.addEventListener("click", () => selectDcm4cheePatient(patient.id))', dcm4chee_view)
        self.assertIn('byId("send-dcm4chee-order")?.addEventListener', dcm4chee_view)
        self.assertIn("patientIdsWithDicomOrders", dcm4chee_view)
        self.assertIn("renderDcm4cheeSelectedPatient", dcm4chee_view)
        self.assertIn("renderDcm4cheeSelectedOrder", dcm4chee_view)
        self.assertIn("renderPatientDcm4cheeResults", dcm4chee_view)
        self.assertIn("DICOM Results", dcm4chee_view)
        self.assertIn("dicomResults", dcm4chee_view)
        self.assertIn("groupDcm4cheeResultsForBrowser", dcm4chee_view)
        self.assertIn("renderDcm4cheeStudyDetails", dcm4chee_view)
        self.assertIn("renderDcm4cheeSeriesDetails", dcm4chee_view)
        self.assertIn("renderDcm4cheeInstanceTable", dcm4chee_view)
        self.assertIn("Study Instance UID", dcm4chee_view)
        self.assertIn("Series Instance UID", dcm4chee_view)
        self.assertIn("SOP Instance UID", dcm4chee_view)
        self.assertIn("Accession Number", dcm4chee_view)
        self.assertIn("Issuer of Patient ID", dcm4chee_view)
        self.assertIn("Open Viewer", dcm4chee_view)
        self.assertIn("Copy Retrieve", dcm4chee_view)
        self.assertIn("Refresh PACS Results", dcm4chee_view)
        self.assertIn("Simulate AP PDF", dcm4chee_view)
        self.assertIn("Simulate AP DICOM", dcm4chee_view)
        self.assertIn("/api/orders/${orderId}/dcm4chee-simulated-ap-return", order_api)
        self.assertIn("Open Artifact", dcm4chee_view)
        self.assertIn("Copy Artifact", dcm4chee_view)
        self.assertIn("MWL Sync", dcm4chee_view)
        self.assertIn("MWL Queryable", dcm4chee_view)
        self.assertIn("AP C-STORE Result", dcm4chee_view)
        self.assertIn("Reconciliation", dcm4chee_view)

        styles = frontend_styles()
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


if __name__ == "__main__":
    unittest.main()
