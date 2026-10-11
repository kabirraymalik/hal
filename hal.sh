#!/bin/sh
# hal launcher. Needs Python 3.11+ (tomllib); override the interpreter with HAL_PYTHON.
HERE="$(cd "$(dirname "$(readlink -f "$0")")" && pwd)"
PY="${HAL_PYTHON:-}"
if [ -z "$PY" ]; then
  for c in python3 "$HOME/miniconda3/bin/python3" /opt/homebrew/bin/python3; do
    if "$c" -c 'import sys; sys.exit(sys.version_info < (3, 11))' 2>/dev/null; then PY="$c"; break; fi
  done
fi
[ -n "$PY" ] || { echo "hal: no python >= 3.11 found; set HAL_PYTHON" >&2; exit 1; }
exec "$PY" -u "$HERE/hal.py" "$@"
