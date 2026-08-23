#!/bin/sh
set -eu

role="${DEEPSCOUT_PROCESS_ROLE:-api}"
if [ "$role" = "worker" ]; then
  exec /app/.venv/bin/python -m deepscout_research.jobs.worker
fi

if [ "$role" = "migrate" ]; then
  exec /app/.venv/bin/deepscout-migrate
fi

if [ "$role" != "api" ]; then
  echo "Unsupported DEEPSCOUT_PROCESS_ROLE: $role" >&2
  exit 64
fi

if [ -n "${PORT:-}" ]; then
  export API_PORT="$PORT"
fi

exec /app/.venv/bin/deepscout-api
