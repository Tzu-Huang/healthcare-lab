# Healthcare Lab Application Architecture

Healthcare Lab uses responsibility-oriented modules. New code belongs in the narrowest layer that owns the behavior; `app.py` is only the process entrypoint and legacy import compatibility boundary.

## Backend placement

| Location | Owns | Must not own |
|---|---|---|
| `backend/app_factory.py` | Flask construction, configuration application, dependency assembly, Blueprint registration, runtime startup | Route implementations, SQL, protocol transports, workflow rules |
| `backend/config.py` | Environment parsing and application configuration | Flask request state or persistence |
| `backend/api/` | HTTP parsing, service invocation, response/error mapping | SQL, external transports, long-running lifecycle logic |
| `backend/services/` | Use cases and workflow coordination | Flask request objects or direct response construction |
| `backend/clients/` | External HTTP, MLLP, DICOM, FHIR, and other protocol transports | Flask or SQLite dependencies |
| `backend/runtime/` | Listeners, watchers, sockets, threads, retry loops, start/stop state | HTTP response mapping or persistence schemas |
| `backend/repositories/` | SQLite queries, transactions, and persistence mapping | HTTP responses or external protocol calls |
| `backend/domain/` | Framework-independent models, statuses, errors, and validation | Flask, SQLite, network, or runtime dependencies |
| `backend/templates/` | Validated, versioned generated payloads | Flask request state or persistence |
| `backend/mappers/` | Reusable persistence-row and upstream-shape presentation | Flask, SQLite connection APIs, SQL, transactions, repositories, services, clients, runtime, or composition |

Dependencies point inward: API and runtime wiring call services; services coordinate clients and repositories; repositories may invoke mappers and templates; mappers use only mapper/domain modules; clients, repositories, mappers, and templates use domain types. `backend/app_factory.py` is the composition root that connects concrete implementations.

Temporary compatibility exports are allowed only when an existing caller imports a moved symbol. The implementation must live in its owning module, and new code must import that module directly.

## Target trees

The directories below are placement destinations. A directory or module does not
need to exist until a responsibility is extracted into it.

```text
backend/
  api/             # HTTP parsing and response mapping by bounded context
  services/        # use cases and cross-adapter coordination
  clients/         # Medplum, dcm4chee, OIE, Docker, and OpenEMR transports
  runtime/         # listeners, watchers, threads, sockets, and lifecycle state
  repositories/    # SQLite persistence grouped by bounded context
  domain/          # framework-independent rules, models, statuses, and errors
  templates/       # HL7, FHIR, GDT, DICOM JSON, and OIE payload construction
  mappers/         # persistence-neutral row and boundary presentation
  app_factory.py   # composition root only
  config.py        # environment and application configuration only

frontend/static/
  js/
    api/           # HTTP calls only
    views/         # patient, order, FHIR, GDT, OIE, dcm4chee, and dashboard views
    components/    # reusable presentation used by at least two feature contracts
    state/         # selection and workspace state without DOM or transport logic
  css/
    base.css       # tokens, reset, and typography
    layout.css     # application shell, sidebar, and shared responsive layout
    components.css # reusable component styles
    views/         # bounded-context workspace styles scoped by view root

tests/
  api/
  services/
  clients/
  runtime/
  repositories/
  domain/
  templates/
  mappers/
  integration/
  e2e/
```

## Bounded-context responsibility map

This inventory is exhaustive by responsibility family. Every function or class
retained in a large compatibility module belongs to one of the rows below; a
new family requires this table and the architecture contract to change before
implementation begins.

