#!/bin/sh
set -e

echo "[entrypoint] alembic upgrade head ..."
alembic upgrade head

echo "[entrypoint] starting: $*"
exec "$@"
