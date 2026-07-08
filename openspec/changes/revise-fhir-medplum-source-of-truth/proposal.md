## Why

ZAC-25 added the FHIR local sync foundation so Healthcare Lab can persist workflow intent, sync state, Medplum references, retry details, and OperationOutcome diagnostics. That foundation is useful, but the next FHIR tickets need a sharper data-ownership boundary before Patient, Order, Task, Result, Medplum inventory, and E2E work build on top of it.

Healthcare Lab should not become a second FHIR server or EMR shadow database. Medplum should remain the canonical FHIR source of truth for clinical resources. Healthcare Lab should keep only the local workflow ledger and demo/control-plane metadata required to make sync, retry, audit, and troubleshooting reliable.

## What Changes

- Clarify that Medplum is the canonical source for FHIR `Patient`, `ServiceRequest`, `Task`, `DiagnosticReport`, `Observation`, `DocumentReference`, `Binary`, and `Provenance` resources.
- Reframe the ZAC-25 local FHIR tables as a workflow ledger, not as complete long-lived clinical resource ownership.
- Define default read behavior for later FHIR UI/worklist flows as live Medplum API queries joined with local ledger metadata when available.
- Define create/update behavior as Medplum-backed writes with local intent, retry, idempotency, and error preservation.
- Keep local persistence for pending/failed writes, sync attempts, OperationOutcome, deterministic identifiers, Medplum references, and AP/demo audit trails.
- Prevent future FHIR tickets from requiring a full local Patient/Order/Result shadow database unless a specific offline/demo feature explicitly scopes it.

## Capabilities

### Modified Capabilities

- `healthcare-lab-fhir-local-sync-foundation`: Clarify Medplum source-of-truth ownership and Healthcare Lab local ledger responsibility.

## Impact

- Affected specs: `healthcare-lab-fhir-local-sync-foundation`.
- Affected future tickets: ZAC-26 through ZAC-32 should use this boundary for Patient, Order, Task, Result, FHIR frontend, and E2E planning.
- No product implementation is included in this proposal step.
- No database migration is required by this proposal alone.
