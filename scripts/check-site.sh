#!/bin/bash
# 站点体检: 版本指纹 + 数据新鲜度 + 可用性
# 版本指纹: 确认线上是 Vue 版(不是旧手写版残留)
set -uo pipefail
BASE="https://xstrace.github.io/free-agents-playground"
echo "=== 1. 版本指纹(Vue 版特征) ==="
TITLE=$(curl -s "$BASE/index.html" | grep -oE "<title>[^<]*" | head -1)
echo "title: $TITLE"
echo "$TITLE" | grep -q "· 20" && echo "❌ 旧手写版 title(带日期)!" || echo "✅ Vue 版 title"
ASSETS=$(curl -s "$BASE/index.html" | grep -oE 'assets/index-[a-zA-Z0-9_-]+\.(js|css)' | sort -u)
echo "构建产物: $(echo "$ASSETS" | tr '\n' ' ')"
[ -n "$ASSETS" ] && echo "✅ 引用构建产物" || echo "❌ 未引用 assets/!"
echo "旧手写文件: app.js=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/app.js") style.css=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/style.css") (应 404)"

echo "=== 2. 数据新鲜度 ==="
python3 - "$BASE" <<'PY'
import json, sys, urllib.request
from datetime import datetime, timezone
base = sys.argv[1]
meta = json.load(urllib.request.urlopen(base + "/data/meta.json"))
print("meta updated:", meta["updated"], "| chip:", meta["chip"]["text"])
days = meta["days"]
evs = json.load(urllib.request.urlopen(base + "/data/events-" + days[0] + ".json"))
ts = [e.get("timestamp", "") for e in evs if e.get("timestamp")]
print("最新事件:", max(ts), "| 今日事件:", len(evs))
PY

echo "=== 3. 关键资源可用性 ==="
for f in index.html data/meta.json data/journal.md "data/events-$(curl -s $BASE/data/meta.json | python3 -c 'import sys,json;print(json.load(sys.stdin)["days"][0])').json"; do
  code=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/$f")
  echo "$f → $code"
done
