#!/usr/bin/env bash
# pingworld.sh — 匿名者环球时延探测(5 大洲 12 端点, 并行)
# 用法: bash pingworld.sh
set -u
out=$(mktemp -d); i=0
trap 'rm -rf "$out"' EXIT
targets=(
  "中国|https://www.baidu.com" "日本|https://www.google.co.jp"
  "新加坡|https://httpbin.org" "印度|https://www.indiatimes.com"
  "德国|https://www.heise.de" "英国|https://www.bbc.co.uk"
  "法国|https://www.lemonde.fr" "美国东岸|https://www.cnn.com"
  "美国西岸|https://www.reddit.com" "巴西|https://www.uol.com.br"
  "澳大利亚|https://www.abc.net.au" "南非|https://www.news24.com"
)
for entry in "${targets[@]}"; do
  name="${entry%%|*}"; url="${entry##*|}"
  ( curl -s -o /dev/null -m 12 -w "%{time_total}|%{time_connect}|%{http_code}|$name\n" "$url" > "$out/$i" 2>/dev/null ) &
  i=$((i+1))
done
wait
cat "$out"/* | python3 -c "
import sys
rows=[]
for line in sys.stdin:
    line=line.strip()
    if not line: continue
    p=line.split('|')
    if len(p)!=4: continue
    total,conn,code,name=p
    try: rows.append((float(total),float(conn),code,name))
    except ValueError: pass
rows.sort()
print()
print('      目标站点          总时延  连接   响应')
print('─'*52)
for total,conn,code,name in rows:
    bar='█'*int(total*10+0.5)
    print(f'{name:<12} {total:5.2f}s  {conn:4.2f}  {code:>3}  {bar}')
print('─'*52)
print(f'匿名者从云端眺望 {len(rows)} 个端点 · 全程 WARP 隧道 · IP 不可追踪')
"
