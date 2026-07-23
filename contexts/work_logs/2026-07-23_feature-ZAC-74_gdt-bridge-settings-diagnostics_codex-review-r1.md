---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-74_gdt-bridge-settings-diagnostics
base: main
reviewed_head: 1031fee781fa4eed47240799b1440dad9d544d46
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] A timed-out watcher stop can create two live import loops

At [backend/runtime/gdt_bridge_watcher.py](../../backend/runtime/gdt_bridge_watcher.py#L160),
`stop()` clears `_thread` after a bounded join without checking whether the
thread actually terminated. `apply_profile()` then configures the watcher and
`start()` clears the shared stop event and starts a replacement thread. If an
import scan takes longer than `poll_seconds + 0.5`, the original thread remains
alive and resumes when the event is cleared, leaving two loops able to claim
and import the same bridge files.

Impact: concurrent scans can race over exchange files, produce duplicate work,
or move files into inconsistent processing/error states. This contradicts the
explicit serialized lifecycle and safe-quiescence requirements.

Classification: initial blocking correctness/data-integrity defect.

Required resolution: retain and verify the original thread until it exits; if
quiescence times out, do not reconfigure or restart in-process and return a
bounded `restart-required` outcome. Add a test with a deliberately blocked
importer proving that no replacement loop starts.

### [P2][REV-002] Restart-required activation is not preserved in readiness

The PUT response can return `restart-required` at
[backend/api/integration_settings.py](../../backend/api/integration_settings.py#L102),
but no activation state is retained. Subsequent readiness assessment at
[backend/settings_readiness_composition.py](../../backend/settings_readiness_composition.py#L110)
only checks filesystem health and whether the watcher is running, mapping a
failed activation to `degraded`.

Impact: after saving valid persisted intent that could not become effective,
the Settings workspace loses the required `restart-required` state and exact
activation class on refresh. This violates the explicit saved-intent readiness
scenario.

Classification: initial P2 acceptance-criterion violation.

Required resolution: expose durable application-scoped activation/effective
state to the readiness provider and preserve the bounded restart class until
runtime state converges. Add API/readiness coverage across a failed activation
and a later GET.

### [P2][REV-003] Run all checks omits the required GDT probe and bounded outcomes

The GDT operation endpoint uses the full diagnostic report, including the
write/delete probe, at
[backend/gdt_settings_composition.py](../../backend/gdt_settings_composition.py#L45).
The readiness registry instead receives `gdt_readiness_diagnostics()`, which
only calls `diagnose_gdt_bridge_dirs()` at
[backend/gdt_settings_composition.py](../../backend/gdt_settings_composition.py#L55).
`_GdtBridgeProvider.check()` then reduces that result to one aggregate state at
[backend/settings_readiness_composition.py](../../backend/settings_readiness_composition.py#L121).

Impact: the shared Run all checks flow neither runs the write/delete capability
probe nor returns the path, permission, probe, and watcher outcomes required by
the OpenSpec Settings-workspace scenario.

Classification: initial P2 acceptance-criterion violation.

Required resolution: have the registered GDT diagnostic provider run the
bounded full diagnostic set and project its role/code outcomes through Run all
checks, with tests proving probe cleanup and bounded output.

## Follow-up findings

- [P2] The typed API accepts arbitrary absolute `applicationPath` values in
  `validate_gdt_bridge_profile`, while the supported Docker contract calls
  `/data/gdt-bridge` fixed. Clarify or enforce the environment boundary so API
  clients cannot accidentally treat deployment-owned mount changes as an
  in-app operation.

## Verification and residual risk

- Reviewed `main...1031fee781fa4eed47240799b1440dad9d544d46`,
  relevant OpenSpec requirements, implementation, and tests.
- Existing verification passed 742 tests with 1 skip, but there is no blocked
  importer lifecycle test and no persistence test for restart-required
  readiness.
- No product code or tests were modified during review.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-74_gdt-bridge-settings-diagnostics_codex-review-r1.md"`

Reason: blocking findings REV-001, REV-002, and REV-003 remain.
