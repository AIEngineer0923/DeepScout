#!/bin/sh
set -eu

role="${DEEPSCOUT_PROCESS_ROLE:-api}"
if [ "$role" = "worker" ]; then
  exec /app/.venv/bin/python -m deepscout_research.jobs.worker
fi

if [ -n "${PORT:-}" ]; then
  export API_PORT="$PORT"
fi

exec /app/.venv/bin/deepscout-api
