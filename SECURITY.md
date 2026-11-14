# Security policy

## Reporting

Use GitHub's **Security → Advisories → Report a vulnerability** for a private report when that option is enabled. Include a minimal reproduction with synthetic data and the affected version or commit. Do not submit credentials, personal files, or unredacted session logs.

If private reporting is unavailable, open an issue containing only a request for a private reporting channel. Keep exploit details and affected data out of the public issue. If a credential was exposed, revoke it through its provider rather than relying on repository deletion to remove access.

Security fixes are applied to the current development branch. Older versions do not have a separate maintenance commitment.

## Intended boundary

The agent is for one trusted user on a local computer. It listens on loopback and checks request Host, Origin when present, and the application header. These checks reduce unwanted browser requests; they are not authentication against other local software. Do not expose the port through a tunnel, reverse proxy, or public network interface.

The companion conversation disables computer tools. Other guide steps can run commands, edit files, install software, and interact with a configured repository according to that step's permissions. Model instructions and plan review are not an operating-system sandbox. Inspect proposed work and use an appropriate account and workspace.

The launcher reuses installed prerequisites or downloads a private Node runtime with a pinned checksum. Claude Code is installed through its official installer when missing. The Mac archive is unsigned and not notarized; use the operating system's normal approval flow rather than disabling protections.

## Sensitive data

Browser state, personalized downloads, provider sessions, command output, startup logs, and generated notes can contain personal or project information. The application is not a general-purpose secret redactor. Keep these files out of public issues and source control. See [privacy and local data](docs/privacy.md) for storage locations and cleanup boundaries.
