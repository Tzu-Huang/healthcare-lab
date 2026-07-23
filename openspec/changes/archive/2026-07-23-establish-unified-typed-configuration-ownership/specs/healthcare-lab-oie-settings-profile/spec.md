## ADDED Requirements

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
