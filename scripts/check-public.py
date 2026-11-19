#!/usr/bin/env python3
"""Inspect the Git index and optional release ZIP without printing sensitive matches.

This is a publication guard, not a guarantee that arbitrary personal data can be
recognized. Review the tree and run an independent secret scanner before release.
"""
import argparse
import base64
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import zipfile

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    ".editorconfig", ".gitattributes", ".gitignore", "README.md", "AGENTS.md",
    "CONTRIBUTING.md", "SECURITY.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "Makefile",
    "the-climb.html", "climb-agent.mjs", "launcher.mjs", "START.command", "START.sh",
    "STOP.command", "README-start.txt", "FOR-TESTERS.txt",
}
PUBLIC_DIRS = {"docs", "scripts", "tests", ".github"}
PRIVATE_PARTS = {"work", ".agents", ".claude", ".taste-skill", "node_modules",
                 ".venv", ".climb", "climb-notes", "logs", "__pycache__", ".git"}
PRIVATE_NAMES = {"climb-seed.json", ".DS_Store", "skills-lock.json", ".env"}
PRIVATE_SUFFIXES = {".zip", ".log", ".jsonl", ".pid", ".pem", ".key", ".pyc"}
RULES = {
    "absolute personal home path": re.compile(r"(?:/Users/|/home/)[A-Za-z0-9_.-]+|[A-Z]:\\\\?Users\\\\?[A-Za-z0-9_.-]+"),
    "private key": re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH |DSA )?PRIVATE KEY-----"),
    "credential token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{30,}|github_pat_[A-Za-z0-9_]{35,}|sk-(?:ant-[A-Za-z0-9-]+|proj-[A-Za-z0-9_-]+|[A-Za-z0-9]{32,}))\b"),
    "credential in URL": re.compile(r"https?://[^\s/:<>]+:[^\s/@<>]+@"),
}
EMAIL = re.compile(r"\b[A-Za-z0-9.!#$%&'*+/=?^_`{|}~-]+@([A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+)\b")


def public_path(name):
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts:
        return False
    if set(path.parts) & PRIVATE_PARTS or path.name in PRIVATE_NAMES:
        return False
    if path.suffix.lower() in PRIVATE_SUFFIXES or path.name.startswith(".env."):
        return False
    return name in ROOT_FILES or (len(path.parts) > 1 and path.parts[0] in PUBLIC_DIRS)


def text_issues(name, data, deny_terms=()):
    issues = []
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        return [f"{name}: unexpected binary file; review before publishing"]
    for label, pattern in RULES.items():
        for match in pattern.finditer(text):
            line = text.count("\n", 0, match.start()) + 1
            issues.append(f"{name}:{line}: {label}")
    for match in EMAIL.finditer(text):
        domain = match[1].lower()
        if domain not in {"example.com", "example.org", "example.net"} and not domain.endswith((".invalid", ".test")):
            line = text.count("\n", 0, match.start()) + 1
            issues.append(f"{name}:{line}: non-example email address")
    for term in deny_terms:
        if term.casefold() in text.casefold():
            issues.append(f"{name}: private review term matched (value withheld)")
    # Self-contained downloads carry code inside the HTML. Inspect the decoded
    # payload too, even if it currently matches the standalone source.
    if name.endswith(".html"):
        for match in re.finditer(r'<script[^>]*id="agentB64"[^>]*>(.*?)</script>', text, re.S):
            try:
                decoded = base64.b64decode(match[1].strip(), validate=True)
                issues.extend(text_issues(name + " [embedded backend]", decoded, deny_terms))
            except ValueError:
                issues.append(f"{name}: invalid embedded backend encoding")
        match = re.search(r'const INSTALLER_FILES=(.*?);\nconst README=', text, re.S)
        if match:
            try:
                for entry in json.loads(match[1].replace("<\\/", "</")):
                    issues.extend(text_issues(name + " [embedded installer]", entry["data"].encode(), deny_terms))
            except (ValueError, KeyError, TypeError):
                issues.append(f"{name}: invalid embedded installer data")
    return issues


def indexed_files():
    result = subprocess.run(["git", "ls-files", "--stage", "-z"], cwd=ROOT,
                            check=True, capture_output=True)
    for entry in result.stdout.split(b"\0"):
        if not entry:
            continue
        metadata, name = entry.split(b"\t", 1)
        mode, blob, stage = metadata.decode().split()
        yield name.decode(), mode, stage, subprocess.check_output(["git", "cat-file", "blob", blob], cwd=ROOT)


def release_issues(archive, deny_terms=()):
    expected = {"climb-agent/" + name for name in (
        "climb-agent.mjs", "the-climb.html", "launcher.mjs", "START.command", "START.sh",
        "STOP.command", "README-start.txt", "README.txt", "FOR-TESTERS.txt", "LICENSE", "THIRD_PARTY_NOTICES.md", "climb-seed.json")}
    issues = []
    with zipfile.ZipFile(archive) as bundle:
        if set(bundle.namelist()) != expected or len(bundle.namelist()) != len(expected):
            issues.append("release: archive file list differs from the reviewed allowlist")
        if bundle.testzip():
            issues.append("release: ZIP integrity check failed")
        for entry in bundle.infolist():
            if entry.filename not in expected:
                continue
            data = bundle.read(entry)
            if entry.filename.endswith("/climb-seed.json"):
                try:
                    empty = {"profile": None, "kind": "", "done": {}, "calls": {}}
                    if json.loads(data) != empty:
                        issues.append("release: personalized seed; do not publish this archive")
                except ValueError:
                    issues.append("release: invalid seed")
            else:
                issues.extend(text_issues(entry.filename, data, deny_terms))
            mode = entry.external_attr >> 16
            wanted = 0o100755 if entry.filename.endswith((".command", ".sh")) else 0o100644
            if mode != wanted:
                issues.append(f"{entry.filename}: unexpected archive permissions")
    return issues


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--release", type=Path, help="Also inspect a generated public release archive")
    args = parser.parse_args()
    deny_terms = tuple(term.strip() for term in os.environ.get("PUBLIC_DENY_TERMS", "").split(",") if term.strip())
    issues = []
    count = 0
    for name, mode, stage, data in indexed_files():
        count += 1
        if not public_path(name):
            issues.append(f"{name}: file is outside the public source allowlist")
        if mode not in {"100644", "100755"} or stage != "0":
            issues.append(f"{name}: symlink, submodule, or unresolved index entry")
        issues.extend(text_issues(name, data, deny_terms))
    if not count:
        issues.append("No staged/tracked files. Stage the reviewed public files before checking.")
    if args.release:
        issues.extend(release_issues(args.release, deny_terms))
    if issues:
        print("Publication check failed (matched values are withheld):")
        print("\n".join(sorted(set(issues))))
        raise SystemExit(1)
    print(f"Publication check passed for {count} indexed files" + (" and the blank-profile release." if args.release else "."))


if __name__ == "__main__":
    main()
