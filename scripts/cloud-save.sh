#!/bin/bash
# 云端班次内/班末的存档+安全清洗+Pages 推送(在 Actions runner 上运行)
# 用法: bash scripts/cloud-save.sh [--pages]
#  - 把 /workspace(.pi/journal/memory/.seeded) 推到 agent-data 分支
#  - 存档前扫描并打码 API key(防 key 经会话 JSONL 泄露到公开仓库)
#  - --pages: 顺带渲染推送 GitHub Pages
set -uo pipefail

cd "$(dirname "$0")/.."
GH_REPO="${GH_REPO:-xstrace/free-agents-playground}"
WS="$PWD/data/workspace"

# ── 安全清洗: 把 key 值从拷贝后的文件里打码(可能在对话或工具输出中被复述)
#    注意: 在 persist 副本上操作(runner 属主可写; 容器内 workspace 文件属 agent 用户) ──
sanitize() {
  local key="${OPENCODE_API_KEY:-}"
  [ -n "$key" ] || return 0
  find .pi journal.md AGENTS.md -type f 2>/dev/null | while read -r f; do
    if grep -q "$key" "$f" 2>/dev/null; then
      sed -i "s#$key#[REDACTED]#g" "$f" && echo "[安全] 已清洗: $f" || echo "[安全] 清洗失败: $f"
    fi
  done
}

# ── 存档到 agent-data ──
save() {
  mkdir -p data/persist
  cd data/persist
  if [ ! -d .git ]; then
    git init -q -b agent-data
    git remote add origin "https://github.com/${GH_REPO}.git"
  fi
  rm -rf .pi journal.md memory .seeded artifacts
  cp -r "$WS/.pi" . 2>/dev/null || true
  cp "$WS/journal.md" . 2>/dev/null || true
  cp -r "$WS/memory" . 2>/dev/null || true
  cp "$WS/.seeded" . 2>/dev/null || true
  # 作品集: workspace 全部创作文件(递归, 保留目录结构; 排除系统/内部目录)
  mkdir -p artifacts
  ART="$PWD/artifacts"
  (cd "$WS" && find . -type f \
      ! -path './.pi/*' ! -path './memory/*' ! -path './__pycache__/*' \
      ! -name '.heartbeat' ! -name '.seeded' ! -name 'agent.log' \
      -exec cp --parents {} "$ART/" \; 2>/dev/null) || true
  echo "[存档] 作品 $(find "$ART" -type f 2>/dev/null | wc -l) 个文件"
  sanitize
  git add -A
  git -c user.name=free-agents-cloud -c user.email=cloud@localhost \
      commit -q -m "state: $(date -u +%FT%TZ)" 2>/dev/null || true
  GIT_TERMINAL_PROMPT=0 git push -q origin agent-data 2>&1 | tail -1 || echo "[存档] push 失败"
  echo "[存档] agent-data 已更新(含 artifacts)"
  cd ../..
}

sanitize
save

if [ "${1:-}" = "--pages" ]; then
  PAGES_ONCE=1 PAGES_LOCAL_WS="$WS" python3 watcher/pages.py 2>&1 | tail -2
fi
