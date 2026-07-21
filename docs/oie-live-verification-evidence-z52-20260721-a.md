# ZAC-52 live verification evidence: Z52-20260721-A

This is the completed run-specific manifest and ledger for the reusable
procedure in `docs/oie-live-verification-runbook.md`. Times are UTC unless an
offset is shown. Minute-level observation windows are used where the bounded
terminal projection did not retain seconds; they are not presented as exact
event timestamps.

## Run manifest

| Field | Recorded value |
| --- | --- |
| Run token | `Z52-20260721-A` |
| Started / ended | `2026-07-21T05:27:34Z` / completed by operator attestation before `2026-07-21T14:00:03+08:00` |
| Operator / witness | Repository operator (manual QHeart-AP witness); Codex captured bounded HLAB/OIE projections |
| Product revision under live exercise | `25cc8f251788b138d90ed0f8fefd52baef9e6db6` |
| Acceptance-record revision | `b6e0fc3ca4b43cedb2cd24b8906375e65a535f63` |
| Worktree status | Clean before the acceptance-record commit |
| OS / Docker / Compose | Windows; Docker Engine `29.5.2`; Compose `5.1.3` |
| Compose project / file | `interoperability-lab`; `deploy/docker-compose.yml` |
| OIE image | `nextgenhealthcare/connect:4.5.2`; digest `sha256:4afa295cfe7c5ffd596efee69594157fea87202e33d66bb4a98a52db4598f836` |
| OIE application / network / appdata | Application reported `4.5.2`; network `interoperability-lab`; volume `interoperability-lab_oie-appdata` |
| HLAB | revision `25cc8f251788b138d90ed0f8fefd52baef9e6db6`; listener read-back `0.0.0.0:6665`, MLLP enabled and running |
| AP simulator | Native QHeart-AP `1.5.3`; OIE destination `192.168.65.254:6671` |
| Management API | `https://localhost:10443/api` (credentials excluded) |
| Synthetic Patient / Order | patient record `79`, MRN `Z52P-1328`; order record `51`, placer `ORD-000051` |
| Message controls | ORM `ORM20260721052758000051`; matched `ZAC52-MATCH-001`; unmatched `ZAC52-UNMATCH-001`; recovery `ZAC52-RECOVERY-001` |
| Evidence root | This file; operator attestation is durably recorded by commit `b6e0fc3ca4b43cedb2cd24b8906375e65a535f63` |

## Evidence references

- `EV-RUNTIME`: run manifest above and the runtime identity/status projections
  recorded in the acceptance commits `47fb987`, `6b82ce6`, and `290bf69`.
- `EV-OIE-ORM`: bounded OIE ORM statistics observed at
  `2026-07-21T05:42Z`: received 1, sent 1, error 0, queued 0.
- `EV-HLAB-RESULTS`: bounded HLAB result projection observed during
  `2026-07-21T05:43Z`-`05:44Z`: matched result 15, unmatched result 16,
  recovery result 17.
- `EV-RECOVERY`: bounded OIE ORU outage projection observed at
  `2026-07-21T05:44Z`: received 3, sent 2, error 0, queued 1; after restart the
  listener read-back reported `lastReceivedAt=2026-07-21T05:44:12Z`.
- `EV-OPERATOR`: the repository operator confirmed the complete manual flow,
  including exactly one correlated QHeart-AP ORM receipt. The attestation was
  recorded before `2026-07-21T14:00:03+08:00` in commit `b6e0fc3`; no AP API or
  screenshot artifact is claimed.
- `EV-AUTOMATED`: commit `290bf69` records focused 51-test and full 580-test
  passes plus compileall, diff, and strict OpenSpec validation.

## Completed evidence ledger

