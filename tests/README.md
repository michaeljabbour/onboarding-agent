# Tests

Run the standard-library suite from the repository root:

```sh
python3 -m unittest discover -s tests -p 'test_*.py'
```

Node.js 22 or newer and a POSIX process environment (macOS or Linux) are required for the runtime tests. These tests exercise the actual backend and launcher over disposable loopback ports. Every backend uses a temporary home, project folder, state directory, and synthetic Claude executable. Test processes and files are cleaned up on completion. No account authentication, model requests, software installation, or project changes are performed.

Coverage includes tool-free companion launch settings, sanitized readiness, origin and host restrictions, conversation context, cumulative usage accounting, structured error redaction, plan approval guards, cancellation, and preservation of unrelated processes by the launcher. Test data is synthetic and uses reserved example domains.

Publication tests also check the public-file allowlist, private-file rejection, decoded HTML payload inspection, redacted scan findings, empty release seeds, archive contents, and executable permissions. Fabricated sensitive patterns are assembled at runtime; temporary test archives never contain actual account data.

These checks do not prove real provider access, fresh-machine installation, browser accessibility, or macOS downloaded-software approval. Those paths need separate manual or browser checks before release. Keep any screenshots, account state, logs, and live-provider results outside the public source tree.

## Optional browser walk-through

`make test-ui` runs `tests/browser/smoke.mjs`: a first-run walk in Chromium against a disposable bridge with synthetic `claude`, `brew`, `gh` and `open`. It covers the first screen, the interview, a partial lesson answer, an install typed into the in-guide terminal, the suggestion issue link, phone-width overflow and the file copy. It needs Playwright, which this project does not depend on; without it the target prints a notice and passes. Point `CLIMB_PLAYWRIGHT` at a Playwright module folder to run it. A guard blocks any real installer command from reaching the shell.
