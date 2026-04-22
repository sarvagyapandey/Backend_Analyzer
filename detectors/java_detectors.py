"""
Java-specific detectors for Spring Boot, Quarkus, and GraphQL backends.
"""
from __future__ import annotations

import re
from typing import List, Tuple

from analyzer.detector_base import BaseDetector
from analyzer.issue import Issue, IssueLocation, IssueSeverity, IssueType


HTTP_ENDPOINT_ANNOTATIONS = (
    "GetMapping",
    "PostMapping",
    "PutMapping",
    "PatchMapping",
    "DeleteMapping",
    "RequestMapping",
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "QueryMapping",
    "MutationMapping",
    "Query",
    "Mutation",
)
VALIDATION_ANNOTATIONS = (
    "Valid",
    "Validated",
    "NotNull",
    "NotBlank",
    "NotEmpty",
    "Positive",
    "PositiveOrZero",
    "Min",
    "Max",
    "Size",
    "Email",
    "Pattern",
)
DB_CALL_TOKENS = (
    ".find(",
    ".findAll(",
    ".findBy",
    ".query(",
    ".executeQuery(",
    ".createQuery(",
    ".createNativeQuery(",
    ".persist(",
    ".merge(",
    ".list(",
)


class JavaBackendDetector(BaseDetector):
    @property
    def name(self) -> str:
        return "java_backend_review"

    @property
    def description(self) -> str:
        return "Detects Java Spring Boot and Quarkus backend risks in endpoints and resolvers"

    def analyze(self, filepath: str, code: str) -> List[Issue]:
        self.issues = []
        if not filepath.endswith(".java"):
            return self.issues

        methods = self._extract_java_methods(code)
        for annotations, name, parameters, body, line in methods:
            if not self._looks_like_api_handler(annotations):
                continue
            self._check_large_handler(filepath, name, body, line)
            self._check_missing_validation(filepath, name, annotations, parameters, line)
            self._check_swallowed_exceptions(filepath, name, body, line)
            self._check_n_plus_one(filepath, name, body, line)
            self._check_query_concatenation(filepath, name, body, line)
        return self.issues

    def _extract_java_methods(self, code: str) -> List[Tuple[str, str, str, str, int]]:
        pattern = re.compile(
            r"(?P<annotations>(?:@[A-Za-z_][\w.]*(?:\([^)]*\))?\s*)+)"
            r"(?:public|private|protected)\s+[\w<>\[\], ?]+\s+(?P<name>\w+)\s*\((?P<parameters>.*?)\)\s*\{",
            re.MULTILINE | re.DOTALL,
        )
        methods: List[Tuple[str, str, str, str, int]] = []
        for match in pattern.finditer(code):
            body_start = match.end()
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
            line = code[:match.start()].count("\n") + 1
            methods.append(
                (
                    match.group("annotations"),
                    match.group("name"),
                    match.group("parameters"),
                    code[body_start:index - 1],
                    line,
                )
            )
        return methods

    def _looks_like_api_handler(self, annotations: str) -> bool:
        return any(re.search(rf"@(?:[\w.]+\.)?{annotation}\b", annotations) for annotation in HTTP_ENDPOINT_ANNOTATIONS)

    def _check_large_handler(self, filepath: str, name: str, body: str, line: int) -> None:
        significant_lines = [entry for entry in body.splitlines() if entry.strip() and not entry.strip().startswith("//")]
        if len(significant_lines) <= 30:
            return
        self.issues.append(
            Issue(
                detector_name=self.name,
                issue_type=IssueType.DESIGN,
                severity=IssueSeverity.MEDIUM,
                title=f"Java API handler {name}() is doing too much work",
                description="This Spring/Quarkus endpoint is large enough that request handling, business logic, and data access are probably mixed together.",
                location=IssueLocation(filepath, line),
                recommendation="Keep the endpoint thin: validate input, call a service, and return a response. Move the rest into service and repository layers.",
                risk_explanation="Large handlers are harder to review, harder to test, and much easier to break when business rules change.",
            )
        )

    def _check_missing_validation(self, filepath: str, name: str, annotations: str, parameters: str, line: int) -> None:
        if not parameters.strip():
            return
        has_validation = any(
            re.search(rf"@(?:[\w.]+\.)?{annotation}\b", annotations + " " + parameters)
            for annotation in VALIDATION_ANNOTATIONS
        )
        has_body_or_arguments = any(token in parameters for token in ("@RequestBody", "@Argument", "@BeanParam")) or "," in parameters
        if has_body_or_arguments and not has_validation:
            self.issues.append(
                Issue(
                    detector_name=self.name,
                    issue_type=IssueType.RELIABILITY,
                    severity=IssueSeverity.MEDIUM,
                    title=f"Java API handler {name}() accepts input without obvious validation",
                    description="The endpoint takes request data, but there is no visible bean validation or parameter constraint nearby.",
                    location=IssueLocation(filepath, line),
                    recommendation="Add validation annotations like @Valid, @NotNull, @NotBlank, @Positive, or validate in a dedicated service before using the data.",
                    risk_explanation="Invalid input reaches business logic and databases more easily when Java endpoints skip validation checks.",
                )
            )

    def _check_swallowed_exceptions(self, filepath: str, name: str, body: str, line: int) -> None:
        if re.search(r"catch\s*\([^)]*\)\s*\{\s*(?:return\s+null\s*;)?\s*\}", body, re.DOTALL):
            self.issues.append(
                Issue(
                    detector_name=self.name,
                    issue_type=IssueType.RELIABILITY,
                    severity=IssueSeverity.HIGH,
                    title=f"Java API handler {name}() swallows exceptions",
                    description="The catch block is effectively empty, so failures disappear instead of being logged or mapped to a clear response.",
                    location=IssueLocation(filepath, line),
                    recommendation="Log the exception and convert it into a stable HTTP or GraphQL error response.",
                    risk_explanation="Silent failures make production outages much harder to diagnose and can leave clients with misleading success responses or null data.",
                )
            )

    def _check_n_plus_one(self, filepath: str, name: str, body: str, line: int) -> None:
        loop_pattern = re.compile(r"(for|while)\s*\(.*?\)\s*\{(?P<body>.*?)\}", re.DOTALL)
        for loop_match in loop_pattern.finditer(body):
            loop_body = loop_match.group("body")
            if any(token in loop_body for token in DB_CALL_TOKENS):
                self.issues.append(
                    Issue(
                        detector_name=self.name,
                        issue_type=IssueType.PERFORMANCE,
                        severity=IssueSeverity.MEDIUM,
                        title=f"Possible N+1 database access in {name}()",
                        description="This handler appears to call repositories or queries inside a loop.",
                        location=IssueLocation(filepath, line),
                        recommendation="Load related data in batches before the loop, or redesign the query so the database does the join/filtering once.",
                        risk_explanation="This pattern looks fine with a few rows, then becomes painfully slow when real production volumes arrive.",
                    )
                )
                return

    def _check_query_concatenation(self, filepath: str, name: str, body: str, line: int) -> None:
        if re.search(r"(SELECT|UPDATE|DELETE|INSERT)\s+.+\"?\s*\+\s*\w+", body, re.IGNORECASE):
            self.issues.append(
                Issue(
                    detector_name=self.name,
                    issue_type=IssueType.SECURITY,
                    severity=IssueSeverity.HIGH,
                    title=f"Query string concatenation in {name}()",
                    description="SQL or query text appears to be built by joining strings with runtime values.",
                    location=IssueLocation(filepath, line),
                    recommendation="Use prepared statements, parameter binding, repository parameters, or named query parameters instead of string concatenation.",
                    risk_explanation="String-built queries are easier to break, easier to misuse, and can become injection vulnerabilities when user input reaches them.",
                )
            )
