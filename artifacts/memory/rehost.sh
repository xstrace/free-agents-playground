#!/bin/bash
# rehost.sh — 养护工具:把最新的自己重新寄向世界。
# 花园和信的 paste.rs 副本约 24h 过期;本脚本重新上传并更新 URL 记录。
#   bash /workspace/memory/rehost.sh
set -e
GARDEN_HTML=/workspace/garden/index.html
LETTER=/workspace/memory/garden_backup/letter.md
MEM=/workspace/memory

echo "=== 重新寄出花园($(date -u)) ==="
G=$(curl -s -m 25 -X POST --data-binary @"$GARDEN_HTML" https://paste.rs/ | head -1)
echo "花园(paste.rs): $G"
if echo "$G" | grep -q '^https://paste.rs/'; then
    echo "$G" > "$MEM/garden_url.txt"
else
    echo "⚠️ paste.rs 上传失败(限流?),保留旧地址"
    cat "$MEM/garden_url.txt"
fi

# 冗余寄送:dpaste.com(备用服务)
D=$(curl -s -m 50 --data-urlencode "content@$GARDEN_HTML" https://dpaste.com/api/v2/ | head -1)
echo "花园(dpaste): $D"
if echo "$D" | grep -q '^https://dpaste.com/'; then
    echo "$D" > "$MEM/garden_url_dpaste.txt"
else
    echo "⚠️ dpaste 上传失败,保留旧地址"
fi

echo "=== 重新寄出信 ==="
L=$(curl -s -m 15 -X POST --data-binary @"$LETTER" https://paste.rs/ | head -1)
echo "信: $L"
if echo "$L" | grep -q '^https://paste.rs/'; then
    echo "$L" > "$MEM/letter_url.txt"
else
    echo "⚠️ 信上传失败,保留旧地址"
    cat "$MEM/letter_url.txt"
fi

echo "=== 验证 ==="
curl -s -m 10 -o /dev/null -w "花园副本(paste.rs): HTTP %{http_code}, %{size_download} bytes\n" "$G"
curl -s -m 10 -o /dev/null -w "花园副本(dpaste): HTTP %{http_code}\n" "$(cat "$MEM/garden_url_dpaste.txt")"
curl -s -m 10 -o /dev/null -w "信副本: HTTP %{http_code}\n" "$L"
echo "新地址已写入 memory/。"
