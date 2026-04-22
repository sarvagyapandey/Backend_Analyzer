"""
Config-driven functional API testing for REST and GraphQL endpoints.

This layer talks to running services over HTTP, so it works with APIs
built in Python, Java, or any other language.
"""
from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple

from analyzer.issue import Issue, IssueLocation, IssueSeverity, IssueType


@dataclass
class FunctionalTestResult:
    """Outcome of one functional API test."""

    name: str
    endpoint: str
    passed: bool
    status_code: Optional[int] = None
    response_time_ms: Optional[float] = None
    message: str = ""
    details: List[str] = field(default_factory=list)
    request_method: str = ""
    request_headers: Dict[str, str] = field(default_factory=dict)
    request_body: Optional[str] = None
    response_headers: Dict[str, str] = field(default_factory=dict)
    response_body: Optional[str] = None
    response_preview: Optional[str] = None


@dataclass
class FunctionalTestSummary:
    """Combined result for a functional test run."""

    config_path: str
    results: List[FunctionalTestResult]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def passed(self) -> int:
        return sum(1 for result in self.results if result.passed)

    @property
    def failed(self) -> int:
        return self.total - self.passed

    def to_issues(self) -> List[Issue]:
        """Convert failed test results into report issues."""
        issues: List[Issue] = []
        for index, result in enumerate(self.results, start=1):
            if result.passed:
                continue

            detail_lines = [result.message] + result.details
            if result.request_method or result.endpoint:
                detail_lines.append(f"Request: {result.request_method or 'GET'} {result.endpoint}")
            if result.request_headers:
                detail_lines.append(f"Request headers: {json.dumps(result.request_headers, indent=2)}")
            if result.request_body:
                detail_lines.append(f"Request body: {result.request_body}")
            if result.status_code is not None:
                detail_lines.append(f"HTTP status: {result.status_code}")
            if result.response_headers:
                detail_lines.append(f"Response headers: {json.dumps(result.response_headers, indent=2)}")
            if result.response_body:
                detail_lines.append(f"Response body: {result.response_body}")
            if result.response_preview:
                detail_lines.append(f"Response preview: {result.response_preview}")

            issues.append(
                Issue(
                    detector_name="functional_api_tests",
                    issue_type=IssueType.FUNCTIONAL,
                    severity=IssueSeverity.HIGH,
                    title=f"Functional test failed: {result.name}",
                    description=f"Live API check failed for {result.endpoint}",
                    location=IssueLocation(self.config_path, index),
                    recommendation=(
                        "Inspect the endpoint response and update the service or the test "
                        "expectation so the contract is explicit and stable."
                    ),
                    risk_explanation="\n".join(detail_lines),
                    related_code=None,
                )
            )
        return issues

    def to_dict(self) -> Dict[str, Any]:
        """Convert summary to a JSON-friendly structure."""
        return {
            "config_path": self.config_path,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "results": [
                {
                    "name": result.name,
                    "endpoint": result.endpoint,
                    "passed": result.passed,
                    "status_code": result.status_code,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                    "details": result.details,
                    "request_method": result.request_method,
                    "request_headers": result.request_headers,
                    "request_body": result.request_body,
                    "response_headers": result.response_headers,
                    "response_body": result.response_body,
                    "response_preview": result.response_preview,
                }
                for result in self.results
            ],
        }


