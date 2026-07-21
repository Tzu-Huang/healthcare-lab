## Why

The completed OIE Settings capabilities have been verified with unit, integration, and simulated recovery tests, but those checks cannot prove that they compose correctly against a clean OIE 4.5.2 runtime and the real AP simulator. The milestone needs a repeatable live acceptance gate with durable evidence before the managed ORM/ORU workflow can be treated as operationally complete.

## What Changes

- Add a repeatable clean-environment verification workflow for provisioning, previewing, creating, deploying, editing, undeploying, deleting, recreating, and recovering the two Healthcare Lab managed Channels.
- Exercise the complete live ORM and ORU routes, including ACK and transmission status, raw HL7 preservation, Patient and Order matching, and Unmatched Results behavior.
- Verify temporary HLAB listener downtime, OIE destination queueing/retry, listener auto-start after restart, eventual delivery, and bounded duplicate handling.
- Record pass/fail evidence for every required verification step and require unresolved blocking defects to be fixed or explicitly stop acceptance.
- Publish the verified port matrix and route diagram, Settings and managed-Channel operating instructions, lifecycle and recovery SOP, known limitations, troubleshooting guidance, and repeatable smoke-check steps.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-live-verification`: Defines the clean-runtime live acceptance gate, evidence contract, operational documentation, and repeatable smoke checks for the end-to-end managed OIE workflow.

### Modified Capabilities

None. This change verifies the existing OIE Settings, managed-Channel, listener, diagnostics, and patient-centered result contracts without changing their requirements unless live verification exposes a separately scoped defect.

## Impact

The change affects live-verification tooling and evidence under the repository, OIE/AP/HLAB operating documentation, route and port references, and the Docker-based local lab procedure. It depends on a real OIE 4.5.2 runtime, the Healthcare Lab application, and an AP simulator reachable on the verified ports; product code changes are out of scope unless a blocking live defect is discovered and explicitly incorporated.
