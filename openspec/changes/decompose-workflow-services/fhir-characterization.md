# ZAC-62 FHIR Workflow Characterization

The following behavior is locked before decomposing `FhirWorkflowService`:

| Use case | Characterization evidence | Preserved contract |
|---|---|---|
| Inventory and filtering | `test_fhir_inventory_exposes_patient_relations_and_local_preview`, `test_historical_fhir_task_is_excluded_from_active_api_contracts` | active resource types, local relations, ordering, and sync-status filtering |
| Record and resource preview | `test_fhir_record_preview_uses_medplum_live_json_for_synced_resource`, `test_fhir_record_preview_falls_back_to_local_json_when_live_fetch_fails`, `test_fhir_resource_preview_fetches_live_binary_reference` | live/local fallback, reference URL construction, and returned JSON shape |
| DiagnosticReport | `test_fhir_diagnostic_reports_fetches_patient_bundle_and_summaries`, empty/fallback/unauthorized/malformed bundle cases in `tests/integration/test_app.py` | search precedence, relationship summaries, optional fallbacks, and upstream errors |
| Sync and retry | `test_fhir_sync_delegates_to_injected_client`, identifier reuse/create/update/failure/retry cases in `tests/integration/test_app.py` | ledger transitions, attempts, OperationOutcome, identifier reuse, and error classification |
| Patient/Order enrichment | `tests/services/test_fhir_coordination.py`, `tests/repositories/test_fhir_workflow_characterization.py` | Patient reference requirements, local Order commit ordering, ledger linkage, and failure preservation |

Decomposition must keep API routes and projections unchanged and reuse these
tests as the focused regression baseline. No live Medplum service or repository
database is used by the focused service checks.
