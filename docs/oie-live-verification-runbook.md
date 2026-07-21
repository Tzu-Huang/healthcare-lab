# OIE 4.5.2 live verification runbook and evidence ledger

This is the canonical operator procedure for ZAC-52. It defines the live gate;
it does **not** assert that a run has passed. Copy the ledger section for each
run, fill every field, and leave the overall gate failed or blocked whenever a
required row lacks passing evidence.

## Route contract

```text
ORM: HLAB -> OIE:6600 -> AP:6671
ORU: AP   -> OIE:6661 -> HLAB:6665
```

| Flow | Sender | Receiver and endpoint | Network detail |
| --- | --- | --- | --- |
| ORM ingress | HLAB | OIE TCP Listener `:6600` | Compose DNS `oie:6600`; host publication defaults to `6600` |
| ORM delivery | OIE | AP MLLP Listener `:6671` | Use the verified AP host/IP reachable from the OIE container |
| ORU ingress | AP | OIE TCP Listener `:6661` | AP uses Docker-host address; host publication defaults to `6661` |
| ORU delivery | OIE | HLAB MLLP Listener `lab-app:6665` | Docker-network endpoint; not published by default |

The managed Channels are exactly `HLAB_ORM_TO_AP` and
`HLAB_ORU_TO_HLAB`. The authoritative OIE image is
`nextgenhealthcare/connect:4.5.2`. Record the resolved image ID/digest during
the run; a floating or unrecorded substitute is not sufficient evidence.

Older documents remain useful historical context but are not authoritative for
this gate. `docs/mirth-connect-setup.md` and parts of `README.md` describe
manual `HOSPITAL_PUSH_TO_AP` / `HOSPITAL_RECEIVE_ORU` Channels.
`docs/ap-integration-test-notes.md` includes an old ORM port `6663`. Do not use
those names or that port for ZAC-52. `docs/healthcare-lab-simple-workflows.md`
and `deploy/README.md` reflect the intended four-port route above.

### 2026-07-21 readiness inventory (not acceptance evidence)

The read-only inventory performed before the first ZAC-52 run found OIE image
`nextgenhealthcare/connect:4.5.2` in Compose project `interoperability-lab`,
HLAB HTTP on host `5000`, and the HLAB listener running internally at
`0.0.0.0:6665`. The Windows-native simulator
`C:\Program Files\QHeart-AP\QHeart-AP.exe` reported product/file version
`1.5.3` and was listening on host `6671`. The repository readiness revision was
`08b22c1196a848317389da9a4f24edb3ffd45f19`; the witnessed acceptance run must
record its own later revision rather than reusing this inventory value.

This runtime is not a clean baseline. Its OIE container still publishes legacy
host port `6663` instead of required `6600`; an external started
`AP_RESULT_TO_LAB` Channel owns OIE listener `6661`; both managed HLAB Channels
are missing; and runtime diagnostics report port conflicts. The desired ORM
destination currently resolves to `hl7tester:6671`, whose reachability from the
OIE container must be proven. These facts block protocol and lifecycle
acceptance until the controlled clean-state procedure resolves them.

A bounded host-side helper run confirmed OIE management, host `6661`, and AP
`6671` reachable; host `6600` and `6665` timed out; and the safe HLAB diagnostic
projection returned `degraded`. The `6665` host result is expected because the
listener is internal-only, while the `6600` result is a blocking publication
mismatch. No fixture was sent during this readiness check.

## Safety and evidence rules

- Use synthetic data only. Never paste passwords, session tokens, API
  authorization headers, production identifiers, or real PHI into evidence.
- Use one run token, for example `Z52-20260721T143000Z-A1B2`, and derive unique
  values such as Patient ID `Z52P-A1B2`, Order ID `Z52O-A1B2`, and message
  controls `Z52-ORM-A1B2`, `Z52-ORU-MATCH-A1B2`,
  `Z52-ORU-UNMATCH-A1B2`, and `Z52-ORU-RECOVER-A1B2`.
- Evidence references must be repository-relative paths or stable external
  references with access instructions. Prefer bounded JSON/text projections,
  timestamps, status codes, Channel IDs/revisions, and redacted screenshots.
