# OIE bootstrap convergence evidence - pending execution

Use one copy of this template for a witnessed ZAC-69 run against OIE 4.5.2.
This blank template records no acceptance result. All execution evidence is
**PENDING / NOT RUN** until observed directly.

## Run and ownership metadata

| Field | Value |
| --- | --- |
| Run token | `NOT RECORDED` |
| Scenario / maintenance window | `NOT RECORDED` |
| Started / ended (timestamp with offset) | `NOT RECORDED` |
| Operator / witness | `NOT RECORDED` |
| Worktree absolute path / repository revision / status | `NOT RECORDED` |
| Exclusive Compose ownership confirmed; competing sessions/jobs | `PENDING / NOT RUN` |
| Compose project / compose file / effective config reference | `NOT RECORDED` |
| OIE 4.5.2 image ID/digest / application version / container ID | `NOT RECORDED` |
| HLAB container ID / network | `NOT RECORDED` |
| Host port owners: `5000`, `6600`, `6661`, `6671` | `NOT RECORDED` |
| Internal `lab-app:6665` ownership | `NOT RECORDED` |
| Local settings resolved target / mount type / owner | `NOT RECORDED` |
| OIE `/opt/connect/appdata` resolved target / mount type / owner | `NOT RECORDED` |
| Backup/recovery decision and approval reference, if destructive | `NOT APPLICABLE / NOT RECORDED` |
| Redacted evidence root | `NOT RECORDED` |

## Safe bootstrap status snapshot

Create one row per observation. Do not record credentials, tokens, raw Channel
configuration, raw HL7, patient data, or unrestricted exception text.

| Observation | Run ID | Mode / state | Started / completed | Attempts | Safe error category | Retry eligible | Allowlisted guidance | Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Before action | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |
| After convergence or timeout | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |
| After explicit Retry, if used | `NOT APPLICABLE` | `NOT APPLICABLE` | `NOT APPLICABLE` | `NOT APPLICABLE` | `NOT APPLICABLE` | `NOT APPLICABLE` | `NOT APPLICABLE` | `PENDING` |

| Observation | Logical type | Classification / outcome / safe status | Channel ID / revision | Started state | Evidence |
| --- | --- | --- | --- | --- | --- |
| Before action | `HLAB_ORM_TO_AP` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |
| Before action | `HLAB_ORU_TO_HLAB` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |
| After action | `HLAB_ORM_TO_AP` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |
| After action | `HLAB_ORU_TO_HLAB` | `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` |

## Scenario ledger

Complete every row. Channel counts mean exactly the approved managed names;
record external/sentinel Channels separately and do not expose their payloads.

| ID | Scenario and required non-PHI evidence | Result | Timestamp / evidence | Blocker or defect |
| --- | --- | --- | --- | --- |
| OWN-01 | Exclusive Compose ownership, worktree, project, containers, networks, ports, and both exact state targets resolved | PENDING / NOT RUN | - | - |
| CLEAN-01 | Clean startup run mode/state/timing/attempts; exactly two approved managed names and IDs/revisions; both started; no duplicate names/IDs | PENDING / NOT RUN | - | - |
| RESTART-01 | Retained local settings and OIE appdata; before/after run IDs and inventories; no-op outcomes; stable Channel IDs/revisions; zero duplicates/unnecessary changes | PENDING / NOT RUN | - | - |
| MISSING-01 | Selected managed Channel removed through guarded UI; peer baseline ID/revision/state; explicit Retry/startup result; selected Channel recreated once; peer unchanged | PENDING / NOT RUN | - | - |
| READY-01 | Approved delayed-readiness method; attempt timestamps/count; bounded timeout and safe category; Retry eligibility/guidance; restored dependency; explicit Retry run ID and convergence | PENDING / NOT RUN | - | - |
| RESET-L-01 | Exact local-settings target and approval; OIE appdata retained; before/after target identity and Channel inventory; resulting status and convergence | PENDING / NOT RUN | - | - |
| RESET-O-01 | Exact OIE appdata target and approval; local settings retained; quiesced cleanup evidence; new mount identity; exactly two managed Channels after convergence | PENDING / NOT RUN | - | - |
| RESET-B-01 | Both exact targets and approval; quiesced cleanup evidence for each; re-resolved mounts; clean convergence with exactly two managed Channels | PENDING / NOT RUN | - | - |
| READ-01 | Status GET, Settings/browser refresh, inventory refresh, and Runtime Diagnostics cause zero Channel mutations; before/after IDs/revisions/counts recorded | PENDING / NOT RUN | - | - |
| SAFE-01 | Evidence reviewed: no secrets, auth headers, raw Channel payloads, raw HL7, PHI, or unrestricted errors | PENDING / NOT RUN | - | - |

## Action timeline

| Timestamp with offset | Action or observation | Run ID / safe correlation | Bounded result | Evidence reference |
| --- | --- | --- | --- | --- |
| `NOT RECORDED` | `NOT RECORDED` | `NOT RECORDED` | `PENDING` | `PENDING` |

## Cleanup and recovery record

For ordinary readiness or lifecycle failures, record dependency correction and
explicit Retry; container recreation and volume deletion are not recovery.
For a named reset scenario, record the exact resolved target and bounded
cleanup command only after approval. Never record passwords or paste raw
configuration.

| Field | Value |
| --- | --- |
| Ordinary correction performed | `NOT RECORDED` |
| Explicit Retry requested / accepted / completed | `NOT RECORDED` |
| Container recreation required by image/env/port/mount change | `NO / NOT RECORDED` |
| Destructive target(s), ownership check, and approval | `NOT APPLICABLE / NOT RECORDED` |
| Post-action mount and port ownership re-resolved | `PENDING / NOT RUN` |
| Queue/message history preserved where required | `PENDING / NOT RUN` |

Overall ZAC-69 live gate: **PENDING / NOT RUN**. Gate owner:
`NOT RECORDED`. Open blockers: `NOT RECORDED`.
