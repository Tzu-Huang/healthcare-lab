## ADDED Requirements

### Requirement: OIE authentication establishes an isolated reusable session

Healthcare Lab SHALL authenticate to the configured OIE Management API with the configured username and password, required request headers, bounded timeouts, and configured TLS policy, and SHALL retain the resulting session cookie only inside that client instance for subsequent operations.

#### Scenario: Login succeeds
- **WHEN** OIE accepts the configured credentials
- **THEN** the client reports an authenticated session
- **AND** subsequent operations reuse the session cookie without returning it to the caller

#### Scenario: Credentials are invalid
- **WHEN** OIE rejects the configured username or password
- **THEN** the client raises an authentication-class error with actionable redacted detail

#### Scenario: Sessions are isolated
- **WHEN** two client instances authenticate independently
- **THEN** neither client sends or exposes the other client's cookies

#### Scenario: Logout clears local authentication
- **WHEN** an authenticated client logs out
- **THEN** it attempts the OIE logout operation and clears its local session state
- **AND** a remote logout failure does not retain locally usable authentication state

### Requirement: Management requests enforce headers, TLS, and timeout policy

The OIE Management API client SHALL add the required `X-Requested-With` header to every applicable request, SHALL support verified TLS and an explicitly configured local-lab self-signed mode, and SHALL apply bounded connect and read timeouts.

#### Scenario: Verified TLS is selected
- **WHEN** TLS verification is enabled
- **THEN** the client validates the OIE server certificate and hostname

#### Scenario: Local self-signed mode is selected
- **WHEN** the explicit local-lab self-signed mode is configured
- **THEN** the client may connect without normal certificate verification
- **AND** the mode is represented as an intentional configuration rather than an automatic fallback

#### Scenario: A request times out
- **WHEN** connection establishment or response reading exceeds its configured bound
- **THEN** the client raises a timeout-class error distinct from authentication, TLS, and unreachable-server failures

### Requirement: The client provides required OIE inspection operations

Healthcare Lab SHALL provide authenticated operations for current-user information, system information and OIE version, Channel list and get, Channel status, and ports-in-use using OIE 4.5.2 request and response contracts.

#### Scenario: Inspect the authenticated runtime
- **WHEN** an authenticated caller requests current-user and system information
- **THEN** the client returns normalized values including the detected OIE version without exposing session material

#### Scenario: Inspect Channels and ports
- **WHEN** an authenticated caller requests Channels, a specific Channel, status, or ports in use
- **THEN** the client returns normalized results that preserve the identifiers and revision information needed by lifecycle coordination

#### Scenario: A success response is malformed
- **WHEN** OIE returns a nominally successful response missing required structure
- **THEN** the client raises an unexpected-response error with bounded redacted detail

### Requirement: The client provides Channel mutation primitives

Healthcare Lab SHALL provide authenticated Channel create, update, delete, deploy, redeploy-all, and undeploy primitives without deciding ownership, generating Channel templates, or automatically sequencing a managed lifecycle.

#### Scenario: Create or delete a Channel
- **WHEN** a caller supplies a valid OIE Channel payload or identifier
- **THEN** the client performs the requested create or delete operation and returns the normalized OIE outcome

#### Scenario: Deploy or undeploy a Channel
- **WHEN** a caller requests deploy or undeploy for a Channel identifier
- **THEN** the client performs exactly that requested primitive and returns its normalized outcome

#### Scenario: Redeploy all Channels
- **WHEN** a caller requests the OIE redeploy-all primitive
- **THEN** the client invokes the declared redeploy-all operation and returns its normalized outcome

#### Scenario: Update uses safe conflict behavior
- **WHEN** a caller updates a Channel without specifying an override value
- **THEN** the client sends the operation with `override=false`
- **AND** a revision conflict is returned as a revision-conflict error without an automatic overriding retry

### Requirement: OIE failures have stable actionable classifications

The client SHALL classify OIE authentication, permission, TLS, connection, timeout, revision-conflict, validation, unsupported-version, server, and unexpected-response failures so callers can select remediation without parsing raw transport exceptions.

#### Scenario: Permission is denied
- **WHEN** an authenticated user lacks permission for an operation
- **THEN** the client raises a permission-class error distinct from invalid authentication

#### Scenario: OIE cannot be reached
- **WHEN** DNS resolution, connection establishment, or remote availability prevents a request
- **THEN** the client raises a connection-class error distinct from TLS and timeout failures

#### Scenario: OIE rejects input
- **WHEN** OIE reports invalid request or Channel content
- **THEN** the client raises a validation-class error preserving only actionable non-secret detail

#### Scenario: OIE reports an internal failure
- **WHEN** OIE returns a server-side failure not covered by a more specific classification
- **THEN** the client raises a server-class error with status context and bounded redacted detail

### Requirement: OIE version targeting is explicit

The client SHALL detect and report the connected OIE version, SHALL recognize `4.5.2` as the supported target, and SHALL surface an unsupported-version classification when the detected version is incompatible with the implemented Management API contract.

#### Scenario: Supported version is detected
- **WHEN** system information identifies OIE version `4.5.2`
- **THEN** the client reports the runtime as supported

#### Scenario: Unsupported version is detected
- **WHEN** system information identifies a version outside the supported contract
- **THEN** the client raises or returns an unsupported-version result before callers rely on incompatible mutation behavior

### Requirement: Authentication material never escapes the client boundary

The client MUST prevent configured passwords, session cookies, authorization material, and equivalent secret values from appearing in returned results, exception messages, object representations, or routine logs.

#### Scenario: A request containing secrets fails
- **WHEN** login or any authenticated operation fails after credentials or cookies have been attached
- **THEN** every returned or logged diagnostic replaces secret values with redacted markers
- **AND** the diagnostic does not include a complete sensitive request or response body

#### Scenario: Client objects are represented for diagnostics
- **WHEN** configuration, transport, error, or client objects are formatted or inspected
- **THEN** their representations omit password and cookie values

### Requirement: Settings integration preserves ownership boundaries

The client SHALL consume a persistence-neutral configuration, and application composition SHALL adapt the final OIE settings owner to that configuration without making the client depend on Flask, SQLite, repositories, mappers, or public Settings JSON presentation.

#### Scenario: Isolated client construction
- **WHEN** a test constructs the client with an explicit configuration and mocked transport
- **THEN** no Flask application, database, settings repository, or live OIE runtime is required

#### Scenario: ZAC-61 integration is available
- **WHEN** the final OIE settings validation and presentation owners from ZAC-61 are integrated
- **THEN** composition maps the configured connection and secret values into the client without changing the public settings contract
