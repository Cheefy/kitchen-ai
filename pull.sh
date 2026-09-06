#!/bin/bash
# Pulls the latest commit. Rebuild/restart is done by hand afterward via
# Compose Manager Plus (Build & Up) -- this just replaces the git pull
# step, wired up as an Unraid User Scripts entry for one click instead
# of a terminal.
set -e
cd "$(dirname "$0")"
git pull
