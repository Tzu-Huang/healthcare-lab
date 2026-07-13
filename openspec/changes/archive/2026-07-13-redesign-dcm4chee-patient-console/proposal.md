## Why

The current dcm4chee frontend does not follow the established OIE patient-centered interaction closely enough: the Patient list is visually compressed, patient details and orders are split across competing panels, long sync metadata overflows its card, and DICOM results can expose raw data instead of an operator-readable table. The console needs a focused redesign so operators can move from Patient to Order and Result without losing context or parsing raw payloads.

## What Changes

- Redesign the dcm4chee Patient area as a wide OIE-style list with a dedicated disclosure control on each Patient row.
- Keep Patient selection and disclosure as separate interactions: selecting a row updates one Patient preview below the entire list, while the disclosure control expands or collapses that Patient's Order and Result sections inline.
- Remove the standalone `MWL Selected Patient Orders` section and present Orders only inside the expanded Patient row.
- Render DICOM Results as structured DICOM-field tables rather than printing a raw object or JSON payload in the UI.
- Constrain the `dcm4chee Patient Sync` card so timestamps, endpoints, error types, and error text wrap within the available width without page-level horizontal overflow.
- Preserve the existing dcm4chee backend APIs, retry/refresh actions, DICOM identifiers, and Healthcare Lab visual language.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Change the DICOM console's Patient selection, inline Order/Result disclosure, Patient preview, and structured result-table requirements.
- `healthcare-lab-dcm4chee-patient-sync`: Require Patient sync details and long diagnostics to remain readable within the sync card without layout overflow.

## Impact

- Frontend structure and accessibility semantics in `frontend/templates/index.html`.
- dcm4chee Patient selection, disclosure, preview, Order, and Result rendering in `frontend/static/app.js`.
- Responsive list, nested table, preview, and sync-card layout rules in `frontend/static/styles.css`.
- Static frontend contract tests in `tests/test_app.py`; browser-level interaction checks may be added if the repository's current test tooling supports them.
- No planned backend API, persistence model, dcm4chee endpoint, or deployment dependency changes.
