import ast
import hashlib
import re
import unittest
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from tempfile import TemporaryDirectory

from tests.architecture_legacy_baseline import (
    BACKEND_LEGACY_BASELINE,
    COMPATIBILITY_FACADE_CALLER_BASELINE,
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
    "mappers",
)
ALLOWED_LAYER_DEPENDENCIES: dict[str, frozenset[str]] = {
    "api": frozenset({"api", "services", "domain", "config"}),
    "services": frozenset({"services", "clients", "domain", "templates", "mappers", "config"}),
    "clients": frozenset({"clients", "domain", "config"}),
    "runtime": frozenset({"runtime", "services", "domain", "config"}),
    "repositories": frozenset({"repositories", "domain", "templates", "mappers", "config"}),
    "domain": frozenset({"domain"}),
    "templates": frozenset({"templates", "domain", "config"}),
    "mappers": frozenset({"mappers", "domain"}),
}
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
    "backend/gdt_adapter.py",
    "backend/dashboard_services.py",
    "backend/lab_operations.py",
)
COMPATIBILITY_FACADE_MODULES = frozenset(
    {
        "backend.dashboard_services",
        "backend.gdt_adapter",
        "backend.lab_operations",
    }
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
FRONTEND_JS_ROOT = ROOT / "frontend" / "static" / "js"
FRONTEND_LAYER_DEPENDENCIES = {
    "app.js": frozenset({"views"}),
    "core": frozenset({"core"}),
    "api": frozenset({"api", "core"}),
    "state": frozenset({"state", "core"}),
    "components": frozenset({"components", "state", "core"}),
    "settings": frozenset({"settings", "api", "state", "components", "core"}),
    "views": frozenset({"views", "settings", "api", "state", "components", "core"}),
}
FRONTEND_IMPORT_PATTERN = re.compile(
    r'^\s*import\s+(?:.+?\s+from\s+)?["\'](?P<path>\.[^"\']+)["\'];?',
    re.MULTILINE,
)
PROTECTED_SQL_TABLE_OWNERS = {
    "local_fhir_workflow_records": "backend/repositories/fhir_ledger.py",
    "local_fhir_sync_attempts": "backend/repositories/fhir_ledger.py",
    "local_gdt_order_records": "backend/repositories/gdt_workflow.py",
    "local_gdt_patient_contexts": "backend/repositories/gdt_workflow.py",
    "local_gdt_message_records": "backend/repositories/gdt_workflow.py",
    "local_gdt_attachment_records": "backend/repositories/gdt_workflow.py",
    "local_gdt_workflow_events": "backend/repositories/gdt_workflow.py",
}
OIE_WORKBENCH_COMPOSITION_CALLS = (
    "self.list_oie_local_adt_inventory",
    "self.list_oie_local_order_inventory",
    "self.oie_repository.list_oie_results",
)


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
    body: str

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
        if definition_has_transport(node, self.aliases) or node.name.endswith(
            ("Adapter", "Connection")
        ):
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


def frontend_top_level_definition_occurrences(source: str) -> list[FrontendDefinition]:
    matches = list(FRONTEND_FUNCTION_PATTERN.finditer(source))
    definitions: list[FrontendDefinition] = []
    for index, match in enumerate(matches):
        name = match.group("declaration", "assignment", "class_name")
        name = next(value for value in name if value)
        end = matches[index + 1].start() if index + 1 < len(matches) else len(source)
        body = source[match.start() : end].strip()
        definitions.append(
            FrontendDefinition(
                name=name,
                line=source.count("\n", 0, match.start()) + 1,
                fingerprint=stable_source_fingerprint(body),
                category=frontend_definition_category(name, body),
                body=body,
            )
        )
    return definitions


def frontend_top_level_definitions(source: str) -> dict[str, FrontendDefinition]:
    return {
        definition.name: definition
        for definition in frontend_top_level_definition_occurrences(source)
        if not is_frontend_compatibility_delegate(definition)
    }


def is_frontend_compatibility_delegate(definition: FrontendDefinition) -> bool:
    normalized = re.sub(r"\s+", " ", definition.body).strip()
    if definition.name == "initializeApplication":
        return (
            normalized.startswith("const initializeApplication = () => {")
            and normalized.endswith(
                'document.addEventListener("DOMContentLoaded", initializeApplication);'
            )
        )
    allowed = {
        "setActiveView": "function setActiveView(viewId) { return activateView(viewId); }",
        "copyTextFromElement": (
            "async function copyTextFromElement(elementId) { "
            "return copyElementText(elementId); }"
        ),
        "renderOieInventory": "function renderOieInventory() { return renderOieView(); }",
        "statusClass": "function statusClass(status) { return dashboardStatusClass(status); }",
        "selectedGdtPatient": "function selectedGdtPatient() { return selectedGdtPatientFromView(); }",
        "hl7Escape": "function hl7Escape(value) { return formatHl7Escape(value); }",
        "hl7EscapeComposite": "function hl7EscapeComposite(value) { return formatHl7EscapeComposite(value); }",
        "pad": "function pad(value) { return formatPad(value); }",
        "hl7Timestamp": "function hl7Timestamp(date = new Date()) { return formatHl7Timestamp(date); }",
        "localDatetimeValue": "function localDatetimeValue(date = new Date()) { return formatLocalDatetimeValue(date); }",
        "taipeiTimestamp": "function taipeiTimestamp(value) { return formatTaipeiTimestamp(value); }",
        "gdtTaipeiTimestamp": "function gdtTaipeiTimestamp(value) { return formatGdtTaipeiTimestamp(value); }",
        "fhirBirthDate": "function fhirBirthDate(dob) { return formatFhirBirthDate(dob); }",
        "fhirGender": "function fhirGender(sex) { return formatFhirGender(sex); }",
    }
    expected = allowed.get(definition.name)
    if normalized == expected:
        return True
    return definition.name == "statusClass" and bool(expected) and normalized.startswith(expected)


def frontend_module_prefix_source(source: str) -> str:
    first_definition = FRONTEND_FUNCTION_PATTERN.search(source)
    prefix_end = first_definition.start() if first_definition else len(source)
    return "\n".join(
        line
        for line in source[:prefix_end].splitlines()
        if not line.strip().startswith("import ")
    ).strip()


def frontend_definition_inventory(source: str) -> frozenset[tuple[str, str]]:
    inventory = {
        (
            FRONTEND_MODULE_PREFIX_NAME,
            stable_source_fingerprint(frontend_module_prefix_source(source)),
        )
    }
    inventory.update(
        definition.baseline_key
        for definition in frontend_top_level_definition_occurrences(source)
        if not is_frontend_compatibility_delegate(definition)
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
    definitions = frontend_top_level_definition_occurrences(source)
    violations = [
        PlacementViolation(
            definition.category,
            PurePosixPath(relative_path),
            definition.line,
            f"New or changed top-level frontend definition {definition.name!r} must move to frontend/static/js/.",
        )
        for definition in definitions
        if definition.baseline_key not in baseline
        and not is_frontend_compatibility_delegate(definition)
    ]
    seen_names: set[str] = set()
    for definition in definitions:
        if is_frontend_compatibility_delegate(definition):
            continue
        if definition.name in seen_names:
            violations.append(
                PlacementViolation(
                    definition.category,
                    PurePosixPath(relative_path),
                    definition.line,
                    f"Duplicate top-level frontend definition {definition.name!r} must move to frontend/static/js/.",
                )
            )
        seen_names.add(definition.name)
    prefix_key = (
        FRONTEND_MODULE_PREFIX_NAME,
        stable_source_fingerprint(frontend_module_prefix_source(source)),
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


def frontend_module_import_violations(relative: str, source: str) -> list[str]:
    path = PurePosixPath(relative)
    try:
        layer = path.parts[path.parts.index("js") + 1]
    except (ValueError, IndexError):
        return []
    allowed = FRONTEND_LAYER_DEPENDENCIES.get(layer, frozenset())
    violations = []
    for match in FRONTEND_IMPORT_PATTERN.finditer(source):
        target = (path.parent / match.group("path")).as_posix()
        normalized = PurePosixPath(target)
        parts = []
        for part in normalized.parts:
            if part == "..":
                if parts:
                    parts.pop()
            elif part != ".":
                parts.append(part)
        try:
            target_layer = parts[parts.index("js") + 1]
        except (ValueError, IndexError):
            continue
        if target_layer not in allowed:
            line = source.count("\n", 0, match.start()) + 1
            violations.append(
                f"{relative}:{line} frontend {layer} module imports disallowed {target_layer} owner"
            )
    return violations


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
            for alias in node.names:
                candidate = f"{node.module}.{alias.name}"
                if backend_module_path(candidate):
                    modules.add(candidate)
    return modules


def hidden_backend_import_violations(
    relative_path: str, tree: ast.AST,
) -> list[PlacementViolation]:
    aliases = import_aliases_from_tree(tree)
    path = PurePosixPath(relative_path.replace("\\", "/"))
    violations: list[PlacementViolation] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        loader = resolve_imported_name(node.func, aliases)
        if loader not in {"importlib.import_module", "__import__"}:
            continue
        module = node.args[0].value if (
            node.args and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
        ) else None
        if module is not None and not module.startswith("backend"):
            continue
        detail = (
            f"Dynamic loading hides backend dependency {module!r}."
            if module is not None
            else "Dynamic loading uses a non-literal module and can hide backend dependencies."
        )
        violations.append(PlacementViolation("dependency", path, node.lineno, detail))
    return violations


def operational_sql_table_references(source: str) -> set[str]:
    tree = ast.parse(source)
    references: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Constant) or not isinstance(node.value, str):
            continue
        for table in PROTECTED_SQL_TABLE_OWNERS:
            if re.search(
                rf"\b(?:DELETE\s+FROM|INSERT\s+INTO|UPDATE|FROM|JOIN)\s+{re.escape(table)}\b",
                node.value,
                re.IGNORECASE,
            ):
                references.add(table)
    return references


def imported_modules(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return imported_modules_from_tree(tree) | resolved_backend_imports_from_tree(
        tree,
        path,
    )


def layer_python_paths(package: str, backend_root: Path = BACKEND) -> list[Path]:
    return sorted((backend_root / package).rglob("*.py"))


def backend_dependency_layer(module: str) -> str | None:
    if module == "backend.config" or module.startswith("backend.config."):
        return "config"
    if module == "backend.app_factory" or module.startswith("backend.app_factory."):
        return "composition"
    if not module.startswith("backend."):
        return None
    candidate = module.split(".", 2)[1]
    return candidate if candidate in ALLOWED_LAYER_DEPENDENCIES else None


def layer_dependency_violations(
    relative_path: str,
    modules: set[str],
    repository_baseline: frozenset[tuple[str, str]],
) -> list[PlacementViolation]:
    path = PurePosixPath(relative_path.replace("\\", "/"))
    source_layer = path.parts[1] if len(path.parts) > 2 else ""
    allowed_layers = ALLOWED_LAYER_DEPENDENCIES.get(source_layer, frozenset())
    violations: list[PlacementViolation] = []
    for module in sorted(modules):
        dependency_layer = backend_dependency_layer(module)
        if dependency_layer is None or dependency_layer in allowed_layers:
            continue
        if (
            dependency_layer == "repositories"
            and (path.as_posix(), module) in repository_baseline
        ):
            continue
        violations.append(
            PlacementViolation(
                "dependency",
                path,
                1,
                f"{source_layer} modules must not depend outward on {module!r}.",
            )
        )
    return violations


def compatibility_facade_caller_violations(
    relative_path: str,
    modules: set[str],
    baseline: frozenset[tuple[str, str]],
) -> list[PlacementViolation]:
    path = PurePosixPath(relative_path.replace("\\", "/"))
    return [
        PlacementViolation(
            "dependency",
            path,
            1,
            f"New callers must import the owner of compatibility facade {module!r} directly.",
        )
        for module in sorted(modules & COMPATIBILITY_FACADE_MODULES)
        if (path.as_posix(), module) not in baseline
    ]


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


def resolved_backend_imports_from_tree(tree: ast.AST, path: Path) -> set[str]:
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


def resolved_backend_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    return resolved_backend_imports_from_tree(tree, path)


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
            if SQL_PATTERN.search(node.value) and package not in {"repositories", "clients"}:
                violations.append(
                    PlacementViolation(
                        "sql",
                        path,
                        node.lineno,
                        "SQL statements must live in backend/repositories or external database clients.",
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


def repository_pure_responsibility_violations(relative: str, source: str) -> list[str]:
    tree = ast.parse(source, filename=relative)
    aliases = import_aliases_from_tree(tree)
    infrastructure_validators = {
        ("backend/repositories/database.py", "_validate_migrations"),
        ("backend/repositories/gdt_bridge_health.py", "validate_gdt_bridge_dirs"),
    }
    violations = []
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if (relative, node.name) in infrastructure_validators:
            continue
        if definition_has_sql_execution(node):
            continue
        calls = [
            resolve_imported_name(child.func, aliases)
            for child in ast.walk(node)
            if isinstance(child, ast.Call)
        ]
        delegates_to_pure_owner = any(
            call.startswith(("backend.domain.", "backend.templates.", "backend.mappers."))
            for call in calls
        )
        returns = [child.value for child in ast.walk(node) if isinstance(child, ast.Return)]
        thin_delegate = delegates_to_pure_owner and all(
            value is None or isinstance(value, (ast.Call, ast.ListComp))
            for value in returns
        )
        if thin_delegate:
            continue
        raises_validation = any(
            isinstance(child, ast.Raise)
            and isinstance(child.exc, ast.Call)
            and resolve_imported_name(child.exc.func, aliases).endswith("SimulatorValidationError")
            for child in ast.walk(node)
        )
        return_literals = {
            child.value
            for value in returns if value is not None
            for child in ast.walk(value)
            if isinstance(child, ast.Constant) and isinstance(child.value, str)
        }
        protocol_shape = any(
            value.startswith(("MSH|", "PID|", "OBR|", "ORC|"))
            or value in {"resourceType", "identifier", "00400100", "00080050"}
            or re.fullmatch(r"[0-9A-Fa-f]{8}", value)
            for value in return_literals
        )
        returns_public_dict = any(isinstance(value, ast.Dict) for value in returns)
        if raises_validation:
            violations.append(f"{relative}:{node.lineno} repository validation {node.name}")
        elif protocol_shape:
            violations.append(f"{relative}:{node.lineno} repository pure responsibility {node.name}")
        elif returns_public_dict:
            violations.append(f"{relative}:{node.lineno} repository presentation {node.name}")
    return violations


class ArchitectureContractTest(unittest.TestCase):
    def test_frontend_modules_follow_declared_dependency_direction(self):
        violations = []
        for path in FRONTEND_JS_ROOT.rglob("*.js"):
            relative = path.relative_to(ROOT).as_posix()
            violations.extend(
                frontend_module_import_violations(
                    relative,
                    path.read_text(encoding="utf-8"),
                )
            )
        self.assertEqual([], violations)

    def test_frontend_dependency_direction_rejects_lower_layer_view_imports(self):
        fixtures = {
            "api": 'import { render } from "../views/patient.js";\n',
            "state": 'import { render } from "../views/order.js";\n',
            "components": 'import { send } from "../api/oie.js";\n',
            "core": 'import { state } from "../state/selection.js";\n',
        }
        for layer, source in fixtures.items():
            with self.subTest(layer=layer):
                violations = frontend_module_import_violations(
                    f"frontend/static/js/{layer}/fixture.js",
                    source,
                )
                self.assertEqual(1, len(violations))
                self.assertIn(f"frontend {layer} module", violations[0])

    def test_frontend_compatibility_delegate_rejects_lookalikes(self):
        accepted = frontend_top_level_definition_occurrences(
            "function setActiveView(viewId) { return activateView(viewId); }"
        )[0]
        self.assertTrue(is_frontend_compatibility_delegate(accepted))
        rejected = (
            "function setActiveView(viewId) { refreshDashboard(); return activateView(viewId); }",
            "function setActiveView(viewId) { return activateView('other'); }",
            "async function copyTextFromElement(elementId) { return navigator.clipboard.writeText(elementId); }",
        )
        for source in rejected:
            with self.subTest(source=source):
                definition = frontend_top_level_definition_occurrences(source)[0]
                self.assertFalse(is_frontend_compatibility_delegate(definition))

    def test_responsibility_packages_exist(self):
        for package in RESPONSIBILITY_PACKAGES:
            with self.subTest(package=package):
                self.assertTrue((BACKEND / package / "__init__.py").is_file())

    def test_repositories_do_not_implement_pure_validation_builders_or_presentation(self):
        violations = []
        for path in layer_python_paths("repositories"):
            relative = path.relative_to(ROOT).as_posix()
            violations.extend(repository_pure_responsibility_violations(
                relative, path.read_text(encoding="utf-8")
            ))
        self.assertEqual([], violations)

    def test_repository_responsibility_rule_rejects_renamed_implementations(self):
        fixtures = {
            "validation": """\
from backend.domain.errors import SimulatorValidationError
def check_input(value):
    if not value:
        raise SimulatorValidationError('required')
    return value
""",
            "protocol-builder": """\
def make_message(patient):
    return 'MSH|^~\\\\&|LAB|' + patient['mrn']
""",
            "presentation": """\
def row_to_public_json(row):
    return {'patientId': row['patient_id']}
""",
        }
        for label, source in fixtures.items():
            with self.subTest(label=label):
                self.assertTrue(repository_pure_responsibility_violations(
                    f"backend/repositories/{label}.py", source
                ))

    def test_repository_responsibility_rule_permits_sql_and_mapper_delegates(self):
        sql = """\
def load(connection):
    row = connection.execute('SELECT * FROM records').fetchone()
    return {'id': row['id']}
"""
        delegate = """\
from backend.mappers.patient import project
def row_to_public_json(row):
    return project(row)
"""
        self.assertEqual([], repository_pure_responsibility_violations(
            "backend/repositories/sql.py", sql
        ))
        self.assertEqual([], repository_pure_responsibility_violations(
            "backend/repositories/delegate.py", delegate
        ))

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
        self.assertEqual(
            {"__future__", "backend.app_factory"},
            modules,
        )
        self.assertLessEqual(len(source.splitlines()), 20)
        for forbidden in ("@app.", "sqlite3", "urllib", "socket", "threading"):
            with self.subTest(forbidden=forbidden):
                self.assertNotIn(forbidden, source)

    def test_lower_layers_do_not_import_flask_or_api_modules(self):
        for package in ("clients", "repositories", "domain", "templates", "mappers"):
            for path in layer_python_paths(package):
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
                    if package in {"domain", "mappers"}:
                        self.assertFalse(
                            any(
                                name == "backend.config" or name.startswith("backend.config.")
                                for name in modules
                            ),
                            f"{path.relative_to(ROOT)} domain layer must not import configuration.",
                        )

    def test_parent_package_imports_resolve_child_modules(self):
        modules = imported_modules_from_tree(
            ast.parse("from backend import api, repositories\n")
        )
        self.assertIn("backend.api", modules)
        self.assertIn("backend.repositories", modules)

    def test_relative_imports_resolve_absolute_backend_modules(self):
        tree = ast.parse(
            "from .. import api, repositories\n"
            "from ..repositories import patient\n"
        )
        modules = resolved_backend_imports_from_tree(
            tree,
            ROOT / "backend" / "domain" / "patient.py",
        )
        self.assertIn("backend.api", modules)
        self.assertIn("backend.repositories", modules)

    def test_layer_module_discovery_is_recursive(self):
        with TemporaryDirectory() as temporary_directory:
            backend_root = Path(temporary_directory)
            nested_module = backend_root / "domain" / "patient" / "model.py"
            nested_module.parent.mkdir(parents=True)
            nested_module.write_text("from backend import api\n", encoding="utf-8")
            self.assertEqual(
                [nested_module],
                layer_python_paths("domain", backend_root),
            )

    def test_layer_dependency_matrix_rejects_outward_imports(self):
        fixtures = {
            "backend/api/example.py": "backend.clients.medplum",
            "backend/clients/example.py": "backend.services.fhir_workflow",
            "backend/repositories/example.py": "backend.clients.dcm4chee",
            "backend/domain/example.py": "backend.services.patient_workflow",
            "backend/mappers/example.py": "backend.repositories.patients",
        }
        for relative_path, module in fixtures.items():
            with self.subTest(path=relative_path, module=module):
                violations = layer_dependency_violations(
                    relative_path,
                    {module},
                    frozenset(),
                )
                self.assertEqual(1, len(violations))
                self.assertEqual("dependency", violations[0].category)

    def test_mapper_dependency_matrix_accepts_only_mapper_and_domain_modules(self):
        self.assertEqual(
            [],
            layer_dependency_violations(
                "backend/mappers/patient.py",
                {"backend.mappers.types", "backend.domain.records"},
                frozenset(),
            ),
        )
        forbidden = (
            "backend.repositories.patients",
            "backend.services.patient_workflow",
            "backend.clients.medplum",
            "backend.runtime.gdt_bridge_watcher",
            "backend.app_factory",
        )
        for module in forbidden:
            with self.subTest(module=module):
                violations = layer_dependency_violations(
                    "backend/mappers/patient.py", {module}, frozenset()
                )
                self.assertEqual(1, len(violations))

    def test_layer_dependencies_follow_allowed_matrix(self):
        violations: list[PlacementViolation] = []
        for package in RESPONSIBILITY_PACKAGES:
            for path in layer_python_paths(package):
                violations.extend(
                    layer_dependency_violations(
                        path.relative_to(ROOT).as_posix(),
                        imported_modules(path),
                        CONCRETE_REPOSITORY_IMPORT_BASELINE,
                    )
                )
        self.assertEqual(
            [],
            violations,
            "Layer dependency violations:\n" + "\n".join(map(str, violations)),
        )

    def test_responsibility_packages_cannot_hide_backend_dependencies(self):
        violations: list[PlacementViolation] = []
        for package in RESPONSIBILITY_PACKAGES:
            for path in layer_python_paths(package):
                tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
                violations.extend(
                    hidden_backend_import_violations(
                        path.relative_to(ROOT).as_posix(), tree,
                    )
                )
        self.assertEqual(
            [],
            violations,
            "Hidden dependency violations:\n" + "\n".join(map(str, violations)),
        )

    def test_hidden_backend_dependency_detection_covers_dynamic_loaders(self):
        fixtures = (
            "from importlib import import_module\nimport_module('backend.repositories.lab')\n",
            "from importlib import import_module as load\nload('backend.templates.fhir')\n",
            "import importlib\nimportlib.import_module(module_name)\n",
            "__import__('backend.services.lab_workflow')\n",
        )
        for source in fixtures:
            with self.subTest(source=source):
                violations = hidden_backend_import_violations(
                    "backend/services/example.py", ast.parse(source),
                )
                self.assertEqual(1, len(violations))
                self.assertEqual("dependency", violations[0].category)

        self.assertEqual(
            [],
            hidden_backend_import_violations(
                "backend/services/example.py",
                ast.parse("from importlib import import_module\nimport_module('decimal')\n"),
            ),
        )

    def test_only_reviewed_modules_import_compatibility_facades(self):
        actual: set[tuple[str, str]] = set()
        violations: list[PlacementViolation] = []
        for path in sorted(BACKEND.rglob("*.py")):
            relative_path = path.relative_to(ROOT).as_posix()
            modules = imported_modules(path)
            actual.update(
                (relative_path, module)
                for module in modules & COMPATIBILITY_FACADE_MODULES
            )
            violations.extend(
                compatibility_facade_caller_violations(
                    relative_path,
                    modules,
                    COMPATIBILITY_FACADE_CALLER_BASELINE,
                )
            )
        self.assertEqual(
            [],
            violations,
            "Compatibility facade caller violations:\n" + "\n".join(map(str, violations)),
        )
        self.assertEqual(
            COMPATIBILITY_FACADE_CALLER_BASELINE,
            actual,
            "Remove facade caller baseline entries when existing callers migrate to owners.",
        )

    def test_new_compatibility_facade_callers_are_rejected(self):
        fixtures = {
            "backend/services/new_gdt.py": "backend.gdt_adapter",
            "backend/clients/new_docker.py": "backend.lab_operations",
            "backend/services/new_dashboard.py": "backend.dashboard_services",
        }
        for relative_path, module in fixtures.items():
            with self.subTest(path=relative_path, module=module):
                violations = compatibility_facade_caller_violations(
                    relative_path,
                    {module},
                    frozenset(),
                )
                self.assertEqual(1, len(violations))
                self.assertEqual("dependency", violations[0].category)
                self.assertIn(module, violations[0].detail)

    def test_services_do_not_depend_transitively_on_concrete_store(self):
        for path in layer_python_paths("services"):
            modules = transitive_backend_imports(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.application_composition",
                    modules,
                    f"{path.relative_to(ROOT)} must not load application composition directly or through another backend module.",
                )

    def test_api_modules_do_not_import_concrete_store(self):
        for path in layer_python_paths("api"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.application_composition",
                    modules,
                    f"{path.relative_to(ROOT)} must map HTTP through service ports, not application composition.",
                )

    def test_api_modules_do_not_import_operation_adapters(self):
        for path in layer_python_paths("api"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.lab_operations",
                    modules,
                    f"{path.relative_to(ROOT)} must handle domain errors without importing operation adapters.",
                )

    def test_runtime_does_not_import_concrete_store(self):
        for path in layer_python_paths("runtime"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn(
                    "backend.application_composition",
                    modules,
                    f"{path.relative_to(ROOT)} must depend on runtime ports, not application composition.",
                )

    def test_services_and_repositories_do_not_import_runtime(self):
        for package in ("services", "repositories"):
            for path in layer_python_paths(package):
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
            for path in layer_python_paths(package):
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
        consumed.discard("list_gdt_orders")
        self.assertTrue(declared, "LabRepositoryPort must declare a structural repository surface.")
        self.assertEqual(
            set(),
            consumed - declared,
            f"LabRepositoryPort is missing consumed operations: {sorted(consumed - declared)}",
        )
        self.assertIn(
            "list_gdt_orders",
            protocol_methods(tree, "LabOperationStorePort"),
            "Cross-context GDT inventory must remain on the operation coordination port.",
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

    def test_fhir_and_gdt_operational_sql_has_one_owner_per_table(self):
        actual_owners = {table: set() for table in PROTECTED_SQL_TABLE_OWNERS}
        for path in BACKEND.rglob("*.py"):
            relative_path = path.relative_to(ROOT).as_posix()
            if relative_path == "backend/repositories/schema.py":
                continue
            for table in operational_sql_table_references(
                path.read_text(encoding="utf-8")
            ):
                actual_owners[table].add(relative_path)

        self.assertEqual(
            {
                table: {owner}
                for table, owner in PROTECTED_SQL_TABLE_OWNERS.items()
            },
            actual_owners,
            "Protected FHIR/GDT tables must have exactly one operational SQL owner; "
            "schema declarations are allowed in backend/repositories/schema.py.",
        )

    def test_protected_table_sql_detection_ignores_schema_declarations(self):
        self.assertEqual(
            {"local_fhir_workflow_records", "local_gdt_order_records"},
            operational_sql_table_references(
                "FIRST = 'SELECT * FROM local_fhir_workflow_records'\n"
                "SECOND = 'UPDATE local_gdt_order_records SET status = ?'\n"
            ),
        )
        self.assertEqual(
            set(),
            operational_sql_table_references(
                "SCHEMA = 'CREATE TABLE local_fhir_workflow_records (id INTEGER)'\n"
            ),
        )

    def test_configuration_does_not_import_concrete_store(self):
        path = BACKEND / "config.py"
        self.assertNotIn(
            "backend.application_composition",
            imported_modules(path),
            "backend/config.py must use domain configuration types, not application composition.",
        )

    def test_patient_and_order_projection_modules_are_persistence_neutral(self):
        forbidden_roots = {"flask", "sqlite3"}
        paths = (
            BACKEND / "domain" / "patient.py",
            BACKEND / "domain" / "order.py",
            BACKEND / "templates" / "patient.py",
            BACKEND / "templates" / "order.py",
        )
        violations = []
        for path in paths:
            modules = imported_modules(path)
            forbidden = sorted(
                module for module in modules if module.split(".", 1)[0] in forbidden_roots
            )
            if forbidden:
                violations.append(
                    f"{path.relative_to(ROOT).as_posix()}: {', '.join(forbidden)}"
                )
        self.assertEqual(
            [],
            violations,
            "Patient/order domain and template modules must not import Flask or SQLite.",
        )

    def test_responsibility_packages_obey_placement_contract(self):
        violations: list[PlacementViolation] = []
        for package in RESPONSIBILITY_PACKAGES:
            for path in layer_python_paths(package):
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
            600,
            "backend/app_factory.py must remain a compact composition root.",
        )

    def test_removed_facade_has_no_replacement_defaults_grab_bag(self):
        replacement = BACKEND / ("application" + "_defaults.py")
        self.assertFalse(
            replacement.exists(),
            "Application defaults must stay with focused configuration, domain, or protocol owners.",
        )
        for path in (BACKEND / "app_factory.py", BACKEND / "application_composition.py"):
            modules = imported_modules(path)
            with self.subTest(path=path.relative_to(ROOT)):
                self.assertNotIn("backend." + "application" + "_defaults", modules)

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
                    "backend/obsolete_facade.py",
                    source,
                    frozenset(),
                )
                matches = [item for item in violations if item.category == category]
                self.assertTrue(matches)
                message = str(matches[0])
                self.assertIn(f"[{category}]", message)
                self.assertIn("backend/obsolete_facade.py", message)
                self.assertRegex(message, r":\d+:")

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

    def test_duplicate_frontend_definition_name_is_rejected(self):
        original = "function renderServices() { return true; }\n"
        baseline = frontend_definition_inventory(original)
        changed = (
            "var renderServices = function () { return fetch('/api/new-monolith'); };\n"
            + original
        )
        violations = frontend_function_violations(
            "frontend/static/app.js",
            changed,
            baseline,
        )
        self.assertIn("transport", {item.category for item in violations})
        self.assertTrue(any("Duplicate" in item.detail for item in violations))

        exact_duplicate_violations = frontend_function_violations(
            "frontend/static/app.js",
            original + original,
            baseline,
        )
        self.assertTrue(
            any("Duplicate" in item.detail for item in exact_duplicate_violations)
        )

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
            "backend/obsolete_facade.py",
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
                    "backend/obsolete_facade.py",
                    source,
                    frozenset(),
                )
                matches = [item for item in violations if item.category == category]
                self.assertTrue(matches)
                self.assertRegex(str(matches[0]), r"backend/obsolete_facade\.py:\d+:")


if __name__ == "__main__":
    unittest.main()
