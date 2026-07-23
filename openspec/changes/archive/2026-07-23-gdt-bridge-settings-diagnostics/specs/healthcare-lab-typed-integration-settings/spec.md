## ADDED Requirements

### Requirement: GDT runtime configuration has typed ownership and one-time bootstrap

Healthcare Lab SHALL classify the host bind mount as deployment-only, persist GDT runtime behavior in a named typed profile, and resolve safe Docker topology defaults without creating a competing source of truth.

#### Scenario: Missing GDT profile is bootstrapped
- **WHEN** Healthcare Lab starts without a persisted GDT Bridge profile
- **THEN** it atomically seeds safe defaults plus eligible legacy environment runtime values
- **AND** records value-free bootstrap provenance
- **AND** treats the resulting profile as authoritative on later starts

#### Scenario: Persisted GDT profile exists
- **WHEN** Healthcare Lab restarts with a persisted GDT Bridge profile and different environment values
- **THEN** runtime consumers retain the persisted profile
- **AND** do not silently overwrite it from the environment

#### Scenario: Background GDT consumer requests configuration
- **WHEN** the watcher, exporter, importer, readiness provider, or diagnostic service requests GDT configuration outside a request context
- **THEN** it receives the same immutable effective typed profile projection
- **AND** does not read GDT runtime values directly from environment variables or raw SQL
