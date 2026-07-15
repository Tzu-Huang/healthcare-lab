# Codex Review Round 3: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`c443d45`)

Verdict: **Changes requested**

## Findings

### [P1] Include the source prefix in the frontend definition inventory

`tests/test_architecture_contract.py:347`

`frontend_top_level_definitions()` fingerprints only the text beginning at the first matched function, function expression, arrow, or class. Source before that first match is never represented in `FRONTEND_FUNCTION_BASELINE`. Because `frontend/static/app.js` begins with the baselined `byId` arrow, a new payload or state global inserted above it is invisible to the architecture contract. This counterexample returns no violations against the current baseline:

```javascript
const NEW_PATIENT_PAYLOAD = { resourceType: "Patient" };
// followed by the unchanged contents of frontend/static/app.js
```

This permits new top-level payload/state responsibility in the legacy entrypoint despite the frozen frontend inventory. Fingerprint an explicit module-prefix chunk (or inventory every top-level statement), and add a fixture that prepends a non-function global to an unchanged baselined file.

### [P1] Discover the first selector nested inside CSS at-rules

`tests/test_architecture_contract.py:101`

`CSS_RULE_PATTERN` only starts a rule match at the beginning of the source or after `}`. The first selector inside `@media`, `@supports`, or another block at-rule follows `{`, so it is skipped. For example, this source produces no selector-family violation with an empty baseline:

```css
@media (max-width: 1px) {
  .brand-new-family { display: block; }
}
```

The production stylesheet already contains several `@media` blocks, making this a practical way to add an unreviewed selector family while the inventory remains green. Parse nested rule blocks or otherwise scan selector preludes independently of the preceding delimiter, and add a negative fixture for the first selector within an at-rule.

## Missing tests and residual risks

- The changed-definition fixture covers function body growth but not new top-level payload/state declarations before the first definition.
- The selector fixture covers a normal top-level rule but not selectors nested under block at-rules.
- Several dependency-direction checks use non-recursive `glob("*.py")`; if backend layers later adopt nested bounded-context packages, those checks will need to switch to recursive discovery.
- Post-fix verification is otherwise green: 24 architecture tests and 223 full-suite tests passed, along with compilation, frontend syntax, Compose configuration, strict OpenSpec validation, and `git diff --check`.

## Resolution

- Frontend source-prefix coverage resolved by `0a04647`: the inventory now includes a stable module-prefix fingerprint and rejects prepended top-level payload/state declarations.
- CSS block at-rule coverage resolved in the follow-up fix: selector discovery now begins after opening as well as closing braces, so the first selector inside `@media` and similar blocks is inventoried.
- Added both requested counterexamples. Focused architecture verification after both fixes: 25 tests passed.
