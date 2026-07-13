## Why

Healthcare Lab now has the main dcm4chee-arc building blocks: DICOM patient sync, MWL order creation, MWL queryability verification, AP C-STORE result reconciliation, and frontend DICOM result display. ZAC-42 closes the remaining acceptance gap by turning those pieces into one repeatable production-like end-to-end verification path.

Operators need proof that a Healthcare Lab-created DICOM order can be created in dcm4chee MWL, found by the AP-facing worklist surface, fulfilled by AP result return, reconciled back into Healthcare Lab, and displayed in the UI with the exact identifiers used during the test.

The verification also needs a deterministic simulated AP-return fixture so UI and reconciliation checks can be repeated without requiring a live AP every time. That fixture should cover at least a returned PDF artifact and/or DICOM result metadata/object record that Healthcare Lab displays as an AP-returned result.

## What Changes

- Add production-like E2E verification for the Healthcare Lab -> dcm4chee MWL -> AP -> dcm4chee C-STORE -> Healthcare Lab frontend workflow.
- Provide demo presets or fixtures that create a known DICOM patient/order with predictable demographics, AP station, and order identifiers.
- Verify Healthcare Lab automatically creates the dcm4chee MWL/order and records the canonical PACS/MWL identifiers.
- Verify the created order is queryable from the configured dcm4chee MWL surface used by APs.
- Add a repeatable simulated AP-return path that records a returned PDF artifact and/or DICOM result metadata/object against the Healthcare Lab order.
- Verify Healthcare Lab reconciliation and frontend display show AP-returned results, including matched order status, PDF or DICOM access links, Study/Series/Instance identifiers when available, and reconciliation diagnostics.
- Document an operator SOP for service startup, required ports, AE titles, expected identifiers, test steps, evidence capture, and troubleshooting.
- Add automated tests where local fixtures can cover behavior, and keep live AP/dcm4chee steps as documented manual production-like checks when external runtime interaction is required.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Extend the dcm4chee order/result workflow with production-like E2E verification, AP-return simulation fixtures, UI-visible result proof, and operator SOP evidence requirements.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, frontend DICOM result/status rendering, tests under `tests/`, and docs under `docs/` or `deploy/`.
- Affected workflows: local DICOM patient/order creation, dcm4chee patient precondition sync, MWL create/read-back/verify, AP C-STORE result return, result refresh/reconciliation, patient/order DICOM result UI, and lab startup SOP.
- The change should not implement AP internals, but it should define the identifiers and artifacts AP must preserve or return for the production-like verification.