- Never store raw configuration exports until they have been checked for
  credentials. Redact secrets, cookies, host credentials, and unrelated
  patient data.
- `PASS` requires direct evidence. Use `FAIL` when an assertion was exercised
  and was false. Use `BLOCKED` when it could not be exercised, and record the
  blocker and owner. `NOT RUN` is not a passing result.

## Run metadata

Fill before changing runtime state.

| Field | Value |
| --- | --- |
| Run token | `NOT RECORDED` |
| Started / ended (UTC with offset) | `NOT RECORDED` |
| Operator / witness | `NOT RECORDED` |
| Repository revision (`git rev-parse HEAD`) | `NOT RECORDED` |
| Worktree status | `NOT RECORDED` |
| OS, Docker and Compose versions | `NOT RECORDED` |
| Compose project name and compose file | `NOT RECORDED` |
| OIE image name, ID and digest | `nextgenhealthcare/connect:4.5.2`; ID/digest `NOT RECORDED` |
| OIE application-reported version | `NOT RECORDED` |
| OIE container ID / network | `NOT RECORDED` |
| OIE data volume or bind-mount absolute target | `NOT RECORDED` |
| HLAB revision / container ID | `NOT RECORDED` |
| AP simulator name, build/revision, host and `6671` endpoint | `NOT RECORDED` |
| Management API URL (no credentials) | `NOT RECORDED` |
| Synthetic Patient / Order IDs | `NOT RECORDED` |
| ORM / matched ORU / unmatched ORU / recovery ORU `MSH-10` | `NOT RECORDED` |
| Evidence root | `NOT RECORDED` |

## Clean-state preparation

### Resolve targets first

1. Confirm the repository revision and that local changes are understood.
2. Resolve Compose configuration and project name. Inspect
   `docker compose -f deploy/docker-compose.yml config` and
   `docker compose -f deploy/docker-compose.yml ps`; record container, network,
   volume, bind-mount, and published-port identities.
3. Inspect the OIE mount target. If the resolved target is missing, broad,
   ambiguous, shared with another Compose project, or contains non-lab data,
   stop with `BLOCKED`.
4. Record the AP simulator build and prove its `6671` listener is a real MLLP
   endpoint rather than a generic TCP acceptor.
5. In OIE, create or identify one harmless external sentinel Channel whose name
   does not start with `HLAB_`. Record its Channel ID, name, revision,
   configuration hash/export reference, and deployed state. This sentinel must
   survive the managed-Channel lifecycle test unchanged.

### Destructive first-run reset

> **DESTRUCTIVE:** removing or replacing the OIE appdata volume erases Channels,
> messages, users/settings, and other OIE state in that target. Do not execute a
> reset from an unresolved environment variable, wildcard, workspace root, home
> directory, or unverified Compose project. Obtain operator approval after the
> exact absolute target and recovery plan are displayed.

For a true clean-runtime proof, export only approved recovery material, stop the
resolved OIE service, remove/reinitialize only the verified lab OIE appdata
target, and recreate OIE from `nextgenhealthcare/connect:4.5.2`. Do not use
routine smoke checks to perform this reset. After reset, recreate the external
sentinel and capture its baseline before creating either managed Channel.

If preserving the sentinel across physical appdata reset is required, export it
before reset, inspect/redact the export, then import it before the baseline.
Never interpret successful restoration as proof that unrelated Channels were
preserved by the reset.

### Ordinary rerun

An ordinary rerun is non-destructive:

1. Use a new run token and new Patient, Order, and all four `MSH-10` values.
2. Record existing managed Channel IDs/revisions and the external sentinel
   baseline.
3. Clear no OIE volume or message history. Do not delete application records.
4. Use the guarded Settings lifecycle operations to return only the two managed
   Channels to their expected deployed definitions.
5. Filter observations by the new correlation values and timestamps.

If a run is interrupted, preserve logs and queue state, mark incomplete rows
`BLOCKED`, record the last completed action, and decide explicitly between
continuing the same run or starting an ordinary rerun. Never reuse an `MSH-10`
to make a fresh run look successful. If an operation preview expired or Channel
identity/revision changed, refresh state and obtain a new preview; do not bypass
the stale-preview guard.

