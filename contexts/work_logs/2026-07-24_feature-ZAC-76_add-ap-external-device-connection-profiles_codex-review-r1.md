---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-76_add-ap-external-device-connection-profiles
base: main
reviewed_head: 3490ac596e617ba81f8d402596e5167011f845b0
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | The effective DICOM merge only replaces `mwl.defaultScheduledStationAETitle`; the other required AP DICOM values have no consumer. |
| REV-002 | P2 | open | `gdt.bridgeProfile` is validated only as non-empty and is ignored when effective GDT settings are composed. |
| REV-003 | P2 | open | OIE desired configuration consumes only AP HL7 host and port; the four AP identity fields are unused. |

## New blocking findings

### [P2][REV-001] Effective DICOM projection omits required AP identity, endpoint, and result role

The accepted DICOM requirement says MWL and result-delivery workflows SHALL
obtain the AP AE title, MWL calling/station identity, endpoint, and supported
role from the effective AP DICOM projection. In
`backend/services/integration_settings.py:430-439`, the merge consumes only
`scheduledStationAETitle`. `aeTitle`, `mwlCallingAETitle`, `host`, `port`, and
`resultDeliveryRole` are never connected to a DICOM workflow. The downstream
composition at `backend/services/dcm4chee_coordination.py:179-183` therefore
continues to source calling identity from the dcm4chee profile, and there is no
AP-owned result-delivery endpoint or role enforcement.

Impact: an enabled AP profile can validate and become effective while MWL or
result-delivery operations continue using stale integration-owned identity and
endpoint values. This violates an explicit acceptance requirement, so it is a
blocking P2.

Required resolution: project every required AP DICOM field through narrow
effective settings into the actual MWL and result-delivery consumers, preserve
dcm4chee ownership of archive values, reject unsupported/incomplete roles
before execution, and add workflow-level tests proving the effective snapshot
is used.

### [P2][REV-002] GDT Bridge association is neither resolved nor validated

The GDT requirement says an enabled AP section SHALL reference a valid GDT
Bridge profile and workflows SHALL combine that selected profile with the AP
identity. `backend/domain/ap_device_profile.py:165-171` checks only that
`bridgeProfile` is non-empty. The effective merge in
`backend/services/integration_settings.py:404-420` copies AP sender and receiver
IDs but never reads `bridgeProfile`, verifies that it names the selected Bridge
profile, or reports `needs-setup` for an unavailable/conflicting association.
The test at `tests/services/test_ap_device_profiles.py:95-100` consequently
asserts only the two identity strings.

Impact: arbitrary or stale Bridge references are accepted and workflows run
against whichever single integration profile happens to be active, contrary to
the saved AP association. This violates an explicit acceptance requirement, so
it is a blocking P2.

Required resolution: resolve and validate the AP `bridgeProfile` against the
available GDT Bridge profile at the application-service boundary, fail with
stable value-safe guidance/readiness when it is unavailable or conflicting,
and add effective-workflow tests for matching and mismatched associations.

### [P2][REV-003] OIE desired state ignores AP-owned HL7 identity fields

The OIE requirement says the ORM-to-AP desired projection SHALL obtain both
the AP destination and owned AP identity values from the effective profile.
Although the AP contract persists sending/receiving application and facility
values (`backend/domain/ap_device_profile.py:154-163`), the lifecycle merge at
`backend/services/oie_channel_lifecycle.py:327-331` applies only host and port.
No other changed production code consumes those four identity fields, and the
new lifecycle test verifies only the endpoint.

Impact: operators can change an effective AP HL7 identity without producing
the required owned-field drift or desired Channel update, leaving routing
identity inconsistent across the saved profile and OIE. This violates an
explicit acceptance requirement, so it is a blocking P2.

Required resolution: define the owned Channel representation for the AP HL7
identity, include it in desired-state normalization, drift, guarded
preview/apply payloads, and tests, while retaining the no-automatic-mutation
rule.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...3490ac596e617ba81f8d402596e5167011f845b0`
  across the OpenSpec requirements, production changes, and focused tests.
- The recorded verification round passed 809 Python tests with 1 skip, 46
  focused architecture tests, JavaScript syntax, Python compilation, strict
  OpenSpec validation, and diff hygiene.
- Those checks remain useful regression evidence, but the focused projection
  test asserts only the partial GDT and DICOM merge and does not exercise the
  missing workflow behavior described above.
- No product code or tests were modified during review.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-24_feature-ZAC-76_add-ap-external-device-connection-profiles_codex-review-r1.md"`

Reason: blocking findings remain.
