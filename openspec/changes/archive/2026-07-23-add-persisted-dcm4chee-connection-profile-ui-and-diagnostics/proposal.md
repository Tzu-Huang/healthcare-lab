## Why

dcm4chee workflows currently consume a startup-time environment projection while the Settings workspace exposes only a disabled placeholder. Operators need one persisted, validated connection profile that drives every DICOM workflow and provides bounded diagnostics for both the built-in Docker topology and external PACS deployments.

## What Changes

- Add a typed, persisted dcm4chee profile covering enablement, operator labels, Web UI, DICOMweb, DIMSE, HL7, AE identities, Patient assigning authority, viewer, UID, TLS, authentication, and mounted credential references.
- Seed eligible `DCM4CHEE_*` values only when the persisted profile is absent, then make persisted settings the canonical runtime source.
- Add a dcm4chee-owned Settings module with essential fields, an Advanced disclosure, stable validation errors, redacted secret/reference handling, and explicit activation results.
- Move Patient ADT sync, MWL create/readback, result reconciliation, viewer links, and diagnostics to the same effective profile.
- Add independent bounded checks for Web UI reachability, QIDO-RS metadata query, HL7 TCP reachability, and DIMSE TCP reachability without treating a TCP connection as protocol success.
- Register dcm4chee readiness and diagnostic results with the Settings Overview and guided setup.

## Capabilities

### New Capabilities

- `healthcare-lab-dcm4chee-settings`: Defines the persisted dcm4chee profile, modular Settings experience, canonical runtime projection, validation, diagnostics, and readiness behavior.

### Modified Capabilities

- `healthcare-lab-typed-integration-settings`: Registers dcm4chee ownership, one-time environment bootstrap, secret/reference projection, and effective-profile access.
- `healthcare-lab-settings-workspace`: Replaces the static dcm4chee placeholder with integration-owned readiness, diagnostics, and guided-setup behavior.

## Impact

- Affects typed settings domain and persistence, application composition, dcm4chee APIs and clients, Patient and Order workflow services, viewer-link projection, readiness aggregation, and the modular Settings frontend.
- Adds focused validation, migration, persistence, diagnostics, API, workflow-consistency, readiness, and frontend tests.
- Does not introduce direct access to the dcm4chee database and does not change deployment-owned archive storage or container topology.
