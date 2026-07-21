# Backend Test Ownership and Collection Baseline

This document is the ZAC-64 ownership inventory for backend integration,
repository, domain, template, runtime, and compatibility coverage. It uses the
same feature taxonomy as `docs/frontend-module-map.md` and keeps frontend
module ownership under ZAC-63.

## Authoritative baseline

The baseline is pinned to mainline commit `ecc21ec1bd4a7664206fd234d27149a61746b688`
(`origin/main`) immediately before the ZAC-64 proposal commit.

The authoritative collection command is:

```powershell
python -m unittest discover -s tests -t . -v
```

It collected **484 tests** and completed successfully on 2026-07-20. The
earlier ZAC-63 record of 478 tests is the pre-final discovery snapshot; the
484-test result includes the final ZAC-63 frontend characterization and
architecture suites. Test count is a guardrail, not proof of assertion
preservation.

The two broad sources contain the following stable method counts on the pinned
commit:

| Source | Test methods | Responsibility covered |
|---|---:|---|
| pinned mainline `tests/integration/test_app.py` | 125 | Flask shell, feature APIs, workflows, runtime and lab-control boundaries |
| pinned mainline `tests/repositories/test_lab_store.py` | 27 | persistence, mapping, protocol/domain payloads and compatibility seams |

To reproduce the source counts:

```powershell
(git grep -n '^    def test_' ecc21ec1bd4a7664206fd234d27149a61746b688 -- tests/integration/test_app.py | Measure-Object).Count
(git grep -n '^    def test_' ecc21ec1bd4a7664206fd234d27149a61746b688 -- tests/repositories/test_lab_store.py | Measure-Object).Count
```

## Collection and ownership rules

- A focused suite owns behavior assertions; support modules only construct
  disposable collaborators, deterministic payloads, or external doubles.
- A test is assigned to one owner. A cross-feature owner is used only when the
  assertion verifies the boundary between two feature responsibilities.
- Every retained assertion method is physically defined in one focused owner;
  support modules contain only setup, deterministic factories, and fakes.
  The ownership inventory contract compares the pinned method-ID inventory with
  the focused owner ASTs and rejects aggregate case libraries or duplicate IDs.
- Frontend module, CSS, template-loading, and controlled browser interaction
  tests remain under `tests/frontend` and are owned by ZAC-63.

## Integration assertion ownership matrix

| Legacy method family | Focused owner | Verification command |
|---|---|---|
| index, static assets, navigation, route registration | `tests/integration/test_application_shell.py` | `python -m unittest tests.integration.test_application_shell` |
| local Patient API and Patient-to-Order boundary | `tests/integration/test_patient_api.py` | `python -m unittest tests.integration.test_patient_api` |
| FHIR inventory, preview, diagnostics and sync | `tests/integration/test_fhir_api.py` | `python -m unittest tests.integration.test_fhir_api` |
| local/FHIR Order API and FHIR order boundary | `tests/integration/test_order_api.py` | `python -m unittest tests.integration.test_order_api` |
| dcm4chee profile, MWL, sync and result workflows | `tests/integration/test_dcm4chee_api.py` | `python -m unittest tests.integration.test_dcm4chee_api` |
| GDT order/result and bridge/watcher API | `tests/integration/test_gdt_api.py` | `python -m unittest tests.integration.test_gdt_api` |
| OIE settings, results, listener and send operations | `tests/integration/test_oie_api.py` | `python -m unittest tests.integration.test_oie_api` |
| OIE listener auto-start, degradation and retry composition | `tests/integration/test_oie_listener_lifecycle.py` | `python -m unittest tests.integration.test_oie_listener_lifecycle` |
| dashboard, lab server, health and controlled runtime operations | `tests/integration/test_dashboard_lab_api.py` | `python -m unittest tests.integration.test_dashboard_lab_api` |

The old integration test IDs are preserved as method names in these focused
owners. Their module-qualified IDs intentionally change because ownership is
now discoverable by feature.

## Repository assertion ownership matrix

