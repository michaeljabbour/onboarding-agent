"""Local HTTP contract tests; no real CLI credentials, model calls, or setup actions."""
import contextlib
import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import threading
import os
from pathlib import Path
import shutil
import signal
import socket
import subprocess
import sys
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

    def __init__(self, auth="signed-in", ollama_port=0):
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
        self.bin = self.directory / "bin"
        self.bin.mkdir()
        env = {"PATH": str(self.bin) + os.pathsep + os.environ.get("PATH", os.defpath), "HOME": str(self.home),
               "CLIMB_PORT": str(self.port), "CLIMB_CLAUDE_BIN": str(fake),
               "CLIMB_STATE_DIR": str(self.state), "CLIMB_WORKDIR": str(self.projects),
               "CLIMB_OLLAMA_PORT": str(ollama_port), "FIXTURE_CALLS": str(self.calls), "FIXTURE_AUTH": auth}
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

    def test_guide_cannot_be_framed_and_feedback_repo_is_off_by_default(self):
        with self.backend.http.open(self.backend.base + "/") as page:
            self.assertEqual(page.headers["X-Frame-Options"], "DENY")
            self.assertIn("frame-ancestors 'none'", page.headers["Content-Security-Policy"])
        status, health = self.backend.api("health")
        self.assertEqual(status, 200)
        self.assertIsNone(health["feedbackRepo"])

    def companion(self, **values):
        body = {"step": "companion", "mode": "run", "input": "Show me one example."}
        body.update(values)
        return self.backend.wait(self.backend.start(**body))

    @unittest.skipUnless(sys.platform == "darwin", "Uses the macOS setup terminal")
    def test_observed_install_streams_pty_output_and_checks_exit_status(self):
        fixtures = {"git": "exit 0", "xcode-select": "exit 0",
                    "gh": 'test -f "$HOME/installed"',
                    "brew": 'if [ "$1" = "--version" ]; then exit 0; fi\n'
                            'test "$*" = "install gh" && test -t 1 || exit 82\n'
                            'echo "Installing fixture"; sleep 0.4\n'
                            'test -f "$HOME/allow" || exit 19\n'
                            'touch "$HOME/installed"'}
        for name, body in fixtures.items():
            script = self.backend.bin / name
            script.write_text("#!/bin/sh\n" + body + "\n")
            script.chmod(0o700)
        body = {"step": "tools", "mode": "run", "profile": {"laptop": "work", "autonomy": "direct"}}
        failed = self.backend.wait(self.backend.start(**body))
        self.assertEqual(failed["status"], "failed")
        self.assertTrue(any("exit 19" in e.get("text", "") for e in failed["events"]))
        (self.backend.home / "allow").touch()
        run = self.backend.start(**body)
        for _ in range(100):
            _, live = self.backend.api("get_run", {"runId": run["runId"]})
            if any(e["kind"] == "terminal" and "Installing fixture" in e["text"] for e in live["events"]):
                break
            time.sleep(0.01)
        else:
            self.fail("Missing terminal output")
        self.assertEqual(live["status"], "running")
        self.assertEqual(self.backend.api("start_step", body)[0], 400)
        self.assertEqual(self.backend.wait(run)["status"], "done")

    @unittest.skipUnless(sys.platform == "darwin", "Uses the macOS setup terminal")
    def test_explicit_setup_install_runs_only_the_selected_native_recipe(self):
        profile = {"laptop": "personal", "autonomy": "plan"}
        for name, body in {
            "git": "exit 0", "gh": 'test -f "$HOME/installed"',
            "xcode-select": "exit 0",
            "brew": 'if [ "$1" = "--version" ]; then exit 0; fi\n'
                    'test "$*" = "install gh" && test -t 1 || exit 82\n'
                    'echo "Installing test tool"; touch "$HOME/installed"'
        }.items():
            script = self.backend.bin / name
            script.write_text("#!/bin/sh\n" + body + "\n")
            script.chmod(0o700)
        # The ordinary agent path continues to enforce the person's preferences.
        self.assertEqual(self.backend.api("start_step", {"step": "tools", "mode": "run", "profile": profile})[0], 400)
        for step in ["project", "newrepo", "prefs", "terminalcheck"]:
            self.assertEqual(self.backend.api("install_tools", {"step": step, "profile": profile})[0], 400)
        status, run = self.backend.api("install_tools", {"step": "tools", "profile": profile})
        self.assertEqual(status, 200, run)
        done = self.backend.wait(run)
        self.assertEqual(done["status"], "done")
        output = [e["text"] for e in done["events"] if e["kind"] == "terminal"]
        self.assertIn("Installing test tool", output)
        self.assertTrue((self.backend.home / "installed").is_file())
        self.assertFalse(self.backend.launches())

    @unittest.skipUnless(sys.platform == "darwin", "The in-guide terminal uses macOS script(1)")
    def test_live_terminal_is_a_real_pty_with_hidden_input_and_clean_close(self):
        def terminal(**body):
            status, result = self.backend.api("terminal", body)
            self.assertEqual(status, 200, result)
            return result

        opened = terminal(op="open", cols=90, rows=20)
        session, seen, position = opened["id"], "", 0

        def until(text):
            nonlocal seen, position
            deadline = time.monotonic() + 8
            while text not in seen and time.monotonic() < deadline:
                reply = terminal(op="read", id=session, since=position, wait=False)
                seen, position = seen + reply["data"], reply["next"]
                time.sleep(0.05)
            self.assertIn(text, seen)

        terminal(op="write", id=session, data="test -t 0 && stty size && echo tty-$((6*7))\r")
        until("20 90")
        until("tty-42")
        terminal(op="resize", id=session, cols=120, rows=30)
        terminal(op="write", id=session, data="stty size\r")
        until("30 120")
        # Input typed at a no-echo prompt must not come back in the transcript.
        terminal(op="write", id=session, data="stty -echo; read answer; stty echo; echo length-${#answer}\r")
        time.sleep(0.4)
        terminal(op="write", id=session, data="synthetic-private-input\r")
        until("length-23")
        self.assertNotIn("synthetic-private-input", seen)
        self.assertNotIn("synthetic-private-input", (self.backend.directory / "server.log").read_text(encoding="utf-8"))
        terminal(op="write", id=session, data="sleep 30\r")
        time.sleep(0.3)
        terminal(op="write", id=session, data="\x03")
        terminal(op="write", id=session, data="echo interrupted-ok\r")
        until("interrupted-ok")
        terminal(op="close", id=session)
        self.assertFalse(terminal(op="read", id=session, since=position, wait=False)["alive"])
        self.assertEqual(self.backend.api("terminal", {"op": "write", "id": session, "data": "x"})[0], 400)
        self.assertEqual(self.backend.api("terminal", {"op": "open"}, headers={"Content-Type": "application/json"})[0], 403)
        self.assertEqual(self.backend.api("terminal", {"op": "read", "id": "missing"})[0], 400)

    @unittest.skipUnless(sys.platform == "darwin", "Setup recipes are written for macOS")
    def test_setup_plan_names_the_next_command_without_running_it(self):
        def tool(name, body):
            path = self.backend.bin / name
            path.write_text("#!/bin/sh\necho \"$0 $*\" >> \"" + str(self.backend.directory / "ran.log") + "\"\n" + body + "\n", encoding="utf-8")
            path.chmod(0o700)

        def plan(step="tools"):
            status, result = self.backend.api("setup_plan", {"step": step})
            self.assertEqual(status, 200, result)
            return result

        tool("xcode-select", "exit 0")
        tool("git", "exit 0")
        tool("brew", "exit 1")
        tool("gh", "exit 1")
        self.assertIn("Homebrew/install/HEAD/install.sh", plan()["command"])
        tool("brew", "exit 0")
        ready = plan()
        self.assertEqual(ready["command"], str(self.backend.bin / "brew") + " install gh")
        self.assertFalse(ready["done"])
        tool("gh", "exit 0")
        self.assertEqual(plan(), {"done": True, "command": "", "label": "", "note": "Git, Node and the GitHub command-line tool are ready."})
        ran = (self.backend.directory / "ran.log").read_text(encoding="utf-8")
        self.assertNotIn(" install", ran)
        self.assertEqual(self.backend.api("setup_plan", {"step": "clone"})[0], 400)

    def test_missing_homebrew_gives_the_command_and_a_way_to_continue(self):
        home_bin = self.backend.bin
        (home_bin / "xcode-select").write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
        (home_bin / "xcode-select").chmod(0o700)
        (home_bin / "brew").write_text("#!/bin/sh\nexit 1\n", encoding="utf-8")
        (home_bin / "brew").chmod(0o700)
        status, run = self.backend.api("install_tools", {"step": "tools", "profile": {"laptop": "work"}})
        self.assertEqual(status, 200, run)
        result = self.backend.wait(run)
        if sys.platform != "darwin":
            return
        self.assertEqual(result["status"], "needs_you")
        commands = [event["text"] for event in result["events"] if event["kind"] == "pre"]
        self.assertEqual(len(commands), 1)
        self.assertIn("Homebrew/install/HEAD/install.sh", commands[0])

    def test_publish_retry_reuses_the_original_commit_and_confirms_the_remote(self):
        gh = self.backend.bin / "gh"
        gh.write_text("""#!/bin/sh
case "$1 $2" in
  'api user') echo learner ;;
  'repo view') test -f "$HOME/published" || exit 1
    printf '{"isPrivate":true,"isEmpty":false}\n' ;;
  'api repos/learner/journal/git/ref/heads/main') cat "$HOME/published" ;;
  'auth setup-git') exit 0 ;;
  'repo create')
    test -f "$HOME/can-publish" || exit 1
    git -C "$6" rev-parse HEAD > "$HOME/published"
    exit 1 ;; # Remote succeeded just before its response was lost.
  *) exit 1 ;;
esac
""")
        gh.chmod(0o700)
        body = {"step": "newrepo", "mode": "run", "input": "journal\nSave a daily note.",
                "profile": {"autonomy": "direct"}}
        run = lambda: self.backend.wait(self.backend.start(**body))
        first = run()
        self.assertEqual(first["status"], "failed")
        self.assertIn("Try again", first["summary"])
        directory = self.backend.projects / "journal"
        head = subprocess.check_output(["git", "-C", str(directory), "rev-parse", "HEAD"], text=True)
        (self.backend.home / "can-publish").touch()
        self.assertEqual(run()["status"], "failed")
        self.assertEqual((self.backend.home / "published").read_text(), head)
        confirmed = run()
        self.assertEqual(confirmed["status"], "done")
        self.assertEqual(confirmed["facts"]["repo"], "learner/journal")
        self.assertEqual(subprocess.check_output(
            ["git", "-C", str(directory), "rev-list", "--count", "HEAD"], text=True).strip(), "1")
        (self.backend.home / "published").write_text("some-other-commit\n")
        self.assertEqual(run()["status"], "failed")
        body["input"] = "project\nLeave this existing project alone."
        self.assertEqual(run()["status"], "failed")
        self.assertFalse((self.backend.projects / "project" / "README.md").exists())

    def test_refresh_reports_failure_and_success_for_the_actual_pull(self):
        repo = self.backend.projects / "project"
        subprocess.run(["git", "init", "-q", "-b", "main", str(repo)], check=True)
        body = {"step": "clone", "mode": "run", "repo": "learner/project", "profile": {"autonomy": "direct"}}
        refresh = lambda: self.backend.wait(self.backend.start(**body))
        failed = refresh()
        self.assertEqual(failed["status"], "failed")
        self.assertIn("remote branch", failed["summary"])
        self.assertTrue(any(e["kind"] == "warn" for e in failed["events"]))
        remote = self.backend.directory / "origin.git"
        subprocess.run(["git", "init", "-q", "--bare", str(remote)], check=True)
        git = lambda *args: subprocess.run(["git", "-C", str(repo), *args], check=True, capture_output=True)
        git("-c", "user.name=Learner", "-c", "user.email=learner@example.invalid",
            "commit", "--allow-empty", "-m", "Fixture")
        git("remote", "add", "origin", str(remote))
        git("push", "-u", "origin", "main")
        self.assertEqual(refresh()["status"], "done")
        git("remote", "set-url", "origin", str(self.backend.directory / "unavailable.git"))
        self.assertEqual(refresh()["status"], "failed")
        git("remote", "set-url", "origin", str(remote))
        git("switch", "-c", "other-work")
        author = ["-c", "user.name=Learner", "-c", "user.email=learner@example.invalid"]
        git(*author, "commit", "--allow-empty", "-m", "Remote work")
        git("push", "origin", "HEAD:main")
        git("switch", "main")
        git(*author, "commit", "--allow-empty", "-m", "Local work")
        self.assertEqual(refresh()["status"], "failed")

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

    def test_device_chat_uses_installed_local_model_only(self):
        received = []
        model_info = {"model_info": {"general.architecture": "fixture"}, "capabilities": ["completion"]}

        class Model(BaseHTTPRequestHandler):
            def log_message(self, *_):
                pass

            def respond(self, body):
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.end_headers()
                self.wfile.write(json.dumps(body).encode())

            def do_GET(self):
                self.respond({"models": [{"name": "qwen3.5:4b"}]})

            def do_POST(self):
                payload = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                if self.path == "/api/show":
                    self.respond(model_info)
                elif self.path == "/api/chat":
                    received.append(payload)
                    self.respond({"message": {"content": "Check the status of the practice install."}})

        with ThreadingHTTPServer(("127.0.0.1", 0), Model) as server:
            threading.Thread(target=server.serve_forever, daemon=True).start()
            try:
                bridge = Backend(ollama_port=server.server_port)
                self.addCleanup(bridge.close)
                params = {"question": "What does this screen mean?", "context": "Quiet install"}
                self.assertEqual(bridge.api("device_tutor", params)[1]["model"], "qwen3.5:4b")
                self.assertIn("Quiet install", received[0]["messages"][1]["content"])
                self.assertNotIn("tools", received[0])
                model_info["remote_host"] = "example.com"
                self.assertEqual(bridge.api("device_tutor", {"probe": True}), (200, {"model": ""}))
                self.assertEqual(bridge.api("device_tutor", params)[0], 400)
                self.assertEqual(len(received), 1)
            finally:
                server.shutdown()

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
