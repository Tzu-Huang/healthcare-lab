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

Dependencies point inward: API and runtime wiring call services; services coordinate clients and repositories; clients, repositories, and templates use domain types. `backend/app_factory.py` is the composition root that connects concrete implementations.

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
  app_factory.py   # composition root only
  config.py        # environment and application configuration only

frontend/static/
  js/
    api/           # HTTP calls only
    views/         # patient, order, FHIR, GDT, OIE, dcm4chee, and dashboard views
    components/    # reusable tables, buttons, summaries, and protocol previews
    state/         # selection and workspace state without DOM or transport logic
  css/
    base/          # tokens, reset, typography, and layout primitives
    components/    # reusable component styles
    views/         # bounded-context workspace styles

tests/
  api/
  services/
  clients/
  runtime/
  repositories/
  domain/
  templates/
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
| Patient | Patient validation, normalization, MRN/visit allocation, and row mapping in `DemoStore` | domain / persistence | `backend/domain/patient.py`, `backend/repositories/patients.py` | `tests/domain/test_patient.py`, `tests/repositories/test_patients.py` | `DemoStore` may delegate existing methods only |
| Patient | ADT, FHIR Patient, GDT patient, and DICOM patient payload builders in `DemoStore` | payload | `backend/templates/hl7_patient.py`, `fhir_patient.py`, `gdt_patient.py`, `dicom_patient.py` | matching `tests/templates/` modules | no new builders in `DemoStore` |
| Patient | Patient creation, FHIR sync, and dcm4chee refresh coordination | workflow / HTTP | `backend/services/patient_workflow.py`, `backend/api/patients.py` | `tests/services/test_patient_workflow.py`, `tests/api/test_patients.py` | existing service/API paths are owners |
| Order | Order validation, identifier allocation, and row mapping in `DemoStore` | domain / persistence | `backend/domain/order.py`, `backend/repositories/orders.py` | `tests/domain/test_order.py`, `tests/repositories/test_orders.py` | `DemoStore` may delegate existing methods only |
| Order | ORM, FHIR ServiceRequest, and DICOM MWL payload builders in `DemoStore` | payload | `backend/templates/hl7_order.py`, `fhir_order.py`, `dicom_mwl.py` | matching `tests/templates/` modules | no new builders in `DemoStore` |
| Order | Order creation, send, retry, verification, and simulated-return coordination | workflow / HTTP | `backend/services/order_workflow.py`, `backend/api/orders.py` | `tests/services/test_order_workflow.py`, `tests/api/test_orders.py` | existing service/API paths are owners |
| FHIR | Resource mapping, identifier rules, workflow ledger, and sync-attempt persistence in `DemoStore` | domain / persistence | `backend/domain/fhir.py`, `backend/repositories/fhir.py` | `tests/domain/test_fhir.py`, `tests/repositories/test_fhir.py` | `DemoStore` may delegate retained operations |
| FHIR | Medplum authentication and HTTP operations | transport | `backend/clients/medplum.py` | `tests/clients/test_medplum.py` | current client is the owner |
| FHIR | Resource sync, inventory, retry, and DiagnosticReport coordination | workflow / HTTP | `backend/services/fhir_workflow.py`, `backend/api/fhir.py` | `tests/services/test_fhir_workflow.py`, `tests/api/test_fhir.py` | existing service/API paths are owners |
| GDT | GDT encoding, parsing, validation, measurement, and attachment interpretation in `backend/gdt_adapter.py` and `DemoStore` | domain / payload | `backend/domain/gdt.py`, `backend/templates/gdt.py` | `tests/domain/test_gdt.py`, `tests/templates/test_gdt.py` | `backend/gdt_adapter.py` may re-export retained symbols |
| GDT | Orders, messages, events, artifacts, bridge health, and result persistence in `DemoStore` | persistence | `backend/repositories/gdt.py`, `backend/repositories/gdt_bridge_health.py` | `tests/repositories/test_gdt.py` | `DemoStore` may delegate retained operations |
| GDT | Order export, inbox import, demo result, and workbench coordination | workflow / HTTP | `backend/services/gdt_workflow.py`, `backend/api/gdt.py` | `tests/services/test_gdt_workflow.py`, `tests/api/test_gdt.py` | existing service/API paths are owners |
| GDT | Inbound folder watching and lifecycle state | runtime | `backend/runtime/gdt_bridge_watcher.py` | `tests/runtime/test_gdt_bridge_watcher.py` | current runtime module is the owner |
| OIE | Settings, result, unmatched-result, ADT inventory, and order inventory persistence in `DemoStore` | persistence | `backend/repositories/oie_settings.py`, `backend/repositories/oie.py` | `tests/repositories/test_oie_settings.py`, `test_oie.py` | settings delegation may remain in `DemoStore` |
| OIE | MLLP send operations and future management API calls | transport | `backend/clients/oie.py`, `backend/clients/oie_management.py` | matching `tests/clients/` modules | current/future clients are owners |
| OIE | ACK/ORU parsing and generated channel payloads | domain / payload | `backend/domain/oie.py`, `backend/templates/oie_channels.py` | `tests/domain/test_oie.py`, `tests/templates/test_oie_channels.py` | no new payload logic in `DemoStore` |
| OIE | Workbench, settings, listener, channel lifecycle, and diagnostics coordination | workflow / HTTP | OIE modules under `backend/services/`, `backend/api/oie.py` | matching `tests/services/` and `tests/api/` modules | existing API may expand only by calling services |
| OIE | Result listener, lifecycle state, and runtime diagnostics | runtime | `backend/runtime/oie_result_listener.py` and named diagnostics runtime modules | matching `tests/runtime/` modules | current listener module is the owner |
| dcm4chee | DICOM identifiers, UID rules, MWL/result mapping, status projection, and error classification in `DemoStore` | domain | `backend/domain/dicom.py` | `tests/domain/test_dicom.py` | no new rules in `DemoStore` |
| dcm4chee | Patient sync, MWL attempts/mappings, result ledger, refresh diagnostics, and reconciliation persistence in `DemoStore` | persistence | `backend/repositories/dcm4chee.py` | `tests/repositories/test_dcm4chee.py` | `DemoStore` may delegate retained operations |
| dcm4chee | DICOMweb, QIDO, MWL, patient, and verification requests | transport | `backend/clients/dcm4chee.py` | `tests/clients/test_dcm4chee.py` | current client is the owner |
| dcm4chee | Patient/order sync, verification, retry, refresh, evidence, and reconciliation coordination | workflow / HTTP | named patient/order/dcm4chee services and `backend/api/dcm4chee.py` | matching service/API tests | cross-context work stays in an explicit service |
| Lab control-plane | Lab server registry, health, and operation history in `DemoStore` | persistence | `backend/repositories/lab.py` | `tests/repositories/test_lab.py` | `DemoStore` may delegate retained operations |
| Lab control-plane | Docker socket/Compose operations in `backend/lab_operations.py` | transport | `backend/clients/docker.py` | `tests/clients/test_docker.py` | `lab_operations.py` may re-export adapters during migration |
| Lab control-plane | Dashboard status/summary projections in `backend/dashboard_services.py` | domain | `backend/domain/dashboard.py` | `tests/domain/test_dashboard.py` | no new projections in the catch-all module |
| Lab control-plane | Docker socket/CLI resource collection in `backend/dashboard_services.py` | transport | `backend/clients/docker.py` | `tests/clients/test_docker.py` | no new transport in the catch-all module |
| Lab control-plane | Health checks, operations, smoke checks, dashboard actions, and resource snapshot coordination | workflow / HTTP | `backend/services/lab_workflow.py`, `backend/services/dashboard_workflow.py`, lab/dashboard API modules | matching service/API tests | existing services/APIs are owners |
| Application | Dependency construction, Blueprint registration, and configured runtime startup in `backend/app_factory.py` | composition | `backend/app_factory.py` | `tests/integration/test_app_factory.py` | this is the composition owner, not a general facade |
| Frontend | HTTP helpers currently in `frontend/static/app.js` | transport | `frontend/static/js/api/` by bounded context | browser/E2E tests | `app.js` remains a loader/legacy entrypoint only |
| Frontend | Patient, order, FHIR, GDT, OIE, dcm4chee, and dashboard rendering in `app.js` | view | `frontend/static/js/views/` by bounded context | browser/E2E tests | retained functions form a frozen baseline |
| Frontend | Tables, buttons, summaries, protocol previews, and shared DOM helpers in `app.js` | component | `frontend/static/js/components/` | component/browser tests | retained functions form a frozen baseline |
| Frontend | Selected records, filters, modes, and workspace state in `app.js` | state | `frontend/static/js/state/` | state/browser tests | retained globals form a frozen baseline |
| Frontend | Base, component, and workspace rules in `frontend/static/styles.css` | presentation | `frontend/static/css/base/`, `components/`, `views/` | browser/E2E tests | retained selectors form a frozen baseline |
| Tests | Mixed API, workflow, repository, runtime, and transport assertions in `tests/integration/test_app.py` | test | matching responsibility package under `tests/`; retain only cross-boundary cases in `integration/` | n/a | assertions move before legacy cases are removed |

