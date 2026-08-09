#!/usr/bin/env python3
"""站点生成器: 把 agent 的会话/日记/作品渲染成单页应用(GitHub Pages)。

输出(gh-pages 分支):
  index.html + style.css + app.js   ← 单页应用壳(来自 watcher/web/)
  data/meta.json                    ← 天列表/日记分天/作品树/状态
  data/events-YYYY-MM-DD.json       ← 按天事件(前端按需加载)
  data/journal.md                   ← 日记原文(前端按天渲染)
  artifacts/**                      ← 作品原文件(可下载)

运行模式:
  - PAGES_LOCAL_WS=<workspace 目录>(云端: 本地挂载; 本地测试: 任意目录)
  - PAGES_ONCE=1 跑一次退出; 否则每 PAGES_INTERVAL 秒循环
"""
import glob
import json
import os
import re
import shutil
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "audit")
os.makedirs(AUDIT, exist_ok=True)

ALL_EVENTS = []
INTERVAL = int(os.environ.get("PAGES_INTERVAL", "60"))
ONCE = os.environ.get("PAGES_ONCE") == "1"
_GH_REPO = os.environ.get("GH_REPO", "xstrace/free-agents-playground")
if "/" in _GH_REPO:
    OWNER, REPO = _GH_REPO.split("/", 1)
else:
    OWNER, REPO = "xstrace", _GH_REPO
REMOTE = f"https://github.com/{OWNER}/{REPO}.git"
SESS_GLOB = "/workspace/.pi/agent/sessions/*/*.jsonl"
LOCAL_WS = os.environ.get("PAGES_LOCAL_WS") or ""
PAGES_REPO = os.environ.get("PAGES_REPO", os.path.join(ROOT, "data", "pages-repo"))

GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}

REDACTED = {}
for _k, _v in os.environ.items():
    if _k.endswith("_API_KEY") and _v and len(_v) > 10:
        REDACTED[_v] = "[REDACTED]"

ARTIFACT_EXCLUDE = {".pi", ".heartbeat", ".seeded", "agent.log",
                    "lost+found", "__pycache__", ".git"}
TEXT_EXTS = (".md", ".py", ".sh", ".json", ".txt", ".ts", ".yml", ".yaml",
             ".log", ".toml", ".conf", ".html", ".css")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def redact(s):
    for k, v in REDACTED.items():
        s = s.replace(k, v)
    return s


def agent_exec(args, user="agent", timeout=120):
    return subprocess.run(["docker", "exec", "-u", user, "fap-agent", *args],
                          cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def pull_latest_session():
    if LOCAL_WS:
        files = sorted(glob.glob(os.path.join(LOCAL_WS, ".pi", "agent", "sessions", "*", "*.jsonl")),
                       key=os.path.getmtime)
        if not files:
            return None, []
        events = []
        for line in open(files[-1]):
            if line.strip():
                events.append(json.loads(line))
        return files[-1], events
    r = agent_exec(["sh", "-c", f"ls -t {SESS_GLOB} 2>/dev/null | head -1"])
    path = r.stdout.strip()
    if not path:
        return None, []
    r = agent_exec(["cat", path])
    events = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    return path, events


def pull_file(container_path):
    if LOCAL_WS:
        local = os.path.join(LOCAL_WS, os.path.basename(container_path))
        if os.path.exists(local):
            with open(local) as f:
                return redact(f.read())
        return ""
    r = agent_exec(["cat", container_path])
    return redact(r.stdout) if r.returncode == 0 else ""


def day_of(ts):
    return (ts or "")[:10]


def split_journal(text):
    """按 '## YYYY-MM-DD' 切分日记并按天合并, 返回 [(date, title, content)] 新→旧"""
    if not text.strip():
        return []
    parts = re.split(r"(?m)^## (\d{4}-\d{2}-\d{2}[^\n]*)", text)
    merged = {}
    i = 1
    while i + 1 < len(parts):
        title_line = parts[i].strip()
        date = title_line[:10]
        if not date[:4].startswith("20"):
            break
        title = title_line[10:].lstrip("· ").strip()
        content = parts[i + 1]
        if date not in merged:
            merged[date] = {"title": title, "blocks": [], "n": 0}
        merged[date]["blocks"].append(f"## {title_line}\n{content}")
        merged[date]["n"] += 1
        i += 2
    days = []
    for date, info in merged.items():
        title = info["title"]
        n = info["n"]
        if n > 1:
            title = f"{title} 等 {n} 条记录"
        days.append((date, title, "\n\n".join(info["blocks"])))
    return sorted(days, key=lambda d: d[0], reverse=True)


# ── 作品树 ─────────────────────────────────────────────
def artifact_files(ws):
    if not os.path.isdir(ws):
        return []
    items = []
    for root, dirs, files in os.walk(ws):
        rel = os.path.relpath(root, ws)
        parts = [] if rel == "." else rel.split(os.sep)
        if parts and parts[0] in ARTIFACT_EXCLUDE:
            dirs[:] = []
            continue
        for name in sorted(files):
            if name in {".heartbeat", ".seeded", "agent.log"}:
                continue
            p = os.path.join(root, name)
            try:
                size = os.path.getsize(p)
            except OSError:
                continue
            rel_path = name if not parts else os.path.join(*parts, name)
            low = name.lower()
            if low.endswith(".md"):
                kind = "md"
            elif low.endswith(IMG_EXTS):
                kind = "img"
            elif low.endswith(TEXT_EXTS):
                kind = "code"
            else:
                kind = "bin"
            items.append((rel_path, size, kind))
    return sorted(items)


def build_tree(ws):
    items = artifact_files(ws)
    root = {"type": "dir", "name": "", "key": "", "children": []}
    for rel, size, kind in items:
        parts = rel.split("/")
        node = root
        cur = ""
        for p in parts[:-1]:
            cur = cur + "/" + p if cur else p
            child = next((c for c in node["children"] if c["type"] == "dir" and c["name"] == p), None)
            if not child:
                child = {"type": "dir", "name": p, "key": cur, "children": []}
                node["children"].append(child)
            node = child
        node["children"].append({
            "type": "file", "name": parts[-1], "key": rel, "size": size, "kind": kind,
            "url": "artifacts/" + rel,
        })
    return root


def copy_artifacts(ws, out):
    items = artifact_files(ws)
    if not items:
        return
    for rel, size, kind in items:
        src = os.path.join(ws, rel)
        dst = Path(out) / "artifacts" / rel
        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dst)
        except Exception:
            continue


