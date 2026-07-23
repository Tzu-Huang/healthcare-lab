---
reviewer: codex
mode: initial
round: 1
branch: feature/ZAC-68_recover-managed-channel-identity-across-volume-loss
base: main
reviewed_head: ae767bded8cb39e6f1ca81197fd5c3eda1a609da
previous_review: null
previous_reviewed_head: null
verdict: changes-requested
---

# Codex Review

## Finding transitions

| ID | Priority | Status | Evidence |
|---|---|---|---|
| REV-001 | P2 | open | Well-formed external payloads with missing or invalid listener data are ignored as route claimants. |
| REV-002 | P2 | open | The atomic bind compares only empty identity fields, not the desired mapping intent that recovery validated. |

## New blocking findings

### [P2][REV-001] Unknown listener evidence can still be classified as recoverable

- Location: `backend/domain/oie_channel_lifecycle.py:208-210`, `backend/domain/oie_channel_lifecycle.py:299-310`
- Impact: Recovery can persist ownership while another well-formed live Channel has missing or invalid listener properties. The implementation treats only an XML `ParseError` as ambiguous; `_parse_listener()` also returns `None` for a missing listener block, missing host/port, non-integer port, and other parse failures, but those cases do not block recovery. This violates the explicit requirement that an ambiguous route claimant blocks recovery.
- Evidence: A complete valid managed candidate plus `<channel><description>Operator owned</description></channel>` currently reconciles to `recoverable` with no blocking reasons. Existing coverage tests malformed XML only, so it does not exercise this well-formed unknown-listener case.
- Classification: acceptance-level correctness defect introduced by this change.
- Required resolution: Preserve listener parse state or a bounded error category and make every live non-candidate whose listener ownership cannot be excluded block recovery. Add tests for well-formed missing listener fields and invalid listener ports, while retaining the known-port collision test.

### [P2][REV-002] Expected-empty binding does not compare the validated desired mapping intent

- Location: `backend/services/oie_channel_lifecycle.py:108-128`, `backend/repositories/oie_settings.py:255-264`
- Impact: `recover_mapping()` revalidates inventory and desired route, but a concurrent settings update can change `channel_name`, `template_version`, or `desired_config_json` after the second snapshot and before the SQL update. The repository predicate checks only `oie_channel_id = ''` and `last_known_revision = ''`, then binds the previously validated Channel to the newly changed intent. That contradicts the stale-recovery and atomic expected-state requirements.
- Evidence: The repository method receives no expected desired-intent values, and its `WHERE` clause contains no comparison for them. Repository tests cover repeated non-empty identity and duplicate-audit rollback, but not an empty-identity desired-config race.
- Classification: acceptance-level concurrency defect introduced by this change.
- Required resolution: Carry a stable expected mapping-intent token or the expected canonical name, template version, and normalized desired configuration from revalidation into the atomic bind predicate. Reject the bind if any expected intent changed, and add a repository/service race test proving the mapping and audit remain unchanged.

## Follow-up findings

None.

## Verification and residual risk

- Reviewed `git diff main...ae767bded8cb39e6f1ca81197fd5c3eda1a609da`, the three delta specs, tasks, domain/repository/lifecycle/bootstrap implementation, and focused tests.
- The persisted verification round reports 72 focused tests, 641 full-suite tests, compilation, diff check, and strict OpenSpec validation passing at the reviewed head.
- Residual environment risk: no destructive live-volume recovery exercise was run in this review; automated matrix coverage exists, but this does not affect the two reproducible code-level blockers above.

## Next Action

`/dev-fix --review "contexts/work_logs/2026-07-23_feature-ZAC-68_recover-managed-channel-identity-across-volume-loss_codex-review-r1.md"`

Reason: REV-001 and REV-002 violate explicit recovery safety requirements and remain blocking.
