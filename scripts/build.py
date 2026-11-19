#!/usr/bin/env python3
"""Synchronize portable HTML payloads and build a reproducible, blank-profile ZIP."""
import argparse
import base64
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LAUNCHERS = ("START.command", "START.sh", "STOP.command", "launcher.mjs", "README-start.txt")
NOTICES = ("LICENSE", "THIRD_PARTY_NOTICES.md")
RELEASE_FILES = ("climb-agent.mjs", "the-climb.html", "FOR-TESTERS.txt", *LAUNCHERS, *NOTICES)
EMPTY_SEED = {"profile": None, "kind": "", "done": {}, "calls": {}}


def js_json(value):
    return json.dumps(value, ensure_ascii=True).replace("</", "<\\/")


def replace_one(pattern, replacement, text):
    result, count = re.subn(pattern, lambda _: replacement, text, flags=re.S)
    if count != 1:
        raise ValueError("Expected exactly one generated payload marker")
    return result


def synchronized_html():
    text = (ROOT / "the-climb.html").read_text()
    backend = base64.b64encode((ROOT / "climb-agent.mjs").read_bytes()).decode()
    text = replace_one(r'<script type="text/plain" id="agentB64">.*?</script>',
                       '<script type="text/plain" id="agentB64">' + backend + '</script>', text)
    payloads = [{"name": "climb-agent/" + name, "data": (ROOT / name).read_text(),
                 "mode": 0o100755 if name.endswith((".command", ".sh")) else 0o100644}
                for name in (*LAUNCHERS, *NOTICES)]
    text = replace_one(r'const INSTALLER_FILES=.*?;\nconst README=',
                       "const INSTALLER_FILES=" + js_json(payloads) + ";\nconst README=", text)
    return replace_one(r'const README=.*?;\nfunction selfCopy\(\)',
                       "const README=" + js_json((ROOT / "README-start.txt").read_text()) + ";\nfunction selfCopy()", text)


def check_syntax(html):
    for name in ("climb-agent.mjs", "launcher.mjs"):
        subprocess.run(["node", "--check", str(ROOT / name)], check=True)
    for name in ("START.command", "START.sh", "STOP.command"):
        subprocess.run(["bash", "-n", str(ROOT / name)], check=True)
    match = re.search(r'<script id="climbMain">(.*?)</script>', html, re.S)
    if not match:
        raise ValueError("Main browser script is missing")
    with tempfile.TemporaryDirectory(prefix="climb-syntax-") as temp:
        script = Path(temp) / "guide.js"
        script.write_text(match[1])
        subprocess.run(["node", "--check", str(script)], check=True)


def build_zip(feedback_repo=""):
    """Write the public ZIP, or with feedback_repo the testers' ZIP that also names where suggestions go."""
    output = ROOT / "dist"
    output.mkdir(exist_ok=True)
    archive = output / ("climb-testers.zip" if feedback_repo else "climb-agent.zip")
    payloads = {name: (ROOT / name).read_bytes() for name in RELEASE_FILES}
    if feedback_repo:
        payloads["climb-config.json"] = (json.dumps({"feedbackRepo": feedback_repo}) + "\n").encode()
    payloads["README.txt"] = (ROOT / "README-start.txt").read_bytes()
    payloads["climb-seed.json"] = (json.dumps(EMPTY_SEED) + "\n").encode()
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as bundle:
        for name, content in sorted(payloads.items()):
            entry = zipfile.ZipInfo("climb-agent/" + name, date_time=(1980, 1, 1, 0, 0, 0))
            entry.create_system = 3
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o100755 if name.endswith((".command", ".sh")) else 0o100644) << 16
            bundle.writestr(entry, content)
    digest = hashlib.sha256(archive.read_bytes()).hexdigest()
    (output / (archive.name + ".sha256")).write_text(digest + "  " + archive.name + "\n")
    print("Built dist/" + archive.name + " with an empty profile and executable launchers." + (" Suggestions go to " + feedback_repo + "." if feedback_repo else ""))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Verify payload synchronization and syntax without writing files")
    parser.add_argument("--feedback-repo", default="", metavar="OWNER/NAME",
                        help="Also build dist/climb-testers.zip, whose guide offers to open a GitHub issue there")
    args = parser.parse_args()
    if args.feedback_repo and not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", args.feedback_repo):
        raise SystemExit("--feedback-repo must look like owner/name.")
    html = synchronized_html()
    if args.check:
        if html != (ROOT / "the-climb.html").read_text():
            raise SystemExit("Embedded payloads are stale. Run make build, then stage the updated HTML.")
    else:
        (ROOT / "the-climb.html").write_text(html)
    check_syntax(html)
    if args.check:
        print("Embedded payloads and JavaScript/shell syntax are valid.")
    else:
        build_zip()
        if args.feedback_repo:
            build_zip(args.feedback_repo)


if __name__ == "__main__":
    main()