| ID | Timestamp / window | Correlation | Result | Stable evidence reference | Blocker / defect |
| --- | --- | --- | --- | --- | --- |
| ENV-01 | `2026-07-21T05:27Z` | `Z52-20260721-A` | PASS | `EV-RUNTIME`: OIE image digest and application `4.5.2` | none |
| ENV-02 | `2026-07-21T05:27Z` | `Z52-20260721-A` | PASS | `EV-RUNTIME`: Compose project, appdata, network, `6600`/`6661`/`6665`/`6671` route | none |
| ENV-03 | `2026-07-21T05:27Z` | QHeart-AP `1.5.3:6671` | PASS | `EV-RUNTIME`: AP build and OIE-network reachability | none |
| ENV-04 | `2026-07-21T05:27Z` | HLAB revision / `6665` | PASS | `EV-RUNTIME`: auto-started, running MLLP listener read-back | none |
| ENV-05 | `2026-07-21T05:27Z` | sentinel `3275d94d-a065-4c6c-9719-15ca98c7d23f`, rev 1 | PASS | `EV-RUNTIME`: `UNDEPLOYED`, baseline SHA-256 `50d3ce409aa3fdba2367894c829cefb682185eace28c6a9f294d8c3ba47124f1` | none |
| CH-01 | `2026-07-21T05:27Z` | saved local-lab profile | PASS | `EV-RUNTIME`: connection reported OIE `4.5.2` | none |
| CH-02 | `2026-07-21T05:39Z` | ORM Channel `e779f4c2-c6d7-4284-a664-116a37fa8d36`, rev 2 | PASS | `EV-RUNTIME`: `STARTED`, `OIE:6600 -> 192.168.65.254:6671` | none |
| CH-03 | `2026-07-21T05:27:34Z` | ORU Channel `5e7bef8d-19c1-4214-8f34-f02eed8cef26`, rev 1 | PASS | `EV-RUNTIME`: `STARTED`, `OIE:6661 -> lab-app:6665` | none |
| ORM-01 | `2026-07-21T05:42:21Z` | `ORM20260721052758000051` | PASS | `EV-OIE-ORM`: HLAB ACK `AA` for patient 79 / order 51 | none |
| ORM-02 | `2026-07-21T05:42Z` | `ORM20260721052758000051` | PASS | `EV-OIE-ORM`: received 1, sent 1, error 0, queued 0 | none |
| ORM-03 | before `2026-07-21T14:00:03+08:00` | `ORM20260721052758000051`, `Z52P-1328`, `ORD-000051` | PASS | `EV-OPERATOR`: exactly one correlated AP receipt, operator-witnessed | none |
| ORU-01 | `2026-07-21T05:43Z` | `ZAC52-MATCH-001` | PASS | `EV-HLAB-RESULTS`: ACK `AA`, result 15 delivered | none |
| ORU-02 | `2026-07-21T05:43Z` | result 15 / patient 79 / order 51 | PASS | `EV-HLAB-RESULTS`: raw payload retained, `order-matched` | none |
| ORU-03 | `2026-07-21T05:43Z` | `ZAC52-UNMATCH-001` / result 16 | PASS | `EV-HLAB-RESULTS`: `unmatched-patient`, null patient/order links | none |
| ORU-04 | `2026-07-21T05:43Z` | results 15 and 16 | PASS | `EV-HLAB-RESULTS`: result 15 remained associated after result 16 | none |
| LIFE-01 | `2026-07-21T05:39:48Z` | ORM Channel rev 2 | PASS | `EV-RUNTIME`: preview/read-back changed `host.docker.internal:6671` to `192.168.65.254:6671` | none |
| LIFE-02 | `2026-07-21T05:39Z` | prior managed ORM / exact managed name | PASS | `EV-RUNTIME`: guarded undeploy and delete completed | none |
| LIFE-03 | `2026-07-21T05:39Z` | ORM Channel `e779f4c2-c6d7-4284-a664-116a37fa8d36` | PASS | `EV-RUNTIME`: recreated, deployed, and `STARTED` | none |
| LIFE-04 | `2026-07-21T05:41Z` | sentinel baseline/current | PASS | `EV-RUNTIME`: ID, revision, status, and hash unchanged | none |
| REC-01 | `2026-07-21T05:44Z` | `ZAC52-RECOVERY-001` | PASS | `EV-RECOVERY`: source ACK `AA` while `lab-app` stopped | none |
| REC-02 | `2026-07-21T05:44Z` | `ZAC52-RECOVERY-001` | PASS | `EV-RECOVERY`: queued 1, error 0 | none |
| REC-03 | `2026-07-21T05:44:12Z` | `ZAC52-RECOVERY-001` / listener `6665` | PASS | `EV-RECOVERY`: listener auto-started and received queued delivery | none |
| REC-04 | after `2026-07-21T05:44:12Z` | `ZAC52-RECOVERY-001` / result 17 | PASS | `EV-HLAB-RESULTS`: exactly one persisted result, matched order 51 | none |
| OPS-01 | `2026-07-21T05:41Z`-`05:44Z` | `Z52-20260721-A` | PASS | `EV-RUNTIME`, `EV-RECOVERY`: bounded management/listener projections exercised | none |
| OPS-02 | `2026-07-21T05:47Z` and acceptance by `14:00:03+08:00` | `Z52-20260721-A` | PASS | `EV-AUTOMATED`, `EV-OPERATOR`: automated checks and synthetic-data evidence review passed | none |

Overall gate: **PASS**. Every required ledger ID has an explicit result,
timestamp or bounded observation window, correlation, and stable evidence
reference. No unresolved blocker remains in this run.