## Preconditions and bounded preflight

Capture output without secrets. A TCP-open result proves reachability only, not
HL7 behavior.

1. Confirm Docker reports the OIE container image/tag and resolved digest, then
   confirm the running application reports version `4.5.2` through its UI or
   Management API.
2. Verify OIE HTTP/HTTPS Management API reachability using the saved local-lab
   Settings profile. Record status and latency, never credentials.
3. Confirm Compose publishes host `6600 -> oie:6600` and
   `6661 -> oie:6661`; confirm `lab-app:6665` is internal and listening.
4. From the OIE container/network perspective, test AP host port `6671`.
5. Open Settings, choose **Refresh all**, and run **Runtime Diagnostics**.
   Record each independent check rather than only the roll-up.
6. If HLAB saved listener intent differs from actual runtime, restart/recreate
   `lab-app` as appropriate, then use **Retry**. Saving listener settings alone
   does not rebind a running socket.

Any image/version mismatch, unreachable required endpoint, missing AP receipt
facility, or ambiguous clean target blocks the affected live steps.

## Settings and managed-Channel lifecycle SOP

1. In **Settings > OIE Connection**, set the Management API URL, username, TLS
   mode, and timeout. Enter a password only when replacing it. Select **Save
   Connection**, then **Test saved connection**.
2. In **HLAB Result Listener**, set `0.0.0.0:6665`, enable MLLP framing and
   auto-start, save, and apply the displayed restart/retry guidance. Confirm
   actual runtime shows the expected endpoint and state.
3. Refresh managed Channels. For each missing managed Channel, choose its create
   action, review Channel name, route, diff and ordered steps in **Operation
   preview**, then execute before the preview expires.
4. Deploy `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB` through fresh previews. Read
   back each Channel ID, revision, endpoint configuration, and started state.
5. To edit the AP destination, change only the approved managed setting, obtain
   a fresh Apply/Redeploy preview, compare the exact old/new endpoint, execute,
   and prove the read-back equals the preview. Restore the intended endpoint by
   the same guarded process if the test used a temporary reachable target.
6. To undeploy, preview the managed Channel and execute, then verify stopped
   state. To delete, obtain a fresh delete preview and type the exact displayed
   Channel name in the confirmation field. Never delete by ID/name outside the
   managed UI during this gate.
7. Recreate and deploy the deleted managed Channel from its fixed template.
   Compare the external sentinel's ID, revision, configuration hash and deployed
   state with its baseline. Any sentinel mutation fails isolation.

Endpoint changes require Apply/Redeploy. Host-published port changes require
OIE container recreation. Listener intent changes require `lab-app`
restart/recreation or Retry; a Channel redeploy cannot apply either of those.

## Protocol verification SOP

### ORM

Create the synthetic Patient and Order in HLAB, preview the ORM, and record its
Patient ID, Order ID, and unique `MSH-10`. Send it to OIE `6600`. Capture the
HLAB send result and ACK, OIE source/destination status, and AP observation on
`6671`. PASS requires an accepted ACK, successful status, and exactly one AP
receipt for the same correlation identifiers within the recorded observation
window.

### Matched and unmatched ORU

From the AP, send a valid matched ORU with a new `MSH-10` to OIE `6661`. PASS
requires the OIE/HLAB ACK path, byte-preserved raw HL7 in HLAB, and association
with the expected Patient and Order. Then send a valid ORU with synthetic but
unknown matching identifiers and its own `MSH-10`. PASS requires preservation
in **Unmatched Results** without changing the matched result.

### Outage and recovery

Stop only `lab-app`; leave OIE and AP running. Send the recovery ORU once to
OIE `6661`. Record OIE acceptance and the `HLAB_ORU_TO_HLAB` destination as
queued/retryable. Do not purge or manually resend it. Restart `lab-app`, record
listener `6665` auto-start, and poll bounded diagnostics/message state until a
documented deadline. PASS requires eventual delivery and exactly one persisted
HLAB result for the recovery `MSH-10`. Record retry interval, queue visibility,
latency, and any duplicates observed.

