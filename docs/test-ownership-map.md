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
| `tests/integration/test_app.py` | 125 | Flask shell, feature APIs, workflows, runtime and lab-control boundaries |
| `tests/repositories/test_lab_store.py` | 27 | persistence, mapping, protocol/domain payloads and compatibility seams |

To reproduce the source counts:

```powershell
(rg -n '^    def test_' tests\\integration\\test_app.py | Measure-Object).Count
(rg -n '^    def test_' tests\\repositories\\test_lab_store.py | Measure-Object).Count
```

## Collection and ownership rules

- A focused suite owns behavior assertions; support modules only construct
  disposable collaborators, deterministic payloads, or external doubles.
- A test is assigned to one owner. A cross-feature owner is used only when the
  assertion verifies the boundary between two feature responsibilities.
- The legacy broad source files remain importable as case libraries during the
  migration, but their methods are registered only by the focused owner files.
  This keeps the old test IDs auditable while preventing catch-all discovery.
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
| retained `DemoStore` and compatibility imports | `tests/repositories/test_compatibility.py` | `python -m unittest tests.repositories.test_compatibility` |

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
python -m py_compile app.py backend\\lab_store.py tests\\integration\\test_app.py tests\\repositories\\test_lab_store.py
git diff --check
openspec validate split-tests-by-feature-and-responsibility --strict
```

The migration may increase collection counts when a support contract or an
explicit compatibility owner adds characterization coverage. Any such change
must be recorded with the resulting count and reason in the change devlog.

## ZAC-65 compatibility handoff

The compatibility owner preserves tests for the retained `DemoStore` facade,
legacy imports, and migration behavior until ZAC-65 removes the corresponding
seams. ZAC-64 does not delete those assertions or change production
compatibility behavior.
