# healthcare-lab-oie-settings-profile Specification

## Purpose
Define Healthcare Lab's persistent, secret-safe OIE settings profile for Management API access, HLAB result listener intent, and managed Channel identity mappings.
## Requirements
### Requirement: Healthcare Lab persists one local OIE settings profile

Healthcare Lab SHALL persist one local OIE settings profile containing Management API connection settings, HLAB result listener settings, and managed Channel mappings without changing the existing Patient, Order, or OIE Result data model.

#### Scenario: A new database receives local defaults

- **WHEN** Healthcare Lab initializes a database without an OIE settings profile
- **THEN** it creates a local profile with Management API URL `http://oie:8080`, username `admin`, a configured case-sensitive password value of `Admin`, TLS verification disabled, and a 10-second request timeout
- **AND** its result listener settings are host `0.0.0.0`, port `6665`, MLLP framing enabled, and auto-start enabled

#### Scenario: Saved settings survive restart

- **WHEN** an operator updates the OIE settings profile and Healthcare Lab initializes again using the same database
- **THEN** Healthcare Lab returns the previously saved profile and managed Channel mappings instead of reseeding the defaults

#### Scenario: Existing workflow records survive migration

- **WHEN** Healthcare Lab initializes an existing database containing Patient, Order, and OIE Result records but no OIE settings tables
- **THEN** it adds and seeds the OIE settings schema without deleting or changing those existing records

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

Healthcare Lab SHALL store result listener configuration as desired settings without starting, stopping, or reconfiguring the runtime listener as part of this capability.

#### Scenario: Save auto-start intent

- **WHEN** a caller saves result listener settings with auto-start enabled
- **THEN** Healthcare Lab persists the value without starting the result listener

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
