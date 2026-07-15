## 1. Publish the Placement Contract

- [x] 1.1 Inventory the SQL, payload, workflow, transport, runtime, persistence, domain, template, HTTP, and composition responsibilities retained in the named large modules.
- [x] 1.2 Document target backend, frontend, and test trees for patient, order, FHIR, GDT, OIE, dcm4chee, and lab control-plane contexts.
- [x] 1.3 Add a responsibility matrix that records each current source, category, named destination, mirrored test location, and compatibility-facade status.
- [x] 1.4 Document dependency direction and the bounded-context/layer placement decision process for engineers and Codex.

## 2. Define Compatibility and Legacy Baselines

- [x] 2.1 Enumerate allowed compatibility facades, their owning destinations, and the existing callers they temporarily support.
- [x] 2.2 Add an explicit reviewed baseline for classified legacy implementation in backend catch-all modules.
- [x] 2.3 Add explicit inventories for retained top-level frontend functions and selectors so existing monolithic assets may shrink but do not gain new responsibility.

## 3. Enforce Placement

- [x] 3.1 Extend the architecture scanner to classify new SQL, payload, workflow, and transport implementation in named catch-all modules.
- [x] 3.2 Make unmatched or materially changed classified implementation fail with category, path, and current source line while allowing baseline removal.
- [x] 3.3 Add negative fixtures for every required violation category and positive fixtures for unchanged baselines, facade delegation, and incremental extraction.
- [x] 3.4 Extend import checks where needed to enforce the documented inward dependency direction and cross-context coordination rule.

## 4. Verify Behavior Preservation

- [x] 4.1 Run focused architecture contract tests and confirm every failure diagnostic contains category, path, and line.
- [ ] 4.2 Run the full Python regression suite and Python compilation checks.
- [ ] 4.3 Run frontend syntax checks and any repository Compose or smoke contract checks affected by the documentation and test changes.
- [ ] 4.4 Run `git diff --check` and strict OpenSpec validation, and record that runtime behavior, APIs, persistence, protocols, and UI behavior are unchanged.
