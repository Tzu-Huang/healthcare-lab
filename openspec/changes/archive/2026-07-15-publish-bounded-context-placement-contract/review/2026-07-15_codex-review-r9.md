# Codex Review Round 9: ZAC-55 bounded-context placement contract

Base: `main`

Head: `feature/ZAC-55_publish-bounded-context-placement-contract` (`591750a`)

Verdict: **Changes requested**

## Findings

### [P1] Freeze callers of root compatibility facades

`tests/test_architecture_contract.py:518`

The new layer matrix classifies only `backend.config` and modules whose first
component is one of the responsibility packages. Root compatibility modules
therefore return `None` from `backend_dependency_layer()`, and
`layer_dependency_violations()` deliberately skips them at line 538. A new
module can consequently become a caller of any retained facade without a
placement violation:

```python
# backend/services/new_gdt.py
from backend.gdt_adapter import parse_gdt

# backend/clients/new_docker.py
from backend.lab_operations import DockerLabOperations

# backend/services/new_dashboard.py
from backend.dashboard_services import collect_dashboard_snapshot
```

Calling `layer_dependency_violations()` for `backend.gdt_adapter`,
`backend.lab_operations`, or `backend.dashboard_services` returns an empty
list. This conflicts with the OpenSpec requirement that compatibility facades
are explicit migration seams and that new callers import the owning module
directly. It also means the documented retained-caller lists are descriptive
only; unlike concrete repository exceptions, they are not enforced.

Add a reviewed facade-caller baseline covering the current imports of
`lab_store`, `gdt_adapter`, `dashboard_services`, and `lab_operations`, then
compare it with recursively discovered live imports. New caller/module pairs
must fail while removal of an existing pair remains valid when its baseline
entry is removed.

## Missing tests and residual risks

- The layer-matrix fixtures exercise only modules below recognized layer
  packages, so none covers imports of root compatibility facades.
- Existing checks special-case a subset of `lab_store` and `lab_operations`
  consumers, but do not enforce the complete enumerated caller set for all four
  backend facades.
- The latest verification remains green at 32 architecture tests and 231
  full-suite tests; this finding is an uncovered policy-enforcement false
  negative rather than a runtime regression.

## Resolution

- Added an explicit caller baseline for all six current backend imports of the
  four root compatibility facades.
- Added a recursive live-tree comparison that rejects new caller/module pairs
  and permits migration when the matching baseline entry is removed.
- Added one negative fixture for each facade. Focused architecture verification:
  34 tests passed.
