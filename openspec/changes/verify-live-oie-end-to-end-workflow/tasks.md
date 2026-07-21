## 1. Live Environment and Evidence Contract

- [ ] 1.1 Identify and document the authoritative OIE 4.5.2 image/runtime, AP simulator build and endpoint, HLAB revision, network topology, and safe synthetic-data assumptions.
- [ ] 1.2 Define the exact clean-state and rerun procedures, including verified Compose project/volume targets, external sentinel Channel setup, and recovery from an interrupted run.
- [ ] 1.3 Add a pass/fail/blocked evidence ledger covering every ZAC-52 verification step with run metadata, correlation identifiers, timestamps, safe evidence references, and blocker tracking.
- [ ] 1.4 Reconcile prerequisites and legacy OIE channel/port documentation before execution so the live procedure has one unambiguous route contract.

## 2. Repeatable Live Smoke Support

- [ ] 2.1 Add bounded preflight checks for OIE version and Management API reachability, HLAB `6665` listener state, published OIE ports, and AP `6671` reachability without exposing credentials.
- [ ] 2.2 Add or document deterministic synthetic ORM and matched, unmatched, and recovery ORU fixtures with unique Patient, Order, and `MSH-10` correlation identifiers.
- [ ] 2.3 Add repeatable smoke steps or helper tooling that captures ACKs, bounded diagnostics, persistence outcomes, and queue/retry observations without destructive cleanup or fixed-sleep assumptions.
- [ ] 2.4 Add automated tests for any new smoke helper parsing, redaction, timeout, and failure-classification behavior.

## 3. Clean Provisioning and ORM Verification

- [ ] 3.1 Start the documented clean OIE and HLAB environment and record OIE 4.5.2, container/runtime, listener auto-start, and port-preflight evidence.
- [ ] 3.2 Connect Settings with the local-lab profile, preview, create, and deploy `HLAB_ORM_TO_AP` and `HLAB_ORU_TO_HLAB`, recording exact route and started-state evidence.
- [ ] 3.3 Create and send a uniquely correlated HLAB ORM through OIE `6600`, then record exactly one AP `6671` receipt, ACK, and successful OIE/HLAB transmission status.

## 4. ORU Matching and Lifecycle Isolation

- [ ] 4.1 Send a uniquely correlated matched ORU from AP through OIE `6661` to HLAB `6665` and record raw-HL7 preservation plus correct Patient and Order association.
- [ ] 4.2 Send a valid unmatchable ORU and record its preserved appearance in Unmatched Results without affecting the matched result.
- [ ] 4.3 Create or identify an external sentinel Channel, record its identity/revision/configuration/deployment baseline, edit the managed AP destination, preview the diff, and redeploy successfully.
- [ ] 4.4 Undeploy, delete with exact-name confirmation, recreate, and deploy one managed Channel, then prove the external sentinel Channel remained unchanged.

## 5. Outage and Recovery Verification

- [ ] 5.1 Stop `lab-app`, send a uniquely correlated recovery ORU to OIE, and record that OIE accepted it while the HLAB destination became queued or retryable.
- [ ] 5.2 Restart `lab-app`, record `6665` listener auto-start and eventual queued delivery, and prove exactly one persisted result for the recovery `MSH-10`.
- [ ] 5.3 Exercise the documented diagnostic and operator recovery guidance for the observed outage layers and record any timing, API-visibility, or queue limitations.

## 6. Operations Documentation and Final Gate

- [ ] 6.1 Publish the verified port matrix and route diagram for `HLAB -> OIE:6600 -> AP:6671` and `AP -> OIE:6661 -> HLAB:6665`.
- [ ] 6.2 Publish Settings and managed-Channel operating instructions plus create/edit/deploy/undeploy/delete/recreate and outage-recovery SOPs.
- [ ] 6.3 Publish known limitations, troubleshooting guidance, clean-rerun instructions, and the repeatable protocol-level smoke check for an operator who did not implement the feature.
- [ ] 6.4 Run focused automated tests, the full regression suite, syntax/compile checks, strict OpenSpec validation, and secret/PHI evidence review.
- [ ] 6.5 Complete the evidence ledger with a result for every required step and leave the gate failed or blocked if any unresolved blocking defect remains.
