import unittest

from ._case_support import *

class CrossFeatureWorkflowTests(ApiCaseSupport):
    """Focused assertion owner for CrossFeatureWorkflowTests."""

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


if __name__ == "__main__":
    unittest.main()
