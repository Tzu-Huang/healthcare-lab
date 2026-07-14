import ast
import re
import unittest
from dataclasses import dataclass
from pathlib import Path, PurePosixPath


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
RESPONSIBILITY_PACKAGES = (
    "api",
    "services",
    "clients",
    "runtime",
    "repositories",
    "domain",
    "templates",
)
HTTP_DECORATORS = {"delete", "get", "patch", "post", "put", "route"}
SQL_PATTERN = re.compile(
    r"\b(?:ALTER\s+TABLE|CREATE\s+TABLE|DELETE\s+FROM|INSERT\s+INTO|SELECT\b|UPDATE\s+\w+)",
    re.IGNORECASE,
)
PROTOCOL_CALLS = {
    "socket.create_connection",
    "urllib.request.urlopen",
    "urlopen",
}


@dataclass(frozen=True)
class PlacementViolation:
    category: str
    path: PurePosixPath
    line: int
    detail: str

    def __str__(self) -> str:
        return f"[{self.category}] {self.path}:{self.line}: {self.detail}"


def imported_modules_from_tree(tree: ast.AST) -> set[str]:
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return imported_modules_from_tree(tree)


def dotted_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = dotted_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def placement_violations(relative_path: str, source: str) -> list[PlacementViolation]:
    path = PurePosixPath(relative_path.replace("\\", "/"))
    tree = ast.parse(source, filename=str(path))
    package = path.parts[1] if len(path.parts) > 2 and path.parts[0] == "backend" else ""
    violations: list[PlacementViolation] = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for decorator in node.decorator_list:
                target = decorator.func if isinstance(decorator, ast.Call) else decorator
                if (
                    isinstance(target, ast.Attribute)
                    and target.attr in HTTP_DECORATORS
                    and package != "api"
                ):
                    violations.append(
                        PlacementViolation(
                            "route",
                            path,
                            node.lineno,
                            "HTTP route decorators must live in backend/api.",
                        )
                    )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            if SQL_PATTERN.search(node.value) and package != "repositories":
                violations.append(
                    PlacementViolation(
                        "sql",
                        path,
                        node.lineno,
                        "SQL statements must live in backend/repositories.",
                    )
                )
        if isinstance(node, ast.Call):
            call_name = dotted_name(node.func)
            if call_name in PROTOCOL_CALLS and package not in {"clients", "runtime"}:
                violations.append(
                    PlacementViolation(
                        "protocol",
                        path,
                        node.lineno,
                        "External protocol transport calls must live in backend/clients or backend/runtime.",
                    )
                )
        if isinstance(node, ast.ClassDef):
            if node.name.endswith(("Listener", "Watcher", "SocketServer")) and package != "runtime":
                violations.append(
                    PlacementViolation(
                        "runtime",
                        path,
                        node.lineno,
                        "Listener and watcher implementations must live in backend/runtime.",
                    )
                )
            if node.name.endswith(("WorkflowService", "Coordinator")) and package != "services":
                violations.append(
                    PlacementViolation(
                        "workflow",
                        path,
                        node.lineno,
                        "Workflow coordination implementations must live in backend/services.",
                    )
                )
    return violations


class ArchitectureContractTest(unittest.TestCase):
    def test_responsibility_packages_exist(self):
        for package in RESPONSIBILITY_PACKAGES:
            with self.subTest(package=package):
                self.assertTrue((BACKEND / package / "__init__.py").is_file())

    def test_process_entrypoint_contains_no_application_implementation(self):
        path = ROOT / "app.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        self.assertEqual([], definitions)
        modules = imported_modules_from_tree(tree)
        self.assertEqual({"__future__", "sys", "backend"}, modules)
        self.assertLessEqual(len(source.splitlines()), 20)
        for forbidden in ("@app.", "sqlite3", "urllib", "socket", "threading"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_lower_layers_do_not_import_flask_or_api_modules(self):
        for package in ("clients", "repositories", "domain", "templates"):
            for path in (BACKEND / package).glob("*.py"):
                modules = imported_modules(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertFalse(
                        any(name == "flask" or name.startswith("flask.") for name in modules),
                        f"{path.relative_to(ROOT)} lower layer must not import Flask.",
                    )
                    self.assertFalse(
                        any(
                            name == "backend.api" or name.startswith("backend.api.")
                            for name in modules
                        ),
                        f"{path.relative_to(ROOT)} lower layer must not import backend.api.",
                    )
                    if package == "domain":
                        self.assertFalse(
                            any(
                                name == "backend.config" or name.startswith("backend.config.")
                                for name in modules
                            ),
                            f"{path.relative_to(ROOT)} domain layer must not import configuration.",
                        )

    def test_services_do_not_import_concrete_store(self):
        for path in (BACKEND / "services").glob("*.py"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_store",
                    modules,
                    f"{path.relative_to(ROOT)} must depend on domain types and repository ports, not DemoStore.",
                )

    def test_configuration_does_not_import_concrete_store(self):
        path = BACKEND / "config.py"
        self.assertNotIn(
            "backend.lab_store",
            imported_modules(path),
            "backend/config.py must use domain configuration types, not DemoStore.",
        )

    def test_responsibility_packages_obey_placement_contract(self):
        violations: list[PlacementViolation] = []
        for package in RESPONSIBILITY_PACKAGES:
            for path in (BACKEND / package).glob("*.py"):
                violations.extend(
                    placement_violations(
                        path.relative_to(ROOT).as_posix(),
                        path.read_text(encoding="utf-8"),
                    )
                )
        factory_path = BACKEND / "app_factory.py"
        violations.extend(
            placement_violations(
                factory_path.relative_to(ROOT).as_posix(),
                factory_path.read_text(encoding="utf-8"),
            )
        )
        self.assertEqual(
            [],
            violations,
            "Architecture placement violations:\n" + "\n".join(map(str, violations)),
        )

    def test_composition_root_surface_is_allowlisted(self):
        path = BACKEND / "app_factory.py"
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        definitions = {
            node.name
            for node in tree.body
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        }
        allowed = {
            "create_app",
            "dcm4chee_result_refresh_generation",
            "main",
        }
        self.assertEqual(allowed, definitions)
        self.assertLessEqual(
            len(source.splitlines()),
            500,
            "backend/app_factory.py must remain a compact composition root.",
        )

    def test_placement_failures_name_category_path_and_line(self):
        fixtures = {
            "route": ("backend/services/misplaced.py", "@app.get('/x')\ndef handler(): pass\n"),
            "sql": ("backend/api/misplaced.py", "QUERY = 'SELECT * FROM records'\n"),
            "protocol": (
                "backend/services/misplaced.py",
                "import socket\nsocket.create_connection(('host', 1))\n",
            ),
            "runtime": ("backend/services/misplaced.py", "class ResultListener: pass\n"),
            "workflow": ("backend/api/misplaced.py", "class PatientWorkflowService: pass\n"),
        }
        for category, (path, source) in fixtures.items():
            with self.subTest(category=category):
                violations = placement_violations(path, source)
                self.assertEqual(1, len(violations))
                message = str(violations[0])
                self.assertIn(f"[{category}]", message)
                self.assertIn(path, message)
                self.assertRegex(message, r":\d+:")


if __name__ == "__main__":
    unittest.main()
