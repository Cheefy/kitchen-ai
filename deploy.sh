#!/bin/bash
# One-shot deploy: pulls the latest commit and rebuilds the stack.
# Run manually, or wire up as an Unraid User Scripts entry for a
# one-click deploy from the web UI instead of the command line.
set -e
cd "$(dirname "$0")"
git pull
docker compose up -d --build
