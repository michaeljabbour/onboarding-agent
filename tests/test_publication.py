"""Publication guard regressions using synthetic content and temporary archives."""
import base64
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile


ROOT = Path(__file__).resolve().parents[1]


def load_script(filename, module_name):
    spec = importlib.util.spec_from_file_location(module_name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PUBLIC = load_script("check-public.py", "publication_guard")
BUILD = load_script("build.py", "release_builder")
EMPTY_SEED = {"profile": None, "kind": "", "done": {}, "calls": {}}
RELEASE_NAMES = (
    "climb-agent.mjs", "the-climb.html", "launcher.mjs", "START.command", "START.sh",
    "STOP.command", "README-start.txt", "README.txt", "FOR-TESTERS.txt", "LICENSE",
    "THIRD_PARTY_NOTICES.md", "climb-seed.json",
)


class PublicationTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="climb-publication-test-")
        self.addCleanup(self.temp.cleanup)
        self.archive = Path(self.temp.name) / "fixture.zip"

    def archive_issues(self, seed=None, extra=None, missing=None, mode=None, duplicate=None):
        entries = [("climb-agent/" + name, b"Synthetic release content.\n")
                   for name in RELEASE_NAMES if name != missing]
        entries = [(name, json.dumps(EMPTY_SEED if seed is None else seed).encode()
                    if name.endswith("/climb-seed.json") else data) for name, data in entries]
        if extra:
            entries.append((extra, b"Synthetic extra file.\n"))
        if duplicate:
            entries.append(("climb-agent/" + duplicate, b"Synthetic duplicate.\n"))
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", UserWarning)
            with zipfile.ZipFile(self.archive, "w") as bundle:
                for name, data in entries:
                    entry = zipfile.ZipInfo(name)
                    entry.create_system = 3
                    expected_mode = 0o100755 if name.endswith((".command", ".sh")) else 0o100644
                    entry.external_attr = (mode if mode is not None else expected_mode) << 16
                    bundle.writestr(entry, data)
        return PUBLIC.release_issues(self.archive)

    def test_public_paths_allow_source_but_reject_forced_private_files(self):
        for name in ["README.md", "AGENTS.md", "docs/privacy.md", "scripts/build.py",
                     "tests/test_publication.py", ".github/workflows/check.yml"]:
            with self.subTest(allowed=name):
                self.assertTrue(PUBLIC.public_path(name))
        for name in ["work/report.md", ".agents/notes.md", ".env", "docs/.env.local",
                     "tests/__pycache__/module.pyc", "docs/logs/output.txt",
                     "climb-seed.json", "scripts/credentials.key", "docs/download.zip",
                     "docs/../private.txt", "/outside.txt", "unexpected.txt"]:
            with self.subTest(rejected=name):
                self.assertFalse(PUBLIC.public_path(name))

    def test_generic_examples_and_reserved_addresses_are_allowed(self):
        content = "\n".join(["Example User", "example/project", "~/dev",
                              "fixture@example.invalid", "sample@example.com"])
        self.assertEqual(PUBLIC.text_issues("docs/example.md", content.encode()), [])

    def test_sensitive_patterns_are_reported_without_echoing_values(self):
        # Assemble fabricated matches so this regression file is safe to publish.
        cases = [
            ("gh" + "p_" + "x" * 36, "credential token"),
            ("/" + "Users" + "/" + "example-person" + "/dev", "absolute personal home path"),
            ("person" + "@" + "mailbox" + ".example", "non-example email address"),
            ("-----" + "BEGIN " + "PRIVATE KEY" + "-----", "private key"),
            ("https://" + "example-user" + ":" + "example-password" + "@example.invalid", "credential in URL"),
        ]
        for value, label in cases:
            with self.subTest(label=label):
                issues = PUBLIC.text_issues("docs/fixture.md", value.encode())
                self.assertTrue(any(label in issue for issue in issues))
                self.assertTrue(all(value not in issue for issue in issues))
        marker = "Private" + "Review" + "Marker"
        issues = PUBLIC.text_issues("docs/fixture.md", marker.upper().encode(), [marker.lower()])
        self.assertTrue(any("private review term" in issue for issue in issues))
        self.assertNotIn(marker.lower(), " ".join(issues).lower())

    def test_encoded_backend_and_installer_payloads_are_inspected(self):
        token = "gh" + "p_" + "z" * 36
        encoded = base64.b64encode(token.encode()).decode()
        backend = '<script type="text/plain" id="agentB64">' + encoded + '</script>'
        issues = PUBLIC.text_issues("the-climb.html", backend.encode())
        self.assertTrue(any("[embedded backend]" in issue and "credential token" in issue for issue in issues))
        installer = "const INSTALLER_FILES=" + json.dumps([{"data": token}]) + ";\nconst README="
        issues = PUBLIC.text_issues("the-climb.html", installer.encode())
        self.assertTrue(any("[embedded installer]" in issue and "credential token" in issue for issue in issues))
        invalid = '<script id="agentB64">**invalid**</script>'
        self.assertTrue(any("invalid embedded backend" in issue
                            for issue in PUBLIC.text_issues("the-climb.html", invalid.encode())))

    def test_release_builder_seed_and_clean_archive_are_empty(self):
        self.assertEqual(BUILD.EMPTY_SEED, EMPTY_SEED)
        self.assertEqual(self.archive_issues(), [])

    def test_release_rejects_saved_answers_and_progress(self):
        for seed in [dict(EMPTY_SEED, profile={"name": "Example User"}),
                     dict(EMPTY_SEED, done={"setup": True}),
                     dict(EMPTY_SEED, calls={"companion": ["Synthetic conversation"]})]:
            with self.subTest(seed=seed):
                self.assertIn("release: personalized seed; do not publish this archive",
                              self.archive_issues(seed=seed))

    def test_release_enforces_allowlist_uniqueness_and_permissions(self):
        for changes in [{"extra": "climb-agent/private-notes.txt"},
                        {"extra": "../outside.txt"}, {"missing": "LICENSE"},
                        {"duplicate": "README.txt"}]:
            with self.subTest(changes=changes):
                self.assertTrue(any("allowlist" in issue for issue in self.archive_issues(**changes)))
        for mode in [0o100600, 0o120777]:
            with self.subTest(mode=mode):
                self.assertTrue(any("permissions" in issue for issue in self.archive_issues(mode=mode)))


if __name__ == "__main__":
    unittest.main()
