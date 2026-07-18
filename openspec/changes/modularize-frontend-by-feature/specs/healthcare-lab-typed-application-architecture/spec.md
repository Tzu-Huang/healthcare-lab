## MODIFIED Requirements

### Requirement: Future frontend work has modular destinations
Project architecture guidance SHALL direct ZAC-50 and later frontend behavior to categorized core, API, view, component, and state JavaScript modules; layered base, layout, component, and view CSS directories; and feature-owned Flask template destinations rather than extending the monolithic `app.js`, `styles.css`, or `index.html` files. The guidance SHALL define dependency direction, thin compatibility entrypoints, matching production/test feature names, and the milestone at which OIE and Settings destinations are ready for ZAC-50 without requiring a frontend framework or build system.

#### Scenario: ZAC-50 planning selects frontend destinations
- **WHEN** the Settings workspace work is planned or implemented
- **THEN** its API access, views, components, state, styles, markup, and focused verification each have a documented modular destination
- **AND** new Settings business behavior is not added to a legacy catch-all entrypoint

#### Scenario: Frontend production and test ownership are coordinated
- **WHEN** ZAC-63 extracts a feature and ZAC-64 reorganizes the related tests
- **THEN** architecture guidance identifies matching feature owners, allowed compatibility seams, assertion-migration responsibility, and the focused verification command required before cleanup
