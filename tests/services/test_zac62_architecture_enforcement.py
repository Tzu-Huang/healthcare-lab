import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET_APIS = (
    "lab_servers.py", "dashboard.py", "fhir.py", "orders.py", "patients.py", "gdt.py",
)
TARGET_SERVICES = (
    "coordination.py",
    "dcm4chee_coordination.py",
    "fhir_coordination.py",
    "fhir_workflow.py",
    "gdt_coordination.py",
    "gdt_workflow.py",
    "lab_workflow.py",
    "order_workflow.py",
    "patient_workflow.py",
)


def thin_variadic_or_dynamic_delegates(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    for owner in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
        for method in (node for node in owner.body if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
            dynamic = method.name == "__getattr__"
            variadic = method.args.vararg is not None or method.args.kwarg is not None
            thin_call = (
                len(method.body) == 1
                and isinstance(method.body[0], ast.Return)
                and isinstance(method.body[0].value, ast.Call)
            )
            if dynamic or (variadic and thin_call):
                violations.append(f"{owner.name}.{method.name}")
    return violations


def behavior_free_facades(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if not owner.name.endswith(("Facade", "Wrapper")):
            continue
        public = [
            node for node in owner.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and not node.name.startswith("_")
        ]
        if public and all(
            len(method.body) == 1
            and isinstance(method.body[0], ast.Return)
            and isinstance(method.body[0].value, ast.Call)
            for method in public
        ):
            violations.append(owner.name)
    return violations


def behavior_free_services(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if not owner.name.endswith("Service") or owner.name.endswith("WorkflowService"):
            continue
        public = [
            node for node in owner.body
            if isinstance(node, ast.FunctionDef) and not node.name.startswith("_")
        ]
        unchanged = []
        for method in public:
            if not (
                len(method.body) == 1
                and isinstance(method.body[0], ast.Return)
                and isinstance(method.body[0].value, ast.Call)
            ):
                unchanged.append(False)
                continue
            call = method.body[0].value
            parameters = [arg.arg for arg in method.args.args if arg.arg != "self"]
            forwarded = [arg.id for arg in call.args if isinstance(arg, ast.Name)]
            unchanged.append(
                len(call.args) == len(forwarded)
                and not call.keywords
                and forwarded == parameters
            )
        if public and all(unchanged):
            violations.append(owner.name)
    return violations


def broad_protocol_methods(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if not any(
            isinstance(base, ast.Name) and base.id == "Protocol"
            for base in owner.bases
        ):
            continue
        for method in (node for node in owner.body if isinstance(node, ast.FunctionDef)):
            variadic = method.args.vararg is not None or method.args.kwarg is not None
            bare_any_return = isinstance(method.returns, ast.Name) and method.returns.id == "Any"
            if variadic or bare_any_return:
                violations.append(f"{owner.name}.{method.name}")
    return violations


def generic_focused_collaborators(source: str) -> list[str]:
    tree = ast.parse(source)
    violations = []
    forbidden_aggregates = {"FhirRepositoryPort", "LabRepositoryPort"}
    for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
        if not owner.name.endswith("Service") or owner.name.endswith("WorkflowService"):
            continue
        constructor = next(
            (node for node in owner.body if isinstance(node, ast.FunctionDef) and node.name == "__init__"),
            None,
        )
        if constructor is None:
            continue
        arguments = [*constructor.args.args, *constructor.args.kwonlyargs]
        for argument in arguments:
            annotation = argument.annotation
            if annotation is None:
                continue
            rendered = ast.unparse(annotation)
            generic_callable = rendered.startswith("Callable[") and "..." in rendered
            bare_any_return = rendered.startswith("Callable[") and rendered.endswith(", Any]")
            if generic_callable or bare_any_return or rendered in forbidden_aggregates:
                violations.append(f"{owner.name}.{argument.arg}:{rendered}")
    return violations


class Zac62ArchitectureEnforcementTest(unittest.TestCase):
    def test_focused_blueprints_use_explicit_bounded_ports(self):
        for filename in TARGET_APIS:
            path = ROOT / "backend" / "api" / filename
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            imports = {
                alias.name
                for node in tree.body if isinstance(node, ast.ImportFrom)
                for alias in node.names
            }
            self.assertFalse(
                any(name.endswith("WorkflowService") for name in imports),
                f"{filename} must depend on focused ports, not a broad workflow façade.",
            )
            for owner in (node for node in tree.body if isinstance(node, ast.ClassDef)):
                if not owner.name.endswith("Port"):
                    continue
                methods = [node for node in owner.body if isinstance(node, ast.FunctionDef)]
                self.assertLessEqual(len(methods), 8, f"{filename}:{owner.name} is a broad service port")
                self.assertTrue(methods, f"{filename}:{owner.name} must declare explicit operations")
                self.assertFalse(any(method.args.vararg or method.args.kwarg for method in methods))

    def test_services_have_no_flask_sqlite_or_runtime_implementation_imports(self):
        forbidden = {"flask", "sqlite3", "threading"}
        for path in (ROOT / "backend" / "services").glob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            roots = {
                alias.name.split(".", 1)[0]
                for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names
            } | {
                (node.module or "").split(".", 1)[0]
                for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)
            }
            self.assertFalse(roots & forbidden, f"{path.name} contains Flask/SQL/runtime implementation")

    def test_services_reject_generic_or_dynamic_delegation(self):
        violations = []
        for path in (ROOT / "backend" / "services").glob("*.py"):
            violations.extend(
                f"{path.name}:{name}"
                for name in thin_variadic_or_dynamic_delegates(path.read_text(encoding="utf-8"))
            )
        self.assertEqual([], violations)

    def test_services_reject_broad_protocols_and_behavior_free_wrappers(self):
        protocol_violations = []
        wrapper_violations = []
        collaborator_violations = []
        for filename in TARGET_SERVICES:
            path = ROOT / "backend" / "services" / filename
            source = path.read_text(encoding="utf-8")
            protocol_violations.extend(
                f"{path.name}:{name}" for name in broad_protocol_methods(source)
            )
            wrapper_violations.extend(
                f"{path.name}:{name}" for name in behavior_free_facades(source)
            )
            wrapper_violations.extend(
                f"{path.name}:{name}" for name in behavior_free_services(source)
            )
            collaborator_violations.extend(
                f"{path.name}:{name}" for name in generic_focused_collaborators(source)
            )
        self.assertEqual([], protocol_violations)
        self.assertEqual([], wrapper_violations)
        self.assertEqual([], collaborator_violations)

    def test_detectors_reject_regression_shapes(self):
        self.assertEqual(
            ["BroadService.forward", "BroadService.__getattr__"],
            thin_variadic_or_dynamic_delegates(
                "class BroadService:\n"
                " def forward(self, *args, **kwargs): return self.owner.run(*args, **kwargs)\n"
                " def __getattr__(self, name): return getattr(self.owner, name)\n"
            ),
        )
        self.assertEqual(
            ["NewWrapper"],
            behavior_free_facades(
                "class NewWrapper:\n"
                " def list(self): return self.owner.list()\n"
                " def get(self, item_id): return self.owner.get(item_id)\n"
            ),
        )
        self.assertEqual(
            ["BroadPort.forward", "BroadPort.load"],
            broad_protocol_methods(
                "from typing import Any, Protocol\n"
                "class BroadPort(Protocol):\n"
                " def forward(self, *args): ...\n"
                " def load(self) -> Any: ...\n"
            ),
        )
        self.assertEqual(
            ["ForwardingService"],
            behavior_free_services(
                "class ForwardingService:\n"
                " def list(self): return self.owner.list()\n"
                " def get(self, item_id): return self.owner.get(item_id)\n"
            ),
        )
        self.assertEqual(
            ["FocusedService.repository:LabRepositoryPort", "FocusedService.run:Callable[..., Any]"],
            generic_focused_collaborators(
                "from collections.abc import Callable\n"
                "from typing import Any\n"
                "class FocusedService:\n"
                " def __init__(self, repository: LabRepositoryPort, run: Callable[..., Any]): pass\n"
            ),
        )


if __name__ == "__main__":
    unittest.main()