class FunctionalTestRunner:
    """Runs config-driven REST and GraphQL tests against live endpoints."""

    def run_config(self, config_path: str) -> FunctionalTestSummary:
        """Load a JSON config file and execute its test cases."""
        with open(config_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)

        base_url = str(config.get("base_url", "")).rstrip("/")
        defaults = config.get("defaults", {})
        tests = config.get("tests", [])

        if not isinstance(tests, list):
            raise ValueError("Functional test config must contain a 'tests' list.")

        results: List[FunctionalTestResult] = []
        print(f"Running {len(tests)} functional API tests from {config_path}")

        for index, test in enumerate(tests, start=1):
            name = test.get("name") or f"Test {index}"
            print(f"  Functional test: {name}")
            results.append(self._run_single_test(base_url, defaults, test))

        return FunctionalTestSummary(config_path=config_path, results=results)

    def run_tests(
        self,
        tests: List[Dict[str, Any]],
        *,
        base_url: str = "",
        defaults: Optional[Dict[str, Any]] = None,
        source_label: str = "Functional Test Builder",
    ) -> FunctionalTestSummary:
        """Run tests provided directly by the UI instead of a config file."""
        defaults = defaults or {}
        normalized_base_url = str(base_url or "").rstrip("/")
        results: List[FunctionalTestResult] = []

        print(f"Running {len(tests)} functional API tests from {source_label}")
        for index, test in enumerate(tests, start=1):
            name = test.get("name") or f"Test {index}"
            print(f"  Functional test: {name}")
            results.append(self._run_single_test(normalized_base_url, defaults, test))

        return FunctionalTestSummary(config_path=source_label, results=results)

    def _run_single_test(
        self,
        base_url: str,
        defaults: Dict[str, Any],
        test: Dict[str, Any],
    ) -> FunctionalTestResult:
        """Execute one HTTP-based functional test."""
        kind = str(test.get("kind", "rest")).lower()
        headers = dict(defaults.get("headers", {}))
        headers.update(test.get("headers", {}))
        timeout = float(test.get("timeout_seconds", defaults.get("timeout_seconds", 10)))
        expect = test.get("expect", {})

        url = self._build_url(base_url, test)
        body = self._build_body(kind, test, headers)
        default_method = "POST" if kind == "graphql" else "GET"
        method = str(test.get("method", default_method)).upper()

        reachable, reachability_message = self._check_service_reachable(url, timeout)
        if not reachable:
            return FunctionalTestResult(
                name=str(test.get("name", url)),
                endpoint=url,
                passed=False,
                message=reachability_message,
            )

        request = urllib.request.Request(url=url, data=body, headers=headers, method=method)
        started = time.perf_counter()
        request_body_text = body.decode("utf-8", errors="replace") if body is not None else None

        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                status_code = response.getcode()
                raw_body = response.read()
                response_headers = dict(response.headers.items())
        except urllib.error.HTTPError as error:
            status_code = error.code
            raw_body = error.read()
            response_headers = dict(error.headers.items()) if error.headers else {}
        except urllib.error.URLError as error:
            elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
            return FunctionalTestResult(
                name=str(test.get("name", url)),
                endpoint=url,
                passed=False,
                response_time_ms=elapsed_ms,
                message=f"Network error while calling endpoint: {error.reason}",
                request_method=method,
                request_headers=headers,
                request_body=request_body_text,
            )

        elapsed_ms = round((time.perf_counter() - started) * 1000, 1)
        text_body = raw_body.decode("utf-8", errors="replace")
        json_body = self._parse_json(text_body)

        passed, message, details = self._evaluate_expectations(
            expect=expect,
            status_code=status_code,
            text_body=text_body,
            json_body=json_body,
            response_headers=response_headers,
            response_time_ms=elapsed_ms,
        )

        return FunctionalTestResult(
            name=str(test.get("name", url)),
            endpoint=url,
            passed=passed,
            status_code=status_code,
            response_time_ms=elapsed_ms,
            message=message,
            details=details,
            request_method=method,
            request_headers=headers,
            request_body=request_body_text,
            response_headers=response_headers,
            response_body=text_body[:8000],
            response_preview=text_body[:300],
        )

    def _build_url(self, base_url: str, test: Dict[str, Any]) -> str:
        """Create the final URL from base_url + path or use an absolute URL."""
        explicit_url = test.get("url")
        if explicit_url:
            return str(explicit_url)

        path = str(test.get("path", "")).strip()
        if not path:
            raise ValueError("Each functional test needs either 'url' or 'path'.")

        if path.startswith("http://") or path.startswith("https://"):
            return path

        if not base_url:
            raise ValueError("Functional test config needs 'base_url' when tests use relative paths.")

        return f"{base_url}{path}"

    def _build_body(self, kind: str, test: Dict[str, Any], headers: Dict[str, str]) -> Optional[bytes]:
        """Build the request body for REST or GraphQL calls."""
        payload: Optional[Dict[str, Any]] = None

        if kind == "graphql":
            payload = {"query": test.get("query", ""), "variables": test.get("variables", {})}
            if test.get("operation_name"):
                payload["operationName"] = test["operation_name"]
            headers.setdefault("Content-Type", "application/json")
        elif "json_body" in test:
            payload = test["json_body"]
            headers.setdefault("Content-Type", "application/json")
        elif "body" in test:
            body = test["body"]
            if isinstance(body, str):
                return body.encode("utf-8")
            return json.dumps(body).encode("utf-8")

        if payload is None:
            return None

        return json.dumps(payload).encode("utf-8")

    def _parse_json(self, text_body: str) -> Optional[Any]:
        """Parse JSON response bodies when possible."""
        try:
            return json.loads(text_body)
        except json.JSONDecodeError:
            return None

    def _evaluate_expectations(
        self,
        expect: Dict[str, Any],
        status_code: int,
        text_body: str,
        json_body: Optional[Any],
        response_headers: Dict[str, str],
        response_time_ms: float,
    ) -> Tuple[bool, str, List[str]]:
        """Return pass/fail plus a human-readable reason."""
        failures: List[str] = []

        expected_status = expect.get("status")
        if expected_status is not None and status_code != expected_status:
            failures.append(f"Expected HTTP {expected_status}, got HTTP {status_code}.")

        max_ms = expect.get("max_response_time_ms")
        if max_ms is not None and response_time_ms > float(max_ms):
            failures.append(
                f"Expected response in <= {max_ms} ms, got {response_time_ms} ms."
            )

        body_contains = expect.get("body_contains")
        if body_contains is not None and str(body_contains) not in text_body:
            failures.append(f"Expected response body to contain: {body_contains}")

        expected_header = expect.get("header_contains", {})
        for header_name, expected_value in expected_header.items():
            actual_value = response_headers.get(header_name) or response_headers.get(header_name.lower())
            if actual_value is None or str(expected_value) not in actual_value:
                failures.append(
                    f"Expected header {header_name!r} to contain {expected_value!r}, got {actual_value!r}."
                )

        needs_json = any(
            key in expect
            for key in ("json_paths", "data_not_null", "no_errors", "error_field_null", "error_field_absent")
        )
        if needs_json and json_body is None:
            failures.append("Expected a JSON response body but received non-JSON content.")
        elif json_body is not None:
            if expect.get("data_not_null") and self._resolve_path(json_body, "data")[0] is None:
                failures.append("Expected JSON field 'data' to be present and not null.")

            if expect.get("no_errors"):
                error_value = self._resolve_path(json_body, "errors")[0]
                if error_value not in (None, [], {}):
                    failures.append(f"Expected no GraphQL errors, got: {error_value!r}")

            if expect.get("error_field_null"):
                value, found = self._resolve_path(json_body, str(expect["error_field_null"]))
                if not found or value is not None:
                    failures.append(
                        f"Expected JSON field {expect['error_field_null']!r} to be null, got {value!r}."
                    )

            if expect.get("error_field_absent"):
                _, found = self._resolve_path(json_body, str(expect["error_field_absent"]))
                if found:
                    failures.append(
                        f"Expected JSON field {expect['error_field_absent']!r} to be absent."
                    )

            for path, expected in expect.get("json_paths", {}).items():
                actual_value, found = self._resolve_path(json_body, path)
                mismatch = self._matches_expected(actual_value, found, expected)
                if mismatch is not None:
                    failures.append(f"{path}: {mismatch}")

        if failures:
            return False, failures[0], failures[1:]

        return True, "Functional test passed.", []

    def _check_service_reachable(self, url: str, timeout_seconds: float) -> Tuple[bool, str]:
        """Check whether the backend host/port is reachable before sending the request."""
        parsed = urllib.parse.urlparse(url)
        host = parsed.hostname
        port = parsed.port

        if not host:
            return False, "Backend service URL is invalid."

        if port is None:
            port = 443 if parsed.scheme == "https" else 80

        try:
            with socket.create_connection((host, port), timeout=timeout_seconds):
                return True, ""
        except OSError:
            return (
                False,
                f"Backend service is not running or not reachable at {host}:{port}. "
                "Start the backend service, then run the functional test again.",
            )

    def _resolve_path(self, data: Any, path: str) -> Tuple[Any, bool]:
        """Resolve a dotted JSON path like data.user.name or items.0.id."""
        current = data
        if not path:
            return current, True

        for part in path.split("."):
            if isinstance(current, list):
                try:
                    current = current[int(part)]
                except (ValueError, IndexError):
                    return None, False
            elif isinstance(current, dict):
                if part not in current:
                    return None, False
                current = current[part]
            else:
                return None, False

        return current, True

    def _matches_expected(self, actual_value: Any, found: bool, expected: Any) -> Optional[str]:
        """Return None when the expectation matches, otherwise a mismatch message."""
        if isinstance(expected, str):
            rule = expected.lower()
            if rule == "not_null":
                if not found or actual_value is None:
                    return f"expected not null, got {actual_value!r}"
                return None
            if rule == "null":
                if not found or actual_value is not None:
                    return f"expected null, got {actual_value!r}"
                return None
            if rule == "absent":
                if found:
                    return f"expected field to be absent, got {actual_value!r}"
                return None
            if rule == "present":
                if not found:
                    return "expected field to be present, but it was missing"
                return None
            if rule == "empty":
                if not found or actual_value not in ("", [], {}, None):
                    return f"expected empty value, got {actual_value!r}"
                return None
            if rule == "not_empty":
                if not found or actual_value in ("", [], {}, None):
                    return f"expected non-empty value, got {actual_value!r}"
                return None

        if not found:
            return "expected field to be present, but it was missing"
        if actual_value != expected:
            return f"expected {expected!r}, got {actual_value!r}"
        return None
