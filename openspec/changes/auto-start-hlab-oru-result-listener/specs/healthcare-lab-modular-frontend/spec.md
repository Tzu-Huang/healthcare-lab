## ADDED Requirements

### Requirement: Settings exposes unapplied listener intent

The modular Settings frontend SHALL tell the operator when a successful Settings save changed listener intent that the running listener has not applied, without adding managed-Channel editing behavior to this change.

#### Scenario: Changed listener settings are saved

- **WHEN** the Settings API confirms that changed listener intent was persisted but not applied to runtime
- **THEN** the Settings view displays a persistent reminder that the operator must Retry/Start the listener or restart lab-app
- **AND** the reminder does not claim that refreshing the browser alone rebinds the listener

#### Scenario: Listener settings are applied

- **WHEN** a later listener Status reports the persisted configuration is running
- **THEN** the Settings view clears the unapplied-listener reminder

#### Scenario: Unrelated settings are saved

- **WHEN** a successful Settings save does not change listener intent
- **THEN** the Settings view does not introduce an unapplied-listener reminder for that save
