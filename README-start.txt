The Climb — your browser companion

On a Mac
1. Extract the entire ZIP.
2. Double-click START.command.
3. If Claude needs sign-in, finish the browser sign-in. The connected guide opens itself.

You can close Terminal after it says the guide is ready. Next time, double-click START.command again. It reuses the running agent. STOP.command stops only the copy started by this launcher.

If macOS asks whether you trust a downloaded launcher, review the file and use macOS's normal Open/Privacy & Security approval. This ZIP is not a signed or notarized Mac app. Do not turn off Gatekeeper. If double-click reports a permission problem, open Terminal, type bash followed by a space, drag START.sh into Terminal, and press Return.

On Linux
Run: bash START.sh
Node.js 22+ is reused when installed. If missing, the launcher installs a private copy from nodejs.org after checking its pinned SHA-256. Claude Code is reused or installed through Anthropic's official installer. No administrator access is needed. Linux needs bash, curl, tar, a SHA-256 tool, and a browser opener; macOS includes these.

On Windows
The automatic launcher is not supported yet. Install Node.js 22+ and Claude Code, then run node climb-agent.mjs from this folder. This opens the same connected browser guide. Keep that terminal open.

Where things live
Mac: ~/Library/Application Support/The Climb
Linux: ~/.local/share/the-climb (or your XDG_DATA_HOME)
App files: app/
Startup logs: logs/agent-4747.log
Answers: your browser's local storage; the initial interview seed is kept beside the installed guide.

This does not start at login. After a restart, open START.command again. It installs no browser extension. The companion's interface runs locally; Claude still needs network access and a supported account or configured provider. Existing account and provider settings are kept.

Settings (optional)
CLIMB_PORT=4747
CLIMB_INSTALL_DIR=/your/private/install/folder
CLIMB_NODE_BIN=/path/to/node
CLIMB_CLAUDE_BIN=/path/to/claude
CLIMB_REPO=owner/name
CLIMB_WORKDIR=/path/to/projects
CLIMB_DAILY_LIMIT_USD=25

To remove the launcher installation, run STOP.command, then remove its The Climb folder. This leaves Claude Code, your projects, ~/.climb history, and browser answers alone.
