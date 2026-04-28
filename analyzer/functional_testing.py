"""
Config-driven functional API testing for REST and GraphQL endpoints.

This layer talks to running services over HTTP, so it works with APIs
built in Python, Java, or any other language.
"""
from __future__ import annotations

import json
import socket
import time
from copy import deepcopy
import urllib.error
import urllib.request
import urllib.parse
from dataclasses import dataclass, field
from html import escape
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
        by_endpoint: Dict[str, Dict[str, Any]] = {}
        for result in self.results:
            bucket = by_endpoint.setdefault(
                result.endpoint,
                {"total": 0, "passed": 0, "failed": 0, "results": []},
            )
            bucket["total"] += 1
            bucket["passed"] += 1 if result.passed else 0
            bucket["failed"] += 0 if result.passed else 1
            bucket["results"].append(
                {
                    "name": result.name,
                    "passed": result.passed,
                    "status_code": result.status_code,
                    "response_time_ms": result.response_time_ms,
                    "message": result.message,
                }
            )
        return {
            "config_path": self.config_path,
            "total": self.total,
            "passed": self.passed,
            "failed": self.failed,
            "by_endpoint": by_endpoint,
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

    def write_json_report(self, output_path: str) -> None:
        """Write the summary to a JSON file."""
        with open(output_path, "w", encoding="utf-8") as handle:
            json.dump(self.to_dict(), handle, indent=2, ensure_ascii=True)

    def write_html_report(self, output_path: str) -> None:
        """Write a detailed HTML report for the functional test sweep."""
        report = self.to_dict()
        rows = []
        for result in report["results"]:
            outcome_class = "pass" if result["passed"] else "fail"
            rows.append(
                "<tr>"
                f"<td>{escape(str(result['name']))}</td>"
                f"<td class='{outcome_class}'>{'PASS' if result['passed'] else 'FAIL'}</td>"
                f"<td>{escape(str(result['endpoint']))}</td>"
                f"<td>{escape(str(result['request_method']))}</td>"
                f"<td>{'' if result['status_code'] is None else escape(str(result['status_code']))}</td>"
                f"<td>{'' if result['response_time_ms'] is None else escape(str(result['response_time_ms']))}</td>"
                f"<td><pre>{escape(str(result['request_body'] or ''))}</pre></td>"
                f"<td><pre>{escape(str(result['response_body'] or ''))}</pre></td>"
                f"<td><pre>{escape(str(result['message'] or ''))}</pre></td>"
                "</tr>"
            )

        endpoint_rows = []
        for endpoint, data in report["by_endpoint"].items():
            endpoint_rows.append(
                "<tr>"
                f"<td>{escape(str(endpoint))}</td>"
                f"<td>{data['total']}</td>"
                f"<td>{data['passed']}</td>"
                f"<td>{data['failed']}</td>"
                "</tr>"
            )

        html = f"""<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>Functional Test Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 24px; color: #111827; }}
    h1, h2 {{ margin-bottom: 8px; }}
    .summary {{ display: grid; grid-template-columns: repeat(4, minmax(120px, 1fr)); gap: 12px; margin: 18px 0 28px; }}
    .card {{ background: #f8fafc; border: 1px solid #d1d5db; border-radius: 10px; padding: 14px; }}
    table {{ border-collapse: collapse; width: 100%; margin-bottom: 28px; }}
    th, td {{ border: 1px solid #d1d5db; padding: 8px; vertical-align: top; text-align: left; }}
    th {{ background: #eff6ff; }}
    .pass {{ color: #166534; font-weight: 700; }}
    .fail {{ color: #b91c1c; font-weight: 700; }}
    pre {{ white-space: pre-wrap; word-break: break-word; margin: 0; }}
  </style>
</head>
<body>
  <h1>Functional Test Report</h1>
  <div class="summary">
    <div class="card"><strong>Total</strong><div>{report['total']}</div></div>
    <div class="card"><strong>Passed</strong><div class="pass">{report['passed']}</div></div>
    <div class="card"><strong>Failed</strong><div class="fail">{report['failed']}</div></div>
    <div class="card"><strong>Source</strong><div>{escape(str(report['config_path']))}</div></div>
  </div>
  <h2>By Endpoint</h2>
  <table>
    <thead><tr><th>Endpoint</th><th>Total</th><th>Passed</th><th>Failed</th></tr></thead>
    <tbody>
      {"".join(endpoint_rows)}
    </tbody>
  </table>
  <h2>Runs</h2>
  <table>
    <thead>
      <tr>
        <th>Test</th><th>Status</th><th>Endpoint</th><th>Method</th><th>HTTP</th><th>Time (ms)</th><th>Request Body</th><th>Response Body</th><th>Message</th>
      </tr>
    </thead>
    <tbody>
      {"".join(rows)}
    </tbody>
  </table>
</body>
</html>"""
        with open(output_path, "w", encoding="utf-8") as handle:
            handle.write(html)


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

    def build_auto_tests_from_discovery(self, discovery, *, base_url: str = "") -> List[Dict[str, Any]]:
        """Build multiple payload variants for every discovered endpoint."""
        tests: List[Dict[str, Any]] = []
        endpoints = getattr(discovery, "endpoints", []) or []
        for endpoint in endpoints:
            tests.extend(self._build_endpoint_variants(endpoint, base_url=base_url))
        return tests

    def _build_endpoint_variants(self, endpoint, *, base_url: str = "") -> List[Dict[str, Any]]:
        url = endpoint.path if str(endpoint.path).startswith(("http://", "https://")) else f"{base_url.rstrip('/')}{endpoint.path}"
        tests: List[Dict[str, Any]] = []

        if endpoint.kind == "graphql":
            query = endpoint.graphql_query or f"query {endpoint.name}Query {{\n  {endpoint.name}\n}}"
            variables = endpoint.graphql_variables or {}
            tests.append(self._graph_ql_test_case(endpoint, url, query, variables, "baseline"))
            for index, variant in enumerate(self._graphql_variable_variants(variables), start=1):
                tests.append(self._graph_ql_test_case(endpoint, url, query, variant, f"variant-{index}"))
            return tests

        body_variants = self._json_body_variants(endpoint.example_json_body)
        if endpoint.method in {"POST", "PUT", "PATCH", "DELETE"}:
            for index, body in enumerate(body_variants, start=1):
                tests.append(
                    {
                        "name": f"{endpoint.label()} payload-{index}",
                        "kind": endpoint.kind,
                        "method": endpoint.method,
                        "url": url,
                        "json_body": body,
                        "expect": {"status": 200},
                    }
                )
        else:
            tests.append(
                {
                    "name": endpoint.label(),
                    "kind": endpoint.kind,
                    "method": endpoint.method,
                    "url": url,
                    "expect": {"status": 200},
                }
            )
        return tests

    def _graph_ql_test_case(self, endpoint, url: str, query: str, variables: Dict[str, Any], suffix: str) -> Dict[str, Any]:
        return {
            "name": f"{endpoint.label()} {suffix}",
            "kind": "graphql",
            "method": "POST",
            "url": url,
            "query": query,
            "variables": variables,
            "expect": {"status": 200, "data_not_null": True, "no_errors": True},
        }

    def _graphql_variable_variants(self, variables: Dict[str, Any]) -> List[Dict[str, Any]]:
        if not variables:
            return [{}]
        variants: List[Dict[str, Any]] = [dict(variables)]
        for key, value in variables.items():
            variants.extend(self._field_variants(dict(variables), key, value))
        return self._dedupe_variants(variants)

    def _json_body_variants(self, body: Optional[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not isinstance(body, dict) or not body:
            return [{}, {"example": "value"}, {"example": "value-2"}]
        variants: List[Dict[str, Any]] = [dict(body)]
        for key, value in body.items():
            variants.extend(self._field_variants(dict(body), key, value))
        return self._dedupe_variants(variants)

    def _field_variants(self, payload: Dict[str, Any], key: str, value: Any) -> List[Dict[str, Any]]:
        variants: List[Dict[str, Any]] = []
        for variant_index in (1, 2):
            mutated = deepcopy(payload)
            mutated[key] = self._variant_value(value, variant_index, depth=0)
            variants.append(mutated)

        if isinstance(value, dict):
            variants.extend(self._nested_dict_variants(payload, key, value, depth=0))
        if isinstance(value, list):
            variants.extend(self._nested_list_variants(payload, key, value, depth=0))
        return variants

    def _nested_dict_variants(self, payload: Dict[str, Any], key: str, value: Dict[str, Any], depth: int) -> List[Dict[str, Any]]:
        if depth >= 3:
            return []
        variants: List[Dict[str, Any]] = []
        for nested_key, nested_value in value.items():
            mutated = deepcopy(payload)
            nested_copy = deepcopy(value)
            nested_copy[nested_key] = self._variant_value(nested_value, 1, depth=depth + 1)
            mutated[key] = nested_copy
            variants.append(mutated)
            if isinstance(nested_value, dict):
                variants.extend(self._nested_dict_variants(mutated, key, nested_copy, depth + 1))
            if isinstance(nested_value, list):
                variants.extend(self._nested_list_variants(mutated, key, nested_copy, depth + 1))
        return variants

    def _nested_list_variants(self, payload: Dict[str, Any], key: str, value: List[Any], depth: int) -> List[Dict[str, Any]]:
        if depth >= 3:
            return []
        if not value:
            mutated = deepcopy(payload)
            mutated[key] = [f"item-{depth + 1}"]
            return [mutated]

        variants: List[Dict[str, Any]] = []
        for index, item in enumerate(value):
            mutated = deepcopy(payload)
            list_copy = deepcopy(value)
            list_copy[index] = self._variant_value(item, 1, depth=depth + 1)
            mutated[key] = list_copy
            variants.append(mutated)
            if isinstance(item, dict):
                variants.extend(self._nested_list_of_dict_variants(mutated, key, list_copy, depth + 1))
            if isinstance(item, list):
                variants.extend(self._nested_list_variants(mutated, key, list_copy, depth + 1))
        return variants

    def _nested_list_of_dict_variants(self, payload: Dict[str, Any], key: str, value: List[Any], depth: int) -> List[Dict[str, Any]]:
        variants: List[Dict[str, Any]] = []
        for index, item in enumerate(value):
            if not isinstance(item, dict):
                continue
            mutated = deepcopy(payload)
            list_copy = deepcopy(value)
            nested_dict = deepcopy(item)
            for nested_key, nested_value in item.items():
                nested_dict[nested_key] = self._variant_value(nested_value, 1, depth=depth + 1)
            list_copy[index] = nested_dict
            mutated[key] = list_copy
            variants.append(mutated)
        return variants

    def _mutate_value(self, payload: Dict[str, Any], key: str, value: Any, variant_index: int) -> Dict[str, Any]:
        payload[key] = self._variant_value(value, variant_index)
        return payload

    def _variant_value(self, value: Any, variant_index: int, depth: int = 0) -> Any:
        if depth >= 3:
            return value
        if isinstance(value, bool):
            return not value if variant_index == 1 else value
        if isinstance(value, int):
            return value + variant_index
        if isinstance(value, float):
            return value + float(variant_index)
        if isinstance(value, str):
            return f"{value}-{variant_index}"
        if isinstance(value, list):
            if not value:
                return [f"item-{variant_index}"]
            mutated = [self._variant_value(item, variant_index, depth + 1) for item in value]
            mutated.append(self._variant_value(value[0], variant_index, depth + 1))
            return mutated
        if isinstance(value, dict):
            mutated = dict(value)
            if mutated:
                first_key = next(iter(mutated))
                mutated[first_key] = self._variant_value(mutated[first_key], variant_index, depth + 1)
            else:
                mutated["example"] = f"value-{variant_index}"
            return mutated
        if value is None:
            return f"value-{variant_index}"
        return value

    def _dedupe_variants(self, variants: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique: List[Dict[str, Any]] = []
        seen = set()
        for variant in variants:
            fingerprint = json.dumps(variant, sort_keys=True, default=str)
            if fingerprint in seen:
                continue
            seen.add(fingerprint)
            unique.append(variant)
        return unique

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