| Context | Current responsibility and source | Category | Named destination | Matching tests | Compatibility |
|---|---|---|---|---|---|
| Patient | Validation, normalization, MRN/visit allocation, persistence, row presentation, and ADT/FHIR/GDT/DICOM construction | domain / persistence / presentation / payload | `backend/domain/patient.py`, `backend/repositories/patients.py`, `backend/mappers/patient.py`, `backend/templates/patient.py` | matching mirrored test modules | consumers use the named repository or workflow port |
| Patient | Patient creation, FHIR sync, and dcm4chee refresh coordination | workflow / HTTP | `backend/services/patient_workflow.py`, `backend/api/patients.py` | `tests/services/test_patient_workflow.py`, `tests/api/test_patients.py` | existing service/API paths are owners |
| Order | Validation, identifier allocation, persistence, row presentation, ORM, FHIR ServiceRequest, and DICOM MWL construction | domain / persistence / presentation / payload | `backend/domain/order.py`, `backend/domain/fhir_order.py`, `backend/repositories/orders.py`, `backend/mappers/order.py`, `backend/templates/order.py`, `backend/templates/fhir.py`, `backend/templates/dicom.py` | matching mirrored test modules | consumers use the named repository or workflow port |
| Order | Order creation, send, retry, verification, and simulated-return coordination | workflow / HTTP | `backend/services/order_workflow.py`, `backend/api/orders.py` | `tests/services/test_order_workflow.py`, `tests/api/test_orders.py` | existing service/API paths are owners |
| FHIR | Resource mapping, identifier rules, workflow ledger, sync-attempt persistence, and presentation | domain / persistence / presentation | `backend/domain/fhir_ledger.py`, `backend/repositories/fhir_ledger.py`, `backend/mappers/fhir.py` | matching mirrored test modules | consumers use the named ledger or workflow port |
| FHIR | Medplum authentication and HTTP operations | transport | `backend/clients/medplum.py` | `tests/clients/test_medplum.py` | current client is the owner |
| FHIR | Resource sync, inventory, retry, and DiagnosticReport coordination | workflow / HTTP | `backend/services/fhir_workflow.py`, `backend/api/fhir.py` | `tests/services/test_fhir_workflow.py`, `tests/api/test_fhir.py` | existing service/API paths are owners |
| GDT | Encoding, parsing, validation, inbound interpretation, outbound construction, and presentation | domain / payload / presentation | `backend/domain/gdt_protocol.py`, `backend/templates/gdt.py`, `backend/mappers/gdt.py` | matching mirrored test modules | `backend/gdt_adapter.py` may re-export retained symbols |
| GDT | Five-table workflow ledger and bridge filesystem readiness | persistence / infrastructure health | `backend/repositories/gdt_workflow.py`, `backend/repositories/gdt_bridge_health.py` | matching repository tests | filesystem readiness stays in `gdt_bridge_health.py`; consumers use focused owners |
| GDT | Order export, inbox import, demo result, and workbench coordination | workflow / HTTP | `backend/services/gdt_workflow.py`, `backend/api/gdt.py` | `tests/services/test_gdt_workflow.py`, `tests/api/test_gdt.py` | existing service/API paths are owners |
| GDT | Inbound folder watching and lifecycle state | runtime | `backend/runtime/gdt_bridge_watcher.py` | `tests/runtime/test_gdt_bridge_watcher.py` | current runtime module is the owner |
| OIE | Settings/result validation, persistence, and presentation | domain / persistence / presentation | `backend/domain/oie.py`, `backend/repositories/oie_settings.py`, `backend/repositories/oie.py`, `backend/mappers/oie.py` | matching mirrored test modules | settings and results use their named repositories |
| OIE | MLLP send operations and future management API calls | transport | `backend/clients/oie.py`, `backend/clients/oie_management.py` | matching `tests/clients/` modules | current/future clients are owners |
| OIE | ACK/ORU parsing and generated channel payloads | domain / payload | `backend/domain/oie.py`, `backend/templates/oie_channels.py` | `tests/domain/test_oie.py`, `tests/templates/test_oie_channels.py` | payload logic remains with domain/template owners |
| OIE | Workbench, settings, listener, channel lifecycle, and diagnostics coordination | workflow / HTTP | OIE modules under `backend/services/`, `backend/api/oie.py` | matching `tests/services/` and `tests/api/` modules | existing API may expand only by calling services |
| OIE | Result listener, lifecycle state, and runtime diagnostics | runtime | `backend/runtime/oie_result_listener.py` and named diagnostics runtime modules | matching `tests/runtime/` modules | current listener module is the owner |
| dcm4chee | DICOM identifiers, UID rules, status policy, payload construction, and row presentation | domain / payload / presentation | `backend/domain/dicom.py`, `backend/templates/dicom.py`, `backend/mappers/dicom.py` | matching mirrored test modules | rules and presentation remain with focused owners |
| dcm4chee Patient sync | Patient-sync mappings, attempts, ACK/error transitions, and enrichment reads | persistence | `backend/repositories/dcm4chee_patient_sync.py` | `tests/repositories/test_dcm4chee_patient_sync.py` | consumers use the named repository |
| dcm4chee MWL | MWL mappings, attempts, verification state, reconciliation lookup, and startup backfill | persistence | `backend/repositories/dcm4chee_mwl.py` | `tests/repositories/test_dcm4chee_mwl.py` | consumers use the named repository/coordinator |
| dcm4chee Results | Result records, reconciliation persistence, refresh generations, diagnostics, and snapshot publication | persistence | `backend/repositories/dcm4chee_results.py` | `tests/repositories/test_dcm4chee_results.py` | consumers use the named repository/coordinator |
| dcm4chee | E2E fixtures, evidence aggregation, and simulated AP returns | workflow | `backend/services/dcm4chee_coordination.py` | focused repository tests and `tests/integration/test_app.py` | composed from explicit patient, order, sync, MWL, and result capabilities |
| dcm4chee | DICOMweb, QIDO, MWL, patient, and verification requests | transport | `backend/clients/dcm4chee.py` | `tests/clients/test_dcm4chee.py` | current client is the owner |
| dcm4chee | Patient/order sync, verification, retry, refresh, evidence, and reconciliation coordination | workflow / HTTP | named patient/order/dcm4chee services and `backend/api/dcm4chee.py` | matching service/API tests | cross-context work stays in an explicit service |
| Lab control-plane | Lab server validation, registry, health, operation history, and presentation | domain / persistence / presentation | `backend/domain/lab.py`, `backend/repositories/lab.py`, `backend/mappers/lab.py` | matching mirrored test modules | consumers use the narrow lab application repository |
| Lab control-plane | Docker socket/Compose operations in `backend/lab_operations.py` | transport | `backend/clients/docker.py` | `tests/clients/test_docker.py` | `lab_operations.py` may re-export adapters during migration |
| Lab control-plane | Dashboard status/summary projections in `backend/dashboard_services.py` | domain | `backend/domain/dashboard.py` | `tests/domain/test_dashboard.py` | no new projections in the catch-all module |
| Lab control-plane | Docker socket/CLI resource collection in `backend/dashboard_services.py` | transport | `backend/clients/docker.py` | `tests/clients/test_docker.py` | no new transport in the catch-all module |
| Lab control-plane | Health checks, operations, smoke checks, dashboard actions, and resource snapshot coordination | workflow / HTTP | `backend/services/lab_workflow.py`, `backend/services/dashboard_workflow.py`, lab/dashboard API modules | matching service/API tests | existing services/APIs are owners |
| Application | Dependency construction, Blueprint registration, and configured runtime startup in `backend/app_factory.py` | composition | `backend/app_factory.py` | `tests/integration/test_app_factory.py` | this is the composition owner, not a general facade |
| Frontend | Shared and feature HTTP operations | transport | `frontend/static/js/api/` by bounded context | focused API/browser tests | compatibility `app.js` imports `js/app.js` only |
| Frontend | Patient, order, FHIR, GDT, OIE, dcm4chee, and dashboard rendering | view | `frontend/static/js/views/` by bounded context | focused view/browser tests | views initialize idempotently through the application coordinator |
| Frontend | Status and genuinely reusable presentation | component | `frontend/static/js/components/` | component/browser tests | reuse requires at least two feature consumers without feature branching |
| Frontend | Shared selections and feature-owned inventory/request state | state | `frontend/static/js/state/` | focused state/browser tests | cross-view coordination uses explicit selection/coordinator APIs |
| Frontend | Base, layout, component, and scoped workspace rules | presentation | `frontend/static/css/*.css`, `frontend/static/css/views/` | characterization/browser tests | `styles.css` is an ordered import-only loader |
| Tests | Mixed API, workflow, repository, runtime, and transport assertions in `tests/integration/test_app.py` | test | matching responsibility package under `tests/`; retain only cross-boundary cases in `integration/` | n/a | assertions move before legacy cases are removed |

