## ADDED Requirements

### Requirement: Settings provides a complete Medplum workspace
The modular Settings workspace SHALL provide feature-owned controls for every persisted Medplum field, write-only secret management, save, explicit secret removal, and Save-and-test results.

#### Scenario: Operator configures Medplum
- **WHEN** the operator activates the Medplum Settings section
- **THEN** the form loads the persisted non-secret values and client-secret configured state
- **AND** labels the FHIR base URL as internal application traffic
- **AND** labels the Web UI URL as browser-facing navigation
- **AND** explains that blank secret input preserves the saved secret

#### Scenario: Save and test completes partially
- **WHEN** a valid profile saves but one or more connection stages fail
- **THEN** the workspace confirms that settings were saved
- **AND** renders metadata, OAuth, and authenticated-read outcomes separately
- **AND** does not collapse the results into a single ambiguous connection status

#### Scenario: Validation fails
- **WHEN** the operator submits an invalid URL, timeout, grace period, or other typed field
- **THEN** the workspace maps stable field errors to the owning controls
- **AND** leaves the previous persisted profile active
