## Why

Healthcare Lab persists managed Channel mappings separately from OIE Channel definitions, so losing either volume can leave a stale mapping or a valid managed Channel with no local identity record. Startup must converge safely across those asymmetric failures without duplicating Channels, adopting external Channels, or changing an intentionally stopped Channel.

## What Changes

- Extend startup reconciliation to distinguish a remotely missing mapped Channel from a uniquely recoverable unmapped managed Channel.
- Recreate and start only approved managed Channels that are genuinely absent after OIE appdata loss.
- Rebind a reset local mapping only when exactly one live Channel has valid Healthcare Lab ownership evidence, the expected logical type, a parseable payload, and an exclusively owned route.
- Block recovery for duplicate or malformed ownership evidence, identity mismatch, same-name external Channels, and listener-port ownership conflicts.
- Preserve the deployment state of a recovered live Channel and keep repeated startup runs idempotent.
- Record bounded, secret- and PHI-safe recovery and blocked-recovery evidence.
- Add automated coverage for the four persistence combinations and all blocking identity cases.

## Capabilities

### New Capabilities

None.

### Modified Capabilities

- `healthcare-lab-oie-startup-bootstrap`: Extend startup convergence from create-missing behavior to safe identity recovery across independent local DB and OIE appdata loss.
- `healthcare-lab-oie-managed-channel-lifecycle`: Add conservative classification and atomic rebinding for uniquely owned Channels whose local mapping was lost.
- `healthcare-lab-oie-settings-profile`: Permit compare-and-bind recovery of one canonical mapping without replacing unrelated settings or mappings.

## Impact

- Affects managed Channel reconciliation, guarded lifecycle orchestration, startup bootstrap sequencing, settings mapping persistence, and lifecycle audit evidence.
- Uses the existing OIE Management API inventory and canonical Channel templates; no new external dependency or public browser mutation endpoint is required.
- Does not recover OIE message history, adopt unmarked Channels, correct drift automatically, or add multi-host coordination.
