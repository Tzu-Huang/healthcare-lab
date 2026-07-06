## Context

ZAC-18 extends the Patient MVP rather than replacing it. The current app already has:

- A Patient page for HL7 v2.3.1 `ADT^A04` local patient creation and payload preview.
- SQLite-backed local patient inventory through `LabStore`.
- An OIE page that lists local ADT records and previews their raw payloads without transmitting them.
- Existing HL7/OIE documentation that treats OIE channel configuration as an external integration responsibility.

The Order MVP should reuse those local concepts so the workflow remains explainable:

1. Create or choose a local patient.
2. Create a local 12-lead ECG order for that patient.
3. Inspect the generated `ORM^O01`.
4. Send exactly one selected order to OIE.
5. Record and display the ACK result.

## Data Model

Add a local order record that references the existing local patient record. The order should store enough denormalized patient/order data to keep the generated payload stable after creation.

Recommended fields:

| Field | Purpose |
| --- | --- |
| `id` | Local SQLite primary key |
| `local_order_number` | Human-readable placer order number used in ORC/OBR |
| `patient_record_id` | Link to local Patient inventory |
| `visit_id` | Local outpatient visit/account id for PV1 |
| `order_status` | Local status such as `Ready to send`, `Accepted`, `Error`, `Rejected`, `Transport error` |
| `priority` | Order priority used in ORC/OBR |
| `requested_at` | Requested service time |
| `ordering_provider` | Demo provider default `1001^WANG^AMY` |
| `clinical_indication` | Free-text reason for the ECG order |
| `order_code` | Local code default `ECG12` |
| `order_code_text` | `12 Lead ECG` |
| `alternate_code` | CPT-like alternate `93000` |
| `orm_payload` | Generated raw HL7 v2.3.1 message |
| `ack_code` | Parsed `MSA-1` when available |
| `ack_control_id` | Parsed `MSA-2` when available |
| `ack_text` | Parsed ACK error/message text when available |
| `ack_payload` | Raw ACK payload for inspection |
| `last_sent_at` | Last send timestamp |

If an existing patient does not carry a visit/account id, order creation should generate a local outpatient `visit_id`/account value and persist it with the order. This keeps the MVP self-contained without expanding Patient registration first.

## HL7 Message

Generate HL7 v2.3.1 `ORM^O01` with:

- `MSH`: sending app/facility `HEALTHCARE_LAB|DASHBOARD`, receiving app/facility `OIE|HL7LAB`, message type `ORM^O01`, processing id `P`, version `2.3.1`.
- `PID`: copied from the selected local patient snapshot.
- `PV1`: outpatient class by default, with local visit/account id.
- `ORC`: new order control, placer order number, provider, and order timing.
- `OBR`: 12-lead ECG service identifier using local primary code and alternate code text.

Recommended ECG coding baseline:

```text
ECG12^12 Lead ECG^L^93000^Electrocardiogram, routine ECG with at least 12 leads^C4
```

## OIE Send and ACK Handling

The OIE page should expose host, port, timeout, and MLLP framing settings with defaults for local development:

- Host: `localhost`
- Port: `6663`
- Timeout: implementation-defined short default
- Framing: MLLP enabled

Sending is manual and one order at a time. On response:

- Parse `MSA-1` into `AA`, `AE`, or `AR` when an HL7 ACK is returned.
- Store the raw ACK payload.
- Store parsed message control id and error text when present.
- Store transport failures separately from HL7 ACK errors.

## Risks

- OIE listener ports vary by developer environment. Defaults should be editable and should fail with clear transport messages.
- ACK parsing should tolerate minimal HL7 ACKs and malformed responses without losing the raw payload.
- Reusing local patient snapshots avoids accidental payload drift, but future patient-edit behavior may need an explicit refresh/regenerate action.
- Disabled future protocol modes should not look functional or block the HL7 v2.3.1 path.
