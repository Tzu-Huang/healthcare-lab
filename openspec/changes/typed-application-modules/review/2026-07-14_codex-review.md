# Codex Review: ZAC-53 Typed Application Modules

- Date: 2026-07-14
- Branch: `feature/ZAC-53_typed-application-modules`
- Base: `main`
- Verdict: Changes requested

## Findings

### [P2] Complete the typed repository boundary for runtime and lab workflows

`backend/runtime/gdt_bridge_watcher.py:13` and `backend/runtime/oie_result_listener.py:11` still import the concrete `DemoStore`, even though both runtime components only retain or pass the store to injected callbacks. The newly extracted `backend/services/lab_workflow.py:53-54` avoids that import by declaring `LabRepositoryPort`, but the Protocol is empty while the module calls a large repository surface throughout `:82-734`; it therefore provides no structural type checking for the boundary it claims to define.

This leaves runtime and the largest extracted service coupled to, or effectively untyped against, the persistence monolith. The architecture contract at `tests/test_architecture_contract.py:180-190` protects services from importing `backend.lab_store` but does not enforce the same direction for runtime modules or verify that repository ports declare their consumed operations.

Define explicit runtime callback/store Protocols and a real lab repository Protocol containing the methods used by the service. Remove the concrete store imports from runtime, and extend the dependency contract to reject them there as well.

### [P2] Keep one owner for GDT bridge directory validation

`backend/lab_store.py:395-412` and `backend/services/lab_workflow.py:63-80` now contain separate copies of `validate_gdt_bridge_dirs`. The watcher imports the store copy at `backend/runtime/gdt_bridge_watcher.py:13,95`, while lab smoke and protocol checks use the service copy. A future change to folder requirements, error classification, or probe behavior can therefore make runtime startup and smoke verification disagree.

Move the filesystem health check to one runtime or health-oriented module and have the watcher, lab workflow, and any compatibility export use that single implementation.

## Resolved From Previous Round

- Composition-root workflow ownership is resolved: `backend/app_factory.py` is 409 lines and its top-level surface is allowlisted.
- Configuration no longer imports `backend.lab_store`; OpenEMR defaults/parsing live in `backend/domain/openemr.py`.
- Focused health client and DICOM domain tests now exist.

## Verification Evidence

- Focused architecture/config/client/domain/service/runtime/repository suites: 35/35 passed.
- Full regression suite: 202/202 passed.
- Python compilation, frontend syntax, Compose config, local Flask smoke, `git diff --check`, and strict OpenSpec validation passed.
- Live Medplum, dcm4chee, OIE, and GDT service smoke was not run.

## Residual Risk

No behavior regression was found. Remaining risk is boundary drift: runtime still names the concrete persistence implementation, the new lab repository port cannot be checked structurally, and two independent GDT folder validators can diverge while all current tests remain green.
