import ast
import hashlib
import re
import unittest
from dataclasses import dataclass
from pathlib import Path, PurePosixPath

from tests.architecture_legacy_baseline import (
    BACKEND_LEGACY_BASELINE,
    CONCRETE_REPOSITORY_IMPORT_BASELINE,
    FRONTEND_FUNCTION_BASELINE,
    FRONTEND_FUNCTION_NAME_INVENTORY,
    FRONTEND_SELECTOR_FAMILY_BASELINE,
)


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
CATCH_ALL_SQL_PATTERN = re.compile(
    r"^\s*(?:ALTER|ATTACH|BEGIN|COMMIT|CREATE|DELETE|DETACH|DROP|END|EXPLAIN|"
    r"INSERT|PRAGMA|REINDEX|RELEASE|REPLACE|ROLLBACK|SAVEPOINT|SELECT|UPDATE|VACUUM|WITH)\b",
    re.IGNORECASE,
)
SQL_EXECUTION_METHODS = {"execute", "executemany", "executescript"}
PROTOCOL_CALLS = {
    "socket.create_connection",
    "subprocess.run",
    "urllib.request.urlopen",
    "urlopen",
}
CATCH_ALL_BACKEND_PATHS = (
    "backend/lab_store.py",
    "backend/gdt_adapter.py",
    "backend/dashboard_services.py",
    "backend/lab_operations.py",
)
PAYLOAD_NAME_PARTS = (
    "ack",
    "attachment",
    "dataset",
    "dicom",
    "fhir",
    "gdt",
    "hl7",
    "identifier",
    "mapping",
    "measurement",
    "message",
    "payload",
    "record_dict",
    "resource",
    "oru",
    "serialize",
)
WORKFLOW_NAME_PREFIXES = (
    "begin_",
    "collect_",
    "complete_",
    "create_",
    "execute_",
    "export_",
    "import_",
    "process_",
    "reconcile_",
    "record_",
    "refresh_",
    "retry_",
    "run_",
    "send_",
    "start_",
    "stop_",
    "sync_",
    "update_",
    "upsert_",
    "verify_",
    "write_",
)
TRANSPORT_MODULES = ("http", "requests", "socket", "subprocess", "urllib")
FRONTEND_FUNCTION_PATTERN = re.compile(
    r"^(?:export\s+)?(?:"
    r"(?:async\s+)?function\s+(?P<declaration>[A-Za-z_$][\w$]*)\s*\(|"
    r"(?:const|let|var)\s+(?P<assignment>[A-Za-z_$][\w$]*)\s*=\s*(?:"
    r"(?:async\s+)?function\b|(?:async\s*)?(?:\([^\n]*\)|[A-Za-z_$][\w$]*)\s*=>)|"
    r"class\s+(?P<class_name>[A-Za-z_$][\w$]*)\b)",
    re.MULTILINE,
)
CSS_RULE_PATTERN = re.compile(r"(?:^|[{}])\s*([^@{}][^{}]*)\{", re.MULTILINE)
CSS_FAMILY_PATTERN = re.compile(r"[.#][A-Za-z_-][\w-]*")
FRONTEND_MODULE_PREFIX_NAME = "<module-prefix>"


@dataclass(frozen=True)
class PlacementViolation:
    category: str
    path: PurePosixPath
    line: int
    detail: str

    def __str__(self) -> str:
        return f"[{self.category}] {self.path}:{self.line}: {self.detail}"


@dataclass(frozen=True, order=True)
class LegacyCandidate:
    category: str
    path: str
    symbol: str
    fingerprint: str
    line: int

    @property
    def baseline_key(self) -> tuple[str, str, str, str]:
        return (self.category, self.path, self.symbol, self.fingerprint)

    def violation(self, detail: str) -> PlacementViolation:
        return PlacementViolation(
            self.category,
            PurePosixPath(self.path),
            self.line,
            detail,
        )


@dataclass(frozen=True)
class FrontendDefinition:
    name: str
    line: int
    fingerprint: str
    category: str

    @property
    def baseline_key(self) -> tuple[str, str]:
        return (self.name, self.fingerprint)


