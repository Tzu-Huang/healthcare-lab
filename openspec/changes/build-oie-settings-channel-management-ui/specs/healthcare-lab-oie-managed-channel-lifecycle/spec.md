## MODIFIED Requirements

### Requirement: Deployment operations are single-target and ownership-safe

Healthcare Lab SHALL deploy, redeploy, or undeploy only one explicitly identified managed Channel after refreshed ownership and revision validation and SHALL NOT expose the OIE redeploy-all primitive.

#### Scenario: Managed Channel is deployed
- **WHEN** a valid deploy preview targets an exact managed Channel
- **THEN** Healthcare Lab invokes deploy only for that Channel ID
- **AND** returns its refreshed status

#### Scenario: Managed Channel is redeployed
- **WHEN** a valid redeploy preview targets one exact deployed managed Channel
- **THEN** Healthcare Lab invokes undeploy and then deploy only for that Channel ID
- **AND** returns ordered step outcomes and refreshed status

#### Scenario: Managed Channel is undeployed
- **WHEN** a valid undeploy preview targets an exact managed Channel
- **THEN** Healthcare Lab invokes undeploy only for that Channel ID
- **AND** returns its refreshed status

#### Scenario: Redeploy-all exists in the low-level client
- **WHEN** managed lifecycle capabilities are presented through the API or UI
- **THEN** redeploy-all is not exposed or invoked

#### Scenario: External target is requested
- **WHEN** a deploy, redeploy, or undeploy request resolves to an external or conflicted Channel
- **THEN** Healthcare Lab rejects it before invoking an OIE mutation

### Requirement: Managed Channel deletion is bounded and recreatable

Healthcare Lab SHALL delete only one exact managed Channel after a state-bound preview and exact displayed Channel-name confirmation, SHALL undeploy it first when required, and SHALL retain its logical template mapping while clearing the deleted OIE Channel ID and revision.

#### Scenario: Managed Channel is deleted
- **WHEN** a valid delete preview and matching exact displayed Channel-name confirmation remain current
- **THEN** Healthcare Lab undeploys the exact Channel if necessary and deletes only that Channel ID
- **AND** clears its persisted OIE Channel ID and last-known revision
- **AND** subsequent inspection reports the template as `Missing` and permits recreation

#### Scenario: Confirmation does not match displayed Channel name
- **WHEN** delete confirmation differs from the previewed Channel name
- **THEN** Healthcare Lab rejects deletion before calling OIE

#### Scenario: Undeploy succeeds but delete fails
- **WHEN** deletion fails after a required undeploy succeeds
- **THEN** Healthcare Lab reports `partial-failure` with both step outcomes
- **AND** a retry refreshes status and ownership before deciding whether deletion is still safe

#### Scenario: External or conflicted Channel is selected
- **WHEN** delete targets a Channel without exact managed identity
- **THEN** Healthcare Lab rejects deletion and does not undeploy or delete it
