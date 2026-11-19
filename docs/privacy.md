# Privacy and local data

The published source and release seed contain no prefilled personal profile. Information entered while using the guide can be personal or confidential. It is not automatically made public, but it may be stored locally or sent to the configured AI provider as described below.

## Data flow

Device mode uses an available browser model, a supported model already installed in Ollama on this computer, or the bundled field guide. The launcher forwards local model questions and context to 127.0.0.1. It does not download models. Selecting Connected Claude sends the request, guide context and recent conversation to the local agent and then to the configured provider. This context may include earlier device-mode messages.

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

The in-guide terminal is a real shell on this computer. What you type there, including a password at a prompt that hides it, travels from the browser tab to the shell over the loopback connection. The bridge does not store or log keystrokes. It keeps up to 256 KB of recent terminal output in memory so a reloaded tab can show it again. That output includes anything the terminal displayed, such as a command you typed at a visible prompt. Choosing Close terminal discards it at once. When a shell ends another way, the last output stays readable for about a minute so the page can show how it ended, and everything is discarded when the bridge stops. The browser tab remembers only the terminal's identifier, in session storage, so a reload can reattach. Commands you run there act with your own account's permissions.

Run events are held in the bridge's memory until it stops. Events can include model text, questions, file names, command snippets, and errors. They are returned to the local browser. The code sanitizes selected authentication failures, but it is not a comprehensive filter for sensitive output. Do not put passwords or tokens into the guide's questions, notes or chat. A password prompt inside the in-guide terminal is the one place a password belongs.

## Downloads and sharing

**Download for Mac** in a running personalized guide creates a ZIP containing `climb-seed.json` with the current interview, project idea and progress state. Treat that ZIP as private. The file-to-local transfer places selected answers in the URL fragment for the local browser to import; do not share that transfer link.

Public releases are built from source with a blank seed. Working files, personalized seeds, logs, exported archives, and local skill installations are excluded by `.gitignore`. Ignore rules do not remove a file that was already committed and do not inspect screenshots or text for accidental disclosures; review changes before publishing.

## Suggesting improvements

**Suggest improvements** builds a draft in the browser from the role and experience categories chosen in the interview, stage progress, steps that took more than one run in the current session, and questions typed into step help or the chat. Known personal values (name, GitHub usernames, repository, project idea, role text and notes) and patterns that look like email addresses, links, home-folder paths, tokens and long numbers are replaced with placeholders. This replacement is a best effort, not a guarantee; the person is asked to read and edit the text first.

Nothing is sent automatically. **Copy the text** places the draft on the clipboard. When a feedback repository is configured (`FEEDBACK_REPO` in the guide or `CLIMB_FEEDBACK_REPO` for the bridge), **Open a GitHub issue with this text** opens GitHub's new-issue page in a new tab with the draft in the address, so it can appear in browser history. The issue exists only after the person presses Submit on GitHub. It is posted from their own GitHub account and is visible, with their username, to anyone who can see that repository. The draft is kept in the guide's browser storage with the other answers.

## Clearing data

- Use **Clear chat** to remove the companion's saved recent messages. This does not remove kept notes or provider-side sessions.
- Remove individual notes from **Things you kept**. Clear the site's browser storage to remove interview answers, drafts, checklist state, and companion storage for that origin.
- Remove a personalized installed `app/climb-seed.json` as well if you want to prevent those initial answers from being imported again after clearing browser storage.
- Stop the owned agent with `STOP.command` before removing its installation directory. This does not delete projects, browser state, the separate `~/.climb` directory, or Claude Code data.
- Review the marked sections in personal agent instruction files before removing them. Preserve unrelated instructions.
- Manage provider and Claude Code session retention through their own controls. Clearing the guide does not clear those systems.

The application is for a trusted local computer. Other software running as the same user may be able to read local files, process arguments, or browser data. See [SECURITY.md](../SECURITY.md) for the local service boundary.
