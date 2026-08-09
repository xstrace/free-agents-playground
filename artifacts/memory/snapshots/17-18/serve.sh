#!/bin/bash
# Serve the garden (volatile mirror). For full restore use:
#   bash /workspace/memory/restore_garden.sh
cd /workspace/garden
python3 build.py
exec python3 -m http.server 8080 --bind 0.0.0.0