## ZAC-62 workflow service ownership

ZAC-62 decomposes the workflow layer into consumer-sized application services.
The compatibility workflow classes remain composition conveniences only; APIs
and runtime callbacks receive the focused ports listed below.

| Context | Focused application owners | Composition destination |
|---|---|---|
| Lab control-plane | `LabRegistryService`, `LabHealthService`, `LabOperationService`, `LabSmokeService`, `DashboardSnapshotService`, `DashboardActionService` | `backend/lab_composition.py`, then Lab and dashboard Blueprints |
| FHIR | `FhirSyncService`, `FhirInventoryService`, `FhirPreviewService`, `FhirDiagnosticReportService`, `FhirRecordService` | `backend/app_factory.py`, then the FHIR Blueprint and Patient/Order coordinators |
| Order / dcm4chee | `DcmMwlSyncService`, `DcmMwlVerificationService`, `DcmEvidenceService`, `Dcm4cheeMwlAttemptCoordinator`, `Dcm4cheeWorkflowCoordinator` | `backend/app_factory.py`, then Order/dcm4chee APIs and cross-context callbacks |
| Patient | `PatientRecordService`, `PatientFhirSyncService`, `DcmResultRefreshService`, `DcmFixtureService` | `backend/app_factory.py`, then the Patient Blueprint |
| GDT | `GdtOrderService`, `GdtBridgeService`, `GdtResultService` | `backend/app_factory.py`, then the GDT Blueprint and watcher callback |

