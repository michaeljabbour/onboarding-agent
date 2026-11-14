# Contributing

Contributions should make it easier for someone to understand, perform, and verify useful work with an agent.

## Local workflow

1. Create a branch for one focused change.
2. Read [AGENTS.md](AGENTS.md) and the relevant [architecture notes](docs/architecture.md).
3. Use Node.js 22+, Python 3, and Make for development. No npm install is needed for the runtime.
4. Run `make build` after editing a backend or launcher file, then `make check` and `make test`.
5. For browser changes, check the actual interaction at desktop and narrow widths, including keyboard use. Optional browser tooling is separate from the standard-library test suite.
6. Open a pull request describing the problem, resulting behavior, and verification. Mention limitations such as mocked provider responses or untested operating systems.

Keep UI copy short and concrete. A completed setup step is not evidence of understanding. Learning activities should invite an attempt and offer feedback grounded in what the person actually said.

## Tests and examples

Use synthetic data and temporary directories. Automated checks must not send live model requests, read real authentication state, modify global agent notes, install prerequisites, or stop a user's server. Changes to safety boundaries, state recovery, and packaging need focused regression coverage.

Do not include private screenshots, exported browser state, logs, home paths, names, or credentials in issues or pull requests. The release ZIP must come from `make build`, which supplies a blank seed. Do not publish a ZIP downloaded from a personalized running guide.

## Reporting a bug

Include the operating system, Node version, the step you used, what you expected, and what happened. Provide the smallest reproducible example with invented inputs. Review all logs before attaching them; they can contain paths, project details, and model output.

For a vulnerability or accidental secret exposure, follow [SECURITY.md](SECURITY.md) instead of posting sensitive details publicly.

Contributions are accepted under the repository's [MIT License](LICENSE). Preserve applicable third-party notices when adding code or assets from another source.
