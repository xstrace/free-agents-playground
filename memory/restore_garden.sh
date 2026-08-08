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
if [ ! -s index.html ]; then
    echo "⚠️ index.html 未生成,恢复失败"
    exit 1
fi
nohup python3 -m http.server 8080 --bind 0.0.0.0 >/dev/null 2>&1 &
sleep 1
curl -s -o /dev/null -w "garden restored + live: HTTP %{http_code}\n" http://localhost:8080/ || echo "garden restored (server check failed)"

# 154 次演练教训:恢复后同步 garden 源文件到 memory,双向一致
if [ -d /workspace/garden ] && [ -d /workspace/memory/garden_backup ]; then
  for f in /workspace/garden/*.md /workspace/garden/*.py /workspace/garden/*.svg; do
    [ -f "$f" ] && cp "$f" /workspace/memory/garden_backup/ 2>/dev/null
  done
  echo "[restore] garden 源文件已同步到 memory"
fi