The composition root retains the ZAC-46 OIE management client, settings
service, workflow service, result-listener extension keys, Blueprint inputs,
and startup order. ZAC-47 continues to own OIE channel domain/template modules.
ZAC-63 owns frontend modularization, ZAC-64 broad test-file decomposition, and
ZAC-65 explicit application composition and removal of the former broad facade.

The workflow baseline audit found no ZAC-62-owned entries in
`tests/architecture_legacy_baseline.py` to remove: affected API callers already
import their service ports directly. Retained compatibility callers are
`backend/app_factory.py`, explicit protocol composition, runtime callbacks,
and tests that patch the published `backend.app_factory` seams. These callers
remain frozen under the existing architecture contract; no replacement
baseline or allowlist entry was added.

## Placement decision process

Use this sequence for every new or moved symbol:

1. Choose exactly one bounded context: patient, order, FHIR, GDT, OIE,
   dcm4chee, or lab control-plane. If multiple contexts participate, name a
   coordinating service and keep each adapter in its original context.
2. Classify the responsibility: HTTP, workflow, transport, runtime,
   persistence, domain, payload/template, mapper/presentation, composition, view, component, state,
   or presentation.
3. Select the named destination from the responsibility map. Do not choose a
   compatibility source merely because related legacy code is still there.
4. Check dependency direction: API/runtime wiring -> services -> ports ->
   repositories -> mappers -> domain and repositories -> templates -> domain. Lower layers never import API,
   Flask request state, runtime lifecycle, or an unrelated concrete repository.
5. Put focused tests in the mirrored test package. Use `tests/integration/`
   only when the assertion crosses real responsibility boundaries, and
   `tests/e2e/` for repeatable external workflow verification.
6. If an existing import must survive, add only a documented re-export or
   delegation facade. New callers import the owning module directly.

## Compatibility facades

Compatibility is an explicit migration exception, not a destination. The
reviewed legacy baseline in `tests/test_architecture_contract.py` may only stay
the same or shrink during normal feature work.