The intended ORU destination contract queues connection failures and ACK
timeouts, retries every 10 seconds indefinitely, retains up to 1000 messages,
uses 5000 ms send/response timeouts, and validates the returned HL7 ACK. Confirm
the live deployed values rather than assuming the template was applied.

## Evidence ledger

Replace `BLOCKED / NOT RUN` only after execution. Add timestamps and references
to every row; expand rows for retries or defects without deleting failures.

| ID | Required observation | Correlation | Result | UTC timestamp / evidence reference | Blocker or defect |
| --- | --- | --- | --- | --- | --- |
| ENV-01 | Exact OIE image/digest and app-reported `4.5.2` | run token | BLOCKED / NOT RUN | - | - |
| ENV-02 | Compose project, mounts, network and four endpoints recorded | run token | BLOCKED / NOT RUN | - | - |
| ENV-03 | AP build and MLLP `6671` endpoint recorded/reachable | run token | BLOCKED / NOT RUN | - | - |
| ENV-04 | HLAB revision and auto-started `6665` listener recorded | run token | BLOCKED / NOT RUN | - | - |
| ENV-05 | External sentinel baseline captured | sentinel ID/revision/hash | BLOCKED / NOT RUN | - | - |
| CH-01 | Settings connection test passes | run token | BLOCKED / NOT RUN | - | - |
| CH-02 | `HLAB_ORM_TO_AP` preview/create/deploy/read-back | Channel ID/revision | BLOCKED / NOT RUN | - | - |
| CH-03 | `HLAB_ORU_TO_HLAB` preview/create/deploy/read-back | Channel ID/revision | BLOCKED / NOT RUN | - | - |
| ORM-01 | HLAB send and accepted ACK | ORM `MSH-10` | BLOCKED / NOT RUN | - | - |
| ORM-02 | OIE successful route status | ORM `MSH-10` | BLOCKED / NOT RUN | - | - |
| ORM-03 | Exactly one AP `6671` receipt | ORM `MSH-10`, Patient, Order | BLOCKED / NOT RUN | - | - |
| ORU-01 | Matched ORU accepted and delivered | matched ORU `MSH-10` | BLOCKED / NOT RUN | - | - |
| ORU-02 | Raw HL7 preserved and correct Patient/Order association | matched ORU `MSH-10` | BLOCKED / NOT RUN | - | - |
| ORU-03 | Unmatchable ORU preserved in Unmatched Results | unmatched ORU `MSH-10` | BLOCKED / NOT RUN | - | - |
| ORU-04 | Matched result remains unchanged | matched + unmatched IDs | BLOCKED / NOT RUN | - | - |
| LIFE-01 | AP destination edit diff preview and redeploy/read-back | Channel ID/revision | BLOCKED / NOT RUN | - | - |
| LIFE-02 | Managed Channel undeploy/delete with exact confirmation | Channel ID/name | BLOCKED / NOT RUN | - | - |
| LIFE-03 | Managed Channel recreate/deploy succeeds | new Channel ID/revision | BLOCKED / NOT RUN | - | - |
| LIFE-04 | External sentinel unchanged | sentinel baseline/current | BLOCKED / NOT RUN | - | - |
| REC-01 | OIE accepts recovery ORU while `lab-app` stopped | recovery `MSH-10` | BLOCKED / NOT RUN | - | - |
| REC-02 | Destination becomes queued/retryable | recovery `MSH-10` | BLOCKED / NOT RUN | - | - |
| REC-03 | Restart auto-starts HLAB `6665` and queue drains | recovery `MSH-10` | BLOCKED / NOT RUN | - | - |
| REC-04 | Exactly one recovery result persisted | recovery `MSH-10` | BLOCKED / NOT RUN | - | - |
| OPS-01 | Diagnostics exercised; timing/API/queue limitations recorded | run token | BLOCKED / NOT RUN | - | - |
| OPS-02 | Evidence reviewed for secrets/PHI and every row resolved | run token | BLOCKED / NOT RUN | - | - |

