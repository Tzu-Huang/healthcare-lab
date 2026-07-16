---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-47_define-managed-hlab-channel-templates
base: main
reviewed_head: a254454cc24bfabe2f02ea6b3f3d7cc7ca82f749
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

None.

## New blocking findings

### [P1][REV-001] Public renderer bypasses both constrained recipes

- Evidence: `backend/templates/oie_channels.py:80` publicly accepts any
  `ManagedChannelConfig`, while `tests/templates/test_oie_channels.py:85` only
  constrains the `orm_to_ap_config` signature. A direct call rendered an ORU
  Channel named `operator-route`, listening on port 7777, sending to
  `attacker.internal:9999`, with queueing disabled.
- Impact: callers can bypass the fixed `HLAB_ORU_TO_HLAB` destination and its
  mandatory indefinite retry policy, so the public interface does expose an
  arbitrary destination/configuration path contrary to the core acceptance
  boundary.
- Classification: initial blocking correctness/safety finding.
- Required resolution: make complete payload rendering enforce the selected
  recipe invariants or make the unconstrained renderer private and expose only
  recipe-specific compile functions. Add tests that attempt to bypass both ORM
  and ORU fixed topology/policy through every public rendering entry point.

### [P2][REV-002] Payload normalization hides owned identity, charset, and protocol drift

- Evidence: `backend/templates/oie_channels.py:126-127` hard-codes protocol and
  charset in normalized output, and `backend/templates/oie_channels.py:144-148`
  extracts only `logical_type` from the description before rebuilding the
  expected marker/version. Changing payload charset from UTF-8 to ISO-8859-1 or
  changing the description to a non-managed marker with template version 999
  produced the same normalized state. The comparison coverage at
  `tests/templates/test_oie_channels.py:105` mutates configs rather than wire
  payload identity/protocol/charset fields.
- Impact: ZAC-48 drift comparison can report equality when Healthcare
  Lab-owned identity, charset, or MLLP/HL7 configuration has changed, violating
  the explicit owned-field drift requirement.
- Classification: initial P2 blocker because it violates an explicit acceptance
  criterion.
- Required resolution: parse and validate all normalized owned fields from the
  payload, including the full marker/template version, charset, and protocol
  primitives; add payload-mutation comparison tests proving each change is
  visible while server metadata remains ignored.

### [P2][REV-003] Private IPv4 validation admits non-private destination classes

- Evidence: `backend/domain/oie_channels.py:93-113` relies on
  `IPv4Address.is_private`. The current validator accepts `127.0.0.1`,
  `169.254.1.1`, and `0.0.0.0` as AP destinations.
- Impact: invalid loopback, link-local, and unspecified endpoints can pass the
  pre-transport boundary even though the contract requires a private-network AP
  host.
- Classification: initial P2 blocker because endpoint rejection is an explicit
  acceptance criterion.
- Required resolution: allow only the intended RFC1918 destination ranges (with
  `0.0.0.0` permitted solely for the listener wildcard) and add negative tests
  for loopback, link-local, multicast, unspecified, reserved, and public IPv4.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `main...a254454cc24bfabe2f02ea6b3f3d7cc7ca82f749`, the OpenSpec requirements,
  domain/template implementation, and focused tests.
- Reproduced all three findings using local, offline Python commands; no live
  OIE instance was contacted.
- The persisted verification round remains valid for the reviewed HEAD, but its
  passing tests do not cover the bypass and drift cases above.

## Next Action

`/dev-fix --review "openspec/changes/define-managed-hlab-channel-templates/review/2026-07-16_feature-ZAC-47_define-managed-hlab-channel-templates_codex-review-r1.md"`

Reason: blocking findings REV-001, REV-002, and REV-003 remain.
