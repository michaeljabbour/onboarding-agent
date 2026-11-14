#!/bin/bash
# Install only what is missing, then open the connected guide.
set -euo pipefail
umask 077

CLIMB_SOURCE_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
CLIMB_SYSTEM="$(uname -s)"
case "$CLIMB_SYSTEM" in
  Darwin) CLIMB_DEFAULT_DIR="$HOME/Library/Application Support/The Climb" ;;
  Linux) CLIMB_DEFAULT_DIR="${XDG_DATA_HOME:-$HOME/.local/share}/the-climb" ;;
  *) printf 'This launcher supports macOS and Linux. On Windows, run node climb-agent.mjs after installing Node.js and Claude Code.\n' >&2; exit 1 ;;
esac
CLIMB_INSTALL_DIR="${CLIMB_INSTALL_DIR:-$CLIMB_DEFAULT_DIR}"
CLIMB_PORT="${CLIMB_PORT:-4747}"
export CLIMB_INSTALL_DIR CLIMB_PORT
case "$CLIMB_PORT" in ''|*[!0-9]*) printf 'CLIMB_PORT must be a port number.\n' >&2; exit 1 ;; esac
if [ "$CLIMB_PORT" -lt 1024 ] || [ "$CLIMB_PORT" -gt 65535 ]; then printf 'Use a port from 1024 to 65535.\n' >&2; exit 1; fi
mkdir -p "$CLIMB_INSTALL_DIR" "$CLIMB_INSTALL_DIR/logs"
CLIMB_INSTALL_DIR="$(cd -- "$CLIMB_INSTALL_DIR" && pwd -P)"
export CLIMB_INSTALL_DIR
export PATH="$HOME/.local/bin:$CLIMB_INSTALL_DIR/runtime/bin:/opt/homebrew/bin:/usr/local/bin:$PATH"
CLIMB_TEMP=""
cleanup() { [ -z "$CLIMB_TEMP" ] || rm -rf -- "$CLIMB_TEMP"; }
trap cleanup EXIT
fail() {
  printf '\nThe Climb could not start: %s\n' "$1" >&2
  printf 'You can run START.command again after fixing this. Logs: %s/logs\n' "$CLIMB_INSTALL_DIR" >&2
  if [ -t 0 ] && [ "${CLIMB_NONINTERACTIVE:-0}" != 1 ]; then read -r -p 'Press Return to close. ' _climb_close; fi
  exit 1
}
trap 'fail "Setup stopped at line $LINENO. Check the message above."' ERR

printf '\nThe Climb — opening your browser companion\n\n'
for CLIMB_FILE in climb-agent.mjs the-climb.html launcher.mjs START.sh START.command STOP.command; do
  [ -f "$CLIMB_SOURCE_DIR/$CLIMB_FILE" ] || fail "Keep $CLIMB_FILE beside START.command. Extract the whole ZIP first."
done

CLIMB_NODE="${CLIMB_NODE_BIN:-$(command -v node || true)}"
if [ -z "$CLIMB_NODE" ] || ! "$CLIMB_NODE" -e 'process.exit(Number(process.versions.node.split(".")[0]) >= 22 ? 0 : 1)' >/dev/null 2>&1; then
  [ "${CLIMB_NO_DOWNLOADS:-0}" != 1 ] || fail 'Node.js 22 or newer is missing; downloads are disabled.'
  printf 'Installing a private copy of Node.js. No administrator password needed.\n'
  CLIMB_NODE_VERSION='v22.23.5'
  case "$CLIMB_SYSTEM/$(uname -m)" in
    Darwin/arm64) CLIMB_NODE_ARCH='darwin-arm64.tar.gz'; CLIMB_NODE_SHA='e7131995759b61a0170b646010d2ad35a5d37b4cb0d471f3e8317eac6f742f3d' ;;
    Darwin/x86_64) CLIMB_NODE_ARCH='darwin-x64.tar.gz'; CLIMB_NODE_SHA='c53383238206b9ae4db23c5d8a63645e2e753bec8ab51a49cc81939aa64e9422' ;;
    Linux/aarch64|Linux/arm64) CLIMB_NODE_ARCH='linux-arm64.tar.xz'; CLIMB_NODE_SHA='2babb9eb5264860d540849f4b064a6fbdebcdc323657d9d382ce23d313fd5e09' ;;
    Linux/x86_64) CLIMB_NODE_ARCH='linux-x64.tar.xz'; CLIMB_NODE_SHA='cdeb8670a0c81f51b4dc4ac61919f9b1ad917b304bf8221eb939570663d240f8' ;;
    *) fail 'This processor needs a manual Node.js 22+ installation from nodejs.org.' ;;
  esac
  CLIMB_TEMP="$(mktemp -d "$CLIMB_INSTALL_DIR/.setup.XXXXXX")"
  CLIMB_ARCHIVE="node-$CLIMB_NODE_VERSION-$CLIMB_NODE_ARCH"
  curl --fail --location --proto '=https' --tlsv1.2 --retry 2 --connect-timeout 15 --max-time 300 "https://nodejs.org/dist/$CLIMB_NODE_VERSION/$CLIMB_ARCHIVE" -o "$CLIMB_TEMP/$CLIMB_ARCHIVE"
  if command -v shasum >/dev/null 2>&1; then
    CLIMB_ACTUAL_SHA="$(shasum -a 256 "$CLIMB_TEMP/$CLIMB_ARCHIVE" | awk '{print $1}')"
  elif command -v sha256sum >/dev/null 2>&1; then
    CLIMB_ACTUAL_SHA="$(sha256sum "$CLIMB_TEMP/$CLIMB_ARCHIVE" | awk '{print $1}')"
  else fail 'A SHA-256 checker is needed (shasum or sha256sum).'; fi
  [ "$CLIMB_ACTUAL_SHA" = "$CLIMB_NODE_SHA" ] || fail 'The Node.js download did not match its official checksum. Nothing was installed.'
  mkdir "$CLIMB_TEMP/runtime"
  tar -xf "$CLIMB_TEMP/$CLIMB_ARCHIVE" --strip-components=1 -C "$CLIMB_TEMP/runtime"
  "$CLIMB_TEMP/runtime/bin/node" --version
  # Move an existing private runtime aside; never touch system Node.
  if [ -d "$CLIMB_INSTALL_DIR/runtime" ]; then mv "$CLIMB_INSTALL_DIR/runtime" "$CLIMB_TEMP/previous-runtime"; fi
  mv "$CLIMB_TEMP/runtime" "$CLIMB_INSTALL_DIR/runtime"
  CLIMB_NODE="$CLIMB_INSTALL_DIR/runtime/bin/node"
