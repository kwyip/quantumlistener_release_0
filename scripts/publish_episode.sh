#!/bin/sh
set -eu
exec python -m scripts.publish_episode "$@"
