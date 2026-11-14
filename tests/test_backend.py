"""Local HTTP contract tests; no real CLI credentials, model calls, or setup actions."""
import contextlib
import json
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import tempfile
import time
import unittest
import urllib.error
import urllib.request


ROOT = Path(__file__).resolve().parents[1]
NODE = shutil.which("node")


def argument(args, flag):
    return args[args.index(flag) + 1]


class Backend:
    """Run the real backend with a synthetic CLI and a private, disposable home."""

    def __init__(self, auth="signed-in"):
        self.temp = tempfile.TemporaryDirectory(prefix="climb-test-")
        self.directory = Path(self.temp.name)
        self.home = self.directory / "home"
        self.home.mkdir()
        self.state = self.directory / "state"
        self.projects = self.directory / "projects"
        (self.projects / "project").mkdir(parents=True)
        self.calls = self.directory / "calls.jsonl"
        self.calls.write_text("", encoding="utf-8")
        fake = self.directory / "fake-claude"
        shutil.copyfile(ROOT / "tests/fixtures/fake_claude.py", fake)
        fake.chmod(0o700)
        with socket.socket() as listener:
            listener.bind(("127.0.0.1", 0))
            self.port = listener.getsockname()[1]
        self.base = "http://127.0.0.1:" + str(self.port)
        # Do not forward model keys, provider configuration, NODE_OPTIONS, or other
        # ambient account settings into the backend process.
        env = {"PATH": os.environ.get("PATH", os.defpath), "HOME": str(self.home),
               "CLIMB_PORT": str(self.port), "CLIMB_CLAUDE_BIN": str(fake),
               "CLIMB_STATE_DIR": str(self.state), "CLIMB_WORKDIR": str(self.projects),
               "FIXTURE_CALLS": str(self.calls), "FIXTURE_AUTH": auth}
        self.log = (self.directory / "server.log").open("w", encoding="utf-8")
        self.process = subprocess.Popen(
            [NODE, str(ROOT / "climb-agent.mjs"), "--no-open"],
            cwd=self.directory, env=env, stdout=self.log, stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        self.http = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            deadline = time.monotonic() + 8
            while time.monotonic() < deadline:
                if self.process.poll() is not None:
                    raise AssertionError("Fixture backend exited during startup")
                try:
                    if self.api("health")[0] == 200:
                        break
                except OSError:
                    time.sleep(0.05)
            else:
                raise AssertionError("Fixture backend did not start")
        except BaseException:
            self.close()
            raise

    def api(self, action, body=None, headers=None):
        if headers is None:
            headers = {"Content-Type": "application/json", "X-Climb": "1", "Origin": self.base}
        request = urllib.request.Request(
            self.base + "/api/" + action,
            data=json.dumps(body or {}).encode(), headers=headers,
        )
        try:
            with self.http.open(request, timeout=5) as response:
                return response.status, json.load(response)
        except urllib.error.HTTPError as error:
            with error:
                raw = error.read().decode()
            try:
                raw = json.loads(raw)
            except ValueError:
                pass
            return error.code, raw

    def start(self, **body):
        status, result = self.api("start_step", body)
        if status != 200:
            raise AssertionError((status, result))
        return result

    def wait(self, run):
        deadline = time.monotonic() + 8
        while time.monotonic() < deadline:
            status, result = self.api("get_run", {"runId": run["runId"]})
            if status != 200:
                raise AssertionError((status, result))
            if result["status"] != "running" and result["endedAt"]:
                return result
            time.sleep(0.03)
        raise AssertionError("Synthetic run did not finish")

    def launches(self):
        calls = [json.loads(line) for line in self.calls.read_text(encoding="utf-8").splitlines()]
        return [call for call in calls if "-p" in call["args"]]

    def close(self):
        # The backend and all synthetic CLI children share this private group.
        with contextlib.suppress(ProcessLookupError):
            os.killpg(self.process.pid, signal.SIGTERM)
        try:
            self.process.wait(timeout=3)
        except subprocess.TimeoutExpired:
            with contextlib.suppress(ProcessLookupError):
                os.killpg(self.process.pid, signal.SIGKILL)
            self.process.wait(timeout=3)
        self.log.close()
        self.temp.cleanup()


@unittest.skipUnless(NODE and os.name == "posix", "Requires Node.js and a POSIX process environment")
class BackendTests(unittest.TestCase):
    def setUp(self):
        self.backend = Backend()
        self.addCleanup(self.backend.close)

    def companion(self, **values):
        body = {"step": "companion", "mode": "run", "input": "Show me one example."}
        body.update(values)
        return self.backend.wait(self.backend.start(**body))

    def test_health_is_sanitized_and_readiness_is_cached(self):
        for _ in range(2):
            status, health = self.backend.api("health")
            self.assertEqual(status, 200)
            self.assertEqual(health["service"], "the-climb")
            self.assertTrue(health["assistantReady"])
            self.assertTrue(health["signedIn"])
            self.assertEqual(health["activeRuns"], 0)
            self.assertNotIn("fixture@example.invalid", json.dumps(health))
            self.assertNotIn("synthetic-credential-marker", json.dumps(health))
        calls = [json.loads(line)["args"] for line in self.backend.calls.read_text().splitlines()]
        self.assertEqual(calls.count(["--version"]), 1)
        self.assertEqual(calls.count(["auth", "status"]), 1)

    def test_api_rejects_untrusted_origin_host_and_missing_header(self):
        headers = [
            {"X-Climb": "1", "Origin": "null"},
            {"X-Climb": "1", "Origin": "https://example.invalid"},
            {"X-Climb": "1", "Origin": self.backend.base, "Host": "example.invalid"},
            {"Origin": self.backend.base},
        ]
        for value in headers:
            with self.subTest(headers=value):
                self.assertEqual(self.backend.api("health", headers=value)[0], 403)

    def test_companion_has_no_tools_and_uses_private_working_directory(self):
        run = self.companion()
        self.assertEqual(run["status"], "done")
        launch = self.backend.launches()[-1]
        args = launch["args"]
        self.assertIn("--safe-mode", args)
        self.assertIn("--strict-mcp-config", args)
        self.assertEqual(argument(args, "--tools"), "")
        self.assertNotIn("--allowedTools", args)
        self.assertIn("You have no tools", argument(args, "--system-prompt"))
        self.assertEqual(Path(launch["cwd"]).resolve(), (self.backend.state / "companion").resolve())
        self.assertFalse(any(event["kind"] == "do" for event in run["events"]))

    def test_followups_refresh_context_and_profile_without_losing_session(self):
        first = self.companion(context="OLD_STAGE", profile={"name": "Example User"})
        session = self.backend.launches()[-1]
        for endpoint, key in [("reply", "runId"), ("start_step", "replyTo")]:
            with self.subTest(endpoint=endpoint):
                status, reply = self.backend.api(endpoint, {
                    key: first["runId"], "text": "Here is my attempt.",
                    "context": "NEW_STAGE with a selected lesson",
                    "profile": {"name": "Example Learner", "style": "visual"},
                })
                self.assertEqual(status, 200)
                self.assertEqual(self.backend.wait(reply)["status"], "done")
                args = self.backend.launches()[-1]["args"]
                self.assertIn("--resume", args)
                self.assertTrue(argument(args, "--resume").startswith("fixture-session-"))
                prompt = argument(args, "-p")
                self.assertIn("NEW_STAGE", prompt)
                self.assertNotIn("OLD_STAGE", prompt)
                self.assertIn("Example Learner", prompt)
                self.assertNotIn("Example User", prompt)
                self.assertEqual(argument(args, "--tools"), "")
        self.assertNotIn("--resume", session["args"])

    def test_resumed_usage_charges_only_increment_even_after_missing_cost(self):
        first = self.companion()
        self.assertAlmostEqual(first["cost"], 0.05)
        status, failed = self.backend.api("reply", {"runId": first["runId"], "text": "FIXTURE_NO_COST"})
        self.assertEqual(status, 200)
        failed = self.backend.wait(failed)
        self.assertEqual(failed["status"], "failed")
        self.assertIsNone(failed["cost"])
        self.assertAlmostEqual(failed["usage"]["usd"], 0.05)
        status, retried = self.backend.api("reply", {"runId": failed["runId"], "text": "Try again."})
        self.assertEqual(status, 200)
        retried = self.backend.wait(retried)
        self.assertEqual(retried["status"], "done")
        self.assertAlmostEqual(retried["cost"], 0.02)
        self.assertAlmostEqual(retried["usage"]["usd"], 0.07)

    def test_provider_auth_error_does_not_echo_credentials(self):
        run = self.companion(input="FIXTURE_AUTH_ERROR")
        self.assertEqual(run["status"], "failed")
        warnings = " ".join(event["text"] for event in run["events"] if event["kind"] == "warn")
        self.assertIn("sign-in", warnings)
        self.assertIn("START.command", warnings)
        self.assertNotIn("synthetic-credential-marker", json.dumps(run))
        self.assertNotIn("fixture@example.invalid", json.dumps(run))

    def test_plan_approval_requires_matching_completed_plan(self):
        body = {"step": "project", "mode": "plan", "input": "Install dependencies.",
                "repo": "example/project", "profile": {"laptop": "work"}}
        plan = self.backend.wait(self.backend.start(**body))
        self.assertEqual(plan["status"], "done")
        approval = dict(body, mode="run", planRunId=plan["runId"])
        launch_count = len(self.backend.launches())
        for override in [{"planRunId": "missing"}, {"input": "Different request"},
                         {"repo": "another/project"}, {"step": "roadmap"}]:
            with self.subTest(override=override):
                self.assertEqual(self.backend.api("start_step", dict(approval, **override))[0], 400)
                self.assertEqual(len(self.backend.launches()), launch_count)
        approved = self.backend.wait(self.backend.start(**approval))
        self.assertEqual(approved["status"], "done")
        self.assertIn("--resume", self.backend.launches()[-1]["args"])

    def test_running_and_cancelled_plans_cannot_be_approved(self):
        body = {"step": "roadmap", "mode": "plan", "input": "FIXTURE_SLOW",
                "repo": "example/project", "profile": {"laptop": "work"}}
        plan = self.backend.start(**body)
        approval = dict(body, mode="run", planRunId=plan["runId"])
        self.assertEqual(self.backend.api("health")[1]["activeRuns"], 1)
        self.assertEqual(self.backend.api("start_step", approval)[0], 400)
        self.assertEqual(self.backend.api("cancel_run", {"runId": plan["runId"]})[0], 200)
        self.assertEqual(self.backend.wait(plan)["status"], "cancelled")
        self.assertEqual(self.backend.api("start_step", approval)[0], 400)
        self.assertEqual(self.backend.api("health")[1]["activeRuns"], 0)

    def test_lost_conversation_is_reported_explicitly(self):
        for action in ["reply", "get_run"]:
            with self.subTest(action=action):
                status, result = self.backend.api(action, {"runId": "unknown-run", "text": "Continue."})
                self.assertEqual(status, 400)
                self.assertIn("restarted", result["error"])


@unittest.skipUnless(NODE and os.name == "posix", "Requires Node.js and a POSIX process environment")
class ReadinessTests(unittest.TestCase):
    def test_unavailable_authentication_never_reports_ready(self):
        for state in ["signed-out", "unknown", "missing"]:
            with self.subTest(state=state):
                backend = Backend(state)
                try:
                    status, health = backend.api("health")
                    self.assertEqual(status, 200)
                    self.assertFalse(health["assistantReady"])
                    self.assertTrue(health["setupMessage"])
                    if state == "signed-out":
                        self.assertFalse(health["signedIn"])
                    elif state == "unknown":
                        self.assertIsNone(health["signedIn"])
                    else:
                        self.assertIsNone(health["claude"])
                finally:
                    backend.close()


if __name__ == "__main__":
    unittest.main()