# ── 站点生成 ───────────────────────────────────────────
def build_site():
    _, events = pull_latest_session()
    journal = pull_file("/workspace/journal.md")
    out = Path(PAGES_REPO)
    # 清理旧版(SVG 前)残留: 多页结构
    for stale in ("days", "journal.html", "artifacts.html"):
        p = out / stale
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        elif p.exists():
            p.unlink()
    if (out / "artifacts").is_dir():
        for f in (out / "artifacts").rglob("*.html"):
            f.unlink()
    (out / "data").mkdir(parents=True, exist_ok=True)

    # 按天拆事件
    by_day = {}
    for r in events:
        d = day_of(r.get("timestamp", ""))
        if d:
            by_day.setdefault(d, []).append(r)
    days = sorted(by_day.keys(), reverse=True)
    for d in days:
        (out / "data" / f"events-{d}.json").write_text(
            json.dumps(by_day[d], ensure_ascii=False), encoding="utf-8")

    # 日记分天(新→旧)
    journal_days = split_journal(journal)
    (out / "data" / "journal.md").write_text(journal, encoding="utf-8")

    # 作品
    copy_artifacts(LOCAL_WS, out)
    tree = build_tree(LOCAL_WS)

    # 状态 chip
    now = datetime.now(timezone.utc)
    updated = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    last_ts = max((r.get("timestamp", "") for r in events), default="")
    chip = {"cls": "", "text": "状态未知"}
    try:
        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        age = (now - last_dt).total_seconds() / 60
        if age < 10:
            chip = {"cls": "live", "text": f"● 活跃 · {int(age)} 分钟前有动静"}
        elif age < 60:
            chip = {"cls": "idle", "text": f"● 空闲 · {int(age)} 分钟前"}
        else:
            chip = {"cls": "down", "text": f"● 离线 · {int(age)} 分钟前"}
    except Exception:
        pass

    meta = {
        "updated": updated,
        "chip": chip,
        "days": days,
        "evCount": {d: len(by_day[d]) for d in days},
        "events": {d: f"data/events-{d}.json" for d in days},
        "journalDays": [{"date": d, "title": t, "content": c} for d, t, c in journal_days],
        "artifacts": tree,
        "artCount": sum(1 for _ in artifact_files(LOCAL_WS)),
    }
    (out / "data" / "meta.json").write_text(json.dumps(meta, ensure_ascii=False), encoding="utf-8")

    # 前端壳(index.html/assets)由 site/ 构建产物提供(gh-pages 根), 本生成器只产数据
    return out


def ensure_repo():
    if os.path.isdir(os.path.join(PAGES_REPO, ".git")):
        return
    r = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "-b", "gh-pages", REMOTE, PAGES_REPO],
        capture_output=True, text=True, timeout=120, env=GIT_ENV)
    if r.returncode != 0:
        os.makedirs(PAGES_REPO, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", "gh-pages"], cwd=PAGES_REPO, check=True)
        subprocess.run(["git", "remote", "add", "origin", REMOTE], cwd=PAGES_REPO, check=True)


def git_push():
    changed = subprocess.run(
        ["git", "status", "--porcelain", "."],
        cwd=PAGES_REPO, capture_output=True, text=True, timeout=60, env=GIT_ENV).stdout
    if not changed.strip():
        return False
    subprocess.run(["git", "add", "-A"], cwd=PAGES_REPO, check=True, timeout=60, env=GIT_ENV)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    subprocess.run(["git", "-c", "user.name=free-agents", "-c", "user.email=free-agents@localhost",
                    "commit", "-q", "-m", f"site: {stamp}"], cwd=PAGES_REPO, check=True,
                   timeout=60, env=GIT_ENV)
    r = subprocess.run(["git", "push", "-q", "origin", "gh-pages"], cwd=PAGES_REPO,
                       timeout=120, env=GIT_ENV)
    return r.returncode == 0


def main():
    print(f"[pages] 站点生成器, 每 {INTERVAL}s 检查 (→ {OWNER}/{REPO} gh-pages)", flush=True)
    while True:
        try:
            ensure_repo()
            out = build_site()
            if out and git_push():
                print(f"[pages] {time.strftime('%H:%M:%S', time.gmtime())} 已推送更新", flush=True)
        except Exception as e:
            print(f"[pages] 错误: {e}", flush=True)
        if ONCE:
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
