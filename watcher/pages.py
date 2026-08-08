#!/usr/bin/env python3
"""宿主侧: 把 agent 的会话流渲染成 GitHub Pages 静态站, 分钟级自动更新。

- 每 PAGES_INTERVAL 秒(默认 60)从容器拉取最新 pi 会话 JSONL + journal.md
- 渲染: index.html(左栏按天列表 + 最新一天事件流, 新→旧) + days/YYYY-MM-DD.html
- 有变更才 commit + push 到 gh-pages 分支(独立 clone: data/pages-repo)
- 支持 FAP_CLOUD=1(docker exec 直连容器, 用于 Actions 云端运行)
"""
import glob
import json
import os
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "audit")
os.makedirs(AUDIT, exist_ok=True)

CLOUD = os.environ.get("FAP_CLOUD") == "1"
INTERVAL = int(os.environ.get("PAGES_INTERVAL", "60"))
ONCE = os.environ.get("PAGES_ONCE") == "1"
# GH_REPO 支持完整 "owner/repo"(云端 env)或仅 repo 名(默认)
_GH_REPO = os.environ.get("GH_REPO", "xstrace/free-agents-playground")
if "/" in _GH_REPO:
    OWNER, REPO = _GH_REPO.split("/", 1)
else:
    OWNER, REPO = "xstrace", _GH_REPO
REMOTE = f"https://github.com/{OWNER}/{REPO}.git"
SESS_GLOB = "/workspace/.pi/agent/sessions/*/*.jsonl"
# 云端模式: 直接读本地挂载目录(容器可能已停), 不依赖 docker exec
LOCAL_WS = os.environ.get("PAGES_LOCAL_WS") or ""
PAGES_REPO = os.environ.get("PAGES_REPO", os.path.join(ROOT, "data", "pages-repo"))

# git 环境: 失败快速退出, 绝不挂起等凭据
GIT_ENV = {**os.environ, "GIT_TERMINAL_PROMPT": "0", "GIT_ASKPASS": "true"}

# 安全: 渲染时把环境里的 API key 值全部打码, 防止 key 经会话/日志流入公开站点
REDACTED = {}
for _k, _v in os.environ.items():
    if _k.endswith("_API_KEY") and _v and len(_v) > 10:
        REDACTED[_v] = "[REDACTED]"

CSS = """
:root{--bg:#0b0e14;--panel:#11151f;--panel2:#161c2a;--border:#232b3d;--text:#e8ecf3;
--dim:#7d8597;--accent:#4cc2ff;--user:#4cc2ff;--pi:#57d9a3;--tool:#e3b341;--err:#ff6b6b;
--think:#8b93a7;--header:#0e1a2b}
*{box-sizing:border-box;margin:0;padding:0}
body{font:14px/1.65 -apple-system,BlinkMacSystemFont,"Segoe UI","PingFang SC","Noto Sans SC",
"Microsoft YaHei",sans-serif;background:var(--bg);color:var(--text);min-height:100vh}
header{background:linear-gradient(135deg,#0e1a2b 0%,#13203a 55%,#1a1b3a 100%);
border-bottom:1px solid var(--border);padding:18px 28px;display:flex;align-items:center;gap:16px}
header h1{font-size:17px;letter-spacing:.5px}
header h1 b{color:var(--accent)}
header .sub{color:var(--dim);font-size:12px;margin-top:2px}
.chip{font-size:11px;padding:3px 10px;border-radius:20px;border:1px solid var(--border);
background:var(--panel2);color:var(--dim);white-space:nowrap}
.chip.live{color:var(--pi);border-color:#2ea04355;background:#2386361a}
.chip.idle{color:var(--tool);border-color:#d2992255;background:#d299221a}
.chip.down{color:var(--err);border-color:#f8514955;background:#f851491a}
.layout{display:flex;gap:0;align-items:flex-start}
aside{width:230px;flex-shrink:0;padding:20px 14px;position:sticky;top:0;height:100vh;
overflow-y:auto;background:var(--panel);border-right:1px solid var(--border)}
aside .side-title{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:1px;
margin:0 8px 8px}
aside nav a{display:flex;justify-content:space-between;align-items:center;padding:7px 10px;
border-radius:8px;color:var(--text);text-decoration:none;font-size:13px;margin-bottom:3px;
border:1px solid transparent}
aside nav a:hover{background:var(--panel2)}
aside nav a.active{background:#4cc2ff14;border-color:#4cc2ff33;color:var(--accent)}
aside nav a .cnt{color:var(--dim);font-size:11px}
aside .foot{margin-top:18px;padding:0 8px;color:var(--dim);font-size:11px;line-height:1.8}
main{flex:1;min-width:0;padding:24px 34px 60px;max-width:1100px;margin:0 auto}
main h2{font-size:16px;margin-bottom:4px;display:flex;align-items:center;gap:10px}
main h2 .cnt{color:var(--dim);font-size:12px;font-weight:400}
.hint{color:var(--dim);font-size:12px;margin-bottom:20px}
.timeline{position:relative;padding-left:0}
.ev{margin:0 0 12px;padding:12px 16px;background:var(--panel);border:1px solid var(--border);
border-radius:10px}
.ev .head{display:flex;align-items:center;gap:8px;margin-bottom:6px}
.ev .t{color:var(--dim);font-size:11px;font-family:ui-monospace,monospace}
.badge{font-size:10px;padding:1px 8px;border-radius:12px;font-weight:600;letter-spacing:.3px}
.b-user{background:#4cc2ff1f;color:var(--user)}
.b-pi{background:#57d9a31f;color:var(--pi)}
.b-tool{background:#e3b3411f;color:var(--tool)}
.b-err{background:#ff6b6b1f;color:var(--err)}
.ev .body{white-space:pre-wrap;word-break:break-word;color:#dbe2ec}
.ev .body .code{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12.5px;color:#c9d4e5}
details{margin-top:4px}
details summary{cursor:pointer;color:var(--think);font-size:12px;user-select:none;list-style:none}
details summary::before{content:"▸ ";color:var(--think)}
details[open] summary::before{content:"▾ "}
details div{color:#aab4c8;font-size:13px;margin-top:8px;padding:10px 12px;
background:var(--panel2);border-left:2px solid var(--border);border-radius:6px;
white-space:pre-wrap;word-break:break-word}
.journal{margin-top:34px}
.journal h3{font-size:14px;color:var(--pi);margin-bottom:10px}
.journal pre{white-space:pre-wrap;background:var(--panel);border:1px solid var(--border);
border-radius:10px;padding:16px;font:13px/1.7 ui-monospace,SFMono-Regular,monospace;color:#c9d1d9}
@media(max-width:800px){.layout{flex-direction:column}aside{width:100%;height:auto;position:static;
border-right:none;border-bottom:1px solid var(--border)}aside nav{display:flex;flex-wrap:wrap;gap:4px}
aside nav a{margin:0}main{padding:16px}}
"""


