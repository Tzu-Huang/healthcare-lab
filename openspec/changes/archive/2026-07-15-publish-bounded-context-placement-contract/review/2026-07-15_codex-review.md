# Codex Review: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`6909704`)

Verdict: **Changes requested**

## Findings

### [P1] Detect SQL execution instead of relying on a partial keyword list

`tests/test_architecture_contract.py:28`

The catch-all scanner only recognizes `ALTER TABLE`, `CREATE TABLE`, `DELETE FROM`, `INSERT INTO`, `SELECT`, and a narrow `UPDATE` form. Common SQLite statements such as `PRAGMA`, `WITH`, `REPLACE INTO`, `DROP TABLE`, and `VACUUM` are not classified. For example, this produces no violation:

```python
def configure(connection):
    connection.execute("PRAGMA journal_mode=WAL")
```

That allows new SQL implementation in `DemoStore` even though rejecting new SQL in catch-all modules is a primary acceptance criterion. Inspect SQL execution calls and/or cover the complete supported statement set, and add negative fixtures for non-CRUD SQLite statements.

### [P1] Payload and workflow enforcement can be bypassed by ordinary function names

`tests/test_architecture_contract.py:182`

Payload and workflow candidates are identified only from substrings or prefixes in the function name. Consequently, both of these additions produce no violation:

```python
def serialize_patient():
    return {"resourceType": "Patient"}

def process_patient():
    return True
```

The implementation therefore does not enforce the documented responsibility rule; it enforces a naming convention that is not part of the contract. Classify relevant AST behavior or freeze every definition in the named catch-all modules so neutral names cannot introduce new responsibility. Add counterexamples whose names do not contain the current allowlisted tokens.

### [P1] Transport aliases evade the scanner

`tests/test_architecture_contract.py:137`

Transport detection recognizes a small set of fully qualified calls and attributes whose root name is exactly `http`, `requests`, `socket`, `subprocess`, or `urllib`. Normal aliasing is invisible. For example, `hc.HTTPConnection("host")` after `import http.client as hc` produces no violation. The same problem applies to aliased `requests`, socket, and imported callables not present in `PROTOCOL_CALLS`.

Resolve import aliases before classifying calls, or reject newly introduced transport imports/calls through an explicit import-aware baseline. Add alias and `from ... import ... as ...` fixtures.

### [P1] Frontend function expressions are absent from the frozen inventory

`tests/test_architecture_contract.py:84`

`FRONTEND_FUNCTION_PATTERN` recognizes function declarations and `const` arrow functions only. A common top-level declaration such as the following is not inventoried and creates no violation:

```javascript
const fetchPatient = function () {
  return fetch("/api/patients");
};
```

`let`/`var` function assignments, async function expressions, and top-level classes are likewise outside the inventory. This leaves `app.js` open to new monolithic transport and workflow code. Expand the parser or use a syntax-aware inventory, with negative fixtures for each supported top-level declaration form.

### [P2] Selector inventory ignores new classes after the first selector token

`tests/test_architecture_contract.py:256`

`frontend_selector_families()` stores only the first class or ID found in each comma-separated selector. Adding `.known-family .new-child { ... }` records only `.known-family`; when that family is already in the baseline, `.new-child` is accepted without review. Pseudo-class arguments and other compound selectors have the same blind spot.

Collect every class and ID token in each selector prelude and add a fixture that introduces a descendant class beneath an existing baseline family.

## Missing tests and residual risks

- Current negative fixtures cover only a `SELECT`, token-named payload/workflow functions, a direct `urllib.request.urlopen` call, an async function declaration, and a single top-level selector.
- Baseline fingerprints are intentionally strict and may create maintenance friction, but that trade-off is documented and is not itself a correctness finding.
- All existing automated checks pass; the findings concern false negatives in the new architecture enforcement, so the passing suite does not establish the acceptance criterion.

## Resolution

- Backend findings resolved by `5f81eac`: catch-all definitions are frozen independent of naming, SQL execution methods and broader SQLite statements are classified without changing the conservative package-wide SQL rule, and transport calls resolve import aliases.
- Frontend findings resolved in the follow-up fix: function declarations, function expressions, arrow assignments using `const`/`let`/`var`, and top-level classes are inventoried; every class and ID token in selector preludes is collected.
- Counterexample coverage now includes `PRAGMA`, neutral definition names, aliased `HTTPConnection`, function expressions, variable declaration variants, classes, and descendant selectors.
- Focused architecture verification after both fixes: 22 tests passed.
