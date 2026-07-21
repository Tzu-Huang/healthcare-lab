## 1. Live Environment and Evidence Contract

- [x] 1.1 Identify and document the authoritative OIE 4.5.2 image/runtime, AP simulator build and endpoint, HLAB revision, network topology, and safe synthetic-data assumptions.
- [x] 1.2 Define the exact clean-state and rerun procedures, including verified Compose project/volume targets, external sentinel Channel setup, and recovery from an interrupted run.
- [x] 1.3 Add a pass/fail/blocked evidence ledger covering every ZAC-52 verification step with run metadata, correlation identifiers, timestamps, safe evidence references, and blocker tracking.
- [x] 1.4 Reconcile prerequisites and legacy OIE channel/port documentation before execution so the live procedure has one unambiguous route contract.

## 2. Repeatable Live Smoke Support

- [x] 2.1 Add bounded preflight checks for OIE version and Management API reachability, HLAB `6665` listener state, published OIE ports, and AP `6671` reachability without exposing credentials.
- [x] 2.2 Add or document deterministic synthetic ORM and matched, unmatched, and recovery ORU fixtures with unique Patient, Order, and `MSH-10` correlation identifiers.
- [x] 2.3 Add repeatable smoke steps or helper tooling that captures ACKs, bounded diagnostics, persistence outcomes, and queue/retry observations without destructive cleanup or fixed-sleep assumptions.
- [x] 2.4 Add automated tests for any new smoke helper parsing, redaction, timeout, and failure-classification behavior.

## 3. Clean Provisioning and ORM Verification

- [x] 3.1 Start the documented clean OIE and HLAB environment and record OIE 4.5.2, container/runtime, listener auto-start, and port-preflight evidence.
- [x] 3.2 Connect Settings with the local-lab profile, preview, create, and deploy `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB`, recording exact route and started-state evidence.
- [ ] 3.3 Create and send a uniquely correlated HLAB ORM through OIE `6600`, then record exactly one AP `6671` receipt, ACK, and successful OIE/HLAB transmission status.

## 4. ORU Matching and Lifecycle Isolation

- [x] 4.1 Send a uniquely correlated matched ORU from AP through OIE `6661` to HLAB `6665` and record raw-HL7 preservation plus correct Patient and Order association.
- [x] 4.2 Send a valid unmatchable ORU and record its preserved appearance in Unmatched Results without affecting the matched result.
- [x] 4.3 Create or identify an external sentinel Channel, record its identity/revision/configuration/deployment baseline, edit the managed AP destination, preview the diff, and redeploy successfully.
- [x] 4.4 Undeploy, delete with exact-name confirmation, recreate, and deploy one managed Channel, then prove the external sentinel Channel remained unchanged.

## 5. Outage and Recovery Verification

- [x] 5.1 Stop `lab-app`, send a uniquely correlated recovery ORU to OIE, and record that OIE accepted it while the HLAB destination became queued or retryable.
- [x] 5.2 Restart `lab-app`, record `6665` listener auto-start and eventual queued delivery, and prove exactly one persisted result for the recovery `MSH-10`.
- [x] 5.3 Exercise the documented diagnostic and operator recovery guidance for the observed outage layers and record any timing, API-visibility, or queue limitations.

## 6. Operations Documentation and Final Gate

- [x] 6.1 Publish the verified port matrix and route diagram for `HLAB -> OIE:6600 -> AP:6671` and `AP -> OIE:6661 -> HLAB:6665`.
- [x] 6.2 Publish Settings and managed-Channel operating instructions plus create/edit/deploy/undeploy/delete/recreate and outage-recovery SOPs.
- [x] 6.3 Publish known limitations, troubleshooting guidance, clean-rerun instructions, and the repeatable protocol-level smoke check for an operator who did not implement the feature.
- [x] 6.4 Run focused automated tests, the full regression suite, syntax/compile checks, strict OpenSpec validation, and secret/PHI evidence review.
- [x] 6.5 Complete the evidence ledger with a result for every required step and leave the gate failed or blocked if any unresolved blocking defect remains.
