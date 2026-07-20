# ZAC-65 facade-removal inventory

This inventory pins the migration owners before facade removal. Behavioral tests
move with their owner; compatibility-only assertions are deleted.

| Current seam | Retained owner / migration |
|---|---|
| `DemoStore.database`, initialization, maintenance and lock | `backend.application_composition` and `SQLiteDatabase` |
| Patient and Order delegates | `PatientRepository` and `OrderRepository` |
| OIE settings/results and Lab delegates | `OieSettingsRepository`, `OieRepository`, and `LabRepository` |
| dcm4chee patient-sync, MWL and result delegates | their three repositories plus named dcm4chee coordinators |
| FHIR persistence and Patient/Order FHIR delegates | `FhirLedgerRepository`, `PatientFhirCoordinator`, and `FhirOrderCoordinator` |
| GDT persistence and workflow delegates | `GdtWorkflowRepository`, `GdtWorkflowCoordinator`, domain and template owners |
| DICOM/FHIR/GDT validation, mapping and payload helpers | existing domain, mapper, template and protocol owners |
| constants re-exported by `backend.lab_store` | `backend.domain.statuses`, protocol/domain/configuration owners, or explicit application defaults |
| `app.extensions["demo_store"]` integration setup/state access | HTTP, named repository fixtures, or focused application-factory injection |
| root `app.py` whole-module alias and patch paths | thin supported entrypoint plus owner-level patch/injection seams |
| DemoStore delegate maps/fingerprints and compatibility callers | removed; replaced by absence and explicit-composition contracts |
| `architecture_legacy_baseline.py` entries for `lab_store.py` | removed without replacement fingerprints or allowlist growth |
| README/architecture/test-ownership references | updated to application composition and current focused commands |

Production currently writes `demo_store` once and never reads it. Repository
and integration tests are the only consumers, so its removal is an internal test
migration and not an HTTP/runtime compatibility change.
