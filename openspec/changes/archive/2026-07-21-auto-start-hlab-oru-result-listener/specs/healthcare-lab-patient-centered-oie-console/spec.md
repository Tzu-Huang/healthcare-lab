## MODIFIED Requirements

### Requirement: Lab app receives OIE-routed ORU results

Healthcare Lab SHALL provide a local, single-process MLLP result listener for OIE -> lab-app ORU messages, configured only from persisted OIE Settings and controllable through explicit Start, Stop, Retry, and Status APIs.

#### Scenario: Auto-start is enabled

- **WHEN** lab-app starts with persisted listener auto-start enabled
- **THEN** Healthcare Lab attempts once to bind the persisted host and port with the persisted MLLP framing value
- **AND** the default persisted configuration listens on `0.0.0.0:6665`

#### Scenario: Auto-start is disabled

- **WHEN** lab-app starts with persisted listener auto-start disabled
- **THEN** Healthcare Lab leaves the listener stopped without attempting to bind

#### Scenario: Auto-start cannot bind

- **WHEN** the persisted listener endpoint cannot be bound during lab-app startup
- **THEN** Healthcare Lab keeps the web application available
- **AND** listener Status reports `degraded`, the attempted configuration, and an actionable error summary

#### Scenario: User starts the listener

- **WHEN** the user invokes Start while the listener is stopped
- **THEN** Healthcare Lab loads the latest persisted listener Settings and starts listening for result messages
- **AND** the Start API does not accept host, port, or MLLP runtime overrides

#### Scenario: User repeats Start

- **WHEN** Start is invoked repeatedly while the listener is already running with the same persisted configuration
- **THEN** Healthcare Lab returns the existing running status without creating another listener socket or thread

#### Scenario: User retries a degraded listener

- **WHEN** the listener is degraded and the user invokes Retry after correcting the conflict or persisted configuration
- **THEN** Healthcare Lab reloads the latest persisted Settings and attempts to start the listener
- **AND** a successful retry clears the prior error and reports `running`

#### Scenario: User stops the listener

- **WHEN** the listener is running and the user invokes Stop
- **THEN** Healthcare Lab stops accepting new listener connections and reports `stopped`
- **AND** it does not change the persisted auto-start value
- **AND** a later lab-app restart reapplies the persisted auto-start intent

#### Scenario: Runtime settings differ while listener is running

- **WHEN** Start or Retry loads persisted settings that differ from the configuration of an already-running listener
- **THEN** Healthcare Lab rejects the transition with an actionable instruction to Stop before applying the changed configuration

#### Scenario: More than one process attempts ownership

- **WHEN** another lab-app process already owns the configured endpoint
- **THEN** this process reports degraded listener status without preventing its web application from starting
