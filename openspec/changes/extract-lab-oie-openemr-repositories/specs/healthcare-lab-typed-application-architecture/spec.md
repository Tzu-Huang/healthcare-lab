## ADDED Requirements

### Requirement: Lab control-plane persistence has a dedicated owner

Healthcare Lab SHALL provide a lab control-plane repository that owns lab server registry, persisted health state, and operation history through the shared SQLite connection factory and application write lock. Lab workflow services SHALL depend on a narrow lab repository port rather than requiring `DemoStore` for these operations.

#### Scenario: Lab workflow uses extracted persistence

- **WHEN** a lab workflow lists or updates servers, persists health, or records operation history
- **THEN** the operation is performed by the lab repository using the shared SQLite owner and not by SQL in `DemoStore`

#### Scenario: Concurrent lab writes share coordination

- **WHEN** a legacy `DemoStore` caller and a directly composed lab repository write to the same database
- **THEN** both writes use the same reentrant application lock and retain existing transaction behavior

### Requirement: OIE result persistence has a dedicated owner

Healthcare Lab SHALL provide OIE repositories that own settings and inbound result persistence, including error records, duplicate message-control detection, persisted matching references, and result row mapping. OIE services and runtime listeners SHALL depend on narrow OIE ports for these operations.

#### Scenario: Inbound OIE result is persisted

- **WHEN** the OIE listener accepts a valid, duplicate, unmatched, or invalid result message
- **THEN** the OIE result repository preserves the current record, matching, duplicate, error, and response semantics without SQL in `DemoStore`

#### Scenario: OIE workbench crosses bounded contexts

- **WHEN** the OIE workbench combines patient, order, and OIE result data
- **THEN** a service coordinates the required narrow ports and the OIE repository remains limited to OIE-owned persistence

### Requirement: OpenEMR external query ownership is separate from SQLite persistence

Healthcare Lab SHALL isolate OpenEMR MariaDB connection and procedure-order query behavior in a dedicated external adapter. OpenEMR row normalization and conversion to the existing GDT order projection SHALL remain framework-independent, and no OpenEMR SQL SHALL be owned by a SQLite repository or `DemoStore`.

#### Scenario: Query configured OpenEMR procedure orders

- **WHEN** the application lists or verifies configured OpenEMR ECG procedure orders
- **THEN** the external adapter executes the MariaDB query and returns the same order and verification projections as before extraction

#### Scenario: OpenEMR schema is unavailable

- **WHEN** the configured MariaDB reports a supported missing procedure-order table condition
- **THEN** the adapter preserves the existing empty-list or degraded verification behavior without changing SQLite state

### Requirement: Extracted boundaries retain compatibility-only DemoStore seams

`DemoStore` SHALL expose only explicit delegation for retained lab and OIE methods needed by existing callers. New composition and service code MUST use the owning repository or external adapter directly, and architecture enforcement SHALL remove the extracted implementation from the reviewed legacy baseline without adding replacement exceptions.

#### Scenario: Existing caller uses DemoStore

- **WHEN** an existing caller invokes a retained lab or OIE persistence method on `DemoStore`
- **THEN** `DemoStore` delegates to the owning repository and returns the existing result shape and errors

#### Scenario: Architecture contract inspects extraction

- **WHEN** architecture tests inspect `lab_store.py` and the responsibility-specific modules
- **THEN** extracted SQL and OpenEMR query implementation are absent from `lab_store.py`, lower layers follow the declared dependency direction, and no new legacy-baseline exception is required

### Requirement: Repository extraction verification is isolated and behavior-preserving

Automated verification SHALL cover the extracted repositories, external adapter, domain mapping, service ports, compatibility delegates, and architecture boundaries using disposable SQLite databases and external-service test doubles.

#### Scenario: Run extraction verification

- **WHEN** focused and full automated tests execute
- **THEN** no repository `instance/*.db` or live OpenEMR/OIE service is accessed and existing APIs, stored data semantics, and startup behavior remain compatible
