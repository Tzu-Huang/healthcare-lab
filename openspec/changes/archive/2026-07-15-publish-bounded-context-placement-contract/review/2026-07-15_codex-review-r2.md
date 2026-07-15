# Codex Review Round 2: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`cf190c0`)

Verdict: **Changes requested**

## Findings

### [P1] Fingerprint existing frontend functions, not only their names

`tests/test_architecture_contract.py:274`

The reviewed frontend baseline is a set of function/class names, and `frontend_function_violations()` only checks whether a discovered name is present. The body is never fingerprinted. Any of the 246 existing functions can therefore receive new transport, payload, or workflow implementation without changing the inventory. This counterexample returns no violations:

```javascript
function renderServices() {
  return fetch("/api/new-monolith");
}
```

with `frozenset({"renderServices"})` as the baseline. Extending an existing global is the most natural way for the monolith to grow, so this bypass defeats the requirement to reject materially changed classified implementation. Store a stable body fingerprint and line-insensitive identity for each reviewed frontend definition, then add a fixture that changes the body of a baseline name.

### [P1] Inspect module-level backend implementation

`tests/test_architecture_contract.py:192`

`LegacyCandidateCollector` classifies SQL constants everywhere, but transport, payload, workflow, and fallback `catch-all` candidates are only added while visiting function or class definitions. Module-level implementation is therefore invisible. Each of these catch-all additions currently produces no violation:

```python
import urllib.request
urllib.request.urlopen("http://example")

PATIENT_TEMPLATE = {"resourceType": "Patient"}

result = run_external_workflow()
```

This leaves protocol payload constants and import-time transport/workflow behavior outside the reviewed baseline. Add a fingerprinted module-body candidate, or explicitly classify top-level assignments and calls, and add negative fixtures for module-level transport, payload, and workflow cases.

## Missing tests and residual risks

- The new frontend fixtures prove that additional declaration forms are discovered, but do not prove that changing an already-baselined definition is rejected.
- Backend fixtures place every counterexample inside a function, leaving module-body behavior uncovered.
- The post-fix suite passes 221 tests; these findings are false negatives in the architecture scanner rather than regression failures in existing behavior.

## Resolution

- Backend module-body coverage resolved by `95aac95`: non-import top-level statements receive stable catch-all fingerprints and additional payload, workflow, SQL, and transport categories where applicable.
- Frontend definition coverage resolved in the follow-up fix: the reviewed baseline now records both readable names and stable fingerprints for each definition chunk, so changing an existing function body fails even when its name is unchanged.
- Added the requested module-level and changed-body counterexamples.
- Focused architecture verification after both fixes: 24 tests passed.
