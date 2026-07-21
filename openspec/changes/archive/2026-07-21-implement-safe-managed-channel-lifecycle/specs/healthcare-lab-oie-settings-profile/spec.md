## ADDED Requirements

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
