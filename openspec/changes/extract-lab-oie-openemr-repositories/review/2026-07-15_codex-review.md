# Code Review: ZAC-57 (Round 4)

## Findings

### [P1] Scope composition exemptions to the exact DemoStore class shell

`tests/test_architecture_contract.py:434` applies `is_repository_compatibility_delegate` before checking the collector's enclosing symbol, so an approved-shaped function outside `DemoStore` reports zero violations. In addition, the class exemption at line 413 depends only on the class name and initializer; adding a base class, decorator, or class-level state leaves the collected candidate set unchanged. Restrict delegate exemptions to methods whose enclosing symbol is exactly `DemoStore`, and require the exempt class shell to have no bases, decorators, keywords, or non-method state. Add negative fixtures for standalone/foreign delegates and structural class mutations.

## Missing Tests and Residual Risks

- No fixture currently proves that an approved-shaped delegate outside `DemoStore` is rejected.
- No fixture currently proves that base classes, decorators, or class-level payload/state invalidate the aggregate class exemption.
- Review did not contact live OpenEMR/OIE services or run Docker, deployment, push, merge, or release actions.

## Prior Finding Status

- Resolved: retained facade methods are bound to exact repository targets.
- Resolved: repository composition constructor arguments are protected by reviewed AST fingerprints.
- Resolved: baseline changes remain removal-only and direct OIE settings module execution passes.

## Verification Reviewed

- Focused extraction and isolation suite: 45 tests passed.
- Architecture contract suite: 36 tests passed, but the context and class-shell probes bypass it.
- Full automated suite: 262 tests passed with `instance/healthcare-lab.db` unchanged.

## Verdict

Changes requested. Close the remaining exemption-scope gap before `/dev-done`.
