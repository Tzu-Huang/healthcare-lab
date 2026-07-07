## Why

Healthcare Lab already has an independent GDT foundation: local GDT ECG orders can generate and store `6302` payloads, `6310` result imports can be persisted, and raw/parsed/canonical records are available for backend inspection. That foundation is intentionally broad, but the GDT rendering, parsing, validation, and canonical result mapping still live inside the persistence layer.

ZAC-23 should turn that foundation into a clear GDT 2.1 adapter boundary. The adapter should translate between Healthcare Lab canonical data and GDT 2.1 messages, enforce BDT record syntax, expose structured validation notices, and normalize ECG result measurements without adding a full GDT hospital/device simulator UI.

## What Changes

- Add a backend GDT 2.1 adapter capability for generating `6302` New Test Request messages from Healthcare Lab order data.
- Add `6310` Test Data Transfer parsing into canonical result JSON with raw GDT text preserved for audit/debug.
- Enforce strict BDT line syntax:
  - 3-byte length prefix,
  - 4-byte tag,
  - encoded value,
  - trailing CRLF.
- Validate `8100` as the full dataset byte length, including the `8100` record itself and every record CRLF.
- Support the minimum ZAC-23 field set:
  - `8000`, `8100`, `9218`,
  - `3000`, `3101`, `3102`, `3103`,
  - `8402`, `8410`, `8420`, `8421`, `8418`,
  - `6227`, `6228`.
- Normalize default ECG measurement `8410` values into canonical measurements:
  - `HR`, `PR`, `QRS`, `QT`, `QTC`,
  - `P_AXIS`, `QRS_AXIS`, `T_AXIS`.
- Preserve the existing GDT order/result persistence APIs while routing GDT message translation through the adapter.
- Add golden-style fixtures/tests for valid `6302`, valid `6310` ECG measurements, bad record length, and bad/missing `8100`.

## Non-Goals

- No GDT 3.5 object parser in this change.
- No full GDT hospital/device simulator UI in Healthcare Lab.
- No dynamic production vendor onboarding UI.
- No support for non-MVP order generation away from `8402=EKG01`.
- No embedding raw ECG waveform payloads directly inside GDT 2.1 messages.
- No certification-grade QMS rule catalog beyond the ZAC-23 validation policy and covered fixtures.

## Key Decisions

- Capability shape: add `healthcare-lab-gdt-21-adapter` as the adapter contract, layered on top of `healthcare-lab-independent-gdt-foundation`.
- Implementation boundary: prefer a backend adapter module, such as `backend/gdt_adapter.py`, so persistence code delegates message rendering, parsing, canonical mapping, and validation.
- GDT version: focus on GDT 2.1 records with `9218=02.10`. Version branching for GDT 3.5 remains future work.
- Encoding: continue using the existing GDT 2.1 compatible ANSI/CP1252 path unless implementation discovers a stronger local convention.
- Measurement mapping: treat `8410` as vendor-defined. The implementation may ship default profile aliases for common ECG IDs, but must keep the structure open for future vendor mapping.
- Validation severity:
  - format errors `000-099` reject,
  - content warnings `100-199` warn when recoverable,
  - required-field/context errors `200-299` reject,
  - semantic/context warnings `300-399` warn when clinically safe.
- Artifacts: `6302-6305` result artifact groups may be parsed by this adapter if present, but this change is primarily about the ZAC-23 minimum field set and canonical ECG result values.

## Capabilities

### New Capabilities

- `healthcare-lab-gdt-21-adapter`: Generate GDT 2.1 `6302` requests and parse/validate GDT 2.1 `6310` ECG results through a reusable adapter boundary.

### Modified Capabilities

- `healthcare-lab-independent-gdt-foundation`: Use the adapter output for raw, parsed, canonical, and validation payloads while preserving existing storage behavior.

## Impact

- Affected code: backend GDT render/parse helpers, GDT result canonical mapping, GDT order/result store integration, tests, and fixtures.
- Affected APIs: existing `/api/gdt/orders` and `/api/gdt/results` behavior remains compatible, with additive validation/canonical detail where useful.
- Affected workflow: developers get deterministic GDT 2.1 adapter behavior that can be tested independently from SQLite persistence and later extended through vendor profiles.
