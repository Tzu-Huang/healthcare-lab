## MODIFIED Requirements

### Requirement: ZAC-50 uses the modular OIE and Settings foundation

The modular frontend SHALL implement the complete OIE Settings and managed-Channel workspace in categorized Settings API, view, state/component, style, template, and verification destinations and SHALL keep legacy catch-all assets as thin loading or compatibility entrypoints.

#### Scenario: ZAC-50 product implementation is present
- **WHEN** the OIE Settings workspace provides connection, listener, or managed-Channel interactions
- **THEN** each behavior is owned by its modular destination and does not extend legacy global business logic

#### Scenario: Existing partial Settings owners are consolidated
- **WHEN** overlapping listener and managed-Channel fragments are integrated
- **THEN** each module has one valid declaration and initialization path
- **AND** navigation activates and refreshes Settings without duplicate listeners or browser errors

### Requirement: Major views have interaction verification

Automated verification SHALL exercise sidebar navigation, initialization without unexpected browser errors, and representative interactions for dashboard, patient, order, FHIR, dcm4chee, OIE, GDT, and the complete Settings workspace. Verification SHALL retain existing backend regression coverage and MUST NOT depend on live external services.

#### Scenario: Frontend reaches the ZAC-50 quality gate
- **WHEN** focused or full frontend verification runs
- **THEN** every major view initializes and performs its representative interaction using the test application and controlled doubles without live OIE, Medplum, dcm4chee, OpenEMR, GDT, or real listener binding
- **AND** Settings coverage includes connection testing, listener status/control, external read-only presentation, preview-bound mutation, delete confirmation, and narrow responsive layout

### Requirement: Settings exposes unapplied listener intent

The modular Settings frontend SHALL tell the operator when a successful Settings save changed listener intent that the running listener has not applied and SHALL coordinate that status with its listener controls and managed ORU route presentation.

#### Scenario: Changed listener settings are saved
- **WHEN** the Settings API confirms that changed listener intent was persisted but not applied to runtime
- **THEN** the Settings view displays a persistent reminder that the operator must Stop/Retry or restart lab-app
- **AND** the reminder does not claim that refreshing the browser alone rebinds the listener

#### Scenario: Listener settings are applied
- **WHEN** a later listener Status reports the persisted configuration is running
- **THEN** the Settings view clears the unapplied-listener reminder

#### Scenario: Changed port affects the managed route
- **WHEN** the saved HLAB listener port differs from the destination port represented by the managed ORU route or runtime exposure
- **THEN** Settings identifies the mismatch and directs the operator to preview/apply the Channel change and review Docker/runtime configuration