Overall gate: **BLOCKED / NOT RUN**. Gate owner: `NOT RECORDED`. Open blockers:
`NOT RECORDED`.

## Repeatable non-destructive smoke check

Use a fresh run token. This smoke check never resets volumes, deletes Channels,
purges queues, or reuses identifiers.

Run the bounded helper from a network context that can reach every named
endpoint. For a host-side preflight where HLAB `6665` is intentionally not
published, omit that unreachable topology only by running the helper inside the
Compose network and naming `lab-app`; do not reinterpret an unavailable host
probe as a pass. Example from the Compose network:

```powershell
python tools\oie_live_smoke.py --host oie --hlab-host lab-app `
  --ap-host host.docker.internal --management-port 8443 `
  --diagnostics-url http://lab-app:5000/api/oie/settings/diagnostics
```

An MLLP send is opt-in: add `--fixture <synthetic-hl7-file>` only after checking
that the file contains the current run's unique identifiers. The helper emits
only the ACK code and a bounded hash of the control ID; it never prints raw HL7.

1. Record revisions/image and run the bounded preflight above.
2. Confirm both managed Channels are started and their live route read-back is
   the four-port contract; confirm the external sentinel is unchanged.
3. Create one synthetic Patient/Order and send one unique ORM. Capture ACK,
   successful OIE status, and exactly one AP receipt.
4. Send one unique matched ORU and one unique unmatched ORU. Capture ACKs, raw
   preservation, correct association, and unmatched isolation.
5. Run Settings diagnostics and record bounded projections.
6. Optionally perform outage/recovery only in an announced maintenance window;
   stopping `lab-app` is disruptive. Never add a fixed sleep: poll until an
   explicit deadline and preserve the observation timeline.
7. Complete every ledger row in scope and mark the overall gate PASS only when
   all required rows pass. A Compose `smoke` status alone is insufficient; it
   does not prove protocol routing, matching, lifecycle isolation, or recovery.

## Troubleshooting and known limitations

| Symptom | Check / recovery |
| --- | --- |
| Management API unavailable | Verify saved URL, OIE container/app health, TLS mode and credentials. Do not capture credentials. Run independent diagnostics. |
| `6600` or `6661` unreachable | Compare Compose resolved publications with the host used by the sender; recreate OIE after publication changes. |
| OIE cannot reach AP `6671` | Test from OIE's network perspective; check AP listener bind address/firewall and configured destination host. `127.0.0.1` inside OIE is the OIE container. |
| OIE cannot reach HLAB `6665` | Use `lab-app:6665`, not host loopback; verify saved intent versus runtime, auto-start state, and Docker network membership. Retry/restart HLAB without purging OIE queue. |
| Lifecycle action rejects preview | State or revision changed, token expired, or confirmation differs. Refresh and create a new preview; never bypass the guard. |
| ORM has ACK but AP evidence is absent | ACK may cover only an upstream hop. Inspect destination status and AP receipt by `MSH-10`; do not mark PASS. |
| ORU is unmatched | Compare Patient, Order/filler/placer identifiers and message type against the synthetic source record; preserve raw HL7. |
| ORU remains queued | Inspect destination error, ACK validation, retry timing, listener state and capacity. Preserve queue; document API visibility gaps. |
| Duplicate result appears | Count persisted rows by recovery `MSH-10`, retain retry timeline and ACK evidence, and file a blocking defect. |

Known limitations for the gate:

- TCP connectivity alone does not prove MLLP framing, HL7 parsing, ACK
  validation, destination delivery, or persistence.
- Browser lifecycle actions and AP receipt may require witnessed screenshots if
  the AP exposes no stable automation interface.
- OIE Management API status/queue projections may lag runtime events; record
  polling timestamps and observed convergence instead of relying on fixed sleep.
- Saving listener settings does not rebind an already running listener.
- Published-port changes require container recreation; managed Channel
  redeployment cannot change Docker publications.
- The live gate is environment-specific. Automated unit/integration tests and
  Compose health checks are supporting evidence, not substitutes for the
  end-to-end ledger.
