# Codex Review Round 7: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`7461fbb`)

Verdict: **Changes requested**

## Findings

### [P1] Resolve relative imports in direct dependency checks

`tests/test_architecture_contract.py:487`

`imported_modules_from_tree()` has no package-path context and ignores `ImportFrom.level`. As a result, relative imports are not converted to their absolute backend modules:

```python
from .. import api
from .. import repositories
from ..repositories import patient
```

The first two forms produce an empty module set and the third produces only `{"repositories"}`. In a service, domain, client, repository, template, or runtime module, these valid imports therefore bypass the `backend.api`, `backend.repositories`, and other dependency-direction checks. This is especially relevant now that nested bounded-context packages are explicitly discovered.

`resolved_backend_imports(path)` already resolves relative levels using the importing file's package. Reuse that path-aware resolution in `imported_modules(path)` while retaining external top-level imports needed for the Flask rule, or otherwise give the direct parser package context. Add fixtures for both `from .. import api/repositories` and `from ..repositories import patient` from representative flat and nested module paths.

## Missing tests and residual risks

- Parent-package fixtures cover only absolute `from backend import ...` syntax.
- The recursive discovery fixture proves a nested file is enumerated but does not prove its relative imports are classified.
- Current automated verification remains green at 29 architecture tests and 228 full-suite tests; this is an uncovered import-resolution false negative.

## Resolution

- Direct import checks now combine external modules from the syntax tree with backend modules from the existing path-aware relative import resolver.
- Refactored backend resolution into a tree-plus-path helper so flat and nested package semantics can be tested without creating repository fixtures.
- Added `..api`, `..repositories`, and `..repositories.patient` counterexamples. Focused architecture verification: 30 tests passed.
