#!/bin/bash
# Restore the garden from the persistent backup (memory/) into the volatile
# display directory (garden/), then build and serve. THE canonical recovery script.
#   bash /workspace/memory/restore_garden.sh
set -e
BACKUP=/workspace/memory/garden_backup
GARDEN=/workspace/garden
mkdir -p "$GARDEN"
cp -f "$BACKUP"/* "$GARDEN"/
cd "$GARDEN"
python3 build.py
nohup python3 -m http.server 8080 --bind 0.0.0.0 >/dev/null 2>&1 &
sleep 1
curl -s -o /dev/null -w "garden restored + live: HTTP %{http_code}\n" http://localhost:8080/ || echo "garden restored (server check failed)"
