# Codex Code Review

- Branch: `feature/redesign-dcm4chee-patient-console`
- Base: `main`
- Change: `redesign-dcm4chee-patient-console`
- Verdict: **Changes requested**

## Findings

### [P2] Preserve PDF artifact metadata in the structured Study table

The new Study table projects result records into DICOM and diagnostic columns, but it drops the previously visible artifact label and media type. The only remaining artifact UI is the generic `Open Artifact` / `Copy Artifact` action derived from the representative record. As a result, operators cannot identify which PDF artifact they are opening, cannot see its media type, and can lose artifact visibility entirely when the artifact is present on another record in the Study group rather than the representative row.

This regresses the archived requirement that a simulated AP PDF return expose the artifact label and link or path metadata. Add structured columns such as Artifact, Artifact Type, and Artifact Location (or equivalent labeled action text), and select artifact metadata across the Study records rather than only from `study.records[0]`.

- Location: `frontend/static/app.js:1090`
- Related requirement: `openspec/specs/healthcare-lab-dcm4chee-mwl-order-model/spec.md:426`

## Missing Tests

- `tests/test_app.py:2592` verifies the new renderer mostly through source-string presence. It does not render a PDF result fixture and assert that artifact label/type/location survive the table projection. A DOM-level regression test for that fixture would have caught the finding above.
- Selection-versus-disclosure and responsive containment were verified with an ad hoc Playwright run, but no executable browser regression test is committed. Future changes can break those interactions while the static source assertions continue to pass.

## Verification Reviewed

- `python -m unittest tests.test_app` — 113 tests passed.
- `node --check frontend/static/app.js` — passed.
- `openspec validate redesign-dcm4chee-patient-console --strict --no-interactive` — passed.
- Headless Chromium checks at 1440px, 900px, and 390px — passed during `/dev-apply`.
- Working tree was clean before this review file was created.

## Residual Risks

- The 10-column Study table depends on horizontal scrolling for readability. The current containment rules prevent page-level overflow, but usability with real long UIDs still depends on the local scroll affordance being discoverable.
