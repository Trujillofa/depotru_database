#!/usr/bin/env bash
# Start / stop / restart the Vanna web UI without "Address already in use" confusion.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
cd "$ROOT"
PORT="${PORT:-8084}"

stop() {
  if command -v fuser >/dev/null 2>&1 && fuser "${PORT}/tcp" >/dev/null 2>&1; then
    fuser -k "${PORT}/tcp"
    echo "✓ Stopped process on port ${PORT}"
    return
  fi
  pids=$(ss -tlnp 2>/dev/null | grep ":${PORT}" | sed -n 's/.*pid=\([0-9]*\).*/\1/p' || true)
  if [[ -n "${pids}" ]]; then
    kill ${pids}
    echo "✓ Stopped PID(s): ${pids}"
  else
    echo "ℹ️  Nothing listening on port ${PORT}"
  fi
}

status() {
  if ss -tlnp 2>/dev/null | grep -q ":${PORT}"; then
    echo "✓ Vanna is running on http://localhost:${PORT}"
    ss -tlnp | grep ":${PORT}" || true
  else
    echo "✗ No server on port ${PORT}"
  fi
}

start() {
  exec uv run python src/vanna_grok.py
}

case "${1:-start}" in
  start) start ;;
  stop) stop ;;
  restart) stop; sleep 1; start ;;
  status) status ;;
  *)
    echo "Usage: $0 {start|stop|restart|status}"
    exit 1
    ;;
esac
