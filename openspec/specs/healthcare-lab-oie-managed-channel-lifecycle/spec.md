# healthcare-lab-oie-managed-channel-lifecycle Specification

## Purpose
TBD - created by archiving change implement-safe-managed-channel-lifecycle. Update Purpose after archive.
## Requirements
### Requirement: Managed Channel inventory is classified conservatively

Healthcare Lab SHALL combine approved templates, persisted mappings, and the complete live OIE Channel inventory to classify expected managed Channels as `Missing`, `Unchanged`, `Drifted`, or `Conflict`, and SHALL classify unrelated Channels as external and read-only.

#### Scenario: Expected Channel is missing
- **WHEN** no live Channel matches the expected managed identity and no contradictory same-name or marker candidate exists
- **THEN** the lifecycle reports the expected Channel as `Missing`
- **AND** permits previewing creation

#### Scenario: Managed Channel is unchanged
- **WHEN** the persisted Channel ID and expected marker identify one live Channel whose normalized owned state equals the desired template
- **THEN** the lifecycle reports `Unchanged`
- **AND** does not propose an update

#### Scenario: Managed Channel has approved-field drift
- **WHEN** exact managed identity is established and normalized owned fields differ from the desired template
- **THEN** the lifecycle reports `Drifted`
- **AND** identifies the changed owned-field paths

#### Scenario: Same name is not ownership
- **WHEN** a live Channel has an expected display name but lacks the exact expected marker and identity
- **THEN** the lifecycle reports `Conflict`
- **AND** does not adopt or mutate that Channel

#### Scenario: Identity evidence is ambiguous
- **WHEN** mappings, IDs, markers, logical types, duplicate candidates, or payload structure provide contradictory ownership evidence
- **THEN** the lifecycle reports `Conflict` with bounded safe reasons
- **AND** permits no mutation

#### Scenario: External Channel is listed
- **WHEN** a live Channel does not claim an expected Healthcare Lab managed identity
- **THEN** it is exposed as external and read-only
- **AND** no managed lifecycle action is permitted for it

### Requirement: Every mutation requires a state-bound preview

Healthcare Lab MUST produce a side-effect-free preview before mutation and MUST bind authorization to one operation, one logical type, the exact observed Channel identity and revision, and the desired normalized state for a bounded time.

#### Scenario: Preview reports a create
- **WHEN** an operator previews creation for a `Missing` managed Channel
- **THEN** the response describes the Channel to be created and returns a bounded mutation token
- **AND** no OIE mutation occurs

#### Scenario: Preview reports an update
- **WHEN** an operator previews a `Drifted` managed Channel
- **THEN** the response lists only approved owned-field differences and the observed revision
- **AND** returns a mutation token bound to those facts

#### Scenario: Preview finds no change
- **WHEN** the managed Channel is `Unchanged`
- **THEN** the response reports a no-op
- **AND** does not issue a mutation token for update

#### Scenario: Preview finds a conflict
- **WHEN** the managed Channel is `Conflict`
- **THEN** the response explains the blocking identity or revision facts without secrets or PHI
- **AND** does not issue a mutation token

#### Scenario: Mutation token is stale or mismatched
- **WHEN** the token is expired, targets another operation or logical type, or live identity, revision, classification, or desired state changed after preview
- **THEN** Healthcare Lab rejects the mutation before any OIE write
- **AND** requires a fresh preview

### Requirement: YOLO-resistant mutation boundaries fail closed

Healthcare Lab MUST provide no force, wildcard, bulk, skip-preview, automatic-adoption, or revision-override path for managed Channel mutations, and SHALL revalidate ownership and live state immediately before every mutation. Automatic startup mutation is limited to guarded single-target creation and deployment of Channels classified as missing when explicit `create-missing` bootstrap mode is enabled.

#### Scenario: Caller requests a force or override operation

- **WHEN** a caller attempts to bypass conflict, ownership, preview, or revision protection
- **THEN** Healthcare Lab rejects the request
- **AND** never calls OIE with `override=true`

#### Scenario: Caller attempts bulk mutation

- **WHEN** a request contains multiple targets, a wildcard, or an OIE redeploy-all request
- **THEN** Healthcare Lab rejects or does not expose the operation
- **AND** no managed or external Channel is mutated

#### Scenario: Application starts with bootstrap disabled

- **WHEN** Healthcare Lab starts or reloads configuration with bootstrap mode `off`
- **THEN** it does not create, update, deploy, undeploy, delete, or adopt any OIE Channel automatically

#### Scenario: Application starts with create-missing bootstrap

- **WHEN** Healthcare Lab starts with bootstrap mode `create-missing`
- **THEN** it may create and deploy only an exact managed Channel freshly classified as `Missing` through state-bound guarded operations
- **AND** it does not update, adopt, redeploy, undeploy, or delete any existing Channel

#### Scenario: Destructive confirmation does not match

- **WHEN** delete confirmation does not exactly match the targeted logical type
- **THEN** Healthcare Lab rejects deletion before calling OIE

#### Scenario: Target changes after confirmation

- **WHEN** ownership, Channel ID, revision, or classification changes between confirmation and execution
- **THEN** Healthcare Lab fails closed and returns a fresh-preview requirement

### Requirement: Managed Channel creation is idempotent and identity-safe

Healthcare Lab SHALL create only an expected Channel classified `Missing`, SHALL use the approved complete template, and SHALL rediscover and persist the resulting exact OIE identity and revision.

#### Scenario: Missing Channel is created
- **WHEN** a valid create preview is executed and revalidation still reports `Missing`
- **THEN** Healthcare Lab creates exactly one approved managed Channel
- **AND** reads back and persists its exact Channel ID, name, template version, and revision

