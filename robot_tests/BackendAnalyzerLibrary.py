from __future__ import annotations

import json
import tempfile
import textwrap
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from robot.libraries.BuiltIn import BuiltIn

from analyzer.detector_manager import DetectorManager
from analyzer.discovery import BackendDiscoveryEngine
from analyzer.functional_testing import FunctionalTestRunner


class _FunctionalHandler(BaseHTTPRequestHandler):
    def _write_json(self, status, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/health":
            self._write_json(200, {"status": "ok", "error": None})
            return
        if self.path == "/broken":
            self._write_json(200, {"data": None, "error": "backend failed"})
            return
        self._write_json(404, {"error": "not found"})

    def do_POST(self):
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length).decode("utf-8") or "{}")
        if self.path == "/graphql":
            variables = payload.get("variables", {})
            if variables.get("id") == "broken":
                self._write_json(200, {"data": None, "errors": [{"message": "bad id"}]})
                return
            self._write_json(200, {"data": {"user": {"id": "1", "name": "Ada"}}, "errors": []})
            return
        self._write_json(404, {"error": "not found"})

    def log_message(self, format, *args):
        return


class BackendAnalyzerLibrary:
    def __init__(self):
        self._server = None
        self._thread = None
        self._temp_dir = None
        self._base_url = ""
        self._functional_runner = FunctionalTestRunner()

    def analyze_python_code(self, *code_parts, filename: str = "sample.py"):
        code = "\n".join(str(part) for part in code_parts).replace("\\n", "\n")
        return DetectorManager().run_all(filename, textwrap.dedent(code))

    def analyze_java_code(self, *code_parts, filename: str = "Sample.java"):
        code = "\n".join(str(part) for part in code_parts).replace("\\n", "\n")
        return DetectorManager().run_all(filename, textwrap.dedent(code))

    def analyze_file(self, path: str):
        with open(path, "r", encoding="utf-8") as handle:
            code = handle.read()
        filename = Path(path).name
        if filename.endswith(".java"):
            return self.analyze_java_code(code, filename=filename)
        return self.analyze_python_code(code, filename=filename)

    def get_issue_titles(self, issues):
        return [issue.title for issue in issues]

    def issue_titles_should_contain(self, issues, expected_text: str):
        titles = self.get_issue_titles(issues)
        if not any(expected_text in title for title in titles):
            raise AssertionError(f"Expected an issue containing '{expected_text}', but got: {titles}")
        message = f"Passed because an issue containing '{expected_text}' was found: {titles}"
        BuiltIn().log(message, level="INFO")
        BuiltIn().set_test_message(message)

    def issue_titles_should_not_contain(self, issues, unexpected_text: str):
        titles = self.get_issue_titles(issues)
        if any(unexpected_text in title for title in titles):
            raise AssertionError(f"Did not expect an issue containing '{unexpected_text}', but got: {titles}")
        message = f"Passed because no issue containing '{unexpected_text}' was found."
        BuiltIn().log(message, level="INFO")
        BuiltIn().set_test_message(message)

    def discover_backend(self, project_path: str):
        return BackendDiscoveryEngine().discover(project_path)

    def start_functional_server(self):
        if self._server:
            BuiltIn().set_suite_variable("${BASE_URL}", self._base_url)
            return self._base_url

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), _FunctionalHandler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()
        self._base_url = f"http://127.0.0.1:{self._server.server_address[1]}"
        BuiltIn().set_suite_variable("${BASE_URL}", self._base_url)
        return self._base_url

    def stop_functional_server(self):
        if not self._server:
            return

        self._server.shutdown()
        self._server.server_close()
        if self._thread:
            self._thread.join(timeout=2)
        self._server = None
        self._thread = None
        self._base_url = ""

    def run_functional_tests(self, tests, base_url=None):
        effective_base_url = base_url or self._base_url
        return self._functional_runner.run_tests(tests, base_url=effective_base_url)

    def create_sample_project(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        project = Path(self._temp_dir.name)
        (project / "app.py").write_text(
            textwrap.dedent(
                """
                from fastapi import FastAPI

                app = FastAPI()

                @app.get("/health")
                async def health():
                    return {"status": "ok"}
                """
            ),
            encoding="utf-8",
        )
        return str(project)

    def cleanup_sample_project(self):
        if self._temp_dir:
            self._temp_dir.cleanup()
            self._temp_dir = None

    def create_temp_project(self):
        self._temp_dir = tempfile.TemporaryDirectory()
        return str(Path(self._temp_dir.name))

    def write_project_file(self, project_path: str, relative_path: str, *content_parts):
        path = Path(project_path) / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        content = "\n".join(str(part) for part in content_parts).replace("\\n", "\n")
        path.write_text(textwrap.dedent(content), encoding="utf-8")
        return str(path)

    def get_endpoint_paths(self, discovery, kind: str = None):
        if kind:
            return [f"{endpoint.method} {endpoint.path}" for endpoint in discovery.endpoints if endpoint.kind == kind]
        return [f"{endpoint.method} {endpoint.path}" for endpoint in discovery.endpoints]

    def get_endpoint_names(self, discovery, kind: str = None):
        if kind:
            return [endpoint.name for endpoint in discovery.endpoints if endpoint.kind == kind]
        return [endpoint.name for endpoint in discovery.endpoints]

    def get_first_endpoint(self, discovery, kind: str):
        for endpoint in discovery.endpoints:
            if endpoint.kind == kind:
                return endpoint
        raise AssertionError(f"No endpoint with kind {kind} found")

    def endpoint_should_contain(self, endpoint, text: str):
        if text not in getattr(endpoint, "graphql_query", ""):
            raise AssertionError(f"Expected '{text}' in endpoint query, got: {getattr(endpoint, 'graphql_query', '')}")
        message = f"Passed because the GraphQL query contains '{text}'."
        BuiltIn().log(message, level="INFO")
        BuiltIn().set_test_message(message)

    def endpoint_variables_should_equal(self, endpoint, expected):
        if str(endpoint.graphql_variables) != str(expected):
            raise AssertionError(f"Expected variables {expected}, got {endpoint.graphql_variables}")
        message = f"Passed because GraphQL variables matched {expected}."
        BuiltIn().log(message, level="INFO")
        BuiltIn().set_test_message(message)

    def response_body_should_equal(self, endpoint, expected):
        if str(endpoint.example_response_body) != str(expected):
            raise AssertionError(f"Expected response body {expected}, got {endpoint.example_response_body}")
        message = f"Passed because response body matched {expected}."
        BuiltIn().log(message, level="INFO")
        BuiltIn().set_test_message(message)
