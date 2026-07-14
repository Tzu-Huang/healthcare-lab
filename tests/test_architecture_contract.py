import ast
import unittest
from pathlib import Path


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


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


class ArchitectureContractTest(unittest.TestCase):
    def test_responsibility_packages_exist(self):
        for package in RESPONSIBILITY_PACKAGES:
            with self.subTest(package=package):
                self.assertTrue((BACKEND / package / "__init__.py").is_file())

    def test_process_entrypoint_contains_no_application_implementation(self):
        path = ROOT / "app.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        definitions = [
            node.name
            for node in ast.walk(tree)
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        ]
        self.assertEqual([], definitions)
        self.assertNotIn("flask", imported_modules(path))

    def test_lower_layers_do_not_import_flask_or_api_modules(self):
        for package in ("clients", "repositories", "domain", "templates"):
            for path in (BACKEND / package).glob("*.py"):
                modules = imported_modules(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertFalse(any(name == "flask" or name.startswith("flask.") for name in modules))
                    self.assertFalse(any(name == "backend.api" or name.startswith("backend.api.") for name in modules))


if __name__ == "__main__":
    unittest.main()
