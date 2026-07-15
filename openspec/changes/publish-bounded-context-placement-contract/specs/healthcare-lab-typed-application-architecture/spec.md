## ADDED Requirements

### Requirement: Bounded contexts have an implementation-ready placement map

Healthcare Lab SHALL publish target backend, frontend, and test trees and SHALL assign every current patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane responsibility in retained large modules to a named destination. The placement map SHALL identify the responsibility category, current compatibility source, target owner, and mirrored test destination.

#### Scenario: Contributor locates an existing responsibility destination

- **WHEN** a contributor plans to move or extend a responsibility currently held by a large compatibility module
- **THEN** the placement map identifies its bounded context, owning layer and module destination, and corresponding test package

#### Scenario: Contributor places a new responsibility

- **WHEN** an engineer or Codex classifies new behavior by bounded context and by HTTP, workflow, transport, runtime, persistence, domain, template, or composition responsibility
- **THEN** the documented decision process yields a named production destination and mirrored test destination outside the catch-all modules

### Requirement: Compatibility facades are explicit migration seams

Healthcare Lab SHALL enumerate allowed compatibility facades and their owning destinations. A compatibility facade MAY re-export or delegate existing behavior during incremental migration, but MUST NOT own new SQL, payload, workflow, or transport implementation, and new callers MUST import the owning module directly.

#### Scenario: Existing caller uses an allowed facade

- **WHEN** an existing caller still imports a symbol through an enumerated compatibility facade
- **THEN** the facade delegates or re-exports the implementation from its named owner without changing observable behavior

#### Scenario: New behavior targets a compatibility module

- **WHEN** a change attempts to add SQL, payload, workflow, or transport implementation to a compatibility facade or retained catch-all module
- **THEN** the architecture contract rejects the placement and directs the responsibility to its named owner

### Requirement: Catch-all enforcement preserves only a reviewed legacy baseline

Architecture tests SHALL inspect the named backend and frontend catch-all modules for SQL, payload, workflow, and transport implementation. Existing implementation MAY remain through an explicit reviewed baseline so migration can proceed incrementally, but new or materially changed classified implementation MUST be rejected. Removing legacy implementation and shrinking the baseline SHALL remain valid.

#### Scenario: Existing baseline remains during incremental migration

- **WHEN** the architecture contract inspects unchanged classified implementation represented by the reviewed legacy baseline
- **THEN** the contract permits it without requiring a broad extraction

#### Scenario: New monolithic implementation is introduced

- **WHEN** a catch-all module contains classified implementation that is not represented by the reviewed baseline
- **THEN** the architecture test fails with a diagnostic containing category, path, and current source line

#### Scenario: Legacy responsibility is extracted

- **WHEN** implementation moves from a catch-all module to its named owner and the corresponding baseline entry is removed
- **THEN** the architecture contract passes without requiring replacement compatibility implementation

### Requirement: Bounded-context dependencies point inward

Within each bounded context, APIs and runtime composition SHALL invoke services; services SHALL coordinate client and repository ports; clients, repositories, and templates SHALL depend only on allowed lower-level configuration and domain types; domain modules SHALL remain framework-independent; and cross-context coordination SHALL reside in an explicitly named service rather than importing another context's API or concrete repository.

#### Scenario: Architecture dependencies are checked across contexts

- **WHEN** architecture tests inspect imports for patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane modules
- **THEN** dependencies follow the published direction and no lower layer imports an API module or unrelated concrete repository
