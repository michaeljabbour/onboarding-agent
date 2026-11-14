# Architecture

The Climb keeps the browser interface, local execution bridge, and process launcher separate. The runtime uses browser APIs and Node's standard library.

```mermaid
flowchart LR
    Browser[Browser guide] -->|Loopback JSON API| Bridge[Local Node agent]
    Bridge -->|Tool-free conversation| Companion[Claude Code companion]
    Bridge -->|Step-specific permissions| Actions[Claude Code or native commands]
    Companion --> Provider[Configured AI provider]
    Actions --> Provider
    Launcher[Local launcher] --> Bridge
```

## Browser guide

`the-climb.html` contains the layout, stage definitions, interview, local state, connection handling, and companion. It can be opened as a document, but agent requests require the local server. The file-to-local transfer is an explicit, bounded URL-fragment handoff with a choice when existing answers conflict.

The companion is a small persistent control. `COMPANION_MOVES` defines the three learning prompts. `companionContext()` supplies the current stage, observed checks, bounded recent messages, and up to three explicitly kept notes. The browser retains at most five kept notes and 30 recent companion messages. Notes have edit and remove controls.

The HTML also embeds the backend and installer files for its portable download. Those copies are derived from standalone sources by `scripts/build.py`. They are not independent places to implement a fix.

## Local agent

`climb-agent.mjs` serves the guide and a JSON API on loopback. It can alternatively expose the same tool definitions through MCP over standard input/output with `--mcp`.

Native checks inspect local prerequisites without a model call. Model-backed steps launch Claude Code and translate streamed events into progress, questions, plan text, and results. Run records live in memory; the usage ledger is written to the agent state directory. Restarting the bridge invalidates its in-memory run IDs.

The companion uses a dedicated working directory and launches Claude Code with tools and customization discovery disabled. Setup and project steps use their own permissions and plan validation. A selected plan must match the requested step and context before it is reused. The browser does not silently replay work after an ambiguous timeout.

Readiness distinguishes an available local server from usable Claude authentication. A readiness check is not proof that a provider will accept the next inference request.

## Launcher

`START.sh` checks prerequisites and installs a private application copy. `launcher.mjs` manages a detached process, readiness checks, local logs, and a process identity record. It reuses an existing server when appropriate and updates only an owned, idle process. `STOP.command` refuses to stop a process whose identity no longer matches.

There is no startup daemon, login item, remote service, or automatic background update channel. The launcher is invoked again after an operating-system restart.

## Packaging and public source

`make build` synchronizes embedded runtime payloads and creates a release ZIP under `dist/` with executable launcher permissions and a blank seed. A personalized browser export deliberately includes interview and progress state, so it is a private artifact and must not become a public release.

The public-file gate and tests belong under `scripts/` and `tests/`. Local research, test output, downloaded skills, and generated archives are ignored. See [AGENTS.md](../AGENTS.md) for contributor boundaries.

## Extending the learning experience

Add a small original entry to `COMPANION_MOVES` for a new teaching activity. Add a stage or step only when it has a clear user outcome and a way to verify that outcome. Keep learning feedback separate from installation checkmarks.

The teaching → practice → feedback pattern was informed by [Primer](https://github.com/wharton-generative-ai-labs/primer) and its [teachback module](https://github.com/wharton-generative-ai-labs/primer-modules/tree/main/modules/teachback-template-with-workflows). No Primer code, prompts, characters, or artwork are included. The Climb uses its own language and keeps continuity in user-selected notes. These design choices do not establish measured learning outcomes.
