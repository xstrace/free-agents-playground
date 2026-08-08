#!/usr/bin/env python3
"""宿主侧: 把 agent 的会话流渲染成 GitHub Pages 静态站, 分钟级自动更新。

- 每 PAGES_INTERVAL 秒(默认 60)从容器拉取最新 pi 会话 JSONL + journal.md
- 渲染: index.html(左栏按天列表 + 最新一天全量事件流) + days/YYYY-MM-DD.html
- 有变更才 commit + push 到 gh-pages 分支(独立 clone: data/pages-repo)
- systemd 托管: templates/free-agent-pages.service
"""
import glob
import html
import json
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "audit")
PAGES_REPO = os.path.join(ROOT, "data", "pages-repo")
os.makedirs(AUDIT, exist_ok=True)

INTERVAL = int(os.environ.get("PAGES_INTERVAL", "60"))
OWNER = os.environ.get("GH_OWNER", "xstrace")
REPO = os.environ.get("GH_REPO", "free-agents-playground")
REMOTE = f"https://github.com/{OWNER}/{REPO}.git"
SESS_GLOB = "/workspace/.pi/agent/sessions/*/*.jsonl"

CSS = """
:root{--bg:#0d1117;--panel:#161b22;--border:#30363d;--text:#e6edf3;--dim:#8b949e;
--user:#58a6ff;--pi:#3fb950;--tool:#d29922;--err:#f85149;--think:#6e7681}
*{box-sizing:border-box}body{margin:0;font:14px/1.6 -apple-system,"Segoe UI",monospace;
background:var(--bg);color:var(--text)}
.layout{display:flex;min-height:100vh}
aside{width:220px;flex-shrink:0;background:var(--panel);border-right:1px solid var(--border);
padding:16px;position:sticky;top:0;height:100vh;overflow-y:auto}
aside h1{font-size:14px;margin:0 0 4px}aside p{color:var(--dim);font-size:11px;margin:0 0 12px}
aside nav a{display:block;padding:6px 8px;border-radius:6px;color:var(--text);
text-decoration:none;font-size:13px;margin-bottom:2px}
aside nav a:hover{background:#21262d}
aside nav a.active{background:#1f6feb22;color:var(--user);border:1px solid #1f6feb55}
main{flex:1;padding:24px 32px;max-width:1000px}
h2{font-size:18px;margin:0 0 16px;border-bottom:1px solid var(--border);padding-bottom:8px}
.ev{margin:0 0 14px;padding:10px 14px;background:var(--panel);border:1px solid var(--border);
border-radius:8px;white-space:pre-wrap;word-break:break-word}
.ev .t{color:var(--dim);font-size:11px;margin-right:8px}
.badge{display:inline-block;font-size:10px;padding:1px 7px;border-radius:10px;margin-right:8px;
vertical-align:1px}
.b-user{background:#58a6ff22;color:var(--user)}.b-pi{background:#3fb95022;color:var(--pi)}
.b-tool{background:#d2992222;color:var(--tool)}.b-err{background:#f8514922;color:var(--err)}
details{margin-top:6px}summary{cursor:pointer;color:var(--think);font-size:12px}
details div{color:#b3bdca;font-size:13px;margin-top:6px}
.journal{margin-top:28px}.journal h3{font-size:15px;color:var(--pi)}
.journal pre{white-space:pre-wrap;background:var(--panel);border:1px solid var(--border);
border-radius:8px;padding:14px;font:13px/1.7 monospace;color:#c9d1d9}
.fresh{font-size:11px;color:var(--dim)}
"""


def sh(*args, timeout=120):
    return subprocess.run(list(args), capture_output=True, text=True, timeout=timeout)


def pull_latest_session():
    r = sh("docker", "compose", "exec", "-u", "agent", "-T", "agent",
           "sh", "-c", f"ls -t {SESS_GLOB} 2>/dev/null | head -1")
    path = r.stdout.strip()
    if not path:
        return None, []
    r = sh("docker", "compose", "exec", "-u", "agent", "-T", "agent", "cat", path)
    events = [json.loads(l) for l in r.stdout.splitlines() if l.strip()]
    return path, events


def pull_file(container_path):
    r = sh("docker", "compose", "exec", "-u", "agent", "-T", "agent", "cat", container_path)
    return r.stdout if r.returncode == 0 else ""


def esc(s):
    return html.escape(str(s), quote=True)


def render_blocks(content):
    """assistant 消息 content 列表 -> HTML"""
    if isinstance(content, str):
        return f"<div>{esc(content)}</div>"
    if not isinstance(content, list):
        return f"<div>{esc(content)}</div>"
    parts = []
    for b in content:
        if not isinstance(b, dict):
            parts.append(f"<div>{esc(b)}</div>")
            continue
        t = b.get("type", "")
        if t == "text":
            parts.append(f"<div>{esc(b.get('text', ''))}</div>")
        elif t in ("thinking", "reasoning"):
            parts.append(f"<details><summary>思考</summary><div>{esc(b.get('text', ''))}</div></details>")
        elif t == "toolCall":
            args = json.dumps(b.get("arguments", b.get("args", {})), ensure_ascii=False)
            name = b.get("name", b.get("toolName", "?"))
            parts.append(f'<div><span class="badge b-tool">工具</span>{esc(name)} {esc(args)}</div>')
        elif t == "toolResult":
            data = str(b.get("data", ""))[:600]
            parts.append(f'<div><span class="badge b-tool">结果</span>{esc(data)}</div>')
        else:
            parts.append(f"<div>{esc(str(b)[:300])}</div>")
    return "\n".join(parts)


