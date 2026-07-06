# Architecture and Integration Boundaries

## Purpose

The ECG HL7 AP Integration Simulator demonstrates an application platform that
receives patient context from a hospital, associates that context with ECG
device data, and returns an ECG result.

It is designed for virtual-data demonstrations and interface research.

## Main Data Flow

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

## Port Map

| Port | Listener | Direction | Purpose |
| --- | --- | --- | --- |
| `6671` | ECG AP simulator | Mirth → AP | Hospital Push of `ADT` or `ORM` context |
| `6661` | Mirth Connect | AP → Mirth | AP return of ECG `ORU^W01` or `ORU^R01` results |
| `5000` | Local Flask UI | Browser → AP UI | Local browser interface |

## Inbound Hospital Push

The first demo supports:

| Message | Purpose |
| --- | --- |
| `ADT^A04` | Patient registration |
| `ADT^A08` | Patient demographic or visit update |
| `ORM^O01` | ECG order context |

The AP listener records:

- Raw HL7
- Message type
- `MSH-10` message control ID
- `PID-3` MRN
- Parsed patient context
- ACK outcome
- Receive timestamp

The listener responds on the same TCP connection with an MLLP-framed ACK.

## ECG JSON Integration

The example ECG JSON contains:

- Patient demographics and MRN
- ECG measurements
- Interpretation statement
- Multi-lead waveform samples

First-version matching is deliberately simple:

```text
ECG JSON patient.mrn == HL7 PID-3
```

This is sufficient for a demo. Production integrations should consider
assigning authority, encounter, order ID, accession number, and correction
rules.

## Demo Queue States

| State | Meaning |
| --- | --- |
| `WAITING_FOR_HL7` | ECG JSON exists but hospital context has not arrived |
| `WAITING_FOR_ECG` | Hospital context exists but ECG JSON has not arrived |
| `READY_TO_SEND` | Matching hospital context and ECG JSON are available |
| `ACCEPTED` | Hospital listener returned `MSA|AA` |
| `REJECTED` | Hospital listener returned `MSA|AE` or `MSA|AR` |
| `ERROR` | Transport failure or incomplete ACK |

SQLite stores the queue so multiple asynchronous records remain inspectable
after browser reloads. It is not a production message broker.

## Outbound ECG Result

Outbound HL7 v2 result messages are generated with `MSH-12 = 2.5.1` and one of
two selectable result profiles.

`ORU^W01` is the waveform profile for ECG JSON. It includes:

- `MSH`
- `PID`
- `OBR`
- `TIM`, `CHN`, and `WAV` waveform `OBX` segments
- MA timepoint-major or NA channel-major waveform array layout

`ORU^R01` is the aECG profile for ECG JSON. It includes:

- `MSH`
- `PID`
- `OBR`
- An inline `OBX|ED` payload containing a minimal Annotated ECG XML document
  with CPT `93000`, effective time, subject/trial identifiers, and MDC lead
  codes for supported leads

PDF report returns use an inline `OBX|ED` payload by default. If a public URL is
provided for the artifact, the result uses `OBX|RP` instead of embedding the
same payload inline.

If a return flow already sends artifact URLs, the same artifact should not also
be sent again inline in that message path.

`PV1` and `ORC` are intentionally excluded from the simulator's minimum result
profile until a specific hospital channel profile requires them.

For hospitals with PACS support, production waveform delivery should prefer
DICOM ECG Waveform Storage and an agreed report workflow.

## Pull Extension

The simulator exposes:

```text
GET /api/mock-fhir/Patient?identifier=<MRN>
```

This read-only mock route demonstrates how a future AP could request missing
patient context. It is not a complete FHIR implementation. A production Pull
workflow must follow the hospital's supported FHIR, HL7 query, or DICOM
Modality Worklist contract.

## Production Boundaries

The simulator intentionally does not provide:

- Production queue guarantees
- Clinical validation
- Universal hospital mappings
- DICOM/PACS implementation
- Complete FHIR support
- TLS or identity management
- Audit logging
- Protected health information controls

Known active gap:

- Patient-name reconciliation is not complete yet. The returned patient name may
  not always match the hospital-sent demographics until the mapping logic is
  corrected.
