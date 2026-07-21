## Context

ZAC-45 through ZAC-51 established persistent OIE Settings, an OIE 4.5.2 Management API client, fixed managed-Channel templates, guarded lifecycle operations, an auto-starting HLAB MLLP listener, a Settings workspace, queue/retry behavior, idempotent result handling, diagnostics, and audit records. Automated coverage uses controlled transports or locally simulated failure and therefore cannot establish that the composed workflow matches a real OIE runtime and AP simulator.

The live gate spans Docker runtime state, browser operations, Management API behavior, MLLP traffic, persistence, and external AP observations. Evidence must remain useful without containing credentials or unnecessary PHI. Existing documentation contains older channel names and port examples, so only values demonstrated by the live run can be labeled verified.

## Goals / Non-Goals

**Goals:**

- Make every ZAC-52 acceptance step repeatable and evidence-backed.
- Correlate each ORM and ORU across HLAB, OIE, and AP using synthetic identifiers.
- Prove managed ownership isolation and outage recovery against OIE 4.5.2.
- Leave a concise operator SOP, troubleshooting path, route diagram, port matrix, and smoke check.

**Non-Goals:**

- Add new arbitrary OIE Channel editing or adoption behavior.
- Introduce production HA, TLS/identity architecture, a secret manager, or clinical validation.
- Treat mock tests as substitutes for the live gate.
- Fold unrelated defects or broad product enhancements into the verification change without explicit scope review.

## Decisions

### Use one run manifest and evidence ledger

Each live run will record environment identity, OIE version, relevant image/application revisions, AP endpoint, synthetic Patient/Order/message identifiers, timestamps, and a row for every acceptance step. Evidence references will point to bounded screenshots, API projections, AP receipts, and safe logs. A single ledger is preferred over scattered notes because it makes omissions and reruns visible.

Alternative considered: rely on browser screenshots alone. Rejected because screenshots do not reliably correlate MLLP receipt, ACK, persistence, and queue recovery.

### Use synthetic correlation identifiers and bounded evidence

The run will create dedicated synthetic data and unique `MSH-10` identifiers for matched, unmatched, and recovery cases. Reports will avoid credentials and redact unnecessary patient or raw-payload content while recording checksums or bounded excerpts where exact-message correlation is needed.

Alternative considered: reuse existing demo records. Rejected because existing messages make exactly-once and matching evidence ambiguous.

### Define clean state explicitly and preserve rerunability

The procedure will distinguish destructive first-run reset from ordinary reruns. The exact OIE data-volume handling, external sentinel Channel creation, and synthetic HLAB cleanup will be documented before execution. Destructive cleanup requires an explicit operator action and verified target; routine smoke checks will not erase runtime data.

Alternative considered: interpret “clean” as merely undeploying Channels. Rejected because retained settings, messages, and identities could hide provisioning defects.

### Combine automation with witnessed external observations

A bounded smoke helper may perform preflight checks, send deterministic MLLP fixtures, capture ACKs, and query safe application diagnostics. Browser-only lifecycle actions and AP receipt observations will remain explicit witnessed steps unless the AP exposes a stable automation interface.

Alternative considered: fully automate through private browser or OIE internals. Rejected because it would couple the gate to unstable implementation details and still could not prove the real AP observed the message.

### Pin acceptance to the exact route contract

All artifacts will use `HLAB -> OIE:6600 -> AP:6671` and `AP -> OIE:6661 -> HLAB:6665`. Documentation with legacy names or ports will be corrected or clearly marked historical after live confirmation.

## Risks / Trade-offs

- [Risk] The AP simulator is unavailable or lacks a stable automation interface. → Record the prerequisite explicitly, use witnessed AP evidence, and mark dependent steps blocked rather than passing them by inference.
- [Risk] Resetting OIE destroys unrelated lab data. → Resolve and verify the exact Compose project and volume targets, require explicit destructive action, and export or preserve anything declared external.
- [Risk] Timing makes retry and exactly-once observations flaky. → Use unique control identifiers, bounded polling windows, timestamped queue snapshots, and persistence counts instead of fixed sleeps.
- [Risk] Evidence leaks credentials or PHI. → Use synthetic data, bounded diagnostic projections, redaction review, and exclude raw secrets from artifacts.
- [Risk] A live defect expands the ticket unpredictably. → Stop the affected gate, record reproducible evidence, and route the defect through an explicit OpenSpec/Linear scope decision before claiming acceptance.

## Migration Plan

1. Inventory the actual OIE/AP/HLAB environment and reconcile the documented clean-state and port prerequisites.
2. Add the evidence template and safe repeatable smoke support without changing product behavior.
3. Execute provisioning, ORM, ORU, lifecycle isolation, and recovery phases in order, recording evidence as each phase completes.
4. Correct operator documentation and publish only the route and limitations demonstrated by the run.
5. Rerun the complete gate after any blocking fix; rollback verification tooling or documentation normally, while restoring the clean lab from its documented reset procedure when required.

## Open Questions

- Which executable AP simulator build and host will be authoritative for the `6671` receipt and ORU send evidence?
- Does the accepted clean-state procedure remove the OIE appdata volume, or use a newly named isolated Compose volume to avoid destructive cleanup?
- Which evidence artifacts should remain repository-local versus be attached to Linear when screenshots contain environment-specific details?
