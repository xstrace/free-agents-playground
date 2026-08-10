#!/bin/bash
# 构建前端并把产物部署到 gh-pages(数据由 pages.py 独立更新, 互不干扰)
set -euo pipefail
cd "$(dirname "$0")/.."
export HOME=/root

echo "[site] 构建前端..."
(cd site && npm run build >/dev/null)

echo "[site] 更新 gh-pages..."
rm -rf data/pages-repo-site
git clone -q --depth 1 -b gh-pages https://github.com/xstrace/free-agents-playground.git data/pages-repo-site
cd data/pages-repo-site
# 清理旧手写版残留(避免与 Vue 构建产物混用)
rm -f index.html app.js style.css
rm -rf assets
cp -r ../../site/dist/* .
git add -A
git -c user.name=free-agents -c user.email=free-agents@localhost \
    commit -q -m "site: $(date -u +%FT%TZ)" 2>/dev/null || true
git push -q origin gh-pages
cd ../..
rm -rf data/pages-repo-site
echo "[site] 部署完成"
