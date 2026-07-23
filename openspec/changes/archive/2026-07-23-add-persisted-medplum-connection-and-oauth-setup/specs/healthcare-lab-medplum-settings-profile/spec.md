## ADDED Requirements

### Requirement: Medplum uses one canonical persisted connection profile
Healthcare Lab SHALL persist one typed Medplum profile containing enabled state, internal FHIR R4 base URL, browser Web UI URL, client ID, write-only client secret, optional scope, optional token URL, token refresh grace seconds, and timeout seconds.

#### Scenario: Operator reads the Medplum profile
- **WHEN** an operator opens Medplum Settings
- **THEN** Healthcare Lab returns every non-secret profile field
- **AND** identifies the client secret only by configured state
- **AND** clearly distinguishes the internal application FHIR URL from the browser-facing Web UI URL

#### Scenario: Docker-local profile is bootstrapped
- **WHEN** no persisted Medplum profile exists in the supported Docker runtime
- **THEN** the internal FHIR base URL defaults to `http://medplum:8103/fhir/R4`
- **AND** the browser Web UI URL defaults to `http://127.0.0.1:3000`
- **AND** container-to-container workflows do not use `127.0.0.1`

### Requirement: Saved Medplum settings activate without container recreation
Healthcare Lab SHALL resolve the effective persisted Medplum profile for each subsequent workflow or diagnostic operation and SHALL NOT require container recreation to activate a valid save.

#### Scenario: Operator changes a connection field
- **WHEN** a valid Medplum profile mutation commits
- **THEN** subsequent Patient, Order, FHIR preview and sync, DiagnosticReport, health, and smoke operations use the new effective profile
- **AND** no competing environment or Lab Server inventory value overrides it

#### Scenario: Medplum is disabled
- **WHEN** the saved profile has `enabled` set to false
- **THEN** Medplum-backed workflows report that the integration is disabled or not configured
- **AND** health and connection diagnostics perform no Medplum network request

### Requirement: Medplum OAuth secrets and tokens remain private
Healthcare Lab MUST preserve write-only client-secret semantics, MUST retain access tokens only in process memory, and MUST NOT expose credentials, tokens, authorization headers, or FHIR resource bodies through logs, errors, audits, APIs, or diagnostics.

#### Scenario: Blank secret is saved
- **GIVEN** a client secret is configured
- **WHEN** an operator saves a valid profile with a blank or omitted secret replacement
- **THEN** Healthcare Lab preserves the configured secret
- **AND** returns only `configured: true`

#### Scenario: Secret is rotated or removed
- **WHEN** an operator supplies a non-blank replacement or invokes explicit secret removal
- **THEN** subsequent OAuth operations use the replaced secret or report credentials unconfigured
- **AND** no response or audit contains the old or new secret

#### Scenario: Sensitive upstream data appears in a failure
- **WHEN** an upstream token or FHIR failure contains a credential, token, authorization header, or resource body
- **THEN** Healthcare Lab returns and logs only an allowlisted bounded failure category and safe summary

### Requirement: Medplum authentication is reused only for the matching profile
Healthcare Lab SHALL reuse valid access tokens through an in-memory auth manager and SHALL invalidate reusable authorization state when authentication-relevant effective settings change.

#### Scenario: Repeated operations use an unchanged profile
- **WHEN** multiple Medplum operations occur while a cached token remains valid beyond the configured grace period
- **THEN** Healthcare Lab reuses the in-memory token
- **AND** does not persist that token

#### Scenario: Authentication settings change
- **WHEN** the base URL, client ID, client secret, scope, token URL, refresh grace, timeout, or enabled state changes
- **THEN** subsequent operations do not reuse authorization state from the previous effective profile

### Requirement: Save and test reports independent bounded stages
Healthcare Lab SHALL save a valid Medplum profile and run separate bounded checks for FHIR metadata reachability, OAuth token acquisition, and an authenticated FHIR read.

#### Scenario: All checks succeed
- **WHEN** the saved metadata endpoint is reachable, OAuth credentials acquire a token, and a bounded authenticated FHIR read succeeds
- **THEN** each stage reports success independently
- **AND** the result contains no access token or FHIR resource body

#### Scenario: A stage fails
- **WHEN** metadata, token acquisition, or authenticated read fails
- **THEN** that stage reports a stable bounded failure
- **AND** other applicable stages retain their own results
- **AND** the valid saved profile remains persisted

#### Scenario: Credentials are absent
- **WHEN** metadata is reachable but OAuth credentials are not configured
- **THEN** metadata reports its observed result
- **AND** OAuth and authenticated-read stages report a bounded not-configured or skipped state

### Requirement: Medplum network operations honor the persisted timeout
Healthcare Lab SHALL apply the positive persisted timeout to metadata, OAuth, authenticated reads, and normal Medplum workflow requests.

#### Scenario: Upstream exceeds the timeout
- **WHEN** a Medplum request does not complete within the configured timeout
- **THEN** Healthcare Lab stops waiting
- **AND** returns a bounded timeout failure without upstream response content
