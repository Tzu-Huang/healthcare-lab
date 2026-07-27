## MODIFIED Requirements

### Requirement: Save and test reports independent bounded stages
Healthcare Lab SHALL save a valid Medplum profile, run separate bounded checks for FHIR metadata reachability, OAuth token acquisition, and an authenticated FHIR read, and persist only the allowlisted outcome associated with the configuration revision that was tested.

#### Scenario: All checks succeed
- **WHEN** the saved metadata endpoint is reachable, OAuth credentials acquire a token, and a bounded authenticated FHIR read succeeds
- **THEN** each stage reports success independently
- **AND** the successful bounded outcome is associated with the tested configuration revision
- **AND** the result contains no access token or FHIR resource body

#### Scenario: A stage fails
- **WHEN** metadata, token acquisition, or authenticated read fails
- **THEN** that stage reports a stable bounded failure
- **AND** other applicable stages retain their own results
- **AND** the valid saved profile remains persisted
- **AND** only allowlisted stage state and category evidence is retained for the tested configuration revision

#### Scenario: Credentials are absent
- **WHEN** metadata is reachable but OAuth credentials are not configured
- **THEN** metadata reports its observed result
- **AND** OAuth and authenticated-read stages report a bounded not-configured or skipped state

#### Scenario: Application restarts after a failed check
- **WHEN** a failed bounded result exists for the current Medplum configuration revision and the application restarts or its container is recreated with retained storage
- **THEN** Healthcare Lab retains the failed bounded result
- **AND** does not infer success from configured fields alone

#### Scenario: Medplum configuration changes after a check
- **WHEN** an authentication- or connectivity-relevant field or secret changes after a bounded result was recorded
- **THEN** the prior result no longer verifies the new configuration revision
- **AND** no secret value or secret-derived fingerprint is persisted in the verification evidence
