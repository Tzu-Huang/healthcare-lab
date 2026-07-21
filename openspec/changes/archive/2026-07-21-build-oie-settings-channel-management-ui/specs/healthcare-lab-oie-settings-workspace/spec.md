## ADDED Requirements

### Requirement: Settings is a separated responsive workspace

Healthcare Lab SHALL expose Settings at the bottom of the sidebar, visually separated from operational workspaces, and SHALL preserve existing navigation and responsive behavior.

#### Scenario: Operator opens Settings
- **WHEN** the operator selects Settings from the sidebar
- **THEN** the application displays OIE Connection, HLAB Result Listener, and Managed Channels sections
- **AND** existing operational views retain their navigation behavior

#### Scenario: Settings is used on a narrow viewport
- **WHEN** the workspace is rendered at a supported narrow viewport
- **THEN** fields, status details, Channel cards, previews, and operation controls remain readable and operable without hiding required safety information

### Requirement: OIE connection settings are secret-safe

The Settings workspace SHALL read and save the Management API URL, username, TLS mode, and timeout, SHALL allow write-only password replacement, and MUST NOT display or return the saved password.

#### Scenario: Saved connection settings are loaded
- **WHEN** Settings loads a profile with a configured password
- **THEN** it reports that a password is configured without rendering the password or a masked placeholder containing it

#### Scenario: Non-secret settings are saved
- **WHEN** the operator saves valid connection or listener changes without entering a replacement password
- **THEN** Healthcare Lab preserves the stored password and returns the saved non-secret profile

#### Scenario: Password is replaced
- **WHEN** the operator supplies a non-empty replacement password and saves valid settings
- **THEN** Healthcare Lab stores it without returning it in the response, status, error, or UI state

### Requirement: Operators can test the saved OIE connection

Healthcare Lab SHALL provide a Settings connection test using the persisted private Management API configuration and SHALL return bounded connection status, OIE version, current user, TLS mode, and test time without exposing session or secret material.

#### Scenario: Supported OIE connection succeeds
- **WHEN** saved credentials authenticate and the connected OIE reports a supported version
- **THEN** Settings displays Connected, the OIE version, current user, TLS mode, and test time

#### Scenario: Connection test fails
- **WHEN** validation, TLS, authentication, permission, connection, timeout, unsupported-version, server, or unexpected-response failure occurs
- **THEN** Settings displays the stable category and an actionable safe message
- **AND** it does not display passwords, cookies, authorization values, headers, or arbitrary upstream bodies

### Requirement: Listener intent and runtime state are both visible

The Settings workspace SHALL display persisted listener host, port, MLLP framing, and auto-start intent separately from actual stopped, running, or degraded runtime state and SHALL expose Start, Stop, and Retry actions.

#### Scenario: Saved listener intent is running
- **WHEN** listener Status matches the persisted enabled configuration
- **THEN** Settings displays the active endpoint, framing, running state, and enabled auto-start intent without an unapplied reminder

#### Scenario: Listener startup is degraded
- **WHEN** binding or runtime startup fails
- **THEN** the web workspace remains available and displays degraded state with the actionable bounded error and Retry action

#### Scenario: Operator controls the listener
- **WHEN** the operator selects Start, Stop, or Retry
- **THEN** Settings performs only that process-local runtime action and refreshes actual status
- **AND** Stop does not change persisted auto-start intent

### Requirement: Listener changes disclose coordinated runtime work

Saving Settings SHALL NOT automatically restart the listener, and the workspace SHALL disclose unapplied intent and coordinated configuration consequences.

#### Scenario: Listener settings change
- **WHEN** a successful save changes host, port, framing, or auto-start intent that runtime has not applied
- **THEN** Settings keeps a visible Stop/Retry-or-restart reminder until runtime Status matches the persisted intent

#### Scenario: Listener port changes
- **WHEN** the operator changes the HLAB result-listener port
- **THEN** Settings warns that the managed ORU destination, Docker/runtime port exposure, firewall, and lab-app Retry or restart may require corresponding work
- **AND** it does not automatically edit Docker or runtime configuration

### Requirement: Channel inventory exposes bounded operational state

Settings SHALL show the two approved managed routes and all external Channels with name, source, destination, ownership/classification, deployment, drift, revision, and last-operation status when available.

#### Scenario: Managed routes are displayed
- **WHEN** managed Channel inventory loads
- **THEN** Settings presents `OIE:6600 -> AP:6671` and `OIE:6661 -> lab-app:6665` with their current lifecycle state and permitted actions

#### Scenario: External Channel is displayed
- **WHEN** inventory includes a Channel not exactly owned by Healthcare Lab
- **THEN** Settings labels it external/read-only and enables no Edit, Apply, Deploy, Redeploy, Undeploy, Delete, or adoption action

#### Scenario: Drift or conflict is displayed
- **WHEN** a managed Channel is drifted or conflicted
- **THEN** Settings shows bounded owned-field differences or blocking reasons without exposing complete Channel payloads

### Requirement: Managed Channel editing is constrained

Settings SHALL allow edits only to approved template-owned endpoint and bounded transport fields, SHALL validate them before transport, and MUST NOT expose raw Channel JSON/XML, arbitrary connectors, filters, transformers, or scripts.

#### Scenario: Operator edits an approved field
- **WHEN** the operator changes a supported source, destination, timeout, queue, or retry value
- **THEN** Settings validates and saves the desired value and requires an Apply preview before OIE mutation

#### Scenario: Unsupported Channel content is requested
- **WHEN** an operator would need to edit raw payload content or an unowned OIE field
- **THEN** Settings provides no editing control or mutation request for that content

### Requirement: Every Channel mutation uses a reviewed preview

Settings MUST require a current preview token for Create, Apply, Deploy, Redeploy, Undeploy, Delete, and Recreate and SHALL display the target, exact route, owned-field differences, expected steps, and blocking facts before enabling execution.

#### Scenario: Permitted operation is previewed
- **WHEN** the operator selects a permitted managed-Channel action
- **THEN** Settings requests a side-effect-free preview and enables execution only when a valid token and any required confirmation are present

#### Scenario: Preview becomes stale
- **WHEN** execution reports changed identity, revision, deployment state, classification, or desired state
- **THEN** Settings disables execution, reports that state changed, and requires a fresh preview

#### Scenario: Operation completes or partially fails
- **WHEN** execution returns success, failure, or partial-failure
- **THEN** Settings displays the bounded ordered step outcomes and refreshes inventory before permitting another mutation

### Requirement: Delete confirmation identifies the visible target

Settings MUST require the exact displayed Channel name before Delete and SHALL disclose the exact route and affected single Channel.

#### Scenario: Delete confirmation matches
- **WHEN** the operator reviews Delete, enters the exact displayed Channel name, and the preview remains current
- **THEN** Settings enables deletion of only the preview-bound managed Channel and reports whether undeploy is required first

#### Scenario: Delete confirmation does not match
- **WHEN** confirmation differs from the displayed Channel name
- **THEN** Settings keeps execution disabled and no OIE mutation occurs

#### Scenario: Deleted Channel becomes recreatable
- **WHEN** deletion succeeds and refreshed inventory classifies the retained logical template as Missing
- **THEN** Settings presents Recreate as the bounded Create flow for that template
