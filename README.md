# Onboarding Agent

**The Climb** is a browser guide for making a first useful change with an AI coding agent. It combines a short onboarding interview, visible setup steps, and a small companion that can explain, rehearse, and review an idea with you.

```text
Show me  →  Let me try  →  Check my thinking  →  Keep this
 example     practice       specific feedback    your notes
```

Open the HTML and choose **Try a practice question** to start immediately. **This device** uses the browser’s built-in language model when it is already available for English text. The connected guide can also use an installed Ollama model (qwen3.5:4b, gemma3:4b, llama3.2:3b or qwen2.5:3b). When local AI is unavailable, the bundled field guide explains the current lesson and offers practice questions. **Connected Claude** uses the local launcher, network access and a configured Claude account or provider.

## Start

Download a release ZIP or clone this repository. Keep the runtime files together.

| Platform | Start | Requirements |
| --- | --- | --- |
| macOS | Double-click `START.command` | The launcher installs missing prerequisites and opens the connected guide. |
| Linux | Run `bash START.sh` | Bash, curl, tar, a SHA-256 tool, and a browser opener. |
| Windows | Run `node climb-agent.mjs` | Install Node.js 22+ and Claude Code first; automatic setup is not supported. |

The Mac/Linux launcher reuses Node.js 22+ and Claude Code when available. Otherwise, it downloads a checksum-verified private Node runtime and uses Anthropic's official Claude Code installer. Finish Claude sign-in if prompted. The guide opens at `http://localhost:4747/`.

On macOS, a downloaded launcher may require the normal **Open** or **Privacy & Security** approval. The ZIP is not signed or notarized. Do not disable Gatekeeper. If the shell file cannot execute, run `bash START.sh` from its folder.

After the launcher reports that the guide is ready, Terminal can close. Open `START.command` again after restarting the computer. `STOP.command` stops the installation's recorded agent. No login item, system daemon, or browser extension is installed. A manually started `node climb-agent.mjs` process needs its terminal to stay open.

Opening `the-climb.html` directly lets you read the guide, but live assistance needs the connected local page. Use **Open connected guide** to transfer answers when offered.

## A package for outside testers

`make package` builds `dist/climb-testers.zip` beside the public ZIP. It is the same guide with a blank profile, plus `climb-config.json` naming the repository that collects suggestions (the `origin` remote unless you pass `FEEDBACK_REPO=owner/name`) and `FOR-TESTERS.txt` explaining what to expect. In that guide, Suggest improvements opens a prefilled GitHub issue that the tester submits from their own account; copying the text stays available.

## What it does

- Shapes explanations and suggested steps around a short interview.
- Checks the laptop and shows setup progress in the guide.
- Offers **Ask Climb** with **Show me**, **Let me try**, and **Check my thinking**. This conversation has no computer tools.
- Keeps up to five notes you explicitly select, with edit and remove controls. The latest three can inform later replies in the same browser.
- Runs separate setup and project steps through the local agent, with their configured tools and plan checks.

The companion is for learning and guidance. Real actions use the guide's step controls. Review what a step proposes before running it. The bridge is intended for a trusted local computer, not a hosted or multi-user service.

## Develop

Runtime code uses Node's standard library and browser APIs; there are no npm runtime dependencies. Development checks and packaging also use Python 3 and Make.

```sh
make check   # syntax, embedded-file consistency, and public-file checks
make test    # isolated automated tests; no live AI calls by default
make build   # refresh embedded runtime files and build dist/climb-agent.zip
make start   # start the local guide
```

The HTML includes copies of the backend and launchers so its download button can create a portable bundle. Edit the standalone runtime files, then run `make build` to synchronize those copies. The release build uses a blank seed; a ZIP exported from a person's browser can contain their answers and must remain private.

```text
.
├── the-climb.html        Browser guide and companion
├── climb-agent.mjs       Local API, MCP interface, and step execution
├── launcher.mjs          Owned-process startup, updates, and shutdown
├── START.command        macOS entry point
├── START.sh             macOS/Linux prerequisite setup
├── STOP.command         Stop the owned installation
├── scripts/             Build and public-file checks
├── tests/               Portable, synthetic test fixtures
├── docs/                Architecture and data handling
└── .github/             Repository automation
```

Private working material, local skill installations, logs, generated archives, and personal seeds are excluded by `.gitignore`. Do not force-add them.

## Configuration

Settings use environment variables. See [README-start.txt](README-start.txt) for launcher details.

| Variable | Default / purpose |
| --- | --- |
| `CLIMB_PORT` | `4747`; use a free local port. |
| `CLIMB_WORKDIR` | `~/dev`; where project work is placed. |
| `CLIMB_REPO` | Optional `owner/name` repository. |
| `CLIMB_INSTALL_DIR` | Platform-specific private installation directory. |
| `CLIMB_STATE_DIR` | `~/.climb`; agent usage state and companion working directory. |
| `CLIMB_CLAUDE_BIN` | `claude`; executable to use. |
| `CLIMB_NODE_BIN` | Optional launcher override for Node. |
| `CLIMB_MODEL` | Optional Claude Code model override. |
| `CLIMB_DAILY_LIMIT_USD` | `25`; prevents starting another run after the recorded daily limit. |

The spending check runs before a model call; it is not a hard cap on an in-flight call. Provider billing and account limits still apply.

## Documentation and contribution

- [Architecture and extension points](docs/architecture.md)
- [Privacy and local data](docs/privacy.md)
- [Contributing](CONTRIBUTING.md)
- [Instructions for coding agents](AGENTS.md)
- [Security policy](SECURITY.md)

The learning interactions use original wording and code, informed by the teaching, practice, and feedback patterns studied in [Primer](https://github.com/wharton-generative-ai-labs/primer). Setup completion is not treated as proof of learning.

Released under the [MIT License](LICENSE).
