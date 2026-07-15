# Code Review: ZAC-57 (Round 3)

## Findings

### [P1] Allow only the retained facade mapping and exact composition arguments

`tests/test_architecture_contract.py:281` recognizes the delegate shape but does not bind the enclosing `DemoStore` method name to an approved target method, so a newly added facade such as `delete_everything -> self.lab_repository.delete_everything()` is silently exempt. Likewise, the initializer check at line 356 compares only the assigned constructor name; arbitrary literal payloads can be inserted into repository constructor arguments while the aggregate class and initializer remain exempt. Both probes currently produce zero violations. Define the exact retained method-to-target mapping and validate the current constructor positional/keyword argument AST shapes (or an equivalently strict signature) so facade growth and hidden initializer payload/workflow changes fail the architecture contract.

## Missing Tests and Residual Risks

- There is no negative fixture for a new mechanically thin `DemoStore` facade method targeting an approved repository.
- There is no negative fixture for changed positional or keyword arguments on an otherwise approved repository constructor assignment.
- Review did not contact live OpenEMR/OIE services or run Docker, deployment, push, merge, or release actions.

## Prior Finding Status

- Resolved: delegate receiver/composer lookalikes and nested calls are rejected.
- Resolved: the legacy baseline diff against `main` contains removals only, with no replacement fingerprints.
- Resolved: direct OIE settings test-module execution imports its exception dependency before starting the runner.

## Verification Reviewed

- Focused extraction and isolation suite: 45 tests passed.
- Architecture contract suite: 36 tests passed, but the two uncovered probes above bypass it.
- Full automated suite: 262 tests passed with `instance/healthcare-lab.db` hash and timestamp unchanged.
- New-facade and modified-initializer probes: zero violations reported.

## Verdict

Changes requested. Bind architecture exemptions to the exact retained facade and composition surface before `/dev-done`.
