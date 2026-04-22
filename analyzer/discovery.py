"""
Codebase discovery helpers for backend profile inference and API cataloging.
"""
from __future__ import annotations

import ast
import os
import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Set, Tuple


HTTP_METHODS = {"GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS", "HEAD"}
PYTHON_FRAMEWORK_HINTS = {
    "fastapi": "FastAPI",
    "flask": "Flask",
    "django": "Django",
    "rest_framework": "Django REST Framework",
    "strawberry": "Strawberry GraphQL",
    "graphene": "Graphene",
    "sqlalchemy": "SQLAlchemy",
    "sqlmodel": "SQLModel",
    "pymongo": "PyMongo",
    "motor": "Motor",
}
JAVA_FRAMEWORK_HINTS = {
    "org.springframework.web": "Spring Web",
    "org.springframework.graphql": "Spring GraphQL",
    "io.quarkus": "Quarkus",
    "org.eclipse.microprofile.graphql": "MicroProfile GraphQL",
    "jakarta.ws.rs": "JAX-RS",
    "javax.ws.rs": "JAX-RS",
    "javax.persistence": "JPA",
    "jakarta.persistence": "JPA",
    "org.springframework.data.mongodb": "Spring Data MongoDB",
}
SQL_MARKERS = ("sqlalchemy", "sqlmodel", "psycopg", "sqlite", "mysql", "postgres", "jpa", "hibernate")
NOSQL_MARKERS = ("mongodb", "mongo", "redis", "cassandra", "dynamodb", "pymongo", "motor")
JAVA_SIMPLE_TYPE_EXAMPLES = {
    "String": "example",
    "Integer": 0,
    "int": 0,
    "Long": 0,
    "long": 0,
    "Short": 0,
    "short": 0,
    "Double": 0.0,
    "double": 0.0,
    "Float": 0.0,
    "float": 0.0,
    "BigDecimal": 0.0,
    "Boolean": False,
    "boolean": False,
    "Map": {},
    "HashMap": {},
    "List": [],
    "ArrayList": [],
    "Set": [],
}
GRAPHQL_SCHEMA_EXTENSIONS = (".graphql", ".gql", ".graphqls")
GRAPHQL_SCALAR_EXAMPLES = {
    "String": "example",
    "ID": "example-id",
    "Int": 0,
    "Float": 0.0,
    "Boolean": False,
    "JSON": {},
}
GRAPHQL_SCALAR_TYPES = set(GRAPHQL_SCALAR_EXAMPLES) | {
    "str", "int", "float", "bool", "dict", "list",
    "String", "ID", "Int", "Float", "Boolean", "JSON",
}


def _normalize_graphql_type_name(type_name: str) -> str:
    cleaned = type_name.strip()
    cleaned = cleaned.split("@")[0].strip()
    cleaned = cleaned.replace("[", "").replace("]", "").replace("!", "").strip()
    return cleaned


def _is_graphql_scalar_type(type_name: str) -> bool:
    return _normalize_graphql_type_name(type_name) in GRAPHQL_SCALAR_TYPES


def _graphql_placeholder_selection() -> str:
    return " {\n    field1\n    field2\n  }"


@dataclass
class DiscoveredEndpoint:
    """One API surface discovered from the codebase."""

    name: str
    kind: str
    method: str
    path: str
    source_file: str
    line: int
    example_json_body: Optional[Dict[str, Any]] = None
    graphql_query: str = ""
    graphql_variables: Dict[str, Any] = field(default_factory=dict)
    example_response_body: Optional[Dict[str, Any]] = None

    def label(self) -> str:
        if self.kind == "graphql":
            return f"{self.method} {self.path} :: {self.name}"
        return f"{self.method} {self.path}"


@dataclass
class JavaParameter:
    """Parsed Java method parameter with lightweight annotation metadata."""

    type_name: str
    name: str
    annotations: List[str] = field(default_factory=list)


@dataclass
class BackendDiscovery:
    """High-level backend profile inferred from source code."""

    runtime: str = "Unknown"
    api_style: str = "Unknown"
    database_type: str = "Unknown"
    frameworks: List[str] = field(default_factory=list)
    endpoints: List[DiscoveredEndpoint] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "runtime": self.runtime,
            "api_style": self.api_style,
            "database_type": self.database_type,
            "frameworks": self.frameworks,
            "endpoints": [
                {
                    "name": endpoint.name,
                    "kind": endpoint.kind,
                    "method": endpoint.method,
                    "path": endpoint.path,
                    "source_file": endpoint.source_file,
                    "line": endpoint.line,
                    "example_json_body": endpoint.example_json_body,
                    "graphql_query": endpoint.graphql_query,
                    "graphql_variables": endpoint.graphql_variables,
                    "example_response_body": endpoint.example_response_body,
                }
                for endpoint in self.endpoints
            ],
        }


