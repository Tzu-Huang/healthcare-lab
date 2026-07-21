## MODIFIED Requirements

### Requirement: Persisted listener intent does not change runtime state

Healthcare Lab SHALL store result listener configuration as desired settings without starting, stopping, or reconfiguring the runtime listener as part of the persistence operation, and SHALL disclose when changed listener intent still requires an explicit Retry/Start or lab-app restart before it is active.

#### Scenario: Save auto-start intent

- **WHEN** a caller saves result listener settings with auto-start enabled
- **THEN** Healthcare Lab persists the value without starting the result listener

#### Scenario: Save changed listener settings

- **WHEN** a caller successfully saves listener host, port, MLLP framing, or auto-start values that differ from the previously persisted profile
- **THEN** Healthcare Lab reports that the listener runtime has not applied the changed intent
- **AND** the Settings UI displays a persistent reminder to Retry/Start the listener or restart lab-app

#### Scenario: Save settings unrelated to the listener

- **WHEN** a caller saves a profile without changing any result-listener value
- **THEN** Healthcare Lab does not claim that a listener reload is required by that save
