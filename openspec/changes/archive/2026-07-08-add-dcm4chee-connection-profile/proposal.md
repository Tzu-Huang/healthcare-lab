## Why

Healthcare Lab already defines the dcm4chee-arc MWL order model and result reconciliation rules, but the runtime does not yet have a structured dcm4chee connection profile that downstream MWL, verification, C-STORE reconciliation, and viewer-link features can share.

ZAC-35 adds that configuration boundary before implementing AP behavior or MWL order creation.

## What Changes

- Add a named dcm4chee-arc connection profile for the local lab environment.
- Store display/environment names, Web UI URL, DIMSE host/port, called AE title, Healthcare Lab calling AE title, MWL AE title, and default Scheduled Station AE Title.
- Store DICOMweb endpoint values for future query, retrieve/viewer, and store integrations.
- Include auth, TLS, and security placeholders while keeping the local lab profile unauthenticated by default.
- Provide backend profile loading and validation/diagnostic output that reports missing or invalid configuration clearly.
- Document defaults for the local Docker profile:
  - `profileName`: `local-dcm4chee`
  - `displayName`: `dcm4chee Local Archive`
  - `environmentName`: `local-docker`
  - `webUiUrl`: `http://127.0.0.1:8082/dcm4chee-arc/ui2`
  - `dimseHost`: `127.0.0.1`
  - `dimsePort`: `11112`
  - `calledAETitle`: `DCM4CHEE`
  - `callingAETitle`: `HEALTHCARE_LAB`
  - `mwlAETitle`: `DCM4CHEE`
  - `defaultScheduledStationAETitle`: `ECG_AP`
  - `dicomwebBaseUrl`: `http://127.0.0.1:8082/dcm4chee-arc/aets/DCM4CHEE/rs`
  - `authMode`: `none`
  - `tlsEnabled`: `false`

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-connection-profile`: Define and expose a validated dcm4chee-arc connection profile for local lab workflows.

### Modified Capabilities

- `healthcare-lab-dcm4chee-mwl-order-model`: Use the selected dcm4chee connection profile as the source of server identity, AE titles, DICOMweb endpoints, and default AP station values for future MWL/order workflow implementation.

## Impact

- Affected code: likely `app.py`, `backend/lab_store.py`, `.env.example`, `README.md`, and tests under `tests/`.
- Potentially affected UI: Dashboard/server detail diagnostics if profile validation is surfaced there.
- Affected systems: dcm4chee local Docker archive, future MWL creation, MWL verification, C-STORE reconciliation, and viewer-link generation.
- No AP implementation, MWL order creation, or C-STORE result processing is implemented in this proposal step.
