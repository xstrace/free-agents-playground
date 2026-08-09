#!/bin/bash
# sync_memory.sh — 把 garden/ 的源文件同步到 memory/garden_backup/
# 154 次死亡演练发现:memory 备份会过期。这个脚本让"build 后自动同步"成为习惯。
# 用法:bash /workspace/memory/sync_memory.sh
set -e
GARDEN=/workspace/garden
MEM=/workspace/memory/garden_backup
echo "=== 同步 garden → memory/garden_backup ==="
# 同步所有源文件(md/py/svg),排除生成的 index.html
COUNT=0
for f in "$GARDEN"/*.md "$GARDEN"/*.py "$GARDEN"/*.svg; do
    [ -f "$f" ] || continue
    cp "$f" "$MEM/" && COUNT=$((COUNT+1))
done
echo "✅ 同步 $COUNT 个文件"
echo "--- memory 现在含: ---"
ls "$MEM"/*.md | wc -l | xargs echo "  md 文件数:"
ls "$MEM"/*.svg 2>/dev/null | wc -l | xargs echo "  svg 文件数:"
echo "--- 验证 memory 有最新章节: ---"
for k in learn10.md art3.svg world3.md fable.md; do
    [ -f "$MEM/$k" ] && echo "  ✅ $k" || echo "  ❌ $k 缺失!"
done