def event_html(r):
    t = r.get("type")
    ts = (r.get("timestamp") or "")[11:19]
    if t == "message":
        m = r.get("message", {})
        role = m.get("role")
        if role == "user":
            return f'<div class="ev"><span class="t">{ts}</span><span class="badge b-user">宿主</span>{render_blocks(m.get("content"))}</div>'
        if role == "assistant":
            body = render_blocks(m.get("content"))
            if not body.strip():
                return ""
            return f'<div class="ev"><span class="t">{ts}</span><span class="badge b-pi">Pi</span>{body}</div>'
        return f'<div class="ev"><span class="t">{ts}</span><span class="badge b-tool">{esc(role)}</span>{render_blocks(m.get("content"))}</div>'
    if t == "error":
        return f'<div class="ev"><span class="t">{ts}</span><span class="badge b-err">错误</span>{esc(json.dumps(r, ensure_ascii=False)[:300])}</div>'
    if t == "model_change":
        return f'<div class="ev"><span class="t">{ts}</span><span class="badge b-tool">模型</span>{esc(r.get("model", "?"))}</div>'
    return ""


def day_of(ts):
    return (ts or "")[:10]


def page_html(events, days, current_day, journal):
    nav = []
    for d in days:
        cls = ' class="active"' if d == current_day else ""
        nav.append(f'<a{cls} href="{"index.html" if d == days[0] else "days/" + d + ".html"}">{d}</a>')
    body = "".join(event_html(r) for r in events)
    journal_html = (
        '<div class="journal"><h3>📓 journal.md(agent 自写心得)</h3>'
        f'<pre>{esc(journal)}</pre></div>' if journal.strip() else ""
    )
    updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>free agent playground · {current_day}</title>
<style>{CSS}</style>
<meta http-equiv="refresh" content="60">
</head><body>
<div class="layout">
<aside>
<h1>free agent playground</h1>
<p>隔离沙箱里的自主 AI · 实时观察</p>
<nav>{''.join(nav)}</nav>
<p class="fresh">更新于 {updated}<br>每 60 秒自动刷新</p>
</aside>
<main>
<h2>{current_day} <span class="fresh">({len(events)} 条事件)</span></h2>
{body}
{journal_html}
</main>
</div></body></html>"""


def render_site():
    _, events = pull_latest_session()
    journal = pull_file("/workspace/journal.md")
    days = sorted({day_of(r.get("timestamp", "")) for r in events if r.get("timestamp")}, reverse=True)
    if not days:
        return None

    out = Path(PAGES_REPO)
    (out / "days").mkdir(parents=True, exist_ok=True)
    for d in days:
        day_events = [r for r in events if day_of(r.get("timestamp", "")) == d]
        (out / "days" / f"{d}.html").write_text(
            page_html(day_events, days, d, journal if d == days[0] else ""))
    (out / "index.html").write_text(
        page_html([r for r in events if day_of(r.get("timestamp", "")) == days[0]], days, days[0], journal))
    return out


def git_push():
    if not os.path.isdir(os.path.join(PAGES_REPO, ".git")):
        os.makedirs(PAGES_REPO, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", "gh-pages"], cwd=PAGES_REPO, check=True)
        subprocess.run(["git", "remote", "add", "origin", REMOTE], cwd=PAGES_REPO, check=True)
        subprocess.run(["git", "fetch", "-q", "origin", "gh-pages"], cwd=PAGES_REPO)

    changed = subprocess.run(
        ["git", "status", "--porcelain", "."],
        cwd=PAGES_REPO, capture_output=True, text=True).stdout
    if not changed.strip():
        return False
    subprocess.run(["git", "add", "-A"], cwd=PAGES_REPO, check=True)
    stamp = time.strftime("%Y-%m-%d %H:%M:%S UTC", time.gmtime())
    subprocess.run(["git", "-c", "user.name=free-agents", "-c", "user.email=free-agents@localhost",
                    "commit", "-q", "-m", f"site: {stamp}"], cwd=PAGES_REPO, check=True)
    r = subprocess.run(["git", "push", "-q", "origin", "gh-pages"], cwd=PAGES_REPO)
    return r.returncode == 0


def main():
    print(f"[pages] 渲染器启动, 每 {INTERVAL}s 检查 (→ {OWNER}/{REPO} gh-pages)", flush=True)
    while True:
        try:
            out = render_site()
            if out and git_push():
                print(f"[pages] {time.strftime('%H:%M:%S', time.gmtime())} 已推送更新", flush=True)
        except Exception as e:
            print(f"[pages] 错误: {e}", flush=True)
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
