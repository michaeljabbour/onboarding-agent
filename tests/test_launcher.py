"""Ensure launcher inspection and stop commands preserve unrelated processes."""
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import threading
import unittest


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


class FixtureHandler(BaseHTTPRequestHandler):
    ready_agent = False

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length", "0")))
        if not self.ready_agent:
            self.send_response(404)
            self.end_headers()
            return
        body = json.dumps({"agent": "fixture", "node": "fixture", "steps": ["ask"],
                           "checks": [], "activeRuns": 1, "assistantReady": True}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args):
        pass


@unittest.skipUnless(NODE and os.name == "posix", "Requires Node.js and a POSIX process environment")
class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="climb-launcher-test-")
        self.addCleanup(self.temp.cleanup)
        self.directory = Path(self.temp.name)
        self.install = self.directory / "installation"
        self.install.mkdir()
        self.handler = type("IsolatedFixtureHandler", (FixtureHandler,), {})
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), self.handler)
        self.server.daemon_threads = True
        thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        thread.start()
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.server.shutdown)
        self.port = self.server.server_port
        self.env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(self.directory),
                    "CLIMB_INSTALL_DIR": str(self.install), "CLIMB_PORT": str(self.port),
                    "CLIMB_NO_OPEN": "1"}

    def command(self, name):
        return subprocess.run([NODE, str(ROOT / "launcher.mjs"), name], env=self.env,
                              cwd=self.directory, capture_output=True, text=True, timeout=10)

    def test_unrelated_listener_is_refused(self):
        result = self.command("existing")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Nothing was stopped", result.stderr)
        self.assertFalse((self.install / ("agent-" + str(self.port) + ".json")).exists())

    def test_running_agent_without_ownership_is_kept(self):
        self.handler.ready_agent = True
        for _ in range(2):
            result = self.command("existing")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("already running", result.stdout)
            self.assertIn("will keep it", result.stdout)
        self.assertFalse((self.install / ("agent-" + str(self.port) + ".json")).exists())

    def test_stop_rejects_record_with_wrong_identity(self):
        record = self.install / ("agent-" + str(self.port) + ".json")
        record.write_text(json.dumps({"pid": os.getpid(), "identity": "wrong fixture identity",
                                     "script": str(self.install / "app/climb-agent.mjs")}), encoding="utf-8")
        result = self.command("stop")
        self.assertEqual(result.returncode, 1)
        self.assertIn("Nothing was stopped", result.stderr)
        self.assertTrue(record.exists())


if __name__ == "__main__":
    unittest.main()
