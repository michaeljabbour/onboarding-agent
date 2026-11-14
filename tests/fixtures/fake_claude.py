#!/usr/bin/env python3
"""A synthetic Claude CLI. Never reads account state or calls a provider."""
import json
import os
from pathlib import Path
import sys
import time


args = sys.argv[1:]
with Path(os.environ["FIXTURE_CALLS"]).open("a", encoding="utf-8") as stream:
    stream.write(json.dumps({"args": args, "cwd": os.getcwd()}) + "\n")

if args == ["--version"]:
    if os.environ.get("FIXTURE_AUTH") == "missing":
        sys.exit(1)
    print("2.1.0 (test fixture)")
    sys.exit(0)

if args == ["auth", "status"]:
    state = os.environ.get("FIXTURE_AUTH", "signed-in")
    if state == "unknown":
        print("Unrecognized fixture authentication response")
        sys.exit(1)
    print(json.dumps({"loggedIn": state != "signed-out",
                      "email": "fixture@example.invalid",
                      "apiKey": "synthetic-credential-marker"}))
    sys.exit(0 if state != "signed-out" else 1)

if "-p" not in args:
    sys.exit(98)

prompt = args[args.index("-p") + 1]
resume = args[args.index("--resume") + 1] if "--resume" in args else None
session = resume or "fixture-session-" + str(os.getpid())
print(json.dumps({"type": "system", "session_id": session}), flush=True)

if "FIXTURE_SLOW" in prompt:
    time.sleep(15)

if "FIXTURE_AUTH_ERROR" in prompt:
    print(json.dumps({"type": "result", "subtype": "error_during_execution",
                      "is_error": True, "session_id": session, "total_cost_usd": 0,
                      "result": "Invalid API key synthetic-credential-marker for fixture@example.invalid"}), flush=True)
    sys.exit(1)

if "FIXTURE_NO_COST" in prompt:
    print(json.dumps({"type": "result", "subtype": "error_during_execution",
                      "is_error": True, "session_id": session,
                      "result": "Temporary overloaded service"}), flush=True)
    sys.exit(1)

print(json.dumps({"type": "assistant", "session_id": session,
                  "message": {"content": [{"type": "text", "text": "The fixture companion replied."}]}}), flush=True)
print(json.dumps({"type": "result", "subtype": "success", "is_error": False,
                  "session_id": session, "total_cost_usd": 0.07 if resume else 0.05}), flush=True)