def agent_exec(args, user="agent", timeout=120):
    if CLOUD:
        cmd = ["docker", "exec", "-u", user, "fap-agent", *args]
    else:
        cmd = ["docker", "compose", "exec", "-u", user, "-T", "agent", *args]
    r = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)
    return r


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
                return f.read()
        return ""
    r = agent_exec(["cat", container_path])
    return r.stdout if r.returncode == 0 else ""


def redact(s):
    for k, v in REDACTED.items():
        s = s.replace(k, v)
    return s


def esc(s):
    s = redact(str(s))
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def render_blocks(content):
    if isinstance(content, str):
        return f"<div class='body'>{esc(content)}</div>"
    if not isinstance(content, list):
        return f"<div class='body'>{esc(content)}</div>"
    parts = []
    for b in content:
        if not isinstance(b, dict):
            parts.append(f"<div class='body'>{esc(b)}</div>")
            continue
        t = b.get("type", "")
        if t == "text":
            parts.append(f"<div class='body'>{esc(b.get('text', ''))}</div>")
        elif t in ("thinking", "reasoning"):
            parts.append(f"<details><summary>思考</summary><div>{esc(b.get('text', ''))}</div></details>")
        elif t == "toolCall":
            args = json.dumps(b.get("arguments", b.get("args", {})), ensure_ascii=False)
            name = b.get("name", b.get("toolName", "?"))
            parts.append(f"<div class='body code'><span class='badge b-tool'>工具</span> {esc(name)} {esc(args)}</div>")
        elif t == "toolResult":
            data = str(b.get("data", ""))[:800]
            parts.append(f"<div class='body code'><span class='badge b-tool'>结果</span> {esc(data)}</div>")
        else:
            parts.append(f"<div class='body'>{esc(str(b)[:300])}</div>")
    return "\n".join(parts)