fi
CLIMB_NODE="$("$CLIMB_NODE" -p 'process.execPath')"
export CLIMB_NODE_BIN="$CLIMB_NODE"

# Reuse a connected agent before any new install or sign-in prompts.
CLIMB_EXISTING_STATUS=0
"$CLIMB_NODE" "$CLIMB_SOURCE_DIR/launcher.mjs" existing || CLIMB_EXISTING_STATUS=$?
case "$CLIMB_EXISTING_STATUS" in
  0) exit 0 ;;
  10) : ;;
  11) : ;;
  *) fail 'The selected local port cannot be used. See the message above.' ;;
esac

CLIMB_CLAUDE="${CLIMB_CLAUDE_BIN:-$(command -v claude || true)}"
if [ -z "$CLIMB_CLAUDE" ] || ! "$CLIMB_CLAUDE" --version >/dev/null 2>&1; then
  [ "${CLIMB_NO_DOWNLOADS:-0}" != 1 ] || fail 'Claude Code is missing; downloads are disabled.'
  printf 'Installing Claude Code with its official installer.\n'
  [ -n "$CLIMB_TEMP" ] || CLIMB_TEMP="$(mktemp -d "$CLIMB_INSTALL_DIR/.setup.XXXXXX")"
  curl --fail --location --proto '=https' --tlsv1.2 --retry 2 --connect-timeout 15 --max-time 120 https://claude.ai/install.sh -o "$CLIMB_TEMP/claude-install.sh"
  /bin/bash "$CLIMB_TEMP/claude-install.sh" stable
  CLIMB_CLAUDE="$(command -v claude || true)"
  [ -n "$CLIMB_CLAUDE" ] && "$CLIMB_CLAUDE" --version >/dev/null 2>&1 || fail 'Claude Code did not finish installing. Run START.command again or see https://code.claude.com/docs/en/setup.'
fi
export CLIMB_CLAUDE_BIN="$CLIMB_CLAUDE"
if ! "$CLIMB_CLAUDE" auth status >/dev/null 2>&1; then
  [ "${CLIMB_NONINTERACTIVE:-0}" != 1 ] || fail 'Claude Code needs sign-in. Run START.command in Terminal to sign in.'
  printf '\nOne-time sign-in: Claude will open your browser. Finish signing in, then return here.\n'
  "$CLIMB_CLAUDE" auth login || fail 'Sign-in did not complete. Run START.command to try again.'
  "$CLIMB_CLAUDE" auth status >/dev/null 2>&1 || fail 'Claude Code is not signed in yet.'
fi

# An already-running agent may have needed only sign-in. Recheck before replacing files.
if [ "$CLIMB_EXISTING_STATUS" = 11 ]; then
  CLIMB_RECHECK_STATUS=0
  "$CLIMB_NODE" "$CLIMB_SOURCE_DIR/launcher.mjs" existing || CLIMB_RECHECK_STATUS=$?
  case "$CLIMB_RECHECK_STATUS" in
    0) exit 0 ;;
    10) : ;;
    *) fail 'Claude sign-in is present, but the running agent is not ready. Stop that copy and run START.command again.' ;;
  esac
fi

CLIMB_APP_DIR="$CLIMB_INSTALL_DIR/app"
mkdir -p "$CLIMB_APP_DIR"
if [ "$CLIMB_SOURCE_DIR" != "$CLIMB_APP_DIR" ]; then
  for CLIMB_FILE in climb-agent.mjs the-climb.html launcher.mjs START.sh START.command STOP.command README-start.txt; do
    if [ -f "$CLIMB_SOURCE_DIR/$CLIMB_FILE" ]; then
      cp "$CLIMB_SOURCE_DIR/$CLIMB_FILE" "$CLIMB_APP_DIR/.$CLIMB_FILE.new.$$"
      mv "$CLIMB_APP_DIR/.$CLIMB_FILE.new.$$" "$CLIMB_APP_DIR/$CLIMB_FILE"
    fi
  done
  # Keep the installed seed; a later ZIP must not overwrite somebody's earlier answers.
  if [ -f "$CLIMB_SOURCE_DIR/climb-seed.json" ] && [ ! -f "$CLIMB_APP_DIR/climb-seed.json" ]; then
    cp "$CLIMB_SOURCE_DIR/climb-seed.json" "$CLIMB_APP_DIR/climb-seed.json"
  fi
fi
chmod 700 "$CLIMB_APP_DIR/START.command" "$CLIMB_APP_DIR/START.sh" "$CLIMB_APP_DIR/STOP.command"
"$CLIMB_NODE" "$CLIMB_APP_DIR/launcher.mjs" start
printf '\nYou can close this Terminal window. The companion keeps running.\n'
printf 'Next time, double-click START.command. Stop it with STOP.command.\n'