| Facade / legacy source | Retained callers | Owning destination | Allowed behavior |
|---|---|---|---|
| `app.py` | process launchers | `backend/app_factory.py` | import the supported app/factory/main symbols and invoke `main`; no whole-module alias |
| `backend/gdt_adapter.py` | services and legacy adapter tests | `backend/domain/gdt.py` and `backend/templates/gdt.py` | retain or re-export reviewed symbols only |
| `backend/dashboard_services.py` | lab workflow, composition, and legacy tests | `backend/domain/dashboard.py`, `backend/clients/docker.py`, `backend/services/dashboard_workflow.py` | retain reviewed functions only |
| `backend/lab_operations.py` | composition, lab workflow, and legacy tests | `backend/clients/docker.py` plus lab domain errors | retain or re-export reviewed adapters only |
| `frontend/static/app.js` | `frontend/templates/index.html` | categorized modules under `frontend/static/js/` | retain reviewed globals/functions or load owners; no new top-level responsibility |
| `frontend/static/styles.css` | `frontend/templates/index.html` | categorized modules under `frontend/static/css/` | retain reviewed selectors/import owners; no new selector family |

Changing an existing facade implementation is not automatically safe. SQL,
payload, workflow, or transport changes must move to the named destination;
updating a legacy baseline requires an explicit architecture decision in the
same review.

## OIE placement

Future OIE work has preassigned destinations:

- ZAC-46: `backend/clients/oie_management.py` and domain errors.
- ZAC-47: `backend/templates/oie_channels.py` and domain models.
- ZAC-48: `backend/services/oie_channel_service.py`, OIE repositories, and `backend/api/oie.py`.
- ZAC-49: `backend/runtime/oie_result_listener.py` plus composition and API wiring.
- ZAC-51: diagnostics services, audit repositories, and runtime diagnostics.
- ZAC-52: repeatable helpers under `tests/e2e/` and verification documentation.

New OIE persistence must use a named OIE repository and be exposed through a focused workflow port.

The HLAB ORU result listener reads host, port, MLLP framing, and auto-start intent
only from the persisted OIE Settings profile. Application composition performs
one best-effort auto-start attempt per process. A bind failure degrades listener
status but does not fail web application creation. Start and Retry reload the
persisted intent; Stop is process-local and does not disable the next startup.
Saving changed listener Settings never rebinds a running socket and must surface
an unapplied-settings reminder until the persisted configuration is running.

Listener ownership is intentionally single-process. Deploy exactly one lab-app
process for an endpoint; multiple WSGI workers or replicas are not coordinated,
and additional processes report a degraded port-conflict state.

## Frontend placement

ZAC-50 must introduce categorized modules instead of extending only `frontend/static/app.js` and `styles.css`:

```text
frontend/static/js/
  api/
  views/
  components/
  state/
frontend/static/css/
  base/
  components/
  views/
```

This placement rule does not require a frontend framework or build system. Existing global assets may remain as compatibility entrypoints while feature implementation moves to owned modules.

## Test placement

Tests mirror production responsibilities under `tests/api`, `services`, `clients`, `runtime`, `repositories`, `domain`, `templates`, `mappers`, `integration`, and `e2e`. Move existing assertions before removing old test locations. Architecture contract tests protect the thin entrypoint and dependency direction.

## Bounded autonomous implementation

Routine failures directly caused by an approved refactor (focused tests,
imports, typing, fixtures, composition, and internal naming) may be corrected
autonomously. Focused and full quality gates remain mandatory.

Stop before schema, migration, seed, or stored-data mutation; access to real
`instance/*.db` files or live services; public API, validation error, payload,
persistence, runtime, or compatibility changes; architecture-baseline,
allowlist, or fingerprint expansion; dependency installation; destructive
operations; unsafe dirty-worktree overlap; or unrelated decomposition. Never
cross a stop condition by weakening tests or compatibility expectations.

## Existing ECG integration context

The ECG HL7 AP Integration Simulator demonstrates an application platform that receives patient context from a hospital, associates that context with ECG device data, and returns an ECG result. It is designed for virtual-data demonstrations and interface research.

### Main data flow

