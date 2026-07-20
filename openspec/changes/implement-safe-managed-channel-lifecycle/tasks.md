## 1. Lifecycle Contracts and Classification

- [x] 1.1 Add persistence-neutral lifecycle classifications, identity evidence, owned-field diff, preview token, step result, operation outcome, and audit event contracts.
- [x] 1.2 Implement deterministic inventory reconciliation across templates, persisted mappings, and live OIE Channels with conservative conflict precedence and external/read-only projection.
- [x] 1.3 Add domain tests for missing, unchanged, drifted, same-name conflict, ID/marker contradiction, duplicate marker, malformed payload, and external classification.

## 2. Targeted Persistence and Audit

- [x] 2.1 Add an idempotent SQLite migration for append-only OIE managed lifecycle audits and required mapping indexes/constraints.
- [x] 2.2 Add targeted compare-and-update and compare-and-clear mapping repository operations that preserve unrelated settings and mappings.
- [x] 2.3 Add transactional mapping-plus-audit writes and standalone audit writes with an explicit secret/PHI-safe field allowlist.
- [x] 2.4 Add repository and migration tests for targeted updates, concurrent mapping conflicts, delete clearing, rollback behavior, audit durability, and forbidden-content absence.

## 3. Preview and YOLO Safety Boundary

- [x] 3.1 Implement side-effect-free create, update, deploy, undeploy, and delete previews bound to exact operation, logical type, desired state, Channel ID, observed revision, and expiry.
- [x] 3.2 Implement preview-token signing or persisted short-lived preview records using the smallest existing project facility, including expiry and single-target validation.
- [x] 3.3 Enforce fail-closed pre-mutation refresh for ownership, classification, identity, revision, desired state, and destructive confirmation.
- [x] 3.4 Add tests proving force/override flags, wildcard or multi-target requests, skip-preview attempts, automatic adoption, startup mutation, stale tokens, target substitution, and redeploy-all cannot reach OIE mutations.

## 4. Managed Lifecycle Operations

- [x] 4.1 Implement idempotent create with refreshed `Missing` validation, exact approved payload creation, live rediscovery, and targeted mapping persistence.
- [x] 4.2 Implement safe update by refreshing the complete live Channel, merging only approved owned fields, preserving all other fields, explicitly using `override=false`, and avoiding unchanged writes.
- [x] 4.3 Implement exact single-Channel deploy and undeploy with refreshed ownership checks and status readback, without exposing redeploy-all.
- [x] 4.4 Implement delete as a bounded undeploy-if-needed and exact-ID delete sequence that retains the logical template mapping while clearing OIE identity/revision.
- [x] 4.5 Implement safe retry and `success`/`failure`/`partial-failure` assembly with ordered performed, failed, no-op, and unattempted steps.
- [x] 4.6 Add mocked service tests for successful and retried create/update/deploy/undeploy/delete, revision races, OIE/local-persistence partial failures, and recovery by refreshed inspection.

## 5. API and Application Composition

- [ ] 5.1 Wire lifecycle ports to the existing management-client factory, template compiler, OIE settings repository, clock, and operation/actor providers.
- [ ] 5.2 Add inspection and preview endpoints that return classifications, safe owned-field diffs, permitted actions, blocking reasons, and bounded mutation tokens.
- [ ] 5.3 Add explicit single-target mutation endpoints with stable status mapping, destructive delete confirmation, and no force, bulk, wildcard, adoption, or redeploy-all surface.
- [ ] 5.4 Add API and composition tests covering safe response projection, error categories, stale-preview responses, partial failures, and absence of secrets/PHI.

## 6. Settings UI Safety Surface

- [ ] 6.1 Present managed and external Channels distinctly with classification, identity evidence, current status, and read-only external controls.
- [ ] 6.2 Add owned-field previews before every action and disable actions for conflicts, stale state, unsupported transitions, or missing confirmation.
- [ ] 6.3 Add explicit delete confirmation tied to the logical type and clear step-level presentation for success, failure, partial failure, and required refresh.
- [ ] 6.4 Add frontend tests proving there is no bulk/force/adopt/redeploy-all control and that stale/conflict/external states cannot trigger mutation requests.

## 7. Verification

- [ ] 7.1 Run focused lifecycle domain, repository, service, API, composition, and frontend tests and record stable pass/fail evidence.
- [ ] 7.2 Run the repository quality checks and confirm existing OIE settings, management-client, template, patient, order, and result workflows remain compatible.
- [ ] 7.3 Audit logs, API fixtures, exception text, and persisted lifecycle records for credentials, cookies, authorization material, PHI, HL7 content, and complete Channel payload leakage.
- [ ] 7.4 Validate all OpenSpec artifacts and document any deferred live OIE 4.5.2 validation without weakening mocked safety acceptance criteria.
