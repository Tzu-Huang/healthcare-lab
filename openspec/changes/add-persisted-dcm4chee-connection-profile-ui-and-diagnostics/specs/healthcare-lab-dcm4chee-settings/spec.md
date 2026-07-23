## ADDED Requirements

### Requirement: Persisted dcm4chee profile is typed and complete
Healthcare Lab SHALL persist one validated dcm4chee profile containing enablement, display and environment names, browser Web UI URL, DICOMweb endpoints, DIMSE and HL7 endpoints, AE and HL7 identities, MWL identity, default Scheduled Station AE Title, Patient assigning authority, viewer template, UID root, TLS/authentication settings, username, token URL, certificate path, and private-key path.

#### Scenario: Built-in profile is available
- **WHEN** a clean built-in Docker deployment starts without a persisted dcm4chee profile
- **THEN** Healthcare Lab creates a valid enabled profile whose application-facing endpoints are reachable through the supported Docker topology and whose Web UI URL is browser-facing

#### Scenario: Invalid profile is rejected
- **WHEN** an operator submits an invalid URL, port, AE title, authentication combination, or unreadable required certificate reference
- **THEN** Healthcare Lab rejects the update with stable field-level errors and does not partially persist it

### Requirement: Sensitive dcm4chee material is redacted
Healthcare Lab SHALL treat stored credentials as write-only secrets and certificate or private-key locations as deployment-mounted references, and MUST NOT return secret values, private-key contents, certificate contents, or raw filesystem errors.

#### Scenario: Profile is read after secrets are configured
- **WHEN** an operator reads a dcm4chee profile containing configured sensitive material
- **THEN** the response reports only bounded configured/reference state and contains none of the sensitive values or file contents

### Requirement: One effective profile drives every dcm4chee workflow
Healthcare Lab SHALL make the persisted effective dcm4chee profile the canonical source for Patient ADT sync, MWL create and readback, result reconciliation, viewer links, and diagnostics, with one immutable snapshot per operation.

#### Scenario: Persisted endpoint changes
- **WHEN** an operator saves a valid external PACS profile
- **THEN** subsequent ADT, MWL, result, viewer, and diagnostic operations all use that profile without consulting conflicting startup environment values

#### Scenario: Stable identity has dependent records
- **WHEN** an operator changes profile identity, Patient assigning authority, or UID root after dependent local mappings exist
- **THEN** Healthcare Lab rejects the unsafe change with stable migration guidance and leaves the prior profile effective

### Requirement: dcm4chee diagnostics are independent and bounded
Healthcare Lab SHALL provide independent timeout-bounded checks for browser Web UI reachability, DICOMweb QIDO-RS metadata query, HL7 TCP reachability, and DIMSE TCP reachability using allowlisted redacted results.

#### Scenario: Partial connectivity
- **WHEN** some dcm4chee endpoints are reachable and another check fails or times out
- **THEN** Healthcare Lab returns every check result independently and reports an aggregate degraded state

#### Scenario: TCP connection succeeds
- **WHEN** an HL7 or DIMSE TCP connection can be established
- **THEN** Healthcare Lab reports transport reachability and does not claim successful HL7 or DICOM protocol negotiation

### Requirement: dcm4chee owns its Settings experience
Healthcare Lab SHALL provide an accessible dcm4chee Settings module with common connection and identity fields visible by default, advanced DICOMweb, viewer, UID, HL7, TLS, authentication, and mounted-reference fields under an Advanced disclosure, and distinct save and diagnostic outcomes.

#### Scenario: Optional integration is disabled
- **WHEN** an operator disables dcm4chee
- **THEN** the module and Settings Overview report `disabled` and guided setup can complete without dcm4chee connectivity

#### Scenario: External PACS is configured
- **WHEN** an operator enters and saves a valid external PACS profile
- **THEN** the module displays the redacted persisted projection and allows diagnostics to be run without exposing credentials
