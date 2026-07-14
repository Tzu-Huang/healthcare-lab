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
