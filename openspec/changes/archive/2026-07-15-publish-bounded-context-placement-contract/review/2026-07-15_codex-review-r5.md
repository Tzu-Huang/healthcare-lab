# Codex Review Round 5: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`c4cbc06`)

Verdict: **Changes requested**

## Findings

### [P1] Retain every frontend definition occurrence instead of overwriting duplicate names

`tests/test_architecture_contract.py:360`

`frontend_top_level_definitions()` stores definitions in a dictionary keyed only by name. If a new same-named definition appears before the reviewed one, the later reviewed occurrence overwrites it, so both the violation scan and exact baseline comparison see only the original entry. Prepending this valid JavaScript to the current `frontend/static/app.js` produces no placement violations and still passes `node --check`:

```javascript
var renderServices = function () {
  return fetch("/api/new-monolith");
};
```

The existing later `function renderServices()` supplies the baselined dictionary value, while the leading `var` assignment executes after function-declaration hoisting and therefore replaces the runtime binding with the new transport implementation. This bypasses the core requirement to reject new frontend catch-all responsibility. Preserve definitions as an ordered list or key them by occurrence, reject duplicate reviewed names explicitly, and add a counterexample against the actual-style baseline.

## Missing tests and residual risks

- Current declaration-form fixtures use unique names and therefore do not exercise duplicate-name collisions.
- The readable name inventory and fingerprint baseline are both sets, so neither independently detects an additional occurrence of an existing name.
- Several dependency-direction checks use non-recursive `glob("*.py")`; nested backend layer packages would require recursive discovery.
- Current verification remains green at 26 architecture tests and 225 full-suite tests; this finding is an uncovered scanner false negative.

## Resolution

- Frontend definition collection now preserves every ordered occurrence for fingerprint comparison instead of collapsing same-named entries into a dictionary.
- Duplicate top-level names are rejected explicitly, including an exact duplicate whose fingerprint already exists in the reviewed baseline.
- Added changed-runtime-binding and exact-copy duplicate counterexamples. Focused architecture verification: 27 tests passed.