#### Scenario: Create is retried after success
- **WHEN** creation succeeded but the caller retries because the prior response or local persistence was uncertain
- **THEN** Healthcare Lab refreshes the live inventory before acting
- **AND** does not create a duplicate Channel

#### Scenario: Conflicting candidate appears before create
- **WHEN** a same-name, same-marker, or mapped candidate appears after preview
- **THEN** Healthcare Lab stops before create and reports conflict or stale preview

### Requirement: Managed Channel updates preserve unowned state and revisions

Healthcare Lab SHALL retrieve the complete current Channel immediately before update, SHALL change only the approved template-owned fields, SHALL preserve all other live fields, and MUST submit the update with `override=false`.

#### Scenario: Approved settings change is applied
- **WHEN** a valid update preview remains current
- **THEN** Healthcare Lab merges approved desired fields into the complete live Channel payload
- **AND** preserves fields outside the approved edit surface
- **AND** refreshes and persists the resulting revision

#### Scenario: Reapplying identical settings
- **WHEN** refreshed normalized owned state already equals desired state
- **THEN** Healthcare Lab returns a no-op success
- **AND** does not call the OIE update primitive

#### Scenario: OIE reports a revision conflict
- **WHEN** OIE rejects an update because its revision changed
- **THEN** Healthcare Lab returns a revision-conflict failure
- **AND** does not retry with override or automatically reapply the update

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

### Requirement: Lifecycle operations return explicit step-level outcomes

Healthcare Lab SHALL return `success`, `failure`, or `partial-failure` results containing an operation ID, ordered bounded step details, stable safe error categories, and refreshed final classification when available.

#### Scenario: Operation completes
- **WHEN** every required lifecycle step succeeds or the intended state already holds
- **THEN** the result is `success` and distinguishes performed steps from no-ops

#### Scenario: Operation fails before mutation
- **WHEN** validation, ownership, preview, or refreshed-state checks fail
- **THEN** the result is `failure`
- **AND** identifies that no mutation step was attempted

#### Scenario: Operation fails after an external mutation
- **WHEN** an OIE step succeeds and a later OIE or persistence step fails
- **THEN** the result is `partial-failure`
- **AND** identifies succeeded, failed, and unattempted steps without claiming rollback

### Requirement: Lifecycle activity is audited without secrets or PHI

Healthcare Lab SHALL append durable audit events for lifecycle previews and mutation outcomes using bounded structured metadata and MUST exclude secrets, PHI, complete Channel payloads, HL7 messages, and arbitrary upstream bodies.

#### Scenario: Mutation is attempted
- **WHEN** a managed lifecycle mutation succeeds, fails, or partially fails
- **THEN** an audit event records operation ID, timestamp, actor label, operation, logical type, Channel ID when known, before/after revision, outcome/error category, and changed owned-field paths

#### Scenario: Sensitive material is present at a lower boundary
- **WHEN** credentials, cookies, headers, complete payloads, messages, patient identifiers, or upstream bodies are available during an operation
- **THEN** none of that material is written to lifecycle audit records or returned diagnostics

#### Scenario: Audit history grows
- **WHEN** lifecycle audit records accumulate in the first release
- **THEN** Healthcare Lab retains them until an explicit retention capability is introduced

### Requirement: Unmapped managed identity recovery requires unique complete evidence

Healthcare Lab SHALL classify an unmapped live Channel as recoverable only when exactly one Channel carries the exact expected Healthcare Lab marker and logical type, its complete owned payload is parseable, its identity is internally consistent, and its route is not owned by another Channel. Healthcare Lab MUST NOT infer ownership from Channel name alone.

#### Scenario: One valid marked Channel is recoverable

- **WHEN** a logical type has empty mapped identity and exactly one live Channel has its exact valid marker, logical type, parseable payload, and exclusively owned listener route
- **THEN** lifecycle reconciliation exposes that Channel as recoverable with its exact ID, name, revision, and current deployment state

#### Scenario: Duplicate ownership markers block recovery

- **WHEN** more than one live Channel carries the expected marker for one logical type
- **THEN** reconciliation classifies the identity as conflicted and permits no adoption or Channel mutation

#### Scenario: Malformed or mismatched identity blocks recovery

- **WHEN** a candidate payload is malformed, cannot normalize, has an unexpected logical type or template version, or contradicts a retained mapped identity
- **THEN** reconciliation classifies the identity as conflicted and permits no recovery or Channel mutation

#### Scenario: Same-name external Channel blocks recovery

- **WHEN** a Channel shares the canonical display name but lacks the exact expected ownership evidence
- **THEN** reconciliation does not adopt or mutate it and blocks ambiguous recovery for that logical type

#### Scenario: Route ownership conflict blocks recovery

- **WHEN** another live Channel owns or ambiguously claims the candidate's required listener route
- **THEN** reconciliation blocks recovery and leaves every involved Channel unchanged

### Requirement: Rebinding preserves recovered Channel state

Healthcare Lab SHALL revalidate a recoverable Channel immediately before binding and SHALL preserve all live Channel configuration and deployment state during identity recovery.

#### Scenario: Recovered Channel is deliberately stopped

- **WHEN** the uniquely recoverable Channel is stopped or undeployed
- **THEN** recovery persists its identity without deploying, redeploying, updating, undeploying, or deleting it

#### Scenario: Recovery evidence becomes stale

- **WHEN** candidate identity, revision, uniqueness, payload validity, or route ownership changes before binding
- **THEN** recovery fails closed without persisting the stale mapping or mutating an OIE Channel