class BackendDiscoveryEngine:
    """Infer backend metadata and endpoint examples from source files."""

    SKIP_DIRS = {
        "venv", "env", ".venv", ".env",
        "__pycache__", ".git", ".github",
        "node_modules", "dist", "build",
        ".pytest_cache", ".tox", "eggs",
        ".egg-info", ".mypy_cache", ".ruff_cache",
        ".vscode", ".idea", "htmlcov",
        "site-packages", ".cache",
    }

    def discover(self, path: str) -> BackendDiscovery:
        discovery = BackendDiscovery()
        python_files: List[str] = []
        java_files: List[str] = []
        java_http_root_path = self._discover_java_http_root_path(path)
        graphql_http_path = self._discover_graphql_http_path(path)
        schema_index = self._discover_graphql_schema(path)

        for file_path in self._iter_source_files(path):
            if file_path.endswith(".py"):
                python_files.append(file_path)
            elif file_path.endswith(".java"):
                java_files.append(file_path)

        if python_files and not java_files:
            discovery.runtime = "Python"
        elif java_files and not python_files:
            discovery.runtime = "Java"
        elif python_files and java_files:
            discovery.runtime = "Python + Java"

        frameworks: Set[str] = set()
        db_markers: Set[str] = set()
        api_styles: Set[str] = set()
        endpoints: List[DiscoveredEndpoint] = []

        for file_path in python_files:
            file_frameworks, file_db_markers, file_api_styles, file_endpoints = self._discover_python_file(
                file_path,
                path,
                graphql_http_path=graphql_http_path,
            )
            frameworks.update(file_frameworks)
            db_markers.update(file_db_markers)
            api_styles.update(file_api_styles)
            endpoints.extend(file_endpoints)

        for file_path in java_files:
            file_frameworks, file_db_markers, file_api_styles, file_endpoints = self._discover_java_file(
                file_path,
                path,
                graphql_http_path=graphql_http_path,
                java_http_root_path=java_http_root_path,
            )
            frameworks.update(file_frameworks)
            db_markers.update(file_db_markers)
            api_styles.update(file_api_styles)
            endpoints.extend(file_endpoints)

        discovery.frameworks = sorted(frameworks)
        discovery.database_type = self._classify_database_type(db_markers)
        discovery.api_style = self._classify_api_style(api_styles)
        endpoints = self._enrich_graphql_endpoints_with_schema(endpoints, schema_index, graphql_http_path)
        discovery.endpoints = self._dedupe_endpoints(endpoints)
        return discovery

    def _iter_source_files(self, path: str):
        if os.path.isfile(path):
            yield path
            return

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if filename.endswith((".py", ".java")):
                    yield os.path.join(root, filename)

    def _iter_graphql_schema_files(self, path: str):
        if os.path.isfile(path):
            if path.endswith(GRAPHQL_SCHEMA_EXTENSIONS):
                yield path
            return

        for root, dirs, files in os.walk(path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if filename.endswith(GRAPHQL_SCHEMA_EXTENSIONS):
                    yield os.path.join(root, filename)

    def _discover_graphql_http_path(self, path: str) -> str:
        if os.path.isfile(path):
            root_path = os.path.dirname(path) or "."
        else:
            root_path = path

        python_files: List[str] = []
        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if filename.endswith(".py"):
                    python_files.append(os.path.join(root, filename))
                if filename not in {"application.properties", "application.yml", "application.yaml"}:
                    continue
                file_path = os.path.join(root, filename)
                configured_path = self._extract_graphql_path_from_config(file_path)
                if configured_path:
                    return configured_path

        for file_path in python_files:
            configured_path = self._extract_graphql_path_from_python(file_path)
            if configured_path:
                return configured_path
        return "/graphql"

    def _discover_java_http_root_path(self, path: str) -> str:
        if os.path.isfile(path):
            root_path = os.path.dirname(path) or "."
        else:
            root_path = path

        for root, dirs, files in os.walk(root_path):
            dirs[:] = [d for d in dirs if d not in self.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if filename not in {"application.properties", "application.yml", "application.yaml"}:
                    continue
                file_path = os.path.join(root, filename)
                configured_path = self._extract_java_http_root_path_from_config(file_path)
                if configured_path:
                    return configured_path
        return ""

    def _discover_graphql_schema(self, path: str) -> Dict[str, Any]:
        object_fields: Dict[str, List[Tuple[str, str]]] = {}
        operations: Dict[Tuple[str, str], Dict[str, Any]] = {}
        for file_path in self._iter_graphql_schema_files(path):
            try:
                with open(file_path, "r", encoding="utf-8") as handle:
                    content = handle.read()
            except Exception:
                continue
            relative_path = os.path.relpath(file_path, path if os.path.isdir(path) else os.path.dirname(path) or ".")
            self._parse_graphql_schema_content(content, relative_path, object_fields, operations)
        return {
            "object_fields": object_fields,
            "operations": operations,
        }

    def _parse_graphql_schema_content(
        self,
        content: str,
        relative_path: str,
        object_fields: Dict[str, List[Tuple[str, str]]],
        operations: Dict[Tuple[str, str], Dict[str, Any]],
    ) -> None:
        block_pattern = re.compile(r"(extend\s+)?type\s+(?P<name>\w+)\s*\{(?P<body>.*?)\}", re.DOTALL)
        for match in block_pattern.finditer(content):
            type_name = match.group("name")
            body = match.group("body")
            line = content[:match.start()].count("\n") + 1
            fields = self._parse_graphql_schema_fields(body)
            if type_name in {"Query", "Mutation"}:
                operation_kind = type_name.lower()
                for field_name, field_type, args in fields:
                    operations[(operation_kind, field_name)] = {
                        "return_type": field_type,
                        "args": args,
                        "source_file": relative_path,
                        "line": line,
                    }
            else:
                existing = object_fields.setdefault(type_name, [])
                for field_name, field_type, _ in fields:
                    if all(existing_name != field_name for existing_name, _ in existing):
                        existing.append((field_name, field_type))

    def _parse_graphql_schema_fields(self, body: str) -> List[Tuple[str, str, List[Tuple[str, str]]]]:
        fields: List[Tuple[str, str, List[Tuple[str, str]]]] = []
        for raw_line in body.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or line.startswith('"""'):
                continue
            field_match = re.match(r"(?P<name>\w+)\s*(?:\((?P<args>[^)]*)\))?\s*:\s*(?P<return>.+)", line)
            if not field_match:
                continue
            args = self._parse_graphql_schema_args(field_match.group("args") or "")
            fields.append(
                (
                    field_match.group("name"),
                    self._normalize_graphql_schema_type(field_match.group("return")),
                    args,
                )
            )
        return fields

    def _parse_graphql_schema_args(self, args_text: str) -> List[Tuple[str, str]]:
        args: List[Tuple[str, str]] = []
        for segment in [part.strip() for part in args_text.split(",") if part.strip()]:
            match = re.match(r"(?P<name>\w+)\s*:\s*(?P<type>.+)", segment)
            if match:
                args.append((match.group("name"), match.group("type").strip()))
        return args

    def _normalize_graphql_schema_type(self, type_name: str) -> str:
        return _normalize_graphql_type_name(type_name)

    def _enrich_graphql_endpoints_with_schema(
        self,
        endpoints: List[DiscoveredEndpoint],
        schema_index: Dict[str, Any],
        graphql_http_path: str,
    ) -> List[DiscoveredEndpoint]:
        operations: Dict[Tuple[str, str], Dict[str, Any]] = schema_index.get("operations", {})
        if not operations:
            return endpoints

        enriched: List[DiscoveredEndpoint] = []
        seen_schema_operations: Set[Tuple[str, str]] = set()
        for endpoint in endpoints:
            if endpoint.kind != "graphql":
                enriched.append(endpoint)
                continue
            operation_kind = self._graphql_operation_kind_from_query(endpoint.graphql_query)
            operation_key = (operation_kind, endpoint.name)
            schema_operation = operations.get(operation_key) or operations.get(("query", endpoint.name)) or operations.get(("mutation", endpoint.name))
            if not schema_operation:
                enriched.append(endpoint)
                continue
            seen_schema_operations.add((operation_kind, endpoint.name))
            schema_query = self._build_graphql_query_from_schema(
                endpoint.name,
                operation_kind,
                schema_operation,
                schema_index.get("object_fields", {}),
            )
            endpoint.graphql_query = schema_query or endpoint.graphql_query
            if not endpoint.graphql_variables:
                endpoint.graphql_variables = self._graphql_variables_from_schema_args(schema_operation.get("args", []))
            enriched.append(endpoint)

        existing_graphql_keys = {(self._graphql_operation_kind_from_query(endpoint.graphql_query), endpoint.name) for endpoint in endpoints if endpoint.kind == "graphql"}
        for (operation_kind, operation_name), schema_operation in operations.items():
            if (operation_kind, operation_name) in existing_graphql_keys:
                continue
            enriched.append(
                DiscoveredEndpoint(
                    name=operation_name,
                    kind="graphql",
                    method="POST",
                    path=graphql_http_path,
                    source_file=schema_operation["source_file"],
                    line=schema_operation["line"],
                    graphql_query=self._build_graphql_query_from_schema(
                        operation_name,
                        operation_kind,
                        schema_operation,
                        schema_index.get("object_fields", {}),
                    ),
                    graphql_variables=self._graphql_variables_from_schema_args(schema_operation.get("args", [])),
                )
            )
        return enriched

    def _graphql_operation_kind_from_query(self, query: str) -> str:
        stripped = query.lstrip()
        if stripped.startswith("mutation"):
            return "mutation"
        return "query"

    def _build_graphql_query_from_schema(
        self,
        name: str,
        operation_kind: str,
        schema_operation: Dict[str, Any],
        object_fields: Dict[str, List[Tuple[str, str]]],
    ) -> str:
        args = schema_operation.get("args", [])
        variable_signature = self._graphql_variable_signature_from_schema_args(args)
        field_arguments = self._graphql_field_arguments_from_schema_args(args)
        selection = self._graphql_selection_from_schema_type(schema_operation.get("return_type", ""), object_fields)
        field_line = f"{name}{field_arguments}{selection}"
        operation_label = f"{name}Operation" if operation_kind == "mutation" else f"{name}Query"
        return f"{operation_kind} {operation_label}{variable_signature} {{\n  {field_line}\n}}"

    def _graphql_variable_signature_from_schema_args(self, args: List[Tuple[str, str]]) -> str:
        if not args:
            return ""
        declarations = [f"${name}: {type_name.strip()}" for name, type_name in args]
        return "(" + ", ".join(declarations) + ")"

    def _graphql_field_arguments_from_schema_args(self, args: List[Tuple[str, str]]) -> str:
        if not args:
            return ""
        rendered = [f"{name}: ${name}" for name, _ in args]
        return "(" + ", ".join(rendered) + ")"

    def _graphql_variables_from_schema_args(self, args: List[Tuple[str, str]]) -> Dict[str, Any]:
        variables: Dict[str, Any] = {}
        for name, type_name in args:
            normalized_type = self._normalize_graphql_schema_type(type_name)
            variables[name] = GRAPHQL_SCALAR_EXAMPLES.get(normalized_type, "")
        return variables

    def _graphql_selection_from_schema_type(
        self,
        type_name: str,
        object_fields: Dict[str, List[Tuple[str, str]]],
        depth: int = 0,
    ) -> str:
        normalized = self._normalize_graphql_schema_type(type_name)
        if not normalized or _is_graphql_scalar_type(normalized):
            return ""
        return _graphql_placeholder_selection()

    def _extract_graphql_path_from_config(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except Exception:
            return ""

        root_path = self._extract_java_http_root_path_from_content(content)

        properties_match = re.search(r"^\s*spring\.graphql\.path\s*=\s*(\S+)\s*$", content, re.MULTILINE)
        if properties_match:
            return self._join_paths(root_path, self._normalize_graphql_path(properties_match.group(1)))

        quarkus_match = re.search(r"^\s*quarkus\.smallrye-graphql\.root-path\s*=\s*(\S+)\s*$", content, re.MULTILINE)
        if quarkus_match:
            return self._join_paths(root_path, self._normalize_graphql_path(quarkus_match.group(1)))

        yaml_match = re.search(
            r"(?ms)^\s*spring\s*:\s*\n(?:^\s+.*\n)*?^\s+graphql\s*:\s*\n(?:^\s+.*\n)*?^\s+path\s*:\s*([^\n#]+)",
            content,
        )
        if yaml_match:
            return self._join_paths(root_path, self._normalize_graphql_path(yaml_match.group(1)))

        quarkus_yaml_match = re.search(
            r"(?ms)^\s*quarkus\s*:\s*\n(?:^\s+.*\n)*?^\s+smallrye-graphql\s*:\s*\n(?:^\s+.*\n)*?^\s+root-path\s*:\s*([^\n#]+)",
            content,
        )
        if quarkus_yaml_match:
            return self._join_paths(root_path, self._normalize_graphql_path(quarkus_yaml_match.group(1)))

        return ""

    def _extract_java_http_root_path_from_config(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                content = handle.read()
        except Exception:
            return ""
        return self._extract_java_http_root_path_from_content(content)

    def _extract_java_http_root_path_from_content(self, content: str) -> str:
        properties_patterns = (
            r"^\s*server\.servlet\.context-path\s*=\s*(\S+)\s*$",
            r"^\s*spring\.webflux\.base-path\s*=\s*(\S+)\s*$",
            r"^\s*quarkus\.http\.root-path\s*=\s*(\S+)\s*$",
        )
        for pattern in properties_patterns:
            match = re.search(pattern, content, re.MULTILINE)
            if match:
                return self._normalize_graphql_path(match.group(1))

        yaml_patterns = (
            r"(?ms)^\s*server\s*:\s*\n(?:^\s+.*\n)*?^\s+servlet\s*:\s*\n(?:^\s+.*\n)*?^\s+context-path\s*:\s*([^\n#]+)",
            r"(?ms)^\s*spring\s*:\s*\n(?:^\s+.*\n)*?^\s+webflux\s*:\s*\n(?:^\s+.*\n)*?^\s+base-path\s*:\s*([^\n#]+)",
            r"(?ms)^\s*quarkus\s*:\s*\n(?:^\s+.*\n)*?^\s+http\s*:\s*\n(?:^\s+.*\n)*?^\s+root-path\s*:\s*([^\n#]+)",
        )
        for pattern in yaml_patterns:
            match = re.search(pattern, content)
            if match:
                return self._normalize_graphql_path(match.group(1))

        return ""

    def _normalize_graphql_path(self, value: str) -> str:
        cleaned = value.strip().strip("\"'")
        if not cleaned:
            return ""
        return cleaned if cleaned.startswith("/") else f"/{cleaned}"

    def _extract_graphql_path_from_python(self, file_path: str) -> str:
        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                code = handle.read()
            tree = ast.parse(code, filename=file_path)
        except Exception:
            return ""

        visitor = _PythonGraphQLPathVisitor()
        visitor.visit(tree)
        return visitor.graphql_http_path or ""

    def _discover_python_file(
        self,
        file_path: str,
        root_path: str,
        *,
        graphql_http_path: str,
    ) -> Tuple[Set[str], Set[str], Set[str], List[DiscoveredEndpoint]]:
        frameworks: Set[str] = set()
        db_markers: Set[str] = set()
        api_styles: Set[str] = set()
        endpoints: List[DiscoveredEndpoint] = []

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                code = handle.read()
            tree = ast.parse(code, filename=file_path)
        except Exception:
            return frameworks, db_markers, api_styles, endpoints

        visitor = _PythonDiscoveryVisitor(
            file_path=os.path.relpath(file_path, root_path),
            code=code,
            graphql_http_path=graphql_http_path,
            project_root=root_path,
        )
        visitor.visit(tree)
        visitor.finalize_rest_discovery()

        for marker in visitor.import_markers:
            lowered = marker.lower()
            for key, name in PYTHON_FRAMEWORK_HINTS.items():
                if key in lowered:
                    frameworks.add(name)
            if any(token in lowered for token in SQL_MARKERS):
                db_markers.add("sql")
            if any(token in lowered for token in NOSQL_MARKERS):
                db_markers.add("nosql")

        if visitor.rest_endpoints:
            api_styles.add("REST")
            endpoints.extend(visitor.rest_endpoints)
        if visitor.graphql_endpoints:
            api_styles.add("GraphQL")
            endpoints.extend(visitor.graphql_endpoints)

        if "django" in code.lower() and "urlpatterns" in code:
            frameworks.add("Django")
            api_styles.add("REST")

        return frameworks, db_markers, api_styles, endpoints

    def _discover_java_file(
        self,
        file_path: str,
        root_path: str,
        *,
        graphql_http_path: str,
        java_http_root_path: str,
    ) -> Tuple[Set[str], Set[str], Set[str], List[DiscoveredEndpoint]]:
        frameworks: Set[str] = set()
        db_markers: Set[str] = set()
        api_styles: Set[str] = set()
        endpoints: List[DiscoveredEndpoint] = []

        try:
            with open(file_path, "r", encoding="utf-8") as handle:
                code = handle.read()
        except Exception:
            return frameworks, db_markers, api_styles, endpoints

        lowered = code.lower()
        for key, name in JAVA_FRAMEWORK_HINTS.items():
            if key in code:
                frameworks.add(name)

        if any(token in lowered for token in SQL_MARKERS):
            db_markers.add("sql")
        if any(token in lowered for token in NOSQL_MARKERS):
            db_markers.add("nosql")

        relative_path = os.path.relpath(file_path, root_path)
        spring_prefix = self._extract_java_request_prefix(code)
        jaxrs_prefix = self._extract_java_jaxrs_class_prefix(code)
        java_type_examples = self._extract_java_type_examples(code)
        java_type_fields = self._extract_java_type_fields(code)

        for method, method_path, name, line, return_type, parameters in self._extract_java_rest_mappings(code):
            api_styles.add("REST")
            full_path = self._join_paths(java_http_root_path, self._join_paths(spring_prefix, method_path))
            endpoints.append(
                DiscoveredEndpoint(
                    name=name,
                    kind="rest",
                    method=method,
                    path=full_path,
                    source_file=relative_path,
                    line=line,
                    example_json_body=self._example_java_request_body(method, parameters, java_type_examples),
                    example_response_body=self._example_from_java_type(return_type, java_type_examples),
                )
            )

        for method, method_path, name, line, return_type, parameters in self._extract_java_jaxrs_mappings(code):
            api_styles.add("REST")
            full_path = self._join_paths(java_http_root_path, self._join_paths(jaxrs_prefix, method_path))
            endpoints.append(
                DiscoveredEndpoint(
                    name=name,
                    kind="rest",
                    method=method,
                    path=full_path,
                    source_file=relative_path,
                    line=line,
                    example_json_body=self._example_java_request_body(method, parameters, java_type_examples),
                    example_response_body=self._example_from_java_type(return_type, java_type_examples),
                )
            )

        for operation, name, line, return_type, parameters in self._extract_java_graphql_operations(code):
            api_styles.add("GraphQL")
            endpoints.append(
                DiscoveredEndpoint(
                    name=name,
                    kind="graphql",
                    method="POST",
                    path=graphql_http_path,
                    source_file=relative_path,
                    line=line,
                    graphql_query=self._build_graphql_query(name, operation, return_type, java_type_examples, java_type_fields, parameters),
                    graphql_variables=self._java_graphql_variables(parameters, java_type_examples),
                )
            )

        for operation, name, line, return_type, parameters in self._extract_java_quarkus_graphql_operations(code):
            api_styles.add("GraphQL")
            endpoints.append(
                DiscoveredEndpoint(
                    name=name,
                    kind="graphql",
                    method="POST",
                    path=graphql_http_path,
                    source_file=relative_path,
                    line=line,
                    graphql_query=self._build_graphql_query(name, operation, return_type, java_type_examples, java_type_fields, parameters),
                    graphql_variables=self._java_graphql_variables(parameters, java_type_examples),
                )
            )

        return frameworks, db_markers, api_styles, endpoints

    def _extract_java_request_prefix(self, code: str) -> str:
        match = re.search(r"@RequestMapping\s*\(\s*(?:path\s*=\s*)?\"([^\"]+)\"", code)
        if match:
            return match.group(1)
        return ""

    def _extract_java_jaxrs_class_prefix(self, code: str) -> str:
        match = re.search(
            r"@Path\s*\(\s*\"([^\"]+)\"\s*\)\s*"
            r"(?:@[A-Za-z_][\w.]*(?:\([^)]*\))?\s*)*"
            r"(?:public|private|protected)?\s*class\s+\w+",
            code,
            re.MULTILINE,
        )
        if match:
            return match.group(1)
        return ""

    def _extract_java_rest_mappings(self, code: str) -> List[Tuple[str, str, str, int, str, List[JavaParameter]]]:
        pattern = re.compile(
            r"@(?P<annotation>GetMapping|PostMapping|PutMapping|PatchMapping|DeleteMapping|RequestMapping)"
            r"(?:\s*\((?P<args>[^)]*)\))?\s*"
            r"(?:public|private|protected)\s+(?P<return_type>[\w<>\[\], ?]+?)\s+(?P<name>\w+)\s*\((?P<parameters>.*?)\)\s*\{",
            re.MULTILINE | re.DOTALL,
        )
        mappings: List[Tuple[str, str, str, int, str, List[JavaParameter]]] = []
        for match in pattern.finditer(code):
            annotation = match.group("annotation")
            args = match.group("args") or ""
            name = match.group("name")
            return_type = match.group("return_type").strip()
            parameters = self._extract_java_parameters(match.group("parameters"))
            method = annotation.replace("Mapping", "").upper()
            if method == "REQUEST":
                method_match = re.search(r"RequestMethod\.(GET|POST|PUT|PATCH|DELETE)", args)
                method = method_match.group(1) if method_match else "GET"
            path_match = re.search(r"\"([^\"]+)\"", args)
            path = path_match.group(1) if path_match else ""
            line = code[:match.start()].count("\n") + 1
            mappings.append((method, path, name, line, return_type, parameters))
        return mappings

    def _extract_java_graphql_operations(self, code: str) -> List[Tuple[str, str, int, str, List[JavaParameter]]]:
        pattern = re.compile(
            r"@(?P<annotation>QueryMapping|MutationMapping)\s*(?:\((?P<args>[^)]*)\))?\s*"
            r"(?:public|private|protected)\s+(?P<return_type>[\w<>\[\], ?]+?)\s+(?P<name>\w+)\s*\((?P<parameters>.*?)\)\s*\{",
            re.MULTILINE | re.DOTALL,
        )
        operations: List[Tuple[str, str, int, str, List[JavaParameter]]] = []
        for match in pattern.finditer(code):
            annotation = match.group("annotation")
            args = match.group("args") or ""
            method_name = match.group("name")
            explicit_name = self._extract_java_graphql_name(args)
            name = explicit_name or method_name
            line = code[:match.start()].count("\n") + 1
            operation = "query" if annotation == "QueryMapping" else "mutation"
            operations.append(
                (
                    operation,
                    name,
                    line,
                    match.group("return_type").strip(),
                    self._extract_java_parameters(match.group("parameters")),
                )
            )
        return operations

    def _extract_java_quarkus_graphql_operations(self, code: str) -> List[Tuple[str, str, int, str, List[JavaParameter]]]:
        operations: List[Tuple[str, str, int, str, List[JavaParameter]]] = []
        for class_match in re.finditer(
            r"(?P<prefix>(?:@[A-Za-z_][\w.]*(?:\([^)]*\))?\s*)*)(?:public|private|protected)?\s*class\s+(?P<name>\w+)[^{]*\{",
            code,
            re.MULTILINE,
        ):
            prefix = class_match.group("prefix") or ""
            if "@GraphQLApi" not in prefix and ".GraphQLApi" not in prefix:
                continue

            body_start = class_match.end()
            depth = 1
            index = body_start
            while index < len(code) and depth > 0:
                if code[index] == "{":
                    depth += 1
                elif code[index] == "}":
                    depth -= 1
                index += 1
            if depth != 0:
                continue

            class_body = code[body_start:index - 1]
            class_offset = body_start
            method_pattern = re.compile(
                r"(?P<annotations>(?:@[A-Za-z_][\w.]*(?:\([^)]*\))?\s*)+)"
                r"(?:public|private|protected)\s+(?P<return_type>[\w<>\[\], ?]+?)\s+(?P<name>\w+)\s*\((?P<parameters>.*?)\)\s*\{",
                re.MULTILINE | re.DOTALL,
            )
            for match in method_pattern.finditer(class_body):
                annotations = match.group("annotations")
                operation = ""
                if re.search(r"@(?:[\w.]+\.)?Mutation\b", annotations):
                    operation = "mutation"
                elif re.search(r"@(?:[\w.]+\.)?Query\b", annotations):
                    operation = "query"
                if not operation:
                    continue

                explicit_name = self._extract_java_graphql_name_from_annotations(annotations)
                method_name = match.group("name")
                name = explicit_name or method_name
                absolute_start = class_offset + match.start()
                line = code[:absolute_start].count("\n") + 1
                operations.append(
                    (
                        operation,
                        name,
                        line,
                        match.group("return_type").strip(),
                        self._extract_java_parameters(match.group("parameters")),
                    )
                )
        return operations

    def _extract_java_graphql_name(self, args: str) -> str:
        if not args:
            return ""

        named_match = re.search(r"\b(?:name|value)\s*=\s*\"([^\"]+)\"", args)
        if named_match:
            return named_match.group(1)

        positional_match = re.search(r"^\s*\"([^\"]+)\"\s*$", args)
        if positional_match:
            return positional_match.group(1)

        return ""

    def _extract_java_graphql_name_from_annotations(self, annotations: str) -> str:
        name_match = re.search(r"@(?:[\w.]+\.)?(?:Name|Query|Mutation)\s*\((?P<args>[^)]*)\)", annotations)
        if not name_match:
            return ""
        return self._extract_java_graphql_name(name_match.group("args"))

    def _extract_java_jaxrs_mappings(self, code: str) -> List[Tuple[str, str, str, int, str, List[JavaParameter]]]:
        pattern = re.compile(
            r"(?P<annotations>(?:@[A-Za-z_][\w.]*(?:\([^)]*\))?\s*)+)"
            r"(?:public|private|protected)\s+(?P<return_type>[\w<>\[\], ?]+?)\s+(?P<name>\w+)\s*\((?P<parameters>.*?)\)\s*\{",
            re.MULTILINE | re.DOTALL,
        )
        mappings: List[Tuple[str, str, str, int, str, List[JavaParameter]]] = []
        for match in pattern.finditer(code):
            annotations = match.group("annotations")
            method = ""
            for http_method in HTTP_METHODS:
                if re.search(rf"@{http_method}\b", annotations):
                    method = http_method
                    break
            if not method:
                continue

            path_match = re.search(r"@Path\s*\(\s*\"([^\"]+)\"\s*\)", annotations)
            path = path_match.group(1) if path_match else ""
            line = code[:match.start()].count("\n") + 1
            mappings.append(
                (
                    method,
                    path,
                    match.group("name"),
                    line,
                    match.group("return_type").strip(),
                    self._extract_java_parameters(match.group("parameters")),
                )
            )
        return mappings

    def _classify_database_type(self, markers: Set[str]) -> str:
        if "sql" in markers and "nosql" in markers:
            return "SQL + NoSQL"
        if "sql" in markers:
            return "SQL"
        if "nosql" in markers:
            return "NoSQL"
        return "Unknown"

    def _classify_api_style(self, styles: Set[str]) -> str:
        if not styles:
            return "Unknown"
        ordered = [style for style in ("REST", "GraphQL") if style in styles]
        return " + ".join(ordered)

    def _dedupe_endpoints(self, endpoints: List[DiscoveredEndpoint]) -> List[DiscoveredEndpoint]:
        seen: Set[Tuple[str, str, str, str]] = set()
        unique: List[DiscoveredEndpoint] = []
        for endpoint in endpoints:
            key = (endpoint.kind, endpoint.method, endpoint.path, endpoint.name)
            if key in seen:
                continue
            seen.add(key)
            unique.append(endpoint)
        unique.sort(key=lambda item: (item.kind, item.path, item.method, item.name))
        return unique

    def _join_paths(self, prefix: str, path: str) -> str:
        combined = "/".join(part.strip("/") for part in (prefix, path) if part)
        return f"/{combined}" if combined else "/"

    def _build_graphql_query(
        self,
        name: str,
        operation: str,
        return_type: str = "",
        java_type_examples: Optional[Dict[str, Dict[str, Any]]] = None,
        java_type_fields: Optional[Dict[str, Dict[str, str]]] = None,
        parameters: Optional[List[JavaParameter]] = None,
    ) -> str:
        graphql_parameters = parameters or []
        variable_signature = self._build_java_graphql_variable_signature(graphql_parameters)
        field_arguments = self._build_java_graphql_arguments(graphql_parameters)
        field_selection = self._build_java_graphql_selection(return_type, java_type_fields or {})
        field_line = f"{name}{field_arguments}{field_selection}"
        if operation == "mutation":
            return f"mutation {name}Operation{variable_signature} {{\n  {field_line}\n}}"
        return f"query {name}Query{variable_signature} {{\n  {field_line}\n}}"

    def _extract_java_type_examples(self, code: str) -> Dict[str, Dict[str, Any]]:
        examples: Dict[str, Dict[str, Any]] = {}
        for class_name, body in self._extract_java_class_bodies(code).items():
            fields: Dict[str, Any] = {}
            for field_type, field_name in re.findall(
                r"(?:private|protected|public)\s+([\w<>\[\], ?]+?)\s+(\w+)\s*(?:=[^;]+)?;",
                body,
            ):
                field_name_lower = field_name.lower()
                if field_name_lower == "serialversionuid":
                    continue
                fields[field_name] = self._example_from_java_type(field_type.strip(), examples)
            if fields:
                examples[class_name] = fields
        return examples

    def _extract_java_type_fields(self, code: str) -> Dict[str, Dict[str, str]]:
        field_types: Dict[str, Dict[str, str]] = {}
        for class_name, body in self._extract_java_class_bodies(code).items():
            fields: Dict[str, str] = {}
            for field_type, field_name in re.findall(
                r"(?:private|protected|public)\s+([\w<>\[\], ?]+?)\s+(\w+)\s*(?:=[^;]+)?;",
                body,
            ):
                if field_name.lower() == "serialversionuid":
                    continue
                fields[field_name] = field_type.strip()
            if fields:
                field_types[class_name] = fields
        return field_types

    def _extract_java_class_bodies(self, code: str) -> Dict[str, str]:
        classes: Dict[str, str] = {}
        for match in re.finditer(r"\bclass\s+(?P<name>\w+)[^{]*\{", code):
            class_name = match.group("name")
            body_start = match.end()
            depth = 1
            index = body_start
            while index < len(code) and depth > 0:
                if code[index] == "{":
                    depth += 1
                elif code[index] == "}":
                    depth -= 1
                index += 1
            if depth == 0:
                classes[class_name] = code[body_start:index - 1]
        return classes

    def _extract_java_parameters(self, parameters_text: str) -> List[JavaParameter]:
        parameters: List[JavaParameter] = []
        for segment in self._split_java_parameters(parameters_text):
            annotations = re.findall(r"@[\w.]+(?:\([^)]*\))?", segment)
            cleaned = re.sub(r"@[\w.]+(?:\([^)]*\))?\s*", "", segment).strip()
            cleaned = cleaned.replace("final ", "").strip()
            if not cleaned:
                continue
            match = re.match(r"(?P<type>[\w<>\[\], ?.]+?)\s+(?P<name>\w+)$", cleaned)
            if match:
                parameters.append(
                    JavaParameter(
                        type_name=match.group("type").strip(),
                        name=match.group("name").strip(),
                        annotations=annotations,
                    )
                )
        return parameters

    def _split_java_parameters(self, parameters_text: str) -> List[str]:
        parts: List[str] = []
        current: List[str] = []
        angle_depth = 0
        paren_depth = 0
        for char in parameters_text:
            if char == "<":
                angle_depth += 1
            elif char == ">":
                angle_depth = max(0, angle_depth - 1)
            elif char == "(":
                paren_depth += 1
            elif char == ")":
                paren_depth = max(0, paren_depth - 1)
            elif char == "," and angle_depth == 0 and paren_depth == 0:
                part = "".join(current).strip()
                if part:
                    parts.append(part)
                current = []
                continue
            current.append(char)
        remainder = "".join(current).strip()
        if remainder:
            parts.append(remainder)
        return parts

    def _example_java_request_body(
        self,
        method: str,
        parameters: List[JavaParameter],
        java_type_examples: Dict[str, Dict[str, Any]],
    ) -> Optional[Dict[str, Any]]:
        if method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None
        body: Dict[str, Any] = {}
        body_param = self._select_java_request_body_parameter(parameters)
        if body_param is not None:
            example = self._example_from_java_type(body_param.type_name, java_type_examples)
            return example if isinstance(example, dict) else {body_param.name: example}

        for parameter in parameters:
            example = self._example_from_java_type(parameter.type_name, java_type_examples)
            if parameter.name in {"request", "response"}:
                continue
            if isinstance(example, dict) and example:
                return example
            body[parameter.name] = example
        return body or {}

    def _example_from_java_type(
        self,
        type_name: str,
        java_type_examples: Dict[str, Dict[str, Any]],
    ) -> Any:
        normalized = self._normalize_java_type_name(type_name)
        if not normalized or normalized in {"void", "Void", "ResponseEntity"}:
            return None
        if normalized in JAVA_SIMPLE_TYPE_EXAMPLES:
            return JAVA_SIMPLE_TYPE_EXAMPLES[normalized]
        if normalized in java_type_examples:
            return java_type_examples[normalized]
        return ""

    def _normalize_java_type_name(self, type_name: str) -> str:
        cleaned = type_name.strip()
        if not cleaned:
            return ""
        cleaned = cleaned.replace("?", "")
        cleaned = re.sub(r"@[\w.]+(?:\([^)]*\))?\s*", "", cleaned)
        base_name = cleaned.split(".")[-1]
        generic_match = re.match(r"(?P<container>\w+)\s*<(?P<inner>.+)>", base_name)
        if generic_match:
            container = generic_match.group("container")
            inner = generic_match.group("inner").strip()
            if container in {"ResponseEntity", "Optional", "Mono", "Uni", "CompletableFuture"}:
                return self._normalize_java_type_name(inner)
            if container in {"List", "Set", "Collection", "Iterable"}:
                return container
            return container
        return base_name

    def _build_java_graphql_variable_signature(self, parameters: List[JavaParameter]) -> str:
        graphql_parameters = self._java_graphql_argument_parameters(parameters)
        if not graphql_parameters:
            return ""
        declarations = [
            f"${parameter.name}: {self._java_type_to_graphql_type(parameter.type_name)}"
            for parameter in graphql_parameters
        ]
        return "(" + ", ".join(declarations) + ")"

    def _build_java_graphql_arguments(self, parameters: List[JavaParameter]) -> str:
        graphql_parameters = self._java_graphql_argument_parameters(parameters)
        if not graphql_parameters:
            return ""
        argument_pairs = [f"{parameter.name}: ${parameter.name}" for parameter in graphql_parameters]
        return "(" + ", ".join(argument_pairs) + ")"

    def _java_graphql_variables(
        self,
        parameters: List[JavaParameter],
        java_type_examples: Dict[str, Dict[str, Any]],
    ) -> Dict[str, Any]:
        variables: Dict[str, Any] = {}
        for parameter in self._java_graphql_argument_parameters(parameters):
            example = self._example_from_java_type(parameter.type_name, java_type_examples)
            if example is not None:
                variables[parameter.name] = example
        return variables

    def _java_graphql_argument_parameters(self, parameters: List[JavaParameter]) -> List[JavaParameter]:
        graphql_params = [
            parameter
            for parameter in parameters
            if any(self._java_annotation_name(annotation) == "Argument" for annotation in parameter.annotations)
        ]
        return graphql_params or [parameter for parameter in parameters if parameter.name not in {"env", "context", "request", "response"}]

    def _build_java_graphql_selection(
        self,
        return_type: str,
        java_type_fields: Dict[str, Dict[str, str]],
        depth: int = 0,
    ) -> str:
        normalized = self._normalize_java_type_name(return_type)
        if normalized in JAVA_SIMPLE_TYPE_EXAMPLES or normalized in {"", "void", "Void"}:
            return ""
        return _graphql_placeholder_selection()

    def _java_type_to_graphql_type(self, type_name: str) -> str:
        normalized = self._normalize_java_type_name(type_name)
        mapping = {
            "String": "String!",
            "Integer": "Int!",
            "int": "Int!",
            "Long": "ID!",
            "long": "ID!",
            "Short": "Int!",
            "short": "Int!",
            "Double": "Float!",
            "double": "Float!",
            "Float": "Float!",
            "float": "Float!",
            "BigDecimal": "Float!",
            "Boolean": "Boolean!",
            "boolean": "Boolean!",
        }
        return mapping.get(normalized, f"{normalized}!")

    def _select_java_request_body_parameter(self, parameters: List[JavaParameter]) -> Optional[JavaParameter]:
        for parameter in parameters:
            if any(self._java_annotation_name(annotation) == "RequestBody" for annotation in parameter.annotations):
                return parameter
        for parameter in parameters:
            if any(
                self._java_annotation_name(annotation) in {"PathVariable", "RequestParam", "PathParam", "QueryParam", "HeaderParam", "Context"}
                for annotation in parameter.annotations
            ):
                continue
            normalized = self._normalize_java_type_name(parameter.type_name)
            if normalized in {"HttpServletRequest", "HttpServletResponse", "ServerRequest", "ServerResponse"}:
                continue
            if normalized not in JAVA_SIMPLE_TYPE_EXAMPLES:
                return parameter
        return None

    def _java_annotation_name(self, annotation: str) -> str:
        cleaned = annotation.strip()
        if cleaned.startswith("@"):
            cleaned = cleaned[1:]
        cleaned = cleaned.split("(", 1)[0]
        return cleaned.split(".")[-1]


class _PythonDiscoveryVisitor(ast.NodeVisitor):
    """AST visitor for Python route and payload discovery."""

    def __init__(self, *, file_path: str, code: str, graphql_http_path: str, project_root: str):
        self.file_path = file_path
        self.code = code
        self.graphql_http_path = graphql_http_path
        self.project_root = project_root
        self.import_markers: Set[str] = set()
        self.rest_endpoints: List[DiscoveredEndpoint] = []
        self.graphql_endpoints: List[DiscoveredEndpoint] = []
        self.model_examples: Dict[str, Dict[str, Any]] = {}
        self.class_stack: List[str] = []
        self.graphql_classes: Set[str] = set()
        self.function_defs: Dict[str, ast.AST] = {}
        self.class_defs: Dict[str, ast.ClassDef] = {}
        self.class_method_lines: Dict[str, Dict[str, int]] = {}
        self.class_bases: Dict[str, Set[str]] = {}
        self.class_serializer_names: Dict[str, str] = {}
        self.django_urlpatterns: List[ast.Call] = []
        self.router_targets: Set[str] = set()
        self.drf_registrations: List[Tuple[str, str, int]] = []
        self.imported_symbols: Dict[str, str] = {}
        self.graphql_type_fields: Dict[str, List[str]] = {}
        self._project_symbol_cache: Dict[str, Optional[ast.AST]] = {}

    def visit_Import(self, node: ast.Import) -> Any:
        for alias in node.names:
            self.import_markers.add(alias.name)
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        module = node.module or ""
        self.import_markers.add(module)
        for alias in node.names:
            self.import_markers.add(f"{module}.{alias.name}")
            self.imported_symbols[alias.asname or alias.name] = module
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> Any:
        model_name = node.name
        base_names = {self._name_from_expr(base) for base in node.bases}
        self.class_defs[node.name] = node
        self.class_bases[node.name] = base_names
        self.class_method_lines[node.name] = {
            statement.name.lower(): statement.lineno
            for statement in node.body
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if {"BaseModel", "SQLModel"} & base_names:
            example: Dict[str, Any] = {}
            for statement in node.body:
                if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                    example[statement.target.id] = self._example_from_annotation(statement.annotation)
            self.model_examples[model_name] = example

        if any(base.endswith("Serializer") for base in base_names):
            example = self._serializer_example_from_class(node)
            if example:
                self.model_examples[model_name] = example

        serializer_name = self._serializer_class_for_view(node)
        if serializer_name:
            self.class_serializer_names[node.name] = serializer_name

        # Check for GraphQL type decorators (handles both @strawberry.type and @type when imported)
        is_graphql_type = any(
            self._decorator_name(decorator) in {"strawberry.type", "type"}
            for decorator in node.decorator_list
        )
        if is_graphql_type:
            self.graphql_classes.add(node.name)
            self.graphql_type_fields[node.name] = self._extract_graphql_type_fields(node)

        self.class_stack.append(node.name)
        self.generic_visit(node)
        self.class_stack.pop()

    def visit_FunctionDef(self, node: ast.FunctionDef) -> Any:
        if not self.class_stack:
            self.function_defs[node.name] = node
        for endpoint in self._extract_rest_endpoints(node):
            self.rest_endpoints.append(endpoint)

        graphql_endpoint = self._extract_graphql_endpoint(node)
        if graphql_endpoint is not None:
            self.graphql_endpoints.append(graphql_endpoint)

        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> Any:
        if not self.class_stack:
            self.function_defs[node.name] = node
        for endpoint in self._extract_rest_endpoints(node):
            self.rest_endpoints.append(endpoint)

        graphql_endpoint = self._extract_graphql_endpoint(node)
        if graphql_endpoint is not None:
            self.graphql_endpoints.append(graphql_endpoint)

        self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign) -> Any:
        for target in node.targets:
            if isinstance(target, ast.Name) and target.id == "urlpatterns" and isinstance(node.value, (ast.List, ast.Tuple)):
                for element in node.value.elts:
                    if isinstance(element, ast.Call):
                        self.django_urlpatterns.append(element)

            if isinstance(target, ast.Name) and isinstance(node.value, ast.Call):
                call_name = self._decorator_name(node.value)
                if call_name.endswith(("DefaultRouter", "SimpleRouter")):
                    self.router_targets.add(target.id)

        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> Any:
        if isinstance(node.value, ast.Call):
            self._capture_drf_router_registration(node.value)
        self.generic_visit(node)

    def finalize_rest_discovery(self) -> None:
        for endpoint in self._extract_django_urlpatterns():
            self.rest_endpoints.append(endpoint)
        for endpoint in self._extract_drf_router_endpoints():
            self.rest_endpoints.append(endpoint)

    def _extract_rest_endpoints(self, node: ast.FunctionDef) -> List[DiscoveredEndpoint]:
        endpoints: List[DiscoveredEndpoint] = []
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call) or not isinstance(decorator.func, ast.Attribute):
                continue

            method = decorator.func.attr.upper()
            path = self._string_arg(decorator)
            if method.lower() == "route":
                methods = self._flask_route_methods(decorator)
                for route_method in methods:
                    endpoints.append(
                        DiscoveredEndpoint(
                            name=node.name,
                            kind="rest",
                            method=route_method,
                            path=path or "/",
                            source_file=self.file_path,
                            line=node.lineno,
                            example_json_body=self._example_body_for_function(node, route_method),
                            example_response_body=self._example_response_for_function(node),
                        )
                    )
                continue

            if method not in HTTP_METHODS:
                continue

            endpoints.append(
                DiscoveredEndpoint(
                    name=node.name,
                    kind="rest",
                    method=method,
                    path=path or "/",
                    source_file=self.file_path,
                    line=node.lineno,
                    example_json_body=self._example_body_for_function(node, method),
                    example_response_body=self._example_response_for_function(node),
                )
            )
        return endpoints

    def _extract_graphql_endpoint(self, node: ast.FunctionDef) -> Optional[DiscoveredEndpoint]:
        decorators = {self._decorator_name(decorator) for decorator in node.decorator_list}
        # Handle both strawberry.field and just field when imported
        has_field_decorator = decorators & {"strawberry.field", "field"}
        has_mutation_decorator = decorators & {"strawberry.mutation", "mutation"}
        
        if has_field_decorator or has_mutation_decorator:
            operation = "mutation" if has_mutation_decorator else "query"
        elif self.class_stack and self.class_stack[-1] in self.graphql_classes:
            operation = "mutation" if self.class_stack[-1].lower() == "mutation" else "query"
        else:
            return None

        return DiscoveredEndpoint(
            name=node.name,
            kind="graphql",
            method="POST",
            path=self.graphql_http_path,
            source_file=self.file_path,
            line=node.lineno,
            graphql_query=self._build_graphql_example(node, operation),
            graphql_variables=self._graphql_variables_for_function(node),
        )

    def _build_graphql_example(self, node: ast.FunctionDef, operation: str) -> str:
        selection = self._graphql_selection_for_annotation(node.returns)
        variable_signature = self._graphql_variable_signature(node)
        field_arguments = self._graphql_field_arguments(node)
        field_line = f"{node.name}{field_arguments}{selection}"
        if operation == "mutation":
            return f"mutation {node.name}Operation{variable_signature} {{\n  {field_line}\n}}"
        return f"query {node.name}Query{variable_signature} {{\n  {field_line}\n}}"

    def _graphql_variables_for_function(self, node: ast.FunctionDef) -> Dict[str, Any]:
        variables: Dict[str, Any] = {}
        for arg in node.args.args:
            if arg.arg in {"self", "cls", "root", "info"}:
                continue
            variables[arg.arg] = self._example_from_annotation(arg.annotation)
        return variables

    def _graphql_variable_signature(self, node: ast.FunctionDef) -> str:
        declarations: List[str] = []
        for arg in node.args.args:
            if arg.arg in {"self", "cls", "root", "info"}:
                continue
            graphql_type = self._graphql_variable_type(arg.annotation)
            if graphql_type:
                declarations.append(f"${arg.arg}: {graphql_type}")
        if not declarations:
            return ""
        return "(" + ", ".join(declarations) + ")"

    def _graphql_field_arguments(self, node: ast.FunctionDef) -> str:
        arguments = [f"{arg.arg}: ${arg.arg}" for arg in node.args.args if arg.arg not in {"self", "cls", "root", "info"}]
        if not arguments:
            return ""
        return "(" + ", ".join(arguments) + ")"

    def _example_response_for_function(self, node: ast.FunctionDef) -> Optional[Dict[str, Any]]:
        """Generate an example response body based on the function's return type."""
        if node.returns is None:
            return None
        
        return_type = self._graphql_type_name(node.returns)
        if not return_type:
            return None
        
        # Check if it's a model we have examples for
        if return_type in self.model_examples:
            return self.model_examples[return_type]
        
        # Try to extract fields from the class definition
        class_node = self._resolve_class_node(return_type)
        if class_node is not None:
            response = self._example_response_from_class_node(class_node)
            return response if response else None
        
        return None

    def _example_body_for_function(self, node: ast.FunctionDef, method: str) -> Optional[Dict[str, Any]]:
        if method not in {"POST", "PUT", "PATCH", "DELETE"}:
            return None

        body: Dict[str, Any] = {}
        for arg in node.args.args:
            if arg.arg in {"request", "response", "self", "cls"}:
                continue
            annotation_name = self._name_from_expr(arg.annotation)
            if annotation_name in self.model_examples:
                return self.model_examples[annotation_name]
            body[arg.arg] = self._example_from_annotation(arg.annotation)

        return body or {}

    def _example_from_annotation(self, annotation: Optional[ast.AST]) -> Any:
        name = self._name_from_expr(annotation)
        lowered = name.lower()
        if lowered in {"str", "optionalstr"}:
            return "example"
        if lowered in {"id", "optionalid"}:
            return "example-id"
        if name.split(".")[-1] == "ID":
            return "example-id"
        if lowered in {"int", "optionalint"}:
            return 0
        if lowered in {"float", "optionalfloat"}:
            return 0.0
        if lowered in {"bool", "optionalbool"}:
            return False
        if lowered in {"dict", "dictstrany", "optionaldict"}:
            return {}
        if lowered in {"list", "liststr", "listint", "optionallist"}:
            return []
        if name in self.model_examples:
            return self.model_examples[name]
        return ""

    def _flask_route_methods(self, decorator: ast.Call) -> List[str]:
        for keyword in decorator.keywords:
            if keyword.arg == "methods" and isinstance(keyword.value, (ast.List, ast.Tuple, ast.Set)):
                methods = []
                for element in keyword.value.elts:
                    if isinstance(element, ast.Constant) and isinstance(element.value, str):
                        methods.append(element.value.upper())
                return methods or ["GET"]
        return ["GET"]

    def _string_arg(self, call: ast.Call) -> str:
        if call.args and isinstance(call.args[0], ast.Constant) and isinstance(call.args[0].value, str):
            return call.args[0].value
        for keyword in call.keywords:
            if keyword.arg in {"path", "rule"} and isinstance(keyword.value, ast.Constant) and isinstance(keyword.value.value, str):
                return keyword.value.value
        return ""

    def _capture_drf_router_registration(self, call: ast.Call) -> None:
        if not isinstance(call.func, ast.Attribute):
            return
        if call.func.attr != "register":
            return
        if not isinstance(call.func.value, ast.Name) or call.func.value.id not in self.router_targets:
            return
        if len(call.args) < 2:
            return
        prefix = self._literal_string(call.args[0])
        viewset_name = self._name_from_expr(call.args[1]).split(".")[-1]
        if prefix and viewset_name:
            self.drf_registrations.append((prefix, viewset_name, call.lineno))

    def _extract_django_urlpatterns(self) -> List[DiscoveredEndpoint]:
        endpoints: List[DiscoveredEndpoint] = []
        for call in self.django_urlpatterns:
            route_type = self._decorator_name(call.func)
            if route_type not in {"path", "re_path"} or len(call.args) < 2:
                continue
            route = self._normalize_django_path(self._literal_string(call.args[0]))
            if not route:
                continue
            view_expr = call.args[1]
            view_name, methods, example_body, line = self._django_view_details(view_expr, call.lineno)
            for method in methods:
                endpoints.append(
                    DiscoveredEndpoint(
                        name=view_name,
                        kind="rest",
                        method=method,
                        path=route,
                        source_file=self.file_path,
                        line=line,
                        example_json_body=example_body if method in {"POST", "PUT", "PATCH", "DELETE"} else None,
                    )
                )
        return endpoints

    def _extract_drf_router_endpoints(self) -> List[DiscoveredEndpoint]:
        endpoints: List[DiscoveredEndpoint] = []
        for prefix, viewset_name, line in self.drf_registrations:
            collection_path = self._normalize_django_path(prefix)
            detail_path = self._join_paths(collection_path, "{id}")
            example_body = self._serializer_example_for_class(viewset_name)
            for method, path, action in self._drf_routes_for_viewset(viewset_name, collection_path, detail_path):
                endpoints.append(
                    DiscoveredEndpoint(
                        name=f"{viewset_name}.{action}",
                        kind="rest",
                        method=method,
                        path=path,
                        source_file=self.file_path,
                        line=line,
                        example_json_body=example_body if method in {"POST", "PUT", "PATCH", "DELETE"} else None,
                    )
                )
        return endpoints

    def _django_view_details(self, view_expr: ast.AST, fallback_line: int) -> Tuple[str, List[str], Optional[Dict[str, Any]], int]:
        if isinstance(view_expr, ast.Call) and isinstance(view_expr.func, ast.Attribute) and view_expr.func.attr == "as_view":
            class_name = self._name_from_expr(view_expr.func.value).split(".")[-1]
            methods, example_body, line = self._resolved_django_class_details(class_name, fallback_line)
            return class_name, methods, example_body, line

        function_name = self._name_from_expr(view_expr).split(".")[-1] or "view"
        methods, line = self._resolved_django_function_details(function_name, fallback_line)
        return function_name, methods, None, line

    def _methods_for_django_function(self, node: ast.AST) -> List[str]:
        decorators = getattr(node, "decorator_list", [])
        for decorator in decorators:
            if not isinstance(decorator, ast.Call):
                continue
            if self._decorator_name(decorator) != "api_view":
                continue
            if not decorator.args:
                break
            methods = self._literal_string_list(decorator.args[0])
            if methods:
                return methods
        return ["GET"]

    def _methods_for_django_class_view(self, class_name: str) -> List[str]:
        method_lines = self.class_method_lines.get(class_name, {})
        methods = [name.upper() for name in ("get", "post", "put", "patch", "delete") if name in method_lines]
        if methods:
            return methods
        bases = self.class_bases.get(class_name, set())
        if any(base.endswith("ReadOnlyModelViewSet") for base in bases):
            return ["GET"]
        if any(base.endswith(("ModelViewSet", "ViewSet", "GenericViewSet")) for base in bases):
            return ["GET", "POST", "PUT", "PATCH", "DELETE"]
        return ["GET"]

    def _drf_routes_for_viewset(self, class_name: str, collection_path: str, detail_path: str) -> List[Tuple[str, str, str]]:
        bases = self.class_bases.get(class_name, set())
        method_lines = self.class_method_lines.get(class_name, {})
        routes: List[Tuple[str, str, str]] = []
        if any(base.endswith("ReadOnlyModelViewSet") for base in bases):
            return [("GET", collection_path, "list"), ("GET", detail_path, "retrieve")]
        if any(base.endswith("ModelViewSet") for base in bases):
            return [
                ("GET", collection_path, "list"),
                ("POST", collection_path, "create"),
                ("GET", detail_path, "retrieve"),
                ("PUT", detail_path, "update"),
                ("PATCH", detail_path, "partial_update"),
                ("DELETE", detail_path, "destroy"),
            ]

        mapping = {
            "list": ("GET", collection_path),
            "create": ("POST", collection_path),
            "retrieve": ("GET", detail_path),
            "update": ("PUT", detail_path),
            "partial_update": ("PATCH", detail_path),
            "destroy": ("DELETE", detail_path),
        }
        for action, (method, path) in mapping.items():
            if action in method_lines:
                routes.append((method, path, action))
        return routes or [("GET", collection_path, "list")]

    def _serializer_example_for_class(self, class_name: str) -> Optional[Dict[str, Any]]:
        serializer_name = self.class_serializer_names.get(class_name)
        if serializer_name and serializer_name in self.model_examples:
            return self.model_examples[serializer_name]
        return {} if class_name in self.class_defs else None

    def _resolved_django_function_details(self, function_name: str, fallback_line: int) -> Tuple[List[str], int]:
        function_node = self.function_defs.get(function_name)
        if function_node is not None:
            return self._methods_for_django_function(function_node), function_node.lineno

        imported_node = self._load_imported_symbol(function_name)
        if isinstance(imported_node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return self._methods_for_django_function(imported_node), imported_node.lineno

        return ["GET"], fallback_line

    def _resolved_django_class_details(self, class_name: str, fallback_line: int) -> Tuple[List[str], Optional[Dict[str, Any]], int]:
        if class_name in self.class_defs:
            methods = self._methods_for_django_class_view(class_name)
            example_body = self._serializer_example_for_class(class_name)
            return methods, example_body, self.class_defs[class_name].lineno

        imported_node = self._load_imported_symbol(class_name)
        if isinstance(imported_node, ast.ClassDef):
            methods = self._methods_for_external_django_class(imported_node)
            example_body = self._serializer_example_for_external_class(imported_node)
            return methods, example_body, imported_node.lineno

        return ["GET"], None, fallback_line

    def _serializer_class_for_view(self, node: ast.ClassDef) -> str:
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id == "serializer_class":
                        return self._name_from_expr(statement.value).split(".")[-1]
        return ""

    def _serializer_example_from_class(self, node: ast.ClassDef) -> Dict[str, Any]:
        example: Dict[str, Any] = {}
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name):
                        field_example = self._serializer_field_example(statement.value)
                        if field_example is not None:
                            example[target.id] = field_example
            elif isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                field_example = self._serializer_field_example(statement.value)
                if field_example is not None:
                    example[statement.target.id] = field_example
        return example

    def _serializer_field_example(self, expr: Optional[ast.AST]) -> Any:
        if not isinstance(expr, ast.Call):
            return None
        field_name = self._name_from_expr(expr.func).lower()
        if field_name.endswith(("charfield", "emailfield", "slugfield", "uuidfield")):
            return "example"
        if field_name.endswith(("integerfield", "primarykeyrelatedfield")):
            return 0
        if field_name.endswith(("floatfield", "decimalfield")):
            return 0.0
        if field_name.endswith("booleanfield"):
            return False
        if field_name.endswith(("listfield", "multiplechoicefield")):
            return []
        if field_name.endswith(("dictfield", "jsonfield")):
            return {}
        return None

    def _extract_graphql_type_fields(self, node: ast.ClassDef) -> List[str]:
        fields: List[str] = []
        for statement in node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                fields.append(statement.target.id)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = {self._decorator_name(decorator) for decorator in statement.decorator_list}
                # Handle both strawberry.field and just field when imported
                if "strawberry.field" in decorators or "field" in decorators:
                    fields.append(statement.name)
        # preserve order and drop duplicates
        return list(dict.fromkeys(fields))

    def _graphql_selection_for_annotation(self, annotation: Optional[ast.AST], depth: int = 0) -> str:
        type_name = self._graphql_type_name(annotation)
        if not type_name:
            return ""
        if _is_graphql_scalar_type(type_name):
            return ""
        return _graphql_placeholder_selection()

    def _graphql_field_annotation(self, type_name: str, field_name: str) -> Optional[ast.AST]:
        class_node = self._resolve_class_node(type_name)
        if class_node is None:
            return None

        for statement in class_node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name) and statement.target.id == field_name:
                return statement.annotation
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name == field_name:
                return statement.returns
        return None

    def _graphql_type_name(self, annotation: Optional[ast.AST]) -> str:
        if annotation is None:
            return ""
        if isinstance(annotation, ast.Name):
            return annotation.id
        if isinstance(annotation, ast.Attribute):
            return annotation.attr
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            return annotation.value.split(".")[-1]
        if isinstance(annotation, ast.Subscript):
            container = self._name_from_expr(annotation.value).split(".")[-1]
            if container in {"Optional", "List", "Sequence", "Iterable", "tuple", "Tuple", "set", "Set", "Annotated"}:
                inner = self._subscript_elements(annotation)
                return self._graphql_type_name(inner[0]) if inner else ""
            if container == "Union":
                for candidate in self._subscript_elements(annotation):
                    candidate_name = self._graphql_type_name(candidate)
                    if candidate_name and candidate_name != "None":
                        return candidate_name
                return ""
            return self._graphql_type_name(annotation.slice)
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            left_name = self._graphql_type_name(annotation.left)
            if left_name and left_name != "None":
                return left_name
            return self._graphql_type_name(annotation.right)
        return self._name_from_expr(annotation).split(".")[-1]

    def _graphql_variable_type(self, annotation: Optional[ast.AST]) -> str:
        if annotation is None:
            return "String"
        if isinstance(annotation, ast.Name):
            return {
                "str": "String!",
                "ID": "ID!",
                "int": "Int!",
                "float": "Float!",
                "bool": "Boolean!",
                "dict": "JSON!",
                "list": "[String!]",
            }.get(annotation.id, annotation.id)
        if isinstance(annotation, ast.Attribute):
            if annotation.attr == "ID":
                return "ID!"
            return annotation.attr
        if isinstance(annotation, ast.Constant) and isinstance(annotation.value, str):
            value = annotation.value.split(".")[-1]
            return "ID!" if value == "ID" else value
        if isinstance(annotation, ast.Subscript):
            container = self._name_from_expr(annotation.value).split(".")[-1]
            inner = self._subscript_elements(annotation)
            if container in {"Optional", "Annotated"}:
                return self._graphql_variable_type(inner[0])[:-1] if inner else "String"
            if container in {"List", "Sequence", "Iterable", "tuple", "Tuple", "set", "Set"}:
                inner_type = self._graphql_variable_type(inner[0]) if inner else "String!"
                inner_type = inner_type or "String!"
                return f"[{inner_type}]"
            if container == "Union":
                for candidate in inner:
                    candidate_type = self._graphql_variable_type(candidate)
                    if candidate_type and candidate_type != "None":
                        return candidate_type[:-1] if candidate_type.endswith("!") else candidate_type
                return "String"
            return self._graphql_variable_type(annotation.slice)
        if isinstance(annotation, ast.BinOp) and isinstance(annotation.op, ast.BitOr):
            left_type = self._graphql_variable_type(annotation.left)
            if left_type and left_type != "None":
                return left_type[:-1] if left_type.endswith("!") else left_type
            right_type = self._graphql_variable_type(annotation.right)
            return right_type[:-1] if right_type.endswith("!") else right_type
        return self._name_from_expr(annotation).split(".")[-1] or "String"

    def _resolve_class_node(self, class_name: str) -> Optional[ast.ClassDef]:
        if class_name in self.class_defs:
            return self.class_defs[class_name]
        imported_node = self._load_imported_symbol(class_name)
        if isinstance(imported_node, ast.ClassDef):
            return imported_node
        project_node = self._load_project_symbol(class_name)
        if isinstance(project_node, ast.ClassDef):
            return project_node
        return None

    def _example_response_from_class_node(self, class_node: ast.ClassDef) -> Dict[str, Any]:
        response: Dict[str, Any] = {}
        for statement in class_node.body:
            if isinstance(statement, ast.AnnAssign) and isinstance(statement.target, ast.Name):
                response[statement.target.id] = self._example_from_annotation(statement.annotation)
            elif isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
                decorators = {self._decorator_name(decorator) for decorator in statement.decorator_list}
                if "property" in decorators or "strawberry.field" in decorators or "field" in decorators:
                    response[statement.name] = self._example_from_annotation(statement.returns)
        return response

    def _subscript_elements(self, annotation: ast.Subscript) -> List[ast.AST]:
        slice_expr = annotation.slice
        if isinstance(slice_expr, ast.Tuple):
            return list(slice_expr.elts)
        return [slice_expr]

    def _normalize_django_path(self, route: str) -> str:
        cleaned = route.strip()
        if not cleaned:
            return "/"
        if cleaned.startswith("^"):
            cleaned = cleaned.lstrip("^").rstrip("$")
        cleaned = re.sub(r"<[^:>]+:([^>]+)>", r"{\1}", cleaned)
        cleaned = re.sub(r"<([^>]+)>", r"{\1}", cleaned)
        return cleaned if cleaned.startswith("/") else f"/{cleaned}"

    def _literal_string(self, expr: ast.AST) -> str:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        return ""

    def _literal_string_list(self, expr: ast.AST) -> List[str]:
        if isinstance(expr, (ast.List, ast.Tuple, ast.Set)):
            methods = []
            for element in expr.elts:
                if isinstance(element, ast.Constant) and isinstance(element.value, str):
                    methods.append(element.value.upper())
            return methods
        return []

    def _load_imported_symbol(self, symbol_name: str) -> Optional[ast.AST]:
        module = self.imported_symbols.get(symbol_name)
        if not module:
            return None

        module_path = os.path.join(self.project_root, *module.split("."))
        candidates = [f"{module_path}.py", os.path.join(module_path, "__init__.py")]
        for candidate in candidates:
            if not os.path.exists(candidate):
                continue
            try:
                with open(candidate, "r", encoding="utf-8") as handle:
                    tree = ast.parse(handle.read(), filename=candidate)
            except Exception:
                return None

            for statement in tree.body:
                if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and statement.name == symbol_name:
                    return statement
        return None

    def _load_project_symbol(self, symbol_name: str) -> Optional[ast.AST]:
        if symbol_name in self._project_symbol_cache:
            return self._project_symbol_cache[symbol_name]

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in BackendDiscoveryEngine.SKIP_DIRS and not d.startswith(".")]
            for filename in files:
                if not filename.endswith(".py"):
                    continue
                candidate = os.path.join(root, filename)
                try:
                    with open(candidate, "r", encoding="utf-8") as handle:
                        tree = ast.parse(handle.read(), filename=candidate)
                except Exception:
                    continue

                for statement in tree.body:
                    if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)) and statement.name == symbol_name:
                        self._project_symbol_cache[symbol_name] = statement
                        return statement

        self._project_symbol_cache[symbol_name] = None
        return None

    def _methods_for_external_django_class(self, node: ast.ClassDef) -> List[str]:
        methods = []
        for statement in node.body:
            if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)) and statement.name.lower() in {"get", "post", "put", "patch", "delete"}:
                methods.append(statement.name.upper())
        return methods or ["GET"]

    def _serializer_example_for_external_class(self, node: ast.ClassDef) -> Optional[Dict[str, Any]]:
        serializer_name = ""
        for statement in node.body:
            if isinstance(statement, ast.Assign):
                for target in statement.targets:
                    if isinstance(target, ast.Name) and target.id == "serializer_class":
                        serializer_name = self._name_from_expr(statement.value).split(".")[-1]
                        break
        if not serializer_name:
            return None

        serializer_node = self._load_imported_symbol(serializer_name)
        if isinstance(serializer_node, ast.ClassDef):
            example = self._serializer_example_from_class(serializer_node)
            return example or {}
        return {}

    def _join_paths(self, prefix: str, path: str) -> str:
        combined = "/".join(part.strip("/") for part in (prefix, path) if part)
        return f"/{combined}" if combined else "/"

    def _decorator_name(self, decorator: ast.AST) -> str:
        target = decorator.func if isinstance(decorator, ast.Call) else decorator
        if isinstance(target, ast.Attribute):
            left = self._decorator_name(target.value)
            return f"{left}.{target.attr}" if left else target.attr
        if isinstance(target, ast.Name):
            return target.id
        return ""

    def _name_from_expr(self, expr: Optional[ast.AST]) -> str:
        if expr is None:
            return ""
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            prefix = self._name_from_expr(expr.value)
            return f"{prefix}.{expr.attr}" if prefix else expr.attr
        if isinstance(expr, ast.Subscript):
            return self._name_from_expr(expr.value)
        if isinstance(expr, ast.BinOp):
            return self._name_from_expr(expr.left)
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        return ""