```text
Hospital HIS / EMR
        |
        | ADT^A04 / ADT^A08 / ORM^O01
        | MLLP-TCP
        v
Mirth Connect Hospital Simulator
        |
        | TCP Sender → Windows AP :6671
        v
ECG AP Integration Simulator
        |
        +-- Receive HL7 patient context
        +-- Return same-socket ACK
        +-- Store demo queue record
        +-- Upload ECG JSON
        +-- Match ECG patient.mrn == HL7 PID-3
        |
        | Generate ORU^W01 waveform OBX or ORU^R01 aECG XML
        | TCP Sender → Ubuntu Mirth :6661
        v
Mirth Connect Hospital Listener
        |
        | ACK: AA / AE / AR
        v
ECG AP Integration Simulator
```

### Port map

| Port | Listener | Direction | Purpose |
| --- | --- | --- | --- |
| `6671` | ECG AP simulator | Mirth → AP | Hospital Push of `ADT` or `ORM` context |
| `6661` | Mirth Connect | AP → Mirth | AP return of ECG `ORU^W01` or `ORU^R01` results |
| `5000` | Local Flask UI | Browser → AP UI | Local browser interface |

### Inbound hospital push

The first demo supports:

| Message | Purpose |
| --- | --- |
| `ADT^A04` | Patient registration |
| `ADT^A08` | Patient demographic or visit update |
| `ORM^O01` | ECG order context |

The AP listener records raw HL7, message type, `MSH-10` message control ID, `PID-3` MRN, parsed patient context, ACK outcome, and receive timestamp. The listener responds on the same TCP connection with an MLLP-framed ACK.

### ECG JSON integration

The example ECG JSON contains patient demographics and MRN, ECG measurements, an interpretation statement, and multi-lead waveform samples. First-version matching is deliberately simple:

```text
ECG JSON patient.mrn == HL7 PID-3
```

This is sufficient for a demo. Production integrations should consider assigning authority, encounter, order ID, accession number, and correction rules.

### Demo queue states

| State | Meaning |
| --- | --- |
| `WAITING_FOR_HL7` | ECG JSON exists but hospital context has not arrived |
| `WAITING_FOR_ECG` | Hospital context exists but ECG JSON has not arrived |
| `READY_TO_SEND` | Matching hospital context and ECG JSON are available |
| `ACCEPTED` | Hospital listener returned `MSA|AA` |
| `REJECTED` | Hospital listener returned `MSA|AE` or `MSA|AR` |
| `ERROR` | Transport failure or incomplete ACK |

SQLite stores the queue so multiple asynchronous records remain inspectable after browser reloads. It is not a production message broker.

### Outbound ECG result

Outbound HL7 v2 result messages are generated with `MSH-12 = 2.5.1` and one of two selectable result profiles.

`ORU^W01` is the waveform profile for ECG JSON. It includes `MSH`, `PID`, `OBR`, `TIM`, `CHN`, and `WAV` waveform `OBX` segments, with MA timepoint-major or NA channel-major waveform array layout.

`ORU^R01` is the aECG profile for ECG JSON. It includes `MSH`, `PID`, `OBR`, and an inline `OBX|ED` payload containing a minimal Annotated ECG XML document with CPT `93000`, effective time, subject/trial identifiers, and MDC lead codes for supported leads.

PDF report returns use an inline `OBX|ED` payload by default. If a public URL is provided for the artifact, the result uses `OBX|RP` instead of embedding the same payload inline. If a return flow already sends artifact URLs, the same artifact should not also be sent again inline in that message path.

`PV1` and `ORC` are intentionally excluded from the simulator's minimum result profile until a specific hospital channel profile requires them. For hospitals with PACS support, production waveform delivery should prefer DICOM ECG Waveform Storage and an agreed report workflow.

### Pull extension

The simulator exposes:

```text
GET /api/mock-fhir/Patient?identifier=<MRN>
```

This read-only mock route demonstrates how a future AP could request missing patient context. It is not a complete FHIR implementation. A production Pull workflow must follow the hospital's supported FHIR, HL7 query, or DICOM Modality Worklist contract.

### Production boundaries

The simulator intentionally does not provide production queue guarantees, clinical validation, universal hospital mappings, DICOM/PACS implementation, complete FHIR support, TLS or identity management, audit logging, or protected health information controls.

Known active gap: patient-name reconciliation is not complete yet. The returned patient name may not always match the hospital-sent demographics until the mapping logic is corrected.
