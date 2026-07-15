# Codex Review Round 6: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`5e6f86d`)

Verdict: **Changes requested**

## Findings

### [P1] Expand imported names for `from package import module`

`tests/test_architecture_contract.py:487`

`imported_modules_from_tree()` records only `ImportFrom.module` and discards the imported aliases. Therefore `from backend import api` and `from backend import repositories` are both represented as only `{"backend"}`. The lower-layer and concrete-repository checks compare against `backend.api` or `backend.repositories`, so these valid imports bypass the new dependency contract even in ordinary flat modules:

```python
# backend/domain/patient.py
from backend import api

# backend/services/patient_workflow.py
from backend import repositories
```

Neither source produces a placement violation, and the second form does not appear in `CONCRETE_REPOSITORY_IMPORT_BASELINE`. Expand each imported alias to `f"{node.module}.{alias.name}"` when it resolves to a module/package, as `resolved_backend_imports()` already does for transitive traversal, and add fixtures for parent-package API and repository imports.

### [P2] Apply dependency checks recursively to nested layer packages

`tests/test_architecture_contract.py:694`

The dependency-direction and placement tests enumerate every layer with non-recursive `glob("*.py")`. A module such as `backend/domain/patient/model.py` is skipped entirely, so it can import Flask, `backend.api`, runtime code, or a concrete repository without reaching the relevant assertions.

The published target is organized by bounded context and does not forbid nested packages, so enforcement should use `rglob("*.py")` for layer modules. Add a nested-path fixture or a shared recursive module iterator to keep future bounded-context packages under the same contract.

## Missing tests and residual risks

- Import fixtures cover fully qualified `import backend.x` and `from backend.x import y` forms, but not `from backend import x`.
- Dependency tests currently exercise only files directly under each layer directory.
- Current automated verification remains green at 27 architecture tests and 226 full-suite tests; both findings are import-discovery false negatives.

## Resolution

- Parent-package import coverage resolved by `85c4dec`: imported aliases are expanded when they resolve to real backend modules or packages, while ordinary imported symbols remain unchanged.
- Recursive discovery resolved in the follow-up fix: all layer dependency and placement loops now share a recursive module iterator.
- Added parent-package alias and nested-module discovery counterexamples. Focused architecture verification after both fixes: 29 tests passed.
