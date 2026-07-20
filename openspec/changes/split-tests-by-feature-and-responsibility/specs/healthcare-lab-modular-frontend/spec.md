## MODIFIED Requirements

### Requirement: ZAC-63 and ZAC-64 share verification ownership

ZAC-63 and ZAC-64 SHALL use the same feature taxonomy, SHALL retain an assertion-ownership inventory in addition to test-count comparison, and MUST complete production and test ownership before deleting catch-all source or test locations. ZAC-63 SHALL own frontend module architecture, lifecycle, static-loading, and interaction checks. ZAC-64 SHALL own broad integration and repository test organization, reusable fixtures/fakes, responsibility-suite independence, and the handoff of retained compatibility coverage to later cleanup.

#### Scenario: Production extraction and test reorganization overlap

- **WHEN** a frontend feature is extracted while ZAC-64 reorganizes related tests
- **THEN** the feature's production and assertion owners remain traceable
- **AND** its focused frontend verification command runs independently
- **AND** no assertion is discarded solely because its former file path changed

#### Scenario: Broad backend tests are reorganized after frontend modularization

- **WHEN** ZAC-64 splits integration or repository coverage for a feature already modularized by ZAC-63
- **THEN** the existing focused frontend owner remains in `tests/frontend`
- **AND** only the matching Flask, repository, domain, template, runtime, or cross-feature ownership is moved

#### Scenario: Catch-all cleanup is proposed

- **WHEN** a broad test location or compatibility seam is considered for deletion
- **THEN** the ownership inventory and focused commands show that its assertions and compatibility responsibilities already have named owners
- **AND** any remaining DemoStore compatibility coverage is recorded for the ZAC-65 cleanup boundary