class _PythonGraphQLPathVisitor(ast.NodeVisitor):
    """Finds mounted GraphQL HTTP paths in Python web apps."""

    GRAPHQL_FACTORY_NAMES = {
        "GraphQLRouter",
        "GraphQL",
        "GraphQLApp",
        "AriadneGraphQL",
    }
    GRAPHQL_VIEW_NAMES = {
        "GraphQLView.as_view",
    }
    ROUTE_METHODS = {"mount", "add_route", "add_api_route", "include_router", "add_url_rule"}

    def __init__(self) -> None:
        self.graphql_http_path = ""
        self.graphql_targets: Set[str] = set()

    def visit_Assign(self, node: ast.Assign) -> Any:
        if self._is_graphql_app_expr(node.value):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    self.graphql_targets.add(target.id)
        self.generic_visit(node)

    def visit_Expr(self, node: ast.Expr) -> Any:
        if isinstance(node.value, ast.Call):
            self._capture_graphql_route(node.value)
        self.generic_visit(node)

    def _capture_graphql_route(self, call: ast.Call) -> None:
        if self.graphql_http_path:
            return
        if not isinstance(call.func, ast.Attribute) or call.func.attr not in self.ROUTE_METHODS:
            return

        mounted_target = self._route_target(call)
        if mounted_target is None or not self._is_graphql_target(mounted_target):
            return

        path = self._route_path(call)
        if path:
            self.graphql_http_path = path

    def _route_target(self, call: ast.Call) -> Optional[ast.AST]:
        func_name = call.func.attr
        if func_name == "add_url_rule":
            for keyword in call.keywords:
                if keyword.arg == "view_func":
                    return keyword.value
            if len(call.args) >= 3:
                return call.args[2]
            return None

        if func_name == "include_router":
            for keyword in call.keywords:
                if keyword.arg == "router":
                    return keyword.value
            if call.args:
                return call.args[0]
            return None

        for keyword in call.keywords:
            if keyword.arg in {"app", "router"}:
                return keyword.value

        if len(call.args) >= 2:
            return call.args[1]
        return None

    def _route_path(self, call: ast.Call) -> str:
        for keyword in call.keywords:
            if keyword.arg in {"path", "prefix", "rule"}:
                return self._normalize_path(self._string_value(keyword.value))

        if call.args:
            return self._normalize_path(self._string_value(call.args[0]))
        return ""

    def _is_graphql_target(self, node: ast.AST) -> bool:
        if self._is_graphql_app_expr(node):
            return True
        if isinstance(node, ast.Name) and node.id in self.graphql_targets:
            return True
        return False

    def _is_graphql_app_expr(self, node: ast.AST) -> bool:
        if isinstance(node, ast.Call):
            name = self._call_name(node)
            base_name = name.split(".")[-1]
            if (
                name in self.GRAPHQL_FACTORY_NAMES
                or name in self.GRAPHQL_VIEW_NAMES
                or base_name in self.GRAPHQL_FACTORY_NAMES
                or base_name.endswith(("GraphQLRouter", "GraphQLApp"))
                or base_name.startswith("GraphQL")
            ):
                return True
        return False

    def _call_name(self, node: ast.Call) -> str:
        return self._name_from_expr(node.func)

    def _name_from_expr(self, expr: Optional[ast.AST]) -> str:
        if expr is None:
            return ""
        if isinstance(expr, ast.Name):
            return expr.id
        if isinstance(expr, ast.Attribute):
            prefix = self._name_from_expr(expr.value)
            return f"{prefix}.{expr.attr}" if prefix else expr.attr
        if isinstance(expr, ast.Call):
            return self._name_from_expr(expr.func)
        return ""

    def _string_value(self, expr: ast.AST) -> str:
        if isinstance(expr, ast.Constant) and isinstance(expr.value, str):
            return expr.value
        return ""

    def _normalize_path(self, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            return ""
        return cleaned if cleaned.startswith("/") else f"/{cleaned}"