## Placement decision process

Use this sequence for every new or moved symbol:

1. Choose exactly one bounded context: patient, order, FHIR, GDT, OIE,
   dcm4chee, or lab control-plane. If multiple contexts participate, name a
   coordinating service and keep each adapter in its original context.
2. Classify the responsibility: HTTP, workflow, transport, runtime,
   persistence, domain, payload/template, composition, view, component, state,
   or presentation.
3. Select the named destination from the responsibility map. Do not choose a
   compatibility source merely because related legacy code is still there.
4. Check dependency direction: API/runtime wiring -> services -> ports ->
   clients/repositories/templates -> domain. Lower layers never import API,
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
| `app.py` | process launchers and tests patching `app.<symbol>` | `backend/app_factory.py` and registered modules | alias the application module and invoke `main`; no definitions |
| `backend/lab_store.py:DemoStore` | composition wiring, repository ports, runtime ports, and legacy tests | bounded-context repositories, domain modules, and templates in the map | retain reviewed methods or delegate; no new classified implementation |
| `backend/gdt_adapter.py` | `DemoStore`, services, and legacy adapter tests | `backend/domain/gdt.py` and `backend/templates/gdt.py` | retain or re-export reviewed symbols only |
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

New OIE persistence must use an OIE repository. Do not add new OIE persistence methods directly to `DemoStore`; retained methods may delegate during compatibility migration.

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

Tests mirror production responsibilities under `tests/api`, `services`, `clients`, `runtime`, `repositories`, `templates`, `integration`, and `e2e`. Move existing assertions before removing old test locations. Architecture contract tests protect the thin entrypoint and dependency direction.

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