def stable_fingerprint(value: ast.AST | str) -> str:
    if isinstance(value, ast.AST):
        payload = ast.dump(value, annotate_fields=True, include_attributes=False)
    else:
        payload = re.sub(r"\s+", " ", value).strip()
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def stable_source_fingerprint(value: str) -> str:
    payload = value.replace("\r\n", "\n").replace("\r", "\n")
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def root_name(node: ast.AST) -> str:
    while isinstance(node, ast.Attribute):
        node = node.value
    return node.id if isinstance(node, ast.Name) else ""


def import_aliases_from_tree(tree: ast.AST) -> dict[str, str]:
    aliases: dict[str, str] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for item in node.names:
                local_name = item.asname or item.name.split(".", 1)[0]
                aliases[local_name] = item.name if item.asname else local_name
        elif isinstance(node, ast.ImportFrom) and node.module:
            for item in node.names:
                aliases[item.asname or item.name] = f"{node.module}.{item.name}"
    return aliases


def resolve_imported_name(node: ast.AST, aliases: dict[str, str]) -> str:
    name = dotted_name(node)
    head, separator, tail = name.partition(".")
    resolved_head = aliases.get(head, head)
    return f"{resolved_head}.{tail}" if separator else resolved_head


def definition_has_transport(node: ast.AST, aliases: dict[str, str]) -> bool:
    for child in ast.walk(node):
        if isinstance(child, ast.Call):
            call_name = resolve_imported_name(child.func, aliases)
            if call_name in PROTOCOL_CALLS or call_name.startswith(TRANSPORT_MODULES):
                return True
        if isinstance(child, ast.Attribute):
            attribute_name = resolve_imported_name(child, aliases)
            if attribute_name.startswith(TRANSPORT_MODULES):
                return True
    return False


def definition_has_sql_execution(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and isinstance(child.func, ast.Attribute)
        and child.func.attr in SQL_EXECUTION_METHODS
        for child in ast.walk(node)
    )


def assigned_names(node: ast.AST) -> list[str]:
    if isinstance(node, (ast.Tuple, ast.List)):
        return [name for item in node.elts for name in assigned_names(item)]
    if isinstance(node, ast.Name):
        return [node.id]
    return []


def module_statement_symbol(node: ast.stmt) -> str:
    if isinstance(node, ast.Assign):
        names = [name for target in node.targets for name in assigned_names(target)]
        if names:
            return f"<module>.{','.join(names)}"
    if isinstance(node, (ast.AnnAssign, ast.AugAssign)):
        names = assigned_names(node.target)
        if names:
            return f"<module>.{','.join(names)}"
    if isinstance(node, ast.Expr) and isinstance(node.value, ast.Call):
        return f"<module>.{dotted_name(node.value.func) or 'call'}"
    return "<module>.statement"


