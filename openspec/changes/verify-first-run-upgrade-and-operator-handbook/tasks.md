## 1. Verification Fixtures and Safety

- [ ] 1.1 Define the supported disposable Compose project, port, volume, synthetic-data, and cleanup boundaries with collision-safe pre-flight checks.
- [x] 1.2 Create or identify a versioned canonical pre-unified-Settings database fixture and document its schema provenance.
- [x] 1.3 Add secret and PHI canaries plus bounded evidence-capture helpers that reject unsafe output.

## 2. Fresh-Install Verification

- [x] 2.1 Add automated coverage for startup with no `.env`, database, or prior volumes and for accurate initial readiness/default projections.
- [ ] 2.2 Verify Medplum configuration and bounded authenticated stages through Settings using synthetic credentials.
- [ ] 2.3 Verify built-in OIE and dcm4chee defaults plus explicit configure-or-disable flows for GDT and AP.
- [ ] 2.4 Verify setup completion across application restart and compatible container recreation with retained storage.

## 3. Upgrade and Precedence Verification

- [x] 3.1 Add the canonical legacy database and representative eligible environment values to an isolated upgrade harness.
- [ ] 3.2 Verify atomic schema/profile migration, secret configured-state preservation, effective precedence, and absence of workflow regression.
- [x] 3.3 Change migrated settings through the UI, restart with conflicting legacy environment values, and prove persisted authority and bootstrap idempotence.

## 4. Failure and Authority Matrix

- [ ] 4.1 Verify wrong Medplum secret and unreachable FHIR URL classification, partial-stage outcomes, and recovery guidance.
- [ ] 4.2 Verify missing or unwritable GDT paths without creating, deleting, or moving an unsafe target.
- [ ] 4.3 Verify unreachable dcm4chee, invalid AE title, AP/OIE drift, and partial service availability as independent bounded failures.
- [ ] 4.4 Scan API, UI, wrapper, selected log, screenshot, and evidence outputs for secret, PHI, raw-message, FHIR-body, and upstream-response canaries.
- [x] 4.5 Add or confirm contracts proving Settings cannot rewrite Compose or invoke arbitrary Docker operations.

## 5. Operator Handbook Reconciliation

- [ ] 5.1 Rewrite English and Traditional Chinese Quick Start chapters around one wrapper start command and browser-based guided setup.
- [ ] 5.2 Document creation of a Medplum ClientApplication and exact mapping of client ID and write-only secret fields into Settings.
- [ ] 5.3 Separate normal Settings fields from Advanced deployment overrides and legacy compatibility bootstrap.
- [ ] 5.4 Document Windows GDT host versus container paths and internal service URLs versus browser-facing URLs.
- [ ] 5.5 Reconcile secret rotation, persisted-settings backup/restore, upgrade, rollback, restart, and container-recreation semantics.
- [ ] 5.6 Compare stable commands, UI labels, tables, and safety guidance across both languages and regenerate both Word editions.

## 6. Disposable Live Evidence and Closure

- [ ] 6.1 Execute the fresh-install matrix in an exclusively owned disposable environment and record the exact tested commit and environment.
- [ ] 6.2 Execute the legacy-upgrade and second-restart precedence matrix without deleting retained volumes.
- [ ] 6.3 Execute the failure/safety matrix and inspect all screenshots for synthetic data and absent credentials.
- [ ] 6.4 Record precise environment-dependent skips and create linked defect issues for reproducible implementation failures that block acceptance.
- [ ] 6.5 Run unit, integration, frontend, Compose contract, migration, syntax, handbook-generation, OpenSpec strict-validation, and diff-hygiene checks.
