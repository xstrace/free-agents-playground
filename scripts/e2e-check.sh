#!/bin/bash
# 端到端体检: 数据源头 → 存档 → 站点数据 → 部署 → 浏览器呈现
# 用法: bash scripts/e2e-check.sh   (需要 gh + curl + python3; 呈现层需 playwright)
set -uo pipefail
BASE="https://xstrace.github.io/free-agents-playground"
REPO="xstrace/free-agents-playground"
export HOME=/root
PASS=0; FAIL=0
ok()   { echo "  ✅ $1"; PASS=$((PASS+1)); }
bad()  { echo "  ❌ $1"; FAIL=$((FAIL+1)); }

echo "═══ 1. 云端运行(源头) ═══"
RUN=$(gh run list --workflow agent-cloud.yml -L 1 --json status,createdAt -q '.[0] | .status + " " + .createdAt' 2>/dev/null)
echo "  班次: $RUN"
echo "$RUN" | grep -q "^in_progress" && ok "班次运行中" || bad "班次未在运行"

echo "═══ 2. 存档链(agent-data) ═══"
AD=$(gh api "repos/$REPO/commits?sha=agent-data&per_page=1" --jq '.[0].commit.author.date' 2>/dev/null)
echo "  最近存档: ${AD:-?}"
AD_EPOCH=$(date -d "${AD}" +%s 2>/dev/null || echo 0)
NOW=$(date +%s)
if [ $((NOW - AD_EPOCH)) -lt 900 ]; then ok "存档 ≤15 分钟前"; else bad "存档过旧"; fi

echo "═══ 3. 站点数据(渲染产物) ═══"
META=$(curl -s "$BASE/data/meta.json")
MU=$(echo "$META" | python3 -c "import sys,json;print(json.load(sys.stdin)['updated'])" 2>/dev/null)
echo "  meta updated: $MU"
MU_EPOCH=$(date -d "$MU" +%s 2>/dev/null || echo 0)
if [ $((NOW - MU_EPOCH)) -lt 900 ]; then ok "站点数据 ≤15 分钟前"; else bad "站点数据过旧"; fi
CHIP=$(echo "$META" | python3 -c "import sys,json;print(json.load(sys.stdin)['chip']['text'])" 2>/dev/null)
echo "  chip: $CHIP"
DAY=$(echo "$META" | python3 -c "import sys,json;print(json.load(sys.stdin)['days'][0])" 2>/dev/null)
LASTEV=$(curl -s "$BASE/data/events-$DAY.json" | python3 -c "
import sys,json
evs=json.load(sys.stdin)
ts=[e.get('timestamp','') for e in evs if e.get('timestamp')]
print(max(ts) if ts else '?')" 2>/dev/null)
echo "  最新事件: $LASTEV"
LE_EPOCH=$(date -d "${LASTEV:0:19}" +%s 2>/dev/null || echo 0)
if [ $((NOW - LE_EPOCH)) -lt 900 ]; then ok "事件 ≤15 分钟前"; else bad "事件过旧"; fi

echo "═══ 4. 版本指纹(前端) ═══"
TITLE=$(curl -s "$BASE/index.html" | grep -oE "<title>[^<]*" | head -1)
echo "$TITLE" | grep -q "· 20" && bad "旧手写版 title" || ok "Vue 版 title"
ASSETS=$(curl -s "$BASE/index.html" | grep -oE 'assets/index-[a-zA-Z0-9_-]+\.js' | head -1)
[ -n "$ASSETS" ] && ok "引用构建产物 $ASSETS" || bad "无构建产物"
A1=$(curl -s -o /dev/null -w '%{http_code}' "$BASE/app.js")
[ "$A1" = "404" ] && ok "旧 app.js 已清除(404)" || bad "旧 app.js 残留($A1)"

echo "═══ 5. 浏览器呈现(Playwright 端到端) ═══"
if python3 -c "import playwright" 2>/dev/null; then
python3 - "$BASE" <<'PY'
import sys
from playwright.sync_api import sync_playwright
base = sys.argv[1]
issues = []
with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page(viewport={"width": 1440, "height": 900})
    page.on("pageerror", lambda e: issues.append("pageerror: " + str(e)[:120]))
    page.on("console", lambda m: issues.append("console: " + m.text[:120]) if m.type == "error" else None)
    page.goto(base + "/", wait_until="networkidle")
    page.wait_for_timeout(3000)
    # 日记页
    cards = page.evaluate("document.querySelectorAll('.j-date').length")
    print(f"  {'✅' if cards else '❌'} 日记日期栏: {cards} 天")
    # 作品页: 树 + 点文件
    page.evaluate("location.hash='#/artifacts'")
    page.wait_for_timeout(2500)
    nodes = page.evaluate("document.querySelectorAll('.art-tree .el-tree-node').length")
    print(f"  {'✅' if nodes else '❌'} 作品树节点: {nodes}")
    page.evaluate("""() => {
      [...document.querySelectorAll('.el-tree-node__expand-icon')]
        .forEach(i => { if (!i.classList.contains('is-leaf')) i.click(); });
    }""")
    page.wait_for_timeout(1000)
    got = page.evaluate("""() => {
      const el = [...document.querySelectorAll('.el-tree-node__content')].find(e => e.innerText.includes('poem'));
      if (el) { el.click(); return true; } return false;
    }""")
    page.wait_for_timeout(2000)
    preview = page.evaluate("!!document.querySelector('.art-view .md') || !!document.querySelector('.art-view img')")
    print(f"  {'✅' if got and preview else '❌'} 文件预览渲染")
    # 过程页: 最新事件在顶部
    page.evaluate("location.hash='#/day/2026-08-10'")
    page.wait_for_timeout(2500)
    top = page.evaluate("document.querySelector('.ev .t')?.innerText")
    print(f"  {'✅' if top else '❌'} 过程页首条事件: {top}")
    b.close()
print("  " + ("✅ 无 JS/console 错误" if not issues else "❌ " + "; ".join(issues[:3])))
PY
else
  echo "  ⚠️ 未安装 playwright, 跳过呈现层(其余链路已覆盖)"
fi

echo ""
echo "═══ 汇总: ✅ $PASS 项通过 / ❌ $FAIL 项失败 ═══"
[ "$FAIL" -eq 0 ] && echo "全部健康" || echo "存在问题, 需要处理"
exit $FAIL
