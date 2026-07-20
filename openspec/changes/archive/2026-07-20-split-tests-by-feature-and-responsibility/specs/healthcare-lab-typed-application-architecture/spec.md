## MODIFIED Requirements

### Requirement: Tests mirror production responsibilities

Automated tests SHALL be organized by API, service, client, runtime, repository, domain, template, integration, compatibility, or E2E responsibility as applicable, while retaining the existing regression assertions. Each responsibility SHALL have a named owner, reusable setup SHALL remain separate from behavior assertions, and focused suites SHALL be independently runnable.

#### Scenario: Contributor locates coverage for a module

- **WHEN** a contributor changes a responsibility-specific production module
- **THEN** the corresponding focused tests are available in the matching responsibility-oriented test package
- **AND** the test owner is recorded in the project assertion-ownership inventory

#### Scenario: Shared setup is extracted

- **WHEN** multiple responsibility suites require the same disposable database, application factory, or external-service fake
- **THEN** the setup is reusable without moving feature assertions into the helper or a new catch-all test module

#### Scenario: Responsibility suite runs independently

- **WHEN** a focused verification command runs for one responsibility
- **THEN** that suite executes without importing unrelated live services, committed databases, or another feature's private test state

#### Scenario: Existing catch-all coverage is reorganized

- **WHEN** assertions move out of a broad integration or store test file
- **THEN** every retained assertion has a named new owner before the old location is removed
- **AND** test-ID and collection-count comparison explains intentional additions or removals