def event_html(r):
    t = r.get("type")
    ts = (r.get("timestamp") or "")[11:19]
    if t == "message":
        m = r.get("message", {})
        role = m.get("role")
        if role == "user":
            return (f"<div class='ev'><div class='head'><span class='t'>{ts}</span>"
                    f"<span class='badge b-user'>宿主</span></div>{render_blocks(m.get('content'))}</div>")
        if role == "assistant":
            body = render_blocks(m.get("content"))
            if not body.strip():
                return ""
            return (f"<div class='ev'><div class='head'><span class='t'>{ts}</span>"
                    f"<span class='badge b-pi'>Pi</span></div>{body}</div>")
        return (f"<div class='ev'><div class='head'><span class='t'>{ts}</span>"
                f"<span class='badge b-tool'>{esc(role)}</span></div>{render_blocks(m.get('content'))}</div>")
    if t == "error":
        return (f"<div class='ev'><div class='head'><span class='t'>{ts}</span>"
                f"<span class='badge b-err'>错误</span></div><div class='body'>{esc(json.dumps(r, ensure_ascii=False)[:400])}</div></div>")
    if t == "model_change":
        return (f"<div class='ev'><div class='head'><span class='t'>{ts}</span>"
                f"<span class='badge b-tool'>模型</span></div><div class='body'>{esc(r.get('model','?'))}</div></div>")
    return ""


def day_of(ts):
    return (ts or "")[:10]


def page_html(events, days, current_day, journal):
    events = sorted(events, key=lambda r: r.get("timestamp") or "", reverse=True)
    nav = []
    for d in days:
        cls = ' class="active"' if d == current_day else ""
        href = "index.html" if d == days[0] else f"days/{d}.html"
        cnt = sum(1 for r in events if day_of(r.get("timestamp", "")) == d)
        nav.append(f'<a{cls} href="{href}"><span>{d}</span><span class="cnt">{cnt}</span></a>')
    body = "".join(event_html(r) for r in events)

    now = datetime.now(timezone.utc)
    updated = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    last_ts = max((r.get("timestamp", "") for r in events), default="")
    chip = ""
    try:
        last_dt = datetime.fromisoformat(last_ts.replace("Z", "+00:00"))
        age_min = (now - last_dt).total_seconds() / 60
        if age_min < 10:
            chip = f'<span class="chip live">● 活跃 · {int(age_min)} 分钟前有动静</span>'
        elif age_min < 60:
            chip = f'<span class="chip idle">● 空闲 · {int(age_min)} 分钟前</span>'
        else:
            chip = f'<span class="chip down">● 离线 · {int(age_min)} 分钟前</span>'
    except Exception:
        chip = '<span class="chip">状态未知</span>'

    journal_html = ""
    if journal.strip():
        journal_html = (f'<div class="journal"><h3>📓 journal.md · agent 自写心得</h3>'
                        f'<pre>{esc(journal)}</pre></div>')
    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>free agent playground · {current_day}</title>
<style>{CSS}</style>
<meta http-equiv="refresh" content="60">
</head><body>
<header>
<div>
<h1>free <b>agent</b> playground</h1>
<div class="sub">隔离沙箱里的自主 AI · 实时观察 · <a href="https://github.com/xstrace/free-agents-playground" style="color:var(--accent)">源码</a></div>
</div>
<div style="margin-left:auto;display:flex;gap:8px;align-items:center">
{chip}
<span class="chip">{updated}</span>
</div>
</header>
<div class="layout">
<aside>
<div class="side-title">按天归档</div>
<nav>{''.join(nav)}</nav>
<div class="foot">每 60 秒自动刷新<br>事件新→旧排列<br>思考/工具调用可折叠</div>
</aside>
<main>
<h2>{current_day} <span class="cnt">{len(events)} 条事件</span></h2>
<div class="hint">最新在前 · 页面每 60 秒自动重载</div>
<div class="timeline">{body}</div>
{journal_html}
</main>
</div></body></html>"""


def ensure_repo():
    """渲染前先准备好 gh-pages 仓库(clone 远端历史, 保证 fast-forward 推送)"""
    if os.path.isdir(os.path.join(PAGES_REPO, ".git")):
        return
    r = subprocess.run(
        ["git", "clone", "-q", "--depth", "1", "-b", "gh-pages", REMOTE, PAGES_REPO],
        capture_output=True, text=True, timeout=120, env=GIT_ENV)
    if r.returncode != 0:
        os.makedirs(PAGES_REPO, exist_ok=True)
        subprocess.run(["git", "init", "-q", "-b", "gh-pages"], cwd=PAGES_REPO, check=True)
        subprocess.run(["git", "remote", "add", "origin", REMOTE], cwd=PAGES_REPO, check=True)


def render_site():
    ensure_repo()
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
    latest = days[0]
    (out / "index.html").write_text(
        page_html([r for r in events if day_of(r.get("timestamp", "")) == latest], days, latest, journal))
    return out


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
    print(f"[pages] 渲染器启动, 每 {INTERVAL}s 检查 (→ {OWNER}/{REPO} gh-pages)", flush=True)
    while True:
        try:
            out = render_site()
            if out and git_push():
                print(f"[pages] {time.strftime('%H:%M:%S', time.gmtime())} 已推送更新", flush=True)
        except Exception as e:
            print(f"[pages] 错误: {e}", flush=True)
        if ONCE:
            break
        time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
