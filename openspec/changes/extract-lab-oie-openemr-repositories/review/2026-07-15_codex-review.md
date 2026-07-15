# Code Review: ZAC-57

## Findings

### [P1] Use the active Python interpreter in the import-isolation regression

`tests/runtime/test_lazy_wsgi.py:32` launches `ROOT / ".venv" / "Scripts" / "python.exe"`. That path exists only in the current Windows checkout. The supported Docker application environment uses Linux (`python:3.11-slim`) and a clean CI or contributor checkout is not required to contain a repository-local Windows virtualenv, so this test raises `FileNotFoundError` before it can perform the isolation assertion. Use `sys.executable` so the subprocess runs with the interpreter executing the test suite.

### [P2] Finish moving pure repository assertions out of the mixed store test module

`tests/repositories/test_lab_store.py:75`, `tests/repositories/test_lab_store.py:101`, `tests/repositories/test_lab_store.py:156`, `tests/repositories/test_lab_store.py:274`, `tests/repositories/test_lab_store.py:292`, and `tests/repositories/test_lab_store.py:321` still contain focused OIE settings and lab repository behavior assertions against `DemoStore`. The new responsibility-specific files add overlapping coverage instead of moving these assertions, leaving OpenSpec task 5.1 incomplete. Move the pure repository cases to `test_oie_settings.py` and `test_lab.py`; retain only compatibility/migration integration assertions in the mixed store module.

## Missing Tests and Residual Risks

- The lazy WSGI wrapper is covered for one-time construction and import isolation, but the subprocess test currently exercises only the local Windows environment because of the P1 issue.
- Existing integration coverage exercises OIE workbench composition and retained `DemoStore` seams; no additional behavioral regression was found in the extracted SQL or projections.
- The review did not contact live OpenEMR/OIE services or run Docker lifecycle actions.

## Verification Reviewed

- Focused extraction and isolation suite: 39 tests passed.
- Architecture contract suite: 34 tests passed.
- Full automated suite: 260 tests passed locally.
- `instance/healthcare-lab.db` hash and timestamp remained unchanged during the post-fix full run.

## Verdict

Changes requested. Address the cross-platform test blocker and complete the responsibility-specific test relocation before `/dev-done`.