class LegacyCandidateCollector(ast.NodeVisitor):
    def __init__(self, path: str, aliases: dict[str, str]):
        self.path = path
        self.aliases = aliases
        self.symbols: list[str] = []
        self.candidates: set[LegacyCandidate] = set()

    @property
    def symbol(self) -> str:
        return ".".join(self.symbols) if self.symbols else "<module>"

    def add(self, category: str, node: ast.AST, *, fingerprint: ast.AST | str | None = None) -> None:
        self.candidates.add(
            LegacyCandidate(
                category,
                self.path,
                self.symbol,
                stable_fingerprint(fingerprint if fingerprint is not None else node),
                getattr(node, "lineno", 1),
            )
        )

    def visit_Module(self, node: ast.Module) -> None:
        for index, statement in enumerate(node.body):
            if isinstance(statement, (ast.Import, ast.ImportFrom)):
                continue
            if (
                index == 0
                and isinstance(statement, ast.Expr)
                and isinstance(statement.value, ast.Constant)
                and isinstance(statement.value.value, str)
            ):
                continue
            if isinstance(statement, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                self.visit(statement)
                continue

            self.symbols.append(module_statement_symbol(statement))
            self.add("catch-all", statement)
            if any(isinstance(child, (ast.Dict, ast.List, ast.Set)) for child in ast.walk(statement)):
                self.add("payload", statement)
            if any(isinstance(child, ast.Call) for child in ast.walk(statement)):
                self.add("workflow", statement)
            if definition_has_sql_execution(statement):
                self.add("sql", statement)
            if definition_has_transport(statement, self.aliases):
                self.add("transport", statement)
            self.generic_visit(statement)
            self.symbols.pop()

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.symbols.append(node.name)
        self.add("catch-all", node)
        if definition_has_transport(node, self.aliases) or node.name.endswith(("Adapter", "Connection")):
            self.add("transport", node)
        self.generic_visit(node)
        self.symbols.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._visit_function(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._visit_function(node)

    def _visit_function(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
        self.symbols.append(node.name)
        lowered = node.name.lower()
        self.add("catch-all", node)
        if any(part in lowered for part in PAYLOAD_NAME_PARTS):
            self.add("payload", node)
        if lowered.startswith(WORKFLOW_NAME_PREFIXES):
            self.add("workflow", node)
        if definition_has_sql_execution(node):
            self.add("sql", node)
        if definition_has_transport(node, self.aliases):
            self.add("transport", node)
        self.generic_visit(node)
        self.symbols.pop()

    def visit_Constant(self, node: ast.Constant) -> None:
        if isinstance(node.value, str) and CATCH_ALL_SQL_PATTERN.search(node.value):
            self.add("sql", node, fingerprint=node.value)


def legacy_backend_candidates(relative_path: str, source: str) -> set[LegacyCandidate]:
    tree = ast.parse(source, filename=relative_path)
    collector = LegacyCandidateCollector(
        relative_path.replace("\\", "/"),
        import_aliases_from_tree(tree),
    )
    collector.visit(tree)
    return collector.candidates


def legacy_backend_violations(
    relative_path: str,
    source: str,
    baseline: frozenset[tuple[str, str, str, str]],
) -> list[PlacementViolation]:
    candidates = legacy_backend_candidates(relative_path, source)
    return [
        item.violation(
            f"New {item.category} implementation must move to its named bounded-context owner; "
            f"legacy symbol {item.symbol!r} is not in the reviewed baseline."
        )
        for item in sorted(candidates)
        if item.baseline_key not in baseline
    ]


def frontend_definition_category(name: str, body: str = "") -> str:
    lowered = name.lower()
    if any(part in lowered for part in ("request", "fetch", "send")) or "fetch(" in body:
        return "transport"
    if any(part in lowered for part in ("build", "parse", "payload", "preview", "render")):
        return "payload"
    return "workflow"


def frontend_top_level_definitions(source: str) -> dict[str, FrontendDefinition]:
    matches = list(FRONTEND_FUNCTION_PATTERN.finditer(source))
    definitions: dict[str, FrontendDefinition] = {}
    for index, match in enumerate(matches):
        name = match.group("declaration", "assignment", "class_name")
        name = next(value for value in name if value)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.start() : end].strip()
        definitions[name] = FrontendDefinition(
            name=name,
            line=source.count("\n", 0, match.start()) + 1,
            fingerprint=stable_source_fingerprint(body),
            category=frontend_definition_category(name, body),
        )
    return definitions


def frontend_definition_inventory(source: str) -> frozenset[tuple[str, str]]:
    first_definition = FRONTEND_FUNCTION_PATTERN.search(source)
    prefix_end = first_definition.start() if first_definition else len(source)
    inventory = {
        (
            FRONTEND_MODULE_PREFIX_NAME,
            stable_source_fingerprint(source[:prefix_end]),
        )
    }
    inventory.update(
        definition.baseline_key
        for definition in frontend_top_level_definitions(source).values()
    )
    return frozenset(inventory)


def frontend_top_level_functions(source: str) -> dict[str, int]:
    return {
        name: definition.line
        for name, definition in frontend_top_level_definitions(source).items()
    }


def frontend_function_violations(
    relative_path: str,
    source: str,
    baseline: frozenset[tuple[str, str]],
) -> list[PlacementViolation]:
    definitions = frontend_top_level_definitions(source)
    violations = [
        PlacementViolation(
            definition.category,
            PurePosixPath(relative_path),
            definition.line,
            f"New or changed top-level frontend definition {name!r} must move to frontend/static/js/.",
        )
        for name, definition in sorted(definitions.items())
        if definition.baseline_key not in baseline
    ]
    first_definition = FRONTEND_FUNCTION_PATTERN.search(source)
    prefix_end = first_definition.start() if first_definition else len(source)
    prefix_key = (
        FRONTEND_MODULE_PREFIX_NAME,
        stable_source_fingerprint(source[:prefix_end]),
    )
    if prefix_key not in baseline:
        violations.insert(
            0,
            PlacementViolation(
                "state",
                PurePosixPath(relative_path),
                1,
                "New or changed top-level frontend module prefix must move to frontend/static/js/.",
            ),
        )
    return violations


def frontend_selector_families(source: str) -> dict[str, int]:
    source_without_comments = re.sub(
        r"/\*.*?\*/",
        lambda match: "\n" * match.group(0).count("\n"),
        source,
        flags=re.DOTALL,
    )
    families: dict[str, int] = {}
    for match in CSS_RULE_PATTERN.finditer(source_without_comments):
        prelude = match.group(1)
        line = source_without_comments.count("\n", 0, match.start(1)) + 1
        for selector in prelude.split(","):
            for family in CSS_FAMILY_PATTERN.finditer(selector):
                families.setdefault(family.group(0), line)
    return families


def frontend_selector_violations(
    relative_path: str,
    source: str,
    baseline: frozenset[str],
) -> list[PlacementViolation]:
    return [
        PlacementViolation(
            "presentation",
            PurePosixPath(relative_path),
            line,
            f"New selector family {family!r} must move to frontend/static/css/.",
        )
        for family, line in sorted(frontend_selector_families(source).items())
        if family not in baseline
    ]


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


def backend_module_path(module: str) -> Path | None:
    if module == "backend":
        return BACKEND / "__init__.py"
    if not module.startswith("backend."):
        return None
    relative = module.split(".")[1:]
    module_path = BACKEND.joinpath(*relative).with_suffix(".py")
    if module_path.is_file():
        return module_path
    package_path = BACKEND.joinpath(*relative, "__init__.py")
    return package_path if package_path.is_file() else None


def resolved_backend_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    relative = path.relative_to(ROOT).with_suffix("")
    module_parts = list(relative.parts)
    if module_parts[-1] == "__init__":
        module_parts.pop()
        package_parts = module_parts
    else:
        package_parts = module_parts[:-1]
    modules: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(
                alias.name for alias in node.names if alias.name.startswith("backend")
            )
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                parent_count = max(0, len(package_parts) - (node.level - 1))
                imported_parts = package_parts[:parent_count]
                if node.module:
                    imported_parts.extend(node.module.split("."))
                module = ".".join(imported_parts)
            else:
                module = node.module or ""
            if module.startswith("backend"):
                modules.add(module)
                for alias in node.names:
                    candidate = f"{module}.{alias.name}"
                    if backend_module_path(candidate):
                        modules.add(candidate)
    return modules


def transitive_backend_imports(path: Path) -> set[str]:
    discovered: set[str] = set()
    pending = list(resolved_backend_imports(path))
    while pending:
        module = pending.pop()
        if module in discovered:
            continue
        discovered.add(module)
        dependency_path = backend_module_path(module)
        if dependency_path:
            pending.extend(resolved_backend_imports(dependency_path) - discovered)
    return discovered


def protocol_methods(tree: ast.AST, protocol_name: str) -> set[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef) and node.name == protocol_name:
            return {
                item.name
                for item in node.body
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef))
            }
    return set()


