## MODIFIED Requirements

### Requirement: Supported Docker deployments distinguish application and host paths

Healthcare Lab SHALL use `/data/gdt-bridge` as the fixed application-visible path for the supported Docker runtime and SHALL let an operator view and explicitly apply one dedicated Windows host bind-mount root through the bounded localhost deployment controller.

#### Scenario: Docker bind mount is discoverable

- **WHEN** Settings reads GDT Bridge deployment information in a supported Docker deployment
- **THEN** it identifies `/data/gdt-bridge` as the fixed application path
- **AND** displays the desired and effective host path and ownership source
- **AND** indicates whether a save, container recreation, verification, or external-override resolution is required

#### Scenario: Operator applies a new host path

- **WHEN** an operator enters a valid dedicated Windows absolute path and confirms apply
- **THEN** Settings submits one root to the bounded localhost controller
- **AND** displays progress while the controller provisions the directory contract and recreates `lab-app`
- **AND** reloads the effective deployment and diagnostics after successful verification

#### Scenario: Host controller is unavailable

- **WHEN** the application cannot safely discover or contact the host controller
- **THEN** Settings still reports `/data/gdt-bridge` as the application path
- **AND** preserves read-only desired/effective deployment metadata when available
- **AND** reports bounded wrapper fallback guidance without degrading GDT solely for controller unavailability

## ADDED Requirements

### Requirement: GDT folder setup uses one operator-owned root

Healthcare Lab SHALL ask the operator for one host bridge root and SHALL derive all supported host and container bridge subdirectories rather than requiring separate GDT-IN and GDT-OUT path coordination.

#### Scenario: GDT setup is rendered

- **WHEN** the operator opens the GDT folder setup surface
- **THEN** it provides one editable host root
- **AND** shows inbox, outbox, processing, archive, error, and diagnostic paths as derived read-only values
- **AND** does not expose `/data/gdt-bridge` as an editable deployment choice
