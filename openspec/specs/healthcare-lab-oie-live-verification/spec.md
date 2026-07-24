# healthcare-lab-oie-live-verification Specification

## Purpose
TBD - created by archiving change verify-live-oie-end-to-end-workflow. Update Purpose after archive.
## Requirements
### Requirement: Clean OIE provisioning is verified live
The verification workflow SHALL begin from a documented clean OIE 4.5.2 state, confirm that the HLAB result listener auto-starts on port `6665`, connect Settings with the documented local-lab profile, and create and deploy exactly `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB` with routes matching their previews.

#### Scenario: Managed routes are provisioned from a clean runtime
- **WHEN** an operator follows the clean-environment verification procedure
- **THEN** both managed Channels are started and evidence records the previewed and deployed routes as `HLAB -> OIE:6600 -> AP:6671` and `AP -> OIE:6661 -> HLAB:6665`

### Requirement: Live ORM delivery is verified exactly once
The verification workflow SHALL create an ORM in HLAB, send it through OIE port `6600`, and prove that the AP receives exactly one ORM on port `6671` with a correct ACK and visible transmission outcome.

#### Scenario: ORM reaches the AP
- **WHEN** a uniquely identifiable HLAB Order is sent through the deployed ORM Channel
- **THEN** evidence correlates the HLAB Order, OIE message, AP receipt, ACK, and successful transmission status without a second AP receipt

### Requirement: Live ORU delivery and matching are verified
The verification workflow SHALL send AP ORU messages through OIE port `6661`, prove delivery to HLAB port `6665`, verify preservation of raw HL7, and verify both matched and unmatched result behavior.

#### Scenario: ORU matches its Patient and Order
- **WHEN** the AP sends a uniquely identifiable ORU for an existing HLAB Patient and Order
- **THEN** HLAB stores the raw HL7 and associates the result with that Patient and Order

#### Scenario: Unmatchable ORU remains reviewable
- **WHEN** the AP sends a valid supported ORU whose identifiers cannot match an HLAB Patient or Order
- **THEN** HLAB preserves it in Unmatched Results with evidence sufficient to distinguish it from the matched result

### Requirement: Managed Channel lifecycle remains safe live
The verification workflow SHALL verify structured edit and diff preview, safe redeploy, undeploy, delete, recreate, and redeploy for one managed Channel while proving that an external Channel is not mutated.

#### Scenario: Managed Channel is edited and redeployed
- **WHEN** the operator changes the approved AP destination, reviews the preview, and applies the redeploy
- **THEN** the deployed managed Channel reflects the previewed route and remains operational

#### Scenario: Managed Channel is deleted and recreated in isolation
- **WHEN** the operator undeploys, deletes, recreates, and deploys a managed Channel using the guarded Settings actions
- **THEN** the managed Channel returns to its intended state and recorded external-Channel identity, revision, configuration, and deployment state remain unchanged

### Requirement: Listener outage recovery is verified live
The verification workflow SHALL prove that an ORU accepted by OIE while `lab-app` is unavailable remains queued or retryable, is delivered after `lab-app` restarts and the `6665` listener auto-starts, and does not create uncontrolled duplicate HLAB results.

#### Scenario: Queued ORU is delivered after HLAB recovery
- **WHEN** `lab-app` is stopped, a uniquely identifiable ORU is accepted by OIE, and `lab-app` is restarted
- **THEN** evidence shows a queued or retryable destination state, listener recovery, eventual successful delivery, and one persisted result for the message-control identifier

### Requirement: Verification produces reusable evidence and operations guidance
The live gate SHALL record a pass, fail, or blocked outcome with timestamped evidence for every required step and SHALL publish the verified port matrix, route diagram, Settings and Channel instructions, lifecycle and recovery SOP, known limitations, troubleshooting guidance, and repeatable smoke-check procedure.

#### Scenario: A new operator repeats the verified workflow
- **WHEN** a reader who did not implement the feature follows the published prerequisites, operating instructions, and smoke checks from a clean environment
- **THEN** the reader can configure the same routes, correlate the required evidence, and identify the prescribed recovery action for each tested failure layer

#### Scenario: Blocking defect prevents acceptance
- **WHEN** a required live step fails because of an unresolved blocking product defect
- **THEN** the report identifies the failed step and evidence, the gate remains failed or blocked, and the workflow is not declared accepted
