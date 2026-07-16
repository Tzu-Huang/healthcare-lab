import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
TARGET_APIS = (
    "lab_servers.py", "dashboard.py", "fhir.py", "orders.py", "patients.py", "gdt.py",
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


if __name__ == "__main__":
    unittest.main()
