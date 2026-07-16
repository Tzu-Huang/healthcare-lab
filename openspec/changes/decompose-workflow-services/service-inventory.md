# ZAC-62 Service Responsibility and Caller Inventory

Baseline: `7119809`, containing ZAC-46 merge `d3bae1a`. Product implementation
must preserve `app.extensions["oie_management_client"]`, constructed by
`create_oie_management_client(store.oie_settings_repository)`.

| Context | Current owner and callers | Focused owners | Narrow capabilities |
|---|---|---|---|
| Lab registry | `LabServerWorkflowService`; Lab API through `app_factory.py` | registry service | lab server CRUD repository, decorator |
| Lab health | `LabServerWorkflowService.check_*`; Lab API and dashboard | health service | server reads, health probe, health persistence |
| Lab operations | `LabServerWorkflowService.execute_operation`; Lab API | operation service | server read, operation runner, operation history |
| Lab smoke | `LabServerWorkflowService.smoke_all_servers`; Lab API | smoke service | server list, smoke runner |
| Dashboard | `DashboardWorkflowService`; Dashboard API | snapshot service and action service | dashboard catalog/resource snapshot; health/action callbacks |
| FHIR records | `FhirWorkflowService`; FHIR API | record query service | FHIR ledger reads/writes |
| FHIR inventory | `FhirWorkflowService.inventory` | inventory service | ledger inventory, Medplum inventory loader |
| FHIR preview | `resource_preview`, `record_preview` | preview service | resource builder, Medplum fetch, settings |
| FHIR DiagnosticReport | `diagnostic_reports` | diagnostic-report service | report bundle loader, settings |
| FHIR sync | `sync_record` | sync service | ledger transitions, resource builder, Medplum transport |
| Order records | `OrderWorkflowService.list/get/create` | order record service | order ledger, protocol-specific creation capabilities |
| dcm4chee MWL | `sync_dcm4chee`, `verify_dcm4chee` | MWL sync and verification coordinators | order/patient reads, MWL ledgers, DICOM client/template operations |
| dcm4chee evidence | `dcm4chee_evidence`, simulated return | evidence service | evidence and simulated-return capabilities, profile loader |
| Patient records | `PatientWorkflowService.list/create` | patient record service | patient ledger and protocol-specific creation capabilities |
| Patient external sync | `sync_fhir`, dcm4chee refresh/fixture | FHIR sync, dcm4chee result, and fixture services | explicit FHIR/DICOM capabilities and settings |
| GDT records | `GdtWorkflowService` order/message/event methods | record service | cohesive GDT repository operations |
| GDT bridge configuration | `bridge_config`, `update_bridge_config` | bridge configuration service | settings and watcher configuration |
| GDT bridge files | inbox/export/import methods | bridge exchange service | filesystem boundary, importer/exporter, GDT repository |
| GDT watcher | watcher start/stop/status methods | runtime control service | watcher lifecycle port only |

## Preserved composition and runtime seams

- Lab, Dashboard, Patient, Order, FHIR, and GDT Blueprints receive application
  services from `backend/app_factory.py`.
- Runtime GDT inbound callbacks consume normalized result-import behavior; file
  discovery, claiming, disposition, and watcher lifecycle remain runtime owners.
- Existing `app.extensions` keys, including `oie_management_client`, are public
  test/patch seams and remain stable.
- ZAC-46 OIE client/settings modules and ZAC-47 OIE channel domain/templates are
  outside this change.

## Port rules

- Ports are declared by consumers and contain only operations used by that use
  case.
- Concrete parameter and return annotations are required; variadic forwarding,
  dynamic delegation, and bare `Any` returns are rejected.
- Cross-context orchestration is named explicitly and assembled in the
  composition root; services do not import APIs, `DemoStore`, or unrelated
  concrete repositories.
