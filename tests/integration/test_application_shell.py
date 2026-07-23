import unittest

from ._case_support import *

class ApplicationShellTests(ApiCaseSupport):
    """Focused assertion owner for ApplicationShellTests."""

    def test_index_serves_dashboard_only_ui(self):
        response = self.client.get("/")
        self.assertEqual(response.status_code, 200)
        self.assertIn(b"<title>Healthcare Lab</title>", response.data)
        self.assertIn(b'data-project-mode="healthcare_lab"', response.data)
        self.assertIn(b"Server Health Dashboard", response.data)
        self.assertNotIn(b'id="protocol-mode"', response.data)

        self.assertIn(b'id="lab-console-view"', response.data)
        self.assertIn(b'id="patient-mode"', response.data)
        self.assertIn(b'class="table-wrap local-record-table-wrap patient-local-table-wrap"', response.data)
        self.assertIn(b"<th>State</th><th>Created</th>", response.data)
        self.assertNotIn(b"<th>FHIR Sync</th>", response.data)
        self.assertNotIn(
            b"<th>ID</th><th>Mode</th><th>MRN</th><th>Name</th><th>DOB</th><th>Sex</th><th>Visit</th>"
            b"<th>FHIR Sync</th><th>Medplum</th><th>Created</th><th>Action</th>",
            response.data,
        )
        self.assertIn(b'id="order-view"', response.data)
        self.assertIn(b'id="order-payload-preview"', response.data)
        self.assertIn(b'class="table-wrap local-record-table-wrap order-local-table-wrap"', response.data)
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
        self.assertIn(b'id="dashboard-service-list"', response.data)
        self.assertNotIn(b'id="orders-workbench-view"', response.data)
        self.assertNotIn(b'id="hl7-v2-view"', response.data)
        self.assertNotIn(b'id="fhir-view"', response.data)
        self.assertNotIn(b'id="gdt-ap-view"', response.data)
        self.assertNotIn(b"GDT AP Simulator", response.data)
        self.assertNotIn(b"Submit to Medplum", response.data)

    def test_native_module_assets_use_conditional_revalidation(self):
        response = self.client.get("/static/js/api/client.js")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers.get("Cache-Control"), "no-cache")
        self.assertTrue(response.headers.get("ETag"))
        self.assertTrue(response.headers.get("Last-Modified"))

        conditional = self.client.get(
            "/static/js/api/client.js",
            headers={"If-None-Match": response.headers["ETag"]},
        )
        self.assertEqual(conditional.status_code, 304)
        conditional.close()
        response.close()

    def test_frontend_exposes_dashboard_children_and_gdt_workspace_order_action(self):
        app_js = Path(__file__).resolve().parents[2] / "frontend" / "static" / "backend.app_factory.js"
        script = (app_js.parent / "js" / "views" / "application.js").read_text(encoding="utf-8")
        oie_script = (app_js.parent / "js" / "views" / "oie.js").read_text(encoding="utf-8")
        dashboard_script = (app_js.parent / "js" / "views" / "dashboard.js").read_text(encoding="utf-8")
        gdt_script = (app_js.parent / "js" / "views" / "gdt.js").read_text(encoding="utf-8")
        gdt_api = (app_js.parent / "js" / "api" / "gdt.js").read_text(encoding="utf-8")
        fhir_script = (app_js.parent / "js" / "views" / "fhir.js").read_text(encoding="utf-8")
        fhir_api = (app_js.parent / "js" / "api" / "fhir.js").read_text(encoding="utf-8")
        patient_script = (app_js.parent / "js" / "views" / "patient.js").read_text(encoding="utf-8")
        order_api = (app_js.parent / "js" / "api" / "order.js").read_text(encoding="utf-8")
        order_script = (app_js.parent / "js" / "views" / "order.js").read_text(encoding="utf-8")

        self.assertIn('const GENERATED_PATIENT_MRN_LABEL = "Generated on create";', patient_script)
        self.assertIn('mrn: "",', patient_script)
        self.assertIn("function patientPreviewMrn(payload)", patient_script)
        self.assertNotIn('["MRN", payload.mrn],', patient_script)
        self.assertIn("patientPreviewMrn(payload)", patient_script)
        self.assertIn("function patientStateLabel(item)", patient_script)
        self.assertIn('syncStatus === "Synced" && /^Patient\\/[^/]+$/.test(reference) ? "OK" : "Error"', patient_script)
        self.assertIn('syncStatus === "Synced" && patient.ack?.code === "AA" ? "OK" : "Error"', patient_script)
        self.assertIn('return messages.length ? "Error" : "OK";', patient_script)
        self.assertNotIn('return "Created";', script)
        self.assertIn("function orderStateLabel(item, mode)", order_script)
        self.assertIn("function orderModeLabel(item, mode)", order_script)
        self.assertIn("function orderRecordMode(item)", order_script)
        self.assertIn("function orderVisitNumber(item)", order_script)
        self.assertIn("expandedPatientIds: new Set()", oie_script)
        self.assertIn("function oiePatientSection(label, title, body)", oie_script)
        self.assertIn("function renderOieTransmission(item)", oie_script)
        self.assertIn('byId("send-selected-oie-order").addEventListener', oie_script)
        self.assertIn("const ORDER_PATIENT_PROTOCOL_BY_MODE", order_script)
        self.assertIn("const ORDER_PATIENT_LABEL_BY_MODE", order_script)
        self.assertIn('"hl7-v251": "HL7 v2.5.1"', order_script)
        self.assertIn('"hl7-v251": "HL7 v2"', order_script)
        self.assertIn("function orderPatientRecordsForMode(mode = currentOrderMode())", order_script)
        self.assertIn("return getPatientRecords().filter((item) => item.protocolVersion === protocolVersion);", order_script)
        self.assertIn("const records = orderPatientRecordsForMode(mode);", order_script)
        self.assertIn("Create a ${orderPatientModeLabel(mode)} patient first", order_script)
        self.assertIn("const records = [...getOrderRecords(), ...getGdtOrderRecords()]", order_script)
        self.assertIn("fetchOrders()", order_script)
        self.assertIn("fetchGdtOrders()", order_script)
        self.assertIn('return "HL7 v2";', order_script)
        self.assertIn('rowCell(orderModeLabel(item, rowMode))', order_script)
        self.assertIn('rowCell(orderVisitNumber(item))', order_script)
        self.assertIn('rowCell(taipeiTimestamp(item.createdAt))', order_script)
        self.assertIn('"Order ID",', oie_script)
        self.assertIn('"Visit Number",', oie_script)
        self.assertIn('"Created At (Taipei)",', oie_script)
        self.assertIn('statusLabel === "Accepted" ? "success" : "error"', order_script)
        self.assertIn('return status === "Created" ? "Accepted" : "Error";', order_script)
        self.assertIn('["error", "rejected", "transport error"].includes(status) ? "Error" : "Accepted"', order_script)
        self.assertNotIn('service.id === "openemr-gdt"', script)
        self.assertIn("function dashboardServiceToggle(service)", dashboard_script)
        self.assertIn("function renderDashboardChild(service, child, body)", dashboard_script)
        self.assertIn("function runChildServiceAction(serviceId, childId, action)", dashboard_script)
        self.assertIn('byId("create-gdt-ecg-order").addEventListener', script)
        self.assertIn('"/api/gdt/orders"', order_api)
        self.assertIn('"/api/gdt/workbench"', gdt_api)
        self.assertIn("Preview GDT-OUT", gdt_script)
        self.assertIn("Import GDT-IN", gdt_script)
        self.assertIn('"/api/gdt/bridge/watcher/start"', gdt_api)
        self.assertIn('"/api/gdt/bridge/watcher/stop"', gdt_api)
        self.assertIn("write-6302", gdt_api)
        self.assertIn('selector.value = "gdt"', script)
        self.assertIn('setActiveView("order-view")', script)
        self.assertIn('"/api/fhir/inventory"', fhir_api)
        self.assertIn('`/api/fhir/diagnostic-reports?${params.toString()}`', fhir_api)
        self.assertIn('`/api/fhir/resource-preview?${params.toString()}`', fhir_api)
        self.assertIn('`/api/fhir/records/${recordId}/preview`', fhir_api)
        self.assertIn('`/api/fhir/records/${recordId}/sync`', fhir_api)
        self.assertIn("Live fetch failed; local submitted JSON", fhir_script)
        self.assertIn("medplumDiagnosticReports", fhir_script)
        self.assertIn("fetchMedplumDiagnosticReportsForCurrentSelection", fhir_script)
        self.assertIn("renderMedplumDiagnosticReportRollup", fhir_script)
        self.assertIn("loadMedplumLiveReportPreview", fhir_script)
        self.assertIn("loadMedplumLiveReferencePreview", fhir_script)
        self.assertIn("resetMedplumDiagnosticReportState", fhir_script)
        self.assertIn("medplumDiagnosticReportKeyMatchesCurrent", fhir_script)
        self.assertIn("medplumDiagnosticReports.requestId + 1", fhir_script)
        self.assertIn("medplumDiagnosticReports.loading && medplumDiagnosticReports.key === key", fhir_script)
        self.assertIn("Patient-level result", fhir_script)
        self.assertIn("Live DiagnosticReport References", fhir_script)
        self.assertIn("medplumRecordMatchesPatient", fhir_script)
        self.assertIn("let expandedMedplumPatientIds = new Set();", fhir_script)
        self.assertIn("function medplumOrderRecordsForPatient(patient)", fhir_script)
        self.assertIn("function medplumResultRecordsForPatient(patient)", fhir_script)
        self.assertIn("function medplumResourceRollupTable(items, emptyText)", fhir_script)
        self.assertIn("function medplumPatientSection(label, title, body)", fhir_script)
        self.assertIn('toggleButton.setAttribute("aria-expanded"', fhir_script)
        self.assertIn('event.stopPropagation();\n      if (expandedMedplumPatientIds.has(patientId))', fhir_script)
        self.assertIn('"FHIR ORDERS"', fhir_script)
        self.assertIn('["Order", "MRN", "Status", "Reference", "Created", "Action"]', fhir_script)
        self.assertIn("medplumOrderRollupTable(patient, orders)", fhir_script)
        self.assertIn('"FHIR RESULTS"', fhir_script)
        self.assertIn('medplumPreviewButton(item)', fhir_script)
        self.assertIn('retryButtonForMedplumRecord(item)', fhir_script)
        self.assertIn("renderMedplumPatientList", fhir_script)
        self.assertIn("renderMedplumPatientList();\n  const patient = selectedMedplumPatient();", fhir_script)
        self.assertIn('const serviceRequests = patient ? medplumRecordsForPatient(patient, "ServiceRequest") : [];', fhir_script)
        self.assertIn('item.resourceType === "ServiceRequest"', fhir_script)
        self.assertIn('"ServiceRequest",\n          medplumOrderRollupTable(patient, orders)', fhir_script)
        self.assertIn("clearMedplumPreview", fhir_script)
        self.assertIn("medplum-service-request-select", fhir_script)
        self.assertIn("medplum-diagnostic-report-select", fhir_script)
        self.assertIn("medplum-related-row", fhir_script)
        self.assertIn("buildFhirOrderPreviewPayload", order_script)
        self.assertIn("FHIR Order requires a synced FHIR Patient", order_script)
        self.assertIn('payload.mode === "hl7-v251"', order_script)
        self.assertIn("FHIR order code is required.", order_script)
        self.assertIn('payload.mode !== "fhir" && payload.requestedAt', order_script)
        self.assertIn("serviceRequest", script)
        self.assertIn('serviceRequest.sync?.status === "Synced"', order_script)
        self.assertIn('/^ServiceRequest\\/[^/]+$/.test(serviceRequestReference)', order_script)
        self.assertNotIn('"Task"', script)
        self.assertNotIn("item.fhir?.task", script)

        template = Path(__file__).resolve().parents[2] / "frontend" / "templates" / "views" / "fhir.html"
        html = template.read_text(encoding="utf-8")
        self.assertIn('id="medplum-diagnostic-report-rollup"', html)
        self.assertIn('id="medplum-diagnostic-report-status"', html)
        self.assertIn("Live Results", html)
        self.assertIn("<th>MRN</th><th>Name</th><th>Created</th><th>Sync</th><th>Orders</th><th>Results</th><th>Action</th>", html)
        self.assertIn("rowCell(medplumTimestamp(patient.createdAt || patientRecord.createdAt))", fhir_script)
        self.assertNotIn("Task", html)

        styles = frontend_styles()
        self.assertIn(".medplum-patient-toggle", styles)
        self.assertIn(".medplum-patient-detail-row td", styles)
        self.assertIn(".medplum-patient-rollup-content", styles)
        self.assertIn(".medplum-nested-table-wrap", styles)
        self.assertIn(".medplum-context-column", styles)

    def test_sidebar_views_hide_inactive_pages(self):
        styles = frontend_styles()
        self.assertIn(".app-view[hidden]", styles)
        self.assertIn("display: none", styles)
        self.assertIn(".local-record-table-wrap", styles)
        self.assertIn("max-height: 360px", styles)
        self.assertIn("overflow: auto", styles)

    def test_only_healthcare_lab_routes_are_registered(self):
        routes = {rule.rule for rule in self.client.application.url_map.iter_rules()}
        self.assertIn("/api/settings/readiness", routes)
        self.assertIn("/api/settings/readiness/checks", routes)
        self.assertIn("/api/dashboard/services", routes)
        self.assertIn("/api/lab/servers", routes)
        self.assertIn("/api/orders", routes)
        self.assertIn("/api/oie/local-orders", routes)
        self.assertIn("/api/oie/settings", routes)
        self.assertIn("/api/oie/result-listener/start", routes)
        self.assertIn("/api/oie/result-listener/retry", routes)
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

    def test_settings_readiness_is_composed_without_openemr(self):
        response = self.client.get("/api/settings/readiness")
        self.assertEqual(200, response.status_code)
        body = response.get_json()
        self.assertTrue(body["success"])
        sections = body["item"]["sections"]
        self.assertEqual(
            [
                "medplum",
                "oie",
                "gdt-bridge",
                "dcm4chee",
                "external-devices",
                "deployment",
            ],
            [item["id"] for item in sections],
        )
        self.assertNotIn("openemr", response.get_data(as_text=True).lower())
        self.assertFalse(body["item"]["complete"])
        self.assertEqual("oie", body["item"]["nextAction"]["sectionId"])
        optional = {
            item["id"]: item["state"]
            for item in sections
            if not item["required"]
        }
        self.assertEqual(
            {
                "gdt-bridge": "disabled",
                "dcm4chee": "ready",
                "external-devices": "disabled",
            },
            optional,
        )

        checks = self.client.post("/api/settings/readiness/checks").get_json()
        states = {
            item["id"]: item["state"] for item in checks["item"]["results"]
        }
        self.assertEqual("unavailable", states["medplum"])
        self.assertEqual("disabled", states["gdt-bridge"])
        self.assertEqual("unavailable", states["deployment"])

    def test_fresh_settings_readiness_requires_operator_setup(self):
        with tempfile.TemporaryDirectory() as directory:
            fresh_app = create_app(
                str(Path(directory) / "fresh.db"), activate_runtime=False
            )
            response = fresh_app.test_client().get("/api/settings/readiness")
        body = response.get_json()["item"]
        self.assertFalse(body["complete"])
        self.assertEqual("medplum", body["nextAction"]["sectionId"])
        self.assertEqual(
            "needs-setup",
            next(
                item["state"]
                for item in body["sections"]
                if item["id"] == "medplum"
            ),
        )


if __name__ == "__main__":
    unittest.main()
