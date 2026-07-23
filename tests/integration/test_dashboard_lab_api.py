import unittest

from ._case_support import *

class DashboardLabApiTests(ApiCaseSupport):
    """Focused assertion owner for DashboardLabApiTests."""

    def test_dashboard_summary_counts_running_primary_and_child_services(self):
        items = [
            {
                "enabled": True,
                "status": "Healthy",
                "children": [],
            },
            {
                "enabled": True,
                "status": "Healthy",
                "children": [
                    {"status": "Healthy", "runtime": {"running": True}},
                    {"status": "Healthy", "runtime": {"running": True}},
                ],
            },
            {
                "enabled": True,
                "status": "Healthy",
                "children": [
                    {"status": "Healthy", "runtime": {"running": True}},
                    {"status": "Healthy", "runtime": {"running": True}},
                ],
            },
        ]
        resources = {
            "status": "ok",
            "totals": {"cpuPercent": 1.0, "memoryPercent": 2.0},
        }

        summary = dashboard_summary(items, resources)

        self.assertEqual(summary["total"], 7)
        self.assertEqual(summary["running"], 7)

        items[1]["children"][0] = {
            "status": "Down",
            "runtime": {"running": False},
        }
        self.assertEqual(dashboard_summary(items, resources)["running"], 6)

    def test_dashboard_services_exposes_three_allowlisted_groups_with_children(self):
        response = self.client.get("/api/dashboard/services")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(
            [item["id"] for item in body["items"]],
            ["hl7-v2-oie", "fhir-medplum", "dicom-dcm4chee"],
        )
        self.assertEqual(body["summary"]["total"], 7)
        by_id = {item["id"]: item for item in body["items"]}
        self.assertEqual(
            by_id["hl7-v2-oie"]["ports"],
            [{"label": "localhost:8080", "url": "http://localhost:8080"}],
        )
        self.assertEqual(
            by_id["fhir-medplum"]["ports"],
            [{"label": "localhost:3000", "url": "http://localhost:3000"}],
        )
        self.assertEqual(
            by_id["dicom-dcm4chee"]["ports"],
            [{
                "label": "8082:8080",
                "url": "http://localhost:8082/dcm4chee-arc/ui2/en/study/patient",
            }],
        )
        self.assertEqual(by_id["hl7-v2-oie"]["children"], [])
        self.assertEqual(
            [child["name"] for child in by_id["fhir-medplum"]["children"]],
            ["medplum-redis-1", "medplum-postgres-1"],
        )
        self.assertEqual(
            [child["name"] for child in by_id["dicom-dcm4chee"]["children"]],
            ["ldap-1", "dcm4chee-db-1"],
        )
        self.assertIn("resources", body)
        self.assertIn("events", body)

    def test_dashboard_rejects_unsupported_service_ids(self):
        preview = self.client.get("/api/dashboard/services/raw-container/restart-preview")
        self.assertEqual(preview.status_code, 404)
        action = self.client.post("/api/dashboard/services/raw-container/restart", json={})
        self.assertEqual(action.status_code, 404)

    @patch("backend.app_factory.run_lab_operation")
    def test_dashboard_action_mapping_and_restart_preview(self, run_operation):
        run_operation.return_value = {
            "operation": {"action": "start", "result": "success"},
            "output": "started",
        }
        response = self.client.post("/api/dashboard/services/fhir-medplum/enable", json={})
        self.assertEqual(response.status_code, 200)
        self.assertEqual(run_operation.call_args.kwargs["action"], "start")
        self.assertEqual(
            run_operation.call_args.kwargs["backing_services"],
            ["medplum-redis", "medplum-postgres", "medplum"],
        )
        self.assertIn("service", response.get_json())

        stopped = self.client.post("/api/dashboard/services/fhir-medplum/disable", json={})
        self.assertEqual(stopped.status_code, 200)
        self.assertEqual(
            run_operation.call_args.kwargs["backing_services"],
            ["medplum", "medplum-postgres", "medplum-redis"],
        )

        restarted = self.client.post("/api/dashboard/services/dicom-dcm4chee/restart", json={})
        self.assertEqual(restarted.status_code, 200)
        self.assertEqual(
            run_operation.call_args.kwargs["backing_services"],
            ["ldap", "dcm4chee-db", "dcm4chee"],
        )

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

    @patch("backend.app_factory.run_lab_operation")
    @patch("backend.app_factory.run_lab_server_health_check")
    def test_dashboard_check_runs_health_check_for_primary_service(
        self, run_health_check, run_operation
    ):
        store = self.lab_repository_view

        def mark_healthy(store_arg, server_id):
            self.assertIs(store_arg._repository, self.dependencies.lab_repository)
            return store_arg.update_lab_server_health(
                server_id,
                overall_status="Healthy",
                process_status="Healthy",
                application_status="Healthy",
                protocol_status="Healthy",
            )

        run_health_check.side_effect = mark_healthy

        response = self.client.post("/api/dashboard/services/dicom-dcm4chee/check", json={})

        self.assertEqual(response.status_code, 200)
        self.assertFalse(run_operation.called)
        self.assertEqual(run_health_check.call_count, 1)
        body = response.get_json()
        self.assertEqual(body["service"]["status"], "Healthy")
        self.assertEqual(body["service"]["checks"]["process"], "Healthy")
        self.assertEqual(
            [item["name"] for item in body["servers"]],
            ["dcm4chee"],
        )

    @patch("backend.app_factory.run_lab_operation")
    def test_dashboard_child_action_targets_only_allowlisted_child(self, run_operation):
        run_operation.return_value = {
            "operation": {"action": "stop", "result": "success"},
            "output": "stopped",
        }

        response = self.client.post(
            "/api/dashboard/services/fhir-medplum/children/medplum-redis/disable",
            json={},
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(run_operation.call_args.kwargs["backing_services"], ["medplum-redis"])
        self.assertEqual(run_operation.call_args.kwargs["operation_service_name"], "medplum-redis-1")
        self.assertFalse(run_operation.call_args.kwargs["refresh_health"])

        rejected = self.client.post(
            "/api/dashboard/services/fhir-medplum/children/arbitrary-container/restart",
            json={},
        )
        self.assertEqual(rejected.status_code, 404)
        self.assertEqual(run_operation.call_count, 1)

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
            with self.assertRaises(TypedSettingsValidationError):
                with patch.dict(
                    os.environ,
                    {
                        "DCM4CHEE_DIMSE_PORT": "abc",
                        "DCM4CHEE_HL7_PORT": "bad",
                        "DCM4CHEE_TLS_ENABLED": "maybe",
                        "DCM4CHEE_TLS_VERIFY": "sometimes",
                    },
                ):
                    create_app(
                        str(Path(temp_dir) / "malformed.db"),
                        activate_runtime=False,
                    )

    @patch("backend.app_factory.socket.create_connection")
    @patch("backend.app_factory.urllib.request.urlopen")
    def test_dcm4chee_smoke_reports_out_of_range_dimse_port(self, urlopen, create_connection):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.client.application.config["DCM4CHEE_DIMSE_PORT"] = "99999"
        store = self.lab_repository_view
        dcm4chee = next(item for item in store.list_lab_servers() if item["name"] == "dcm4chee")

        result = run_lab_smoke_check(self.client.application, store, dcm4chee)

        self.assertEqual(result["status"], "Healthy")
        dimse_step = next(step for step in result["steps"] if step["name"] == "dicom_dimse")
        self.assertEqual(dimse_step["status"], "Healthy")
        create_connection.assert_called_once()

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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.socket.create_connection")
    @patch("backend.app_factory.urllib.request.urlopen")
    def test_oie_smoke_uses_compose_network_endpoints(self, urlopen, create_connection):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        create_connection.return_value.__enter__.return_value = object()
        store = self.lab_repository_view
        oie = next(item for item in store.list_lab_servers() if item["name"] == "OIE")

        result = run_lab_smoke_check(self.client.application, store, oie)

        self.assertEqual(result["status"], "Healthy")
        request = urlopen.call_args.args[0]
        self.assertEqual(request.full_url, "http://oie:8080")
        create_connection.assert_called_with(("oie", 6661), 3)

    @patch("backend.app_factory.urllib.request.urlopen")
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
        store = self.lab_repository_view
        medplum = next(item for item in store.list_lab_servers() if item["name"] == "Medplum")

        result = run_lab_smoke_check(self.client.application, store, medplum)

        self.assertEqual(result["status"], "Degraded")
        service_request_step = next(
            step for step in result["steps"] if step["name"] == "service_request_fetch"
        )
        self.assertIn("FHIR data fetch unauthorized", service_request_step["message"])

    @patch("backend.app_factory.urllib.request.urlopen")
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
        store = self.lab_repository_view
        medplum = next(item for item in store.list_lab_servers() if item["name"] == "Medplum")

        result = run_lab_smoke_check(self.client.application, store, medplum)

        diagnostic_step = next(
            step for step in result["steps"] if step["name"] == "diagnostic_report_fetch"
        )
        self.assertEqual(diagnostic_step["status"], "Healthy")
        self.assertIn("0 report(s)", diagnostic_step["message"])

    @patch("backend.app_factory.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_reports_healthy_steps(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.install_openemr_source(lambda: FakeDbConnection(rows=[{"procedure_order_id": 1}]))
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        for name in ("inbox", "outbox"):
            (bridge_root / name).mkdir(parents=True, exist_ok=True)

        result = self.run_openemr_smoke()

        self.assertEqual(result["status"], "Healthy")
        by_name = {step["name"]: step for step in result["steps"]}
        self.assertEqual(by_name["openemr_http"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_db_connection"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_order_schema"]["status"], "Healthy")
        self.assertEqual(by_name["openemr_ecg_orders"]["status"], "Healthy")
        self.assertFalse(by_name["openemr_ecg_orders"]["required"])
        self.assertEqual(by_name["gdt_folder_contract"]["status"], "Healthy")

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
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

    @patch("backend.app_factory.urllib.request.urlopen")
    def test_openemr_gdt_backend_verify_degrades_when_no_ecg_orders_exist(self, urlopen):
        urlopen.return_value = FakeHttpResponse(b"ok", status=200)
        self.install_openemr_source(lambda: FakeDbConnection(rows=[]))
        bridge_root = Path(self.client.application.config["GDT_BRIDGE_PATH"])
        for name in ("inbox", "outbox"):
            (bridge_root / name).mkdir(parents=True, exist_ok=True)

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

        inspect_command = adapter.build_command("inspect", "medplum-redis")
        self.assertIn("inspect", inspect_command)
        self.assertIn("medplum-redis", inspect_command)

    def test_lab_compose_operation_adapter_parses_array_and_line_json_status(self):
        array_rows = DockerComposeLabOperationAdapter.parse_compose_ps_json(
            '[{"Name":"interoperability-lab-ldap-1","State":"running"}]'
        )
        line_rows = DockerComposeLabOperationAdapter.parse_compose_ps_json(
            '{"Name":"one","State":"running"}\n{"Name":"two","State":"exited"}'
        )

        self.assertEqual(array_rows[0]["Name"], "interoperability-lab-ldap-1")
        self.assertEqual([item["State"] for item in line_rows], ["running", "exited"])

    def test_default_compose_omits_openemr_and_keeps_gdt_in_lab_app(self):
        repo = Path(__file__).resolve().parents[2]
        compose = (repo / "deploy" / "docker-compose.yml").read_text(encoding="utf-8")
        lab_script = (repo / "deploy" / "lab.ps1").read_text(encoding="utf-8")

        self.assertNotIn("\n  openemr:\n", compose)
        self.assertNotIn("\n  openemr-db:\n", compose)
        self.assertNotIn("OPENEMR_DB_HOST: openemr-db", compose)
        self.assertIn("GDT_BRIDGE_PATH: /data/gdt-bridge", compose)
        self.assertIn('"medplum-redis" = @("medplum-redis")', lab_script)
        self.assertIn('"dcm4chee-db" = @("dcm4chee-db")', lab_script)
        self.assertIn('"ldap" = @("ldap")', lab_script)
        self.assertNotIn('"openemr" = @("openemr")', lab_script)

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
