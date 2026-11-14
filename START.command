#!/bin/bash
# Double-click this file on a Mac. Keep it beside START.sh.
CLIMB_LAUNCHER_DIR="$(cd -- "$(dirname -- "$0")" && pwd -P)"
exec /bin/bash "$CLIMB_LAUNCHER_DIR/START.sh" "$@"
