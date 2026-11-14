#!/bin/bash
set -euo pipefail
CLIMB_LAUNCHER_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
case "$(uname -s)" in
  Darwin) CLIMB_DEFAULT_DIR="$HOME/Library/Application Support/The Climb" ;;
  *) CLIMB_DEFAULT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/the-climb" ;;
esac
export CLIMB_INSTALL_DIR="${CLIMB_INSTALL_DIR:-$CLIMB_DEFAULT_DIR}"
export PATH="$CLIMB_INSTALL_DIR/runtime/bin:$HOME/.local/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
CLIMB_NODE="${CLIMB_NODE_BIN:-$(command -v node || true)}"
if [ -z "$CLIMB_NODE" ]; then printf 'Node.js is not available. The Climb may already be stopped.\n'; exit 1; fi
exec "$CLIMB_NODE" "$CLIMB_LAUNCHER_DIR/launcher.mjs" stop