def receiver_method_calls(tree: ast.AST, receiver: str) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == receiver
    }


def owned_receiver_method_calls(
    tree: ast.AST, owner: str, receiver: str
) -> set[str]:
    return {
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Attribute)
        and isinstance(node.func.value.value, ast.Name)
        and node.func.value.value.id == owner
        and node.func.value.attr == receiver
    }


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

    def test_services_do_not_depend_transitively_on_concrete_store(self):
        for path in (BACKEND / "services").glob("*.py"):
            modules = transitive_backend_imports(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_store",
                    modules,
                    f"{path.relative_to(ROOT)} must not load DemoStore directly or through another backend module.",
                )

    def test_api_modules_do_not_import_concrete_store(self):
        for path in (BACKEND / "api").glob("*.py"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_store",
                    modules,
                    f"{path.relative_to(ROOT)} must map HTTP through service ports, not DemoStore.",
                )

    def test_api_modules_do_not_import_operation_adapters(self):
        for path in (BACKEND / "api").glob("*.py"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_operations",
                    modules,
                    f"{path.relative_to(ROOT)} must handle domain errors without importing operation adapters.",
                )

    def test_runtime_does_not_import_concrete_store(self):
        for path in (BACKEND / "runtime").glob("*.py"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_store",
                    modules,
                    f"{path.relative_to(ROOT)} must depend on runtime ports, not DemoStore.",
                )

    def test_services_and_repositories_do_not_import_runtime(self):
        for package in ("services", "repositories"):
            for path in (BACKEND / package).glob("*.py"):
                modules = imported_modules(path)
                with self.subTest(path=path.relative_to(ROOT)):
                    self.assertFalse(
                        any(
                            name == "backend.runtime" or name.startswith("backend.runtime.")
                            for name in modules
                        ),
                        f"{path.relative_to(ROOT)} must not depend outward on runtime modules.",
                    )

    def test_only_reviewed_modules_import_concrete_repositories(self):
        actual: set[tuple[str, str]] = set()
        for package in ("api", "services", "clients", "runtime", "domain", "templates"):
            for path in (BACKEND / package).glob("*.py"):
                relative_path = path.relative_to(ROOT).as_posix()
                for module in imported_modules(path):
                    if module == "backend.repositories" or module.startswith(
                        "backend.repositories."
                    ):
                        actual.add((relative_path, module))
        self.assertEqual(
            CONCRETE_REPOSITORY_IMPORT_BASELINE,
            actual,
            "Only reviewed legacy imports may bypass repository ports; new cross-context "
            "coordination belongs in an explicit service.",
        )

    def test_lab_repository_port_declares_consumed_operations(self):
        path = BACKEND / "services" / "lab_workflow.py"
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        declared = protocol_methods(tree, "LabRepositoryPort")
        consumed = (
            receiver_method_calls(tree, "store")
            | owned_receiver_method_calls(tree, "self", "repository")
            | {"list_lab_servers"}
        )
        self.assertTrue(declared, "LabRepositoryPort must declare a structural repository surface.")
        self.assertEqual(
            set(),
            consumed - declared,
            f"LabRepositoryPort is missing consumed operations: {sorted(consumed - declared)}",
        )

    def test_runtime_store_ports_declare_operations(self):
        expected = {
            "gdt_bridge_watcher.py": ("GdtBridgeStorePort", {"record_gdt_result"}),
            "oie_result_listener.py": (
                "OieResultStorePort",
                {"record_oie_result", "record_oie_result_error"},
            ),
        }
        for filename, (protocol_name, operations) in expected.items():
            path = BACKEND / "runtime" / filename
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertEqual(operations, protocol_methods(tree, protocol_name))

    def test_gdt_bridge_directory_validation_has_one_owner(self):
        owners = []
        for path in BACKEND.rglob("*.py"):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            if any(
                isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
                and node.name == "validate_gdt_bridge_dirs"
                for node in ast.walk(tree)
            ):
                owners.append(path.relative_to(ROOT).as_posix())
        self.assertEqual(["backend/repositories/gdt_bridge_health.py"], owners)

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

    def test_backend_catch_all_modules_match_reviewed_legacy_baseline(self):
        actual: set[tuple[str, str, str, str]] = set()
        violations: list[PlacementViolation] = []
        for relative_path in CATCH_ALL_BACKEND_PATHS:
            source = (ROOT / relative_path).read_text(encoding="utf-8")
            candidates = legacy_backend_candidates(relative_path, source)
            actual.update(item.baseline_key for item in candidates)
            violations.extend(
                legacy_backend_violations(
                    relative_path,
                    source,
                    BACKEND_LEGACY_BASELINE,
                )
            )
        self.assertEqual(
            [],
            violations,
            "Catch-all placement violations:\n" + "\n".join(map(str, violations)),
        )
        self.assertEqual(
            BACKEND_LEGACY_BASELINE,
            actual,
            "Remove reviewed baseline entries in the same change that extracts legacy implementation.",
        )

    def test_frontend_entrypoints_match_reviewed_legacy_inventories(self):
        js_path = ROOT / "frontend" / "static" / "app.js"
        js_source = js_path.read_text(encoding="utf-8")
        function_violations = frontend_function_violations(
            "frontend/static/app.js",
            js_source,
            FRONTEND_FUNCTION_BASELINE,
        )
        self.assertEqual(
            [],
            function_violations,
            "Frontend placement violations:\n" + "\n".join(map(str, function_violations)),
        )
        self.assertEqual(
            FRONTEND_FUNCTION_BASELINE,
            frontend_definition_inventory(js_source),
            "Remove frontend definition baseline entries when globals move to owned modules.",
        )
        self.assertEqual(
            FRONTEND_FUNCTION_NAME_INVENTORY,
            frozenset(frontend_top_level_definitions(js_source)),
            "Keep the readable frontend name inventory aligned with definition fingerprints.",
        )

        css_path = ROOT / "frontend" / "static" / "styles.css"
        css_source = css_path.read_text(encoding="utf-8")
        selector_violations = frontend_selector_violations(
            "frontend/static/styles.css",
            css_source,
            FRONTEND_SELECTOR_FAMILY_BASELINE,
        )
        self.assertEqual(
            [],
            selector_violations,
            "Frontend placement violations:\n" + "\n".join(map(str, selector_violations)),
        )
        self.assertEqual(
            FRONTEND_SELECTOR_FAMILY_BASELINE,
            frozenset(frontend_selector_families(css_source)),
            "Remove selector-family baseline entries when styles move to owned modules.",
        )

    def test_catch_all_violation_fixtures_name_category_path_and_line(self):
        fixtures = {
            "sql": (
                "def configure(connection):\n"
                "    connection.execute('PRAGMA journal_mode=WAL')\n"
            ),
            "payload": "def serialize_patient():\n    return {'resourceType': 'Patient'}\n",
            "workflow": "def process_patient():\n    return True\n",
            "transport": (
                "import http.client as hc\n"
                "def contact():\n"
                "    return hc.HTTPConnection('host')\n"
            ),
        }
        for category, source in fixtures.items():
            with self.subTest(category=category):
                violations = legacy_backend_violations(
                    "backend/lab_store.py",
                    source,
                    frozenset(),
                )
                matches = [item for item in violations if item.category == category]
                self.assertTrue(matches)
                message = str(matches[0])
                self.assertIn(f"[{category}]", message)
                self.assertIn("backend/lab_store.py", message)
                self.assertRegex(message, r":\d+:")

    def test_compatibility_delegation_and_incremental_extraction_are_allowed(self):
        facade = "from backend.domain.patient import normalize_patient as normalize_patient\n"
        self.assertEqual(
            [],
            legacy_backend_violations("backend/lab_store.py", facade, frozenset()),
        )
        self.assertEqual(
            set(),
            legacy_backend_candidates("backend/lab_store.py", ""),
        )

    def test_new_frontend_globals_and_selector_families_are_rejected(self):
        function_sources = {
            "declaration": "async function fetchNewPatient() { return fetch('/api/patients'); }\n",
            "function expression": "const fetchNewPatient = function () { return fetch('/api/patients'); };\n",
            "let arrow": "let processPatient = (value) => value;\n",
            "var async function": "var loadPatient = async function () { return true; };\n",
            "class": "class PatientWorkspace {}\n",
        }
        for form, source in function_sources.items():
            with self.subTest(form=form):
                function_violations = frontend_function_violations(
                    "frontend/static/app.js",
                    source,
                    frozenset(),
                )
                self.assertTrue(function_violations)
                self.assertRegex(
                    str(function_violations[0]),
                    r"frontend/static/app\.js:\d+:",
                )

        selector_violations = frontend_selector_violations(
            "frontend/static/styles.css",
            ".known-family .new-patient-card { display: block; }\n",
            frozenset({".known-family"}),
        )
        self.assertEqual([".new-patient-card"], [item.detail.split("'")[1] for item in selector_violations])
        self.assertEqual("presentation", selector_violations[0].category)
        self.assertRegex(
            str(selector_violations[0]),
            r"frontend/static/styles\.css:\d+:",
        )

        nested_selector_violations = frontend_selector_violations(
            "frontend/static/styles.css",
            "@media (max-width: 1px) { .brand-new-family { display: block; } }\n",
            frozenset(),
        )
        self.assertEqual(
            [".brand-new-family"],
            [item.detail.split("'")[1] for item in nested_selector_violations],
        )
        self.assertRegex(
            str(nested_selector_violations[0]),
            r"frontend/static/styles\.css:\d+:",
        )

        commented_selector_violations = frontend_selector_violations(
            "frontend/static/styles.css",
            "/* first\nsecond\nthird */\n.new-family { display: block; }\n",
            frozenset(),
        )
        self.assertEqual(4, commented_selector_violations[0].line)

    def test_changed_frontend_definition_body_is_rejected(self):
        original = "function renderServices() { return true; }\n"
        original_baseline = frontend_definition_inventory(original)
        changed = "function renderServices() { return fetch('/api/new-monolith'); }\n"
        violations = frontend_function_violations(
            "frontend/static/app.js",
            changed,
            original_baseline,
        )
        self.assertEqual(1, len(violations))
        self.assertEqual("transport", violations[0].category)

    def test_frontend_literal_whitespace_change_is_rejected(self):
        original = 'function buildPayload() { return "A B"; }\n'
        changed = 'function buildPayload() { return "A  B"; }\n'
        violations = frontend_function_violations(
            "frontend/static/app.js",
            changed,
            frontend_definition_inventory(original),
        )
        self.assertEqual(1, len(violations))
        self.assertEqual("payload", violations[0].category)

    def test_frontend_module_prefix_growth_is_rejected(self):
        original = "const byId = (id) => document.getElementById(id);\n"
        changed = "const NEW_PATIENT_PAYLOAD = { resourceType: 'Patient' };\n" + original
        violations = frontend_function_violations(
            "frontend/static/app.js",
            changed,
            frontend_definition_inventory(original),
        )
        self.assertEqual(1, len(violations))
        self.assertEqual("state", violations[0].category)
        self.assertRegex(str(violations[0]), r"frontend/static/app\.js:1:")

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

    def test_neutrally_named_catch_all_definition_is_rejected(self):
        violations = legacy_backend_violations(
            "backend/lab_store.py",
            "def helper(value):\n    return value\n",
            frozenset(),
        )
        self.assertIn("catch-all", {item.category for item in violations})

    def test_module_level_catch_all_implementation_is_rejected(self):
        fixtures = {
            "transport": (
                "import urllib.request\n"
                "urllib.request.urlopen('http://example')\n"
            ),
            "payload": "PATIENT_TEMPLATE = {'resourceType': 'Patient'}\n",
            "workflow": "result = run_external_workflow()\n",
        }
        for category, source in fixtures.items():
            with self.subTest(category=category):
                violations = legacy_backend_violations(
                    "backend/lab_store.py",
                    source,
                    frozenset(),
                )
                matches = [item for item in violations if item.category == category]
                self.assertTrue(matches)
                self.assertRegex(str(matches[0]), r"backend/lab_store\.py:\d+:")


if __name__ == "__main__":
    unittest.main()
