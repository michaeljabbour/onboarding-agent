# Privacy and local data

The published source and release seed contain no prefilled personal profile. Information entered while using the guide can be personal or confidential. It is not automatically made public, but it may be stored locally or sent to the configured AI provider as described below.

## Data flow

The browser sends requests to the local Node agent. For AI replies, the agent passes the relevant request and context to Claude Code, which uses the account or provider already configured on the computer. The app does not provide offline model inference.

Companion context can include interview facts, the current stage, observed laptop checks, recent conversation, and up to three kept notes. Action steps may let Claude Code read relevant project files and run commands. Provider processing and retention follow that provider's account settings and policies. Claude Code can also retain its own session data independently of this application.

The application has no analytics integration or remote application database. This does not mean that all activity stays on the device: AI inference, prerequisite downloads, sign-in, and requested repository actions use external services.

## What is retained

| Location | Data |
| --- | --- |
| Browser local storage for the guide's origin | Interview answers, checklist state, last stage, input drafts, recent companion messages, and chosen notes. Different ports and browsers have separate storage. |
| Installed `app/climb-seed.json`, if supplied | Initial interview and progress state from a personalized download. Later launches preserve an existing seed. Public release builds use a blank seed. |
| `~/.climb` or `CLIMB_STATE_DIR` | Daily usage ledger and the companion working directory. Claude Code manages any associated session records separately. |
| Installation `logs/` | Agent startup and process output. This can include local paths and error details. |
| Installation process record | Process ID, start identity, executable path, and local port used to recognize the owned process. |
| Personal agent instruction files | Selected teaching/preferences steps can write marked sections into `~/.claude/CLAUDE.md` and, when present, `~/.codex/AGENTS.md`. These are separate from companion notes. |
| Project workspace and `climb-notes/` | Files created by explicitly selected project or learning steps, such as an application tour. |

Mac installations default to `~/Library/Application Support/The Climb`; Linux uses the `the-climb` directory under `XDG_DATA_HOME`, or `~/.local/share` when unset.

Run events are held in the bridge's memory until it stops. Events can include model text, questions, file names, command snippets, and errors. They are returned to the local browser. The code sanitizes selected authentication failures, but it is not a comprehensive filter for sensitive output. Do not put passwords or tokens into the guide.

## Downloads and sharing

**Download for Mac** in a running personalized guide creates a ZIP containing `climb-seed.json` with the current interview and progress state. Treat that ZIP as private. The file-to-local transfer places selected answers in the URL fragment for the local browser to import; do not share that transfer link.

Public releases are built from source with a blank seed. Working files, personalized seeds, logs, exported archives, and local skill installations are excluded by `.gitignore`. Ignore rules do not remove a file that was already committed and do not inspect screenshots or text for accidental disclosures; review changes before publishing.

## Clearing data

- Use **Clear chat** to remove the companion's saved recent messages. This does not remove kept notes or provider-side sessions.
- Remove individual notes from **Things you kept**. Clear the site's browser storage to remove interview answers, drafts, checklist state, and companion storage for that origin.
- Remove a personalized installed `app/climb-seed.json` as well if you want to prevent those initial answers from being imported again after clearing browser storage.
- Stop the owned agent with `STOP.command` before removing its installation directory. This does not delete projects, browser state, the separate `~/.climb` directory, or Claude Code data.
- Review the marked sections in personal agent instruction files before removing them. Preserve unrelated instructions.
- Manage provider and Claude Code session retention through their own controls. Clearing the guide does not clear those systems.

The application is for a trusted local computer. Other software running as the same user may be able to read local files, process arguments, or browser data. See [SECURITY.md](../SECURITY.md) for the local service boundary.
