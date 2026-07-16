## Why

Healthcare Lab currently relies on manually configured OIE Channels, so the agreed ORM and ORU routes cannot be provisioned or compared safely by later Settings workflows. Two constrained, versioned OIE 4.5.2 templates are needed now as the ownership and validation boundary for the later managed Channel lifecycle.

## What Changes

- Define the managed `HLAB_ORM_TO_AP` template for `0.0.0.0:6600` to a configurable private-network AP host on port `6671`.
- Define the managed `HLAB_ORU_TO_HLAB` template for `0.0.0.0:6661` to `lab-app:6665`, with a 10-second indefinite destination queue/retry policy so temporary lab-app downtime does not silently discard accepted ORU delivery.
- Generate complete OIE 4.5.2 Channel payloads using the checked-in operator exports as canonical structural evidence while replacing environment-specific IDs, revisions, timestamps, names, and endpoints.
- Assign stable logical identities, template version `1`, and a machine-readable `Managed by Healthcare Lab` marker independently of OIE Channel IDs.
- Expose only the approved endpoint, timeout, connection, queue, enabled, and initial-state inputs; reject invalid endpoints and listener-port conflicts before any OIE call.
- Produce a deterministic normalized representation for later preview, drift classification, and lifecycle decisions without treating OIE-managed metadata as desired configuration.
- Keep AP host persistence outside this change; the template accepts the future Settings value as an explicit input, and ZAC-48 integration must not hard-code the current environment IP.

## Capabilities

### New Capabilities

- `healthcare-lab-oie-managed-channel-templates`: Complete, validated, versioned OIE 4.5.2 templates and normalized representations for the two Healthcare Lab-managed HL7 routes.

### Modified Capabilities

- None.

## Impact

- Adds persistence-neutral OIE Channel domain/template modules and mirrored tests.
- Uses `docs/Dashboard_to_OIE_to_AP.xml` and `docs/AP_RESULT_TO_LAB.xml`, introduced on the active ZAC-61 branch, as canonical OIE 4.5.2 evidence after that source is available to this branch.
- Does not modify OIE Settings persistence, the Management API client, Flask APIs, runtime listeners, Channel lifecycle services, Docker configuration, or frontend assets.
- Establishes inputs and normalized output consumed later by ZAC-48 and ZAC-50.
