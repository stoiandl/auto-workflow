#!/usr/bin/env sh
set -euo pipefail

HOST=${1:-127.0.0.1}
PORT=${2:-5432}
TRIES=${TRIES:-90}

while [ $TRIES -gt 0 ]; do
  if nc -z "$HOST" "$PORT" >/dev/null 2>&1; then
    echo "Postgres is up on ${HOST}:${PORT}"
    exit 0
  fi
  TRIES=$((TRIES-1))
  sleep 1
done

echo "Timed out waiting for Postgres on ${HOST}:${PORT}" >&2
exit 1