| Legacy method family | Focused owner | Verification command |
|---|---|---|
| schema migration and database initialization | existing database/schema suites | `python -m unittest tests.repositories.test_database tests.repositories.test_schema_migrations` |
| Patient and generic Order persistence | `tests/repositories/test_patients_orders.py` and `tests/repositories/test_lab.py` | `python -m unittest tests.repositories.test_patients_orders tests.repositories.test_lab` |
| dcm4chee mapping, patient sync and result ledger | existing dcm4chee suites | `python -m unittest discover -s tests/repositories -p 'test_dcm4chee_*.py' -t .` |
| FHIR ledger/order workflow persistence | existing FHIR repository suites | `python -m unittest tests.repositories.test_fhir_ledger tests.repositories.test_fhir_workflow_characterization` |
| GDT workflow and result persistence | `tests/repositories/test_gdt_workflow.py` | `python -m unittest tests.repositories.test_gdt_workflow` |
| OIE settings/result persistence | `tests/repositories/test_oie.py tests/repositories/test_oie_settings.py` | `python -m unittest tests.repositories.test_oie tests.repositories.test_oie_settings` |
| explicit application construction and absence of a broad facade | `tests/test_application_composition.py` | `python -m unittest tests.test_application_composition` |

Pure validation, payload and template assertions continue to be owned by the
corresponding `tests/domain`, `tests/mappers`, and `tests/templates` suites.
They are not duplicated in generic repository helpers.

## Focused verification and final comparison

Every owner is independently runnable with the disposable support package and
without live external services or committed database files. The final gate is:

```powershell
python -m unittest discover -s tests/integration -t .
python -m unittest discover -s tests/repositories -t .
python -m unittest discover -s tests/frontend -t .
python -m unittest discover -s tests -t .
python -m py_compile app.py backend\\app_factory.py backend\\application_composition.py `
  tests\\support\\app.py tests\\support\\fakes.py tests\\support\\test_contracts.py `
  tests\\integration\\_case_support.py tests\\integration\\test_application_shell.py `
  tests\\integration\\test_cross_feature_workflows.py tests\\integration\\test_dashboard_lab_api.py `
  tests\\integration\\test_dcm4chee_api.py tests\\integration\\test_fhir_api.py `
  tests\\integration\\test_gdt_api.py tests\\integration\\test_oie_api.py `
  tests\\integration\\test_order_api.py tests\\integration\\test_patient_api.py `
  tests\\repositories\\_case_support.py `
  tests\\repositories\\test_dcm4chee_store.py tests\\repositories\\test_fhir_store.py `
  tests\\repositories\\test_gdt_store.py tests\\repositories\\test_oie_store.py `
  tests\\repositories\\test_patient_order_store.py tests\\repositories\\test_template_compatibility.py `
  tests\\test_zac64_ownership.py
git diff --check
openspec validate split-tests-by-feature-and-responsibility --strict
```

The migration may increase collection counts when a support contract or an
explicit compatibility owner adds characterization coverage. Any such change
must be recorded with the resulting count and reason in the change devlog.

## Final collection comparison for this change

| Collection | Baseline | ZAC-64 result | Difference | Explanation |
|---|---:|---:|---:|---|
| Complete discovery | 484 | 489 | +5 | Four support-contract characterization tests and one ownership-inventory contract were added. |
| Integration responsibility selection | 125 | 125 | 0 | All legacy integration methods retained under focused owners. |
| Repository responsibility selection | 27 | 27 | 0 | All legacy store methods retained under focused owners. |

The 125 integration and 27 repository method names are preserved while their
module-qualified IDs now point to focused owner classes. No legacy behavior
assertion was removed; the five-count increase is limited to support and
ownership contracts.

## ZAC-65 composition handoff

ZAC-65 removed the broad persistence facade and its compatibility-only test.
Disposable test applications now retain named repository fixtures outside
Flask, while integration assertions use HTTP or those focused owners. The
application composition result is data-only and remains private to startup.
