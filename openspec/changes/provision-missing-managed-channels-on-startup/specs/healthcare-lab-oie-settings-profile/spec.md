## MODIFIED Requirements

### Requirement: Healthcare Lab persists one local OIE settings profile

Healthcare Lab SHALL persist one local OIE settings profile containing Management API connection settings, HLAB result listener settings, and desired mappings for both canonical managed Channels without changing the existing Patient, Order, or OIE Result data model.

#### Scenario: A new database receives local defaults

- **WHEN** Healthcare Lab initializes a database without an OIE settings profile
- **THEN** it creates a local profile with Management API URL `http://oie:8080`, username `admin`, a configured case-sensitive password value of `Admin`, TLS verification disabled, and a 10-second request timeout
- **AND** its result listener settings are host `0.0.0.0`, port `6665`, MLLP framing enabled, and auto-start enabled
- **AND** it persists empty-identity desired mappings for `HLAB_ORM_TO_AP` from `OIE:6600` to `AP:6671` and `HLAB_ORU_TO_HLAB` from `OIE:6661` to `lab-app:6665`

#### Scenario: Saved settings survive restart

- **WHEN** an operator updates the OIE settings profile and Healthcare Lab initializes again using the same database
- **THEN** Healthcare Lab returns the previously saved profile and managed Channel mappings instead of reseeding or overwriting them with defaults

#### Scenario: Existing workflow records survive migration

- **WHEN** Healthcare Lab initializes an existing database containing Patient, Order, and OIE Result records but no OIE settings tables or canonical mapping rows
- **THEN** it adds and seeds the OIE settings schema and only missing canonical mapping intent without deleting or changing existing workflow records or mapping rows
