#!/bin/sh
set -eu

if docker compose version >/dev/null 2>&1; then
  exec docker compose "$@"
fi

if command -v docker-compose >/dev/null 2>&1; then
  exec docker-compose "$@"
fi

cat >&2 <<'MESSAGE'
Docker Compose is not installed.

Amazon Linux first attempt:
  sudo dnf install -y docker-compose-plugin

If that package is unavailable, follow the official Docker Compose plugin
installation instructions linked from docs/AWS_CONSOLE_SETUP.md. After installing,
confirm `docker compose version`, then rerun this command.
MESSAGE
exit 127
