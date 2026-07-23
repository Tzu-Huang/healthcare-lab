# healthcare-lab-oie-settings-profile Specification

## Purpose
Define Healthcare Lab's persistent, secret-safe OIE settings profile for Management API access, HLAB result listener intent, and managed Channel identity mappings.
## Requirements
### Requirement: Healthcare Lab persists one local OIE settings profile

Healthcare Lab SHALL persist one local OIE settings profile containing Management API connection settings, HLAB result listener settings, and desired mappings for both canonical managed Channels without changing the existing Patient, Order, or OIE Result data model.

#### Scenario: A new database receives local defaults

- **WHEN** Healthcare Lab initializes a database without an OIE settings profile
- **THEN** it creates a local profile with Management API base URL `https://oie:8443`, username `admin`, a configured case-sensitive password value of `admin`, TLS verification disabled for the local self-signed certificate, and a 10-second request timeout
- **AND** its result listener settings are host `0.0.0.0`, port `6665`, MLLP framing enabled, and auto-start enabled
- **AND** it persists empty-identity desired mappings for `HLAB_ORM_TO_AP` from `OIE:6600` to `AP:6671` and `HLAB_ORU_TO_HLAB` from `OIE:6661` to `lab-app:6665`

#### Scenario: Saved settings survive restart

- **WHEN** an operator updates the OIE settings profile and Healthcare Lab initializes again using the same database
- **THEN** Healthcare Lab returns the previously saved profile and managed Channel mappings instead of reseeding or overwriting them with defaults

#### Scenario: Existing workflow records survive migration

- **WHEN** Healthcare Lab initializes an existing database containing Patient, Order, and OIE Result records but no OIE settings tables or canonical mapping rows
- **THEN** it adds and seeds the OIE settings schema and only missing canonical mapping intent without deleting or changing existing workflow records or mapping rows

### Requirement: OIE profile secrets are write-only

Healthcare Lab MUST accept a password update without returning or logging the stored password and SHALL report only whether a password is configured.

#### Scenario: Read a newly seeded profile

- **WHEN** a caller reads the newly seeded OIE settings profile
- **THEN** the response contains username `admin` and `passwordConfigured: true`
- **AND** the response does not contain the password value or a masked password placeholder

#### Scenario: Update settings without a password

- **WHEN** a caller updates valid non-secret settings without a `password` field
- **THEN** Healthcare Lab preserves the existing stored password
- **AND** the response contains only `passwordConfigured: true` for password state

#### Scenario: Replace the password

- **WHEN** a caller provides a non-empty `password` in an otherwise valid update
- **THEN** Healthcare Lab stores the new password and does not include it in the response or application logs

#### Scenario: Reject an empty password update

- **WHEN** a caller explicitly provides an empty or null `password`
- **THEN** Healthcare Lab rejects the update with an actionable validation error and preserves the existing password

### Requirement: Backend APIs read and update the complete OIE profile

Healthcare Lab SHALL expose backend endpoints to read and atomically replace the persisted non-secret profile fields and managed Channel mapping collection.

#### Scenario: Read the profile

- **WHEN** a caller sends `GET /api/oie/settings`
- **THEN** Healthcare Lab returns the Management API settings, listener settings, managed Channel mappings, and password configuration state

#### Scenario: Update the profile

- **WHEN** a caller sends a valid complete profile to `PUT /api/oie/settings`
- **THEN** Healthcare Lab atomically saves the profile fields and replaces the managed Channel mapping collection
- **AND** the response returns the complete saved profile without the password

#### Scenario: A profile update is invalid

- **WHEN** any field or managed Channel mapping in an update fails validation
- **THEN** Healthcare Lab rejects the entire update and leaves the previously persisted profile and mappings unchanged

### Requirement: OIE settings validation returns actionable errors

Healthcare Lab SHALL validate the OIE Management API URL, username, numeric timeout, result listener host and port, and managed Channel mapping identity before persistence.

#### Scenario: Reject an invalid Management API URL

- **WHEN** the Management API URL does not use HTTP or HTTPS or does not contain a host
- **THEN** Healthcare Lab rejects the update with an error identifying the Management API URL and its required form

#### Scenario: Reject missing required text

- **WHEN** the username, result listener host, mapping logical type, or mapping Channel name is empty
- **THEN** Healthcare Lab rejects the update with an error naming the missing field

#### Scenario: Reject an invalid timeout

- **WHEN** the Management API timeout is non-numeric or not positive
- **THEN** Healthcare Lab rejects the update with an error stating that the timeout must be a positive number

#### Scenario: Reject an invalid listener port

- **WHEN** the result listener port is non-numeric or outside `1-65535`
- **THEN** Healthcare Lab rejects the update with an error stating the numeric port range

### Requirement: Managed Channel mappings preserve logical OIE identity

Healthcare Lab SHALL persist managed Channel mappings containing logical type, OIE Channel ID, Channel name, template version, and last known revision, with at most one mapping for each logical type in the local profile.

#### Scenario: Save a planned Channel mapping

- **WHEN** a valid mapping has a logical type and Channel name but the Channel has not yet been deployed
- **THEN** Healthcare Lab saves the mapping with an empty OIE Channel ID, template version, or last known revision as supplied

#### Scenario: Reject duplicate logical types

- **WHEN** an update contains more than one managed Channel mapping with the same logical type
- **THEN** Healthcare Lab rejects the update with an error identifying the duplicate logical type

#### Scenario: Return persisted Channel metadata

