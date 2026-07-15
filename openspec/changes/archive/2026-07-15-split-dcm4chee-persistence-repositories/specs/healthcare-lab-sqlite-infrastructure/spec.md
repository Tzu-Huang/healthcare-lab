## ADDED Requirements

### Requirement: MWL persistence owns deterministic historical backfill

Healthcare Lab SHALL assign historical dcm4chee MWL mapping repair to the MWL persistence boundary while the shared SQLite infrastructure retains ordered startup maintenance, the initialization lock, and the active initialization transaction.

#### Scenario: Historical attempts have no mapping

- **WHEN** startup encounters eligible historical MWL attempts without a canonical mapping
- **THEN** the MWL backfill creates only missing mappings using the established deterministic latest-attempt rules
- **AND** it links eligible unmapped attempts without overwriting existing mappings or user-managed data

#### Scenario: Backfill is invoked during initialization

- **WHEN** shared database initialization runs MWL maintenance
- **THEN** the backfill uses the supplied active connection and shared initialization lock
- **AND** it does not open an independent connection, commit separately, or change maintenance ordering

#### Scenario: Backfill verification runs

- **WHEN** automated backfill or migration verification executes
- **THEN** it operates only on disposable databases
- **AND** no repository `instance/*.db` or live external service is accessed or modified
