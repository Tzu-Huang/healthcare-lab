## Overview

The current GDT implementation is functional but persistence-centered. `lab_store.py` owns message rendering, parsing, canonical mapping, and database writes. This change should introduce an adapter boundary so GDT 2.1 message concerns are testable without constructing the full store.

The adapter should not replace the independent GDT foundation. It should provide the translation and validation layer used by that foundation.

## Proposed Adapter Shape

Add a backend module such as `backend/gdt_adapter.py` with functions or small classes for:

- rendering one GDT record with strict byte length,
- rendering a full GDT 2.1 dataset with stabilized `8100`,
- parsing raw GDT text into ordered records and repeated field maps,
- validating required fields by message type,
- generating `6302` from canonical order data,
- parsing `6310` into canonical result JSON,
- returning structured validation notices.

Expected output shape:

```json
{
  "rawGdtText": "...",
  "parsedFields": {
    "8410": ["HR"],
    "8420": ["75"],
    "8421": ["/min"]
  },
  "canonical": {
    "patient": {},
    "order": {},
    "result": {},
    "attachments": [],
    "correlation": {}
  },
  "validation": {
    "errors": [],
    "warnings": []
  }
}
```

## GDT 2.1 Record Rules

Each record must be encoded as:

```text
[length3][tag4][value][CRLF]
```

The `length3` value is the encoded byte length of the whole record, including:

- 3 bytes for `length3`,
- 4 bytes for `tag4`,
- value bytes,
- 2 bytes for CRLF.

The adapter must reject malformed record envelopes, nonnumeric lengths, invalid tag widths, truncated records, and records missing CRLF.

## `8100` Total Length

`8100` must equal the encoded byte length of the full dataset, including:

- `8000`,
- `8100` itself,
- `9218`,
- all remaining records,
- every record CRLF.

Generation should keep the existing stabilization approach or an equivalent deterministic two-pass strategy. Parsing should verify the actual total length against `8100`.

## `6302` Generation

The adapter should generate `6302` New Test Request messages from canonical order input containing:

- patient GDT number for `3000`,
- surname `3101`,
- first name `3102`,
- birth date `3103` as `DDMMYYYY`,
- ECG test type `8402=EKG01`,
- order/test identifier in the existing Healthcare Lab-compatible field set.

The existing order API must continue to expose the raw generated message as `payload` while storing raw/parsed/canonical forms through the foundation.

## `6310` Parsing

The adapter should parse `6310` Test Data Transfer messages and build canonical result JSON:

```json
{
  "patient": {
    "gdtPatientNumber": "02345",
    "lastName": "",
    "firstName": "",
    "dob": ""
  },
  "order": {
    "identifiers": []
  },
  "result": {
    "status": "B",
    "measurements": {
      "HR": { "value": 75, "unit": "/min" },
      "PR": { "value": 160, "unit": "ms" },
      "QRS": { "value": 95, "unit": "ms" },
      "QT": { "value": 400, "unit": "ms" },
      "QTC": { "value": 420, "unit": "ms" }
    },
    "comments": [],
    "formattedText": []
  },
  "attachments": [],
  "correlation": {}
}
```

`3101` and `3102` are optional for `6310`; the adapter should not reject result messages solely because result demographics are absent when `3000` can be used for linkage.

## Measurement Mapping

`8410` is vendor-defined. The default adapter profile should normalize common IDs:

| GDT `8410` | Canonical key |
| --- | --- |
| `HR` | `HR` |
| `PR` | `PR` |
| `QRS` | `QRS` |
| `QT` | `QT` |
| `QTC` | `QTC` |
| `P-AXIS` | `P_AXIS` |
| `QRS-AXIS` | `QRS_AXIS` |
| `T-AXIS` | `T_AXIS` |

Measurements are represented by nearby `8410`, `8420`, and `8421` records. Implementation should preserve unknown `8410` values in parsed fields and may add warnings for unmapped values instead of dropping them.

## Text and Status Fields

- `8418` should map to result status.
- `6227` should map to comments.
- `6228` should map to formatted report text.
- Multi-line text handling via `6226/6228` can be added where present, but ZAC-23 requires at least repeated `6228` preservation.

## Validation Notices

Use structured notices:

```json
{
  "code": "001",
  "severity": "error",
  "field": "8100",
  "message": "GDT 8100 total length does not match actual byte length."
}
```

Initial code bands:

- `000-099`: format errors, reject.
- `100-199`: content warnings, warn where recoverable.
- `200-299`: missing required fields or invalid required context, reject.
- `300-399`: semantic/context warnings, warn where clinically safe.

For Flask/API integration, validation errors should continue to surface as client errors through existing error response patterns. Warnings should be stored in canonical or validation JSON for inspection.

## Testing Strategy

Add focused adapter tests before broad store/API tests:

- valid `6302` generation for `8402=EKG01`,
- generated record lengths and `8100`,
- valid `6310` ECG measurements for HR, PR, QRS, QT, and QTC,
- optional `6310` name fields,
- invalid record length reject,
- missing or mismatched `8100` reject,
- unknown vendor `8410` warning,
- store/API integration still preserves raw text and parsed/canonical JSON.
