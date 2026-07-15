# Code Review: ZAC-57 (Round 2)

## Findings

### [P1] Keep the compatibility-delegate exemption structurally narrow

`tests/test_architecture_contract.py:268` treats any one-line return call as a compatibility delegate when any attribute in the call chain ends with `_repository`; line 263 similarly exempts every global function whose name starts with `compose_`. Because `_visit_function` returns before traversing the function body, arbitrary new implementation such as `return attacker.fake_repository.execute(payload)` or SQL/workflow calls nested in its arguments produces no legacy candidate at all. This weakens the guard that ZAC-57 is intended to strengthen. Restrict the exemption to an exact mechanically thin shape rooted at `self.<approved_repository>.<method>(...)` (and any specifically approved composition seam), continue visiting argument expressions, and add negative fixtures proving lookalike repository/compose calls are rejected.

### [P1] Do not refresh reviewed legacy exceptions to make the extraction pass

`tests/architecture_legacy_baseline.py:69` replaces the reviewed `DemoStore` catch-all fingerprint with a new fingerprint, and line 600 does the same for the aggregate transport exception. The OpenSpec design explicitly makes any changed exception a stop condition and permits only removal of extracted entries. Refreshing these fingerprints approves the modified catch-all class wholesale and prevents the contract from demonstrating exception reduction. Change the collector/baseline representation so the extracted entries can be removed without replacing the existing `DemoStore` catch-all or transport exception with newly reviewed hashes.

### [P2] Import the asserted exception before the test runner starts

`tests/repositories/test_oie_settings.py:144` imports `SimulatorValidationError` after the `if __name__ == "__main__": unittest.main()` block. Discovery happens to work because the module import reaches line 144, but direct module execution starts the suite first and `test_rejects_duplicate_logical_types_atomically` fails with `NameError`. Move the import to the normal import section; `python -m tests.repositories.test_oie_settings` should pass as well as discovery.

## Missing Tests and Residual Risks

- The delegate exemption has no negative fixtures for lookalike `_repository` attributes, broad `compose_*` names, or implementation hidden in call arguments.
- The automated suite passes only because test discovery imports the entire OIE settings module before running it; direct module execution exposes the ordering defect.
- Review did not contact live OpenEMR/OIE services or run Docker, deployment, push, merge, or release actions.

## Prior Finding Status

- Resolved: the lazy WSGI import-isolation regression now launches `sys.executable`.
- Resolved: pure lab and OIE settings assertions moved from the mixed `DemoStore` module to responsibility-specific repository suites.

## Verification Reviewed

- Focused extraction and isolation suite: 45 tests passed.
- Architecture contract suite: 34 tests passed, but the exemptions above make that pass insufficient.
- Full automated suite: 260 tests passed with `instance/healthcare-lab.db` hash and timestamp unchanged.
- Direct `python -m tests.repositories.test_oie_settings`: 4 tests run, 1 error (`NameError`).
- Architecture-rule probes for arbitrary `_repository` and `compose_*` return calls: zero violations reported.

## Verdict

Changes requested. Tighten the architecture enforcement without baseline exception churn and correct the relocated test import before `/dev-done`.
