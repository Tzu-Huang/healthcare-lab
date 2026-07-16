## Apply safety baseline

- Starting branch: `feature/ZAC-60_extract-fhir-gdt-workflow-repositories`
- Starting commit: `829f2b0`
- Starting worktree: clean (`git status --porcelain=v1` produced no entries)
- Linear mapping: `ZAC-60`
- Product-code scope: `backend/lab_store.py`, new FHIR/GDT domain, template,
  repository, coordination, and composition modules, plus the directly affected
  service ports.
- Test scope: focused FHIR/GDT domain, adapter, repository, service-port,
  architecture, database-characterization, and integration tests.
- Architecture baseline: the reviewed entries for FHIR/GDT implementations in
  `backend/lab_store.py` and `backend/gdt_adapter.py` may only be removed after
  the corresponding implementation is extracted. No entry, fingerprint,
  allowlist, exclusion, or skip may be added or refreshed.
- Disposable resources: repository and integration tests construct SQLite files
  below `tempfile.TemporaryDirectory`; transport behavior uses mocks or injected
  doubles. Verification must not resolve to repository `instance/*.db`, Docker,
  configured healthcare endpoints, or live Medplum/OpenEMR/dcm4chee/OIE services.
- Hard stop: pause before any schema/index/data migration, real database or live
  service access, public contract change, new dependency, baseline expansion,
  unrelated extraction, destructive Git action, or unsafe dirty-file overlap.

Before each increment, inspect `git status --porcelain=v1`, the exact diff, and
the intended explicit staging paths. Directly caused test, typing, import,
fixture, and composition failures remain routine in-scope repairs.
