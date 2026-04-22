import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from analyzer.functional_testing import FunctionalTestRunner


class _TestHandler(BaseHTTPRequestHandler):
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


class FunctionalRunnerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = ThreadingHTTPServer(("127.0.0.1", 0), _TestHandler)
        cls.thread = threading.Thread(target=cls.server.serve_forever, daemon=True)
        cls.thread.start()
        cls.base_url = f"http://127.0.0.1:{cls.server.server_address[1]}"

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()
        cls.server.server_close()
        cls.thread.join(timeout=2)

    def _write_config(self, payload):
        temp_dir = tempfile.TemporaryDirectory()
        config_path = Path(temp_dir.name) / "functional.json"
        config_path.write_text(json.dumps(payload), encoding="utf-8")
        self.addCleanup(temp_dir.cleanup)
        return str(config_path)

    def test_runner_passes_rest_and_graphql_checks(self):
        config_path = self._write_config(
            {
                "base_url": self.base_url,
                "tests": [
                    {
                        "name": "health ok",
                        "kind": "rest",
                        "path": "/health",
                        "expect": {
                            "status": 200,
                            "json_paths": {"status": "not_null", "error": "null"},
                        },
                    },
                    {
                        "name": "graphql data present",
                        "kind": "graphql",
                        "path": "/graphql",
                        "query": "query($id: ID!) { user(id: $id) { id name } }",
                        "variables": {"id": "1"},
                        "expect": {
                            "status": 200,
                            "data_not_null": True,
                            "no_errors": True,
                            "json_paths": {"data.user.name": "Ada"},
                        },
                    },
                ],
            }
        )

        summary = FunctionalTestRunner().run_config(config_path)
        self.assertEqual(summary.total, 2)
        self.assertEqual(summary.failed, 0)
        self.assertEqual(summary.passed, 2)

    def test_runner_turns_null_data_and_errors_into_failures(self):
        config_path = self._write_config(
            {
                "base_url": self.base_url,
                "tests": [
                    {
                        "name": "broken rest response",
                        "kind": "rest",
                        "path": "/broken",
                        "expect": {
                            "status": 200,
                            "json_paths": {"data": "not_null", "error": "null"},
                        },
                    },
                    {
                        "name": "broken graphql response",
                        "kind": "graphql",
                        "path": "/graphql",
                        "query": "query($id: ID!) { user(id: $id) { id name } }",
                        "variables": {"id": "broken"},
                        "expect": {
                            "status": 200,
                            "data_not_null": True,
                            "no_errors": True,
                        },
                    },
                ],
            }
        )

        summary = FunctionalTestRunner().run_config(config_path)
        self.assertEqual(summary.failed, 2)
        self.assertEqual(len(summary.to_issues()), 2)
        self.assertIn("Functional test failed", summary.to_issues()[0].title)


if __name__ == "__main__":
    unittest.main()