- **WHEN** a caller reads a profile containing managed Channel mappings
- **THEN** each mapping includes its logical type, OIE Channel ID, Channel name, template version, and last known revision

### Requirement: Persisted listener intent does not change runtime state

Healthcare Lab SHALL store result listener configuration as desired settings without starting, stopping, or reconfiguring the runtime listener as part of the persistence operation, and SHALL disclose when changed listener intent still requires an explicit Retry/Start or lab-app restart before it is active.

#### Scenario: Save auto-start intent

- **WHEN** a caller saves result listener settings with auto-start enabled
- **THEN** Healthcare Lab persists the value without starting the result listener

#### Scenario: Save changed listener settings

- **WHEN** a caller successfully saves listener host, port, MLLP framing, or auto-start values that differ from the previously persisted profile
- **THEN** Healthcare Lab reports that the listener runtime has not applied the changed intent
- **AND** the Settings UI displays a persistent reminder to Retry/Start the listener or restart lab-app

#### Scenario: Save settings unrelated to the listener

- **WHEN** a caller saves a profile without changing any result-listener value
- **THEN** Healthcare Lab does not claim that a listener reload is required by that save

### Requirement: Lifecycle mapping changes are targeted and concurrency-safe

Healthcare Lab SHALL update or clear one managed Channel mapping without replacing unrelated settings or mappings and SHALL compare expected prior identity and revision values before persistence.

#### Scenario: Created Channel identity is persisted
- **WHEN** lifecycle creation reads back a managed Channel ID and revision
- **THEN** the repository updates only that logical type's mapping
- **AND** preserves every unrelated profile field and mapping

#### Scenario: Deleted Channel identity is cleared
- **WHEN** lifecycle deletion succeeds
- **THEN** the repository retains logical type, Channel name, and template version
- **AND** clears only the deleted Channel ID and last-known revision

#### Scenario: Local mapping changed concurrently
- **WHEN** the stored Channel ID or revision differs from the lifecycle operation's expected prior values
- **THEN** the targeted persistence operation fails with a conflict
- **AND** does not overwrite the newer mapping or unrelated settings

### Requirement: Managed Channel lifecycle audits are durable and secret-safe

Healthcare Lab SHALL persist append-only managed Channel lifecycle audit records containing only the approved bounded operation metadata and MUST NOT persist secrets, PHI, complete Channel payloads, HL7 messages, or arbitrary upstream bodies.

#### Scenario: Audit and mapping update follow an OIE mutation
- **WHEN** an OIE mutation succeeds and its mapping must be updated
- **THEN** Healthcare Lab writes the targeted mapping change and corresponding audit record in one local transaction

#### Scenario: Audit records are inspected
- **WHEN** stored lifecycle audit data is read or tested
- **THEN** it contains no password, cookie, authorization material, patient identifier, message content, or complete Channel payload

#### Scenario: First-release retention applies
- **WHEN** audit records age
- **THEN** they remain stored until a later explicit retention policy is implemented

### Requirement: Runtime port settings have unambiguous ownership

Healthcare Lab SHALL distinguish OIE container listener ports, HLAB container listener ports, Management API ports, and host-published ports so one setting does not configure two different delivery endpoints.

#### Scenario: Default Docker delivery contract is inspected
- **WHEN** the default managed runtime is configured
- **THEN** HLAB-to-OIE uses OIE container port `6600`, AP-to-OIE uses OIE container port `6661`, and OIE-to-HLAB uses `lab-app:6665`
- **AND** host-published ports are represented separately from those container endpoints

#### Scenario: A host-published port changes
- **WHEN** an operator changes a Compose host-published port
- **THEN** Healthcare Lab identifies that container recreation is required
- **AND** does not imply that Channel redeploy alone applies the mapping

### Requirement: Settings mutations are audited safely

Healthcare Lab SHALL append a bounded Settings audit record in the same local transaction as each successful profile mutation and MUST NOT store setting values, credentials, PHI, or complete payloads in that audit.

#### Scenario: Settings are updated
- **WHEN** a valid OIE Settings mutation commits
- **THEN** its audit records actor, operation, changed approved field paths, outcome, and timestamp
- **AND** contains neither old nor new field values

#### Scenario: Settings validation fails
- **WHEN** an invalid Settings mutation is rejected before persistence
- **THEN** the prior profile remains unchanged
- **AND** no successful mutation audit is recorded

### Requirement: OIE settings participate in the shared typed settings boundary

Healthcare Lab SHALL expose the existing local OIE settings profile through the shared typed integration-settings reader and mutation contracts while preserving the specialized OIE schema, managed Channel mappings, lifecycle concurrency guards, and existing public API behavior.

#### Scenario: A shared consumer reads OIE configuration

- **WHEN** an application-composed consumer requests effective OIE settings through the shared boundary
- **THEN** the OIE adapter loads the persisted local OIE profile and returns its typed effective configuration
- **AND** does not expose the Management API password through a public projection

#### Scenario: OIE settings are updated through the shared boundary

- **WHEN** a valid OIE profile mutation is dispatched through the shared settings service
- **THEN** Healthcare Lab delegates validation and persistence to the specialized OIE settings model
- **AND** preserves atomic mapping replacement, targeted lifecycle mapping operations, and existing audit protections

#### Scenario: Shared bootstrap encounters an existing OIE profile

- **WHEN** shared settings initialization finds the specialized OIE profile already persisted
- **THEN** it treats that profile as authoritative and does not recreate, migrate into a generic profile, or overwrite it from environment values
