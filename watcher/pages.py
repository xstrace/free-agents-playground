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
import re
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
.ev .body.md p{margin:4px 0}
.ev .body.md ul,.ev .body.md ol{margin:6px 0 6px 20px}
.ev .body.md li{margin:2px 0}
.ev .body.md pre{background:#0a0e16;border:1px solid var(--border);border-radius:6px;
padding:10px;overflow-x:auto;font:12px/1.6 ui-monospace,monospace;margin:6px 0;color:#c9d4e5}
.ev .body.md code{background:var(--panel2);border-radius:4px;padding:0 5px;
font:12px ui-monospace,monospace;color:#e3b341}
.ev .body.md pre code{background:none;padding:0;color:inherit}
.ev .body.md blockquote{margin:6px 0;padding:4px 10px;border-left:2px solid var(--tool);
color:#b9c3d4}
.cmd{font-family:ui-monospace,SFMono-Regular,monospace;font-size:12.5px;background:#0a0e16;
border:1px solid var(--border);border-left:3px solid var(--tool);border-radius:6px;
padding:7px 10px;margin-top:4px;white-space:pre-wrap;word-break:break-all;color:#d8e0ee}
.cmd .prompt{color:var(--tool)}
details{margin-top:4px}
details summary{cursor:pointer;color:var(--think);font-size:12px;user-select:none;list-style:none}
details summary::before{content:"▸ ";color:var(--think)}
details[open] summary::before{content:"▾ "}
details div{color:#aab4c8;font-size:13px;margin-top:8px;padding:10px 12px;
background:var(--panel2);border-left:2px solid var(--border);border-radius:6px;
white-space:pre-wrap;word-break:break-word}
.journal-page{margin-top:0}
.journal-page h2{font-size:16px;margin-bottom:14px}
.art{display:flex;align-items:center;gap:10px;background:var(--panel);border:1px solid var(--border);
border-radius:10px;padding:12px 16px;margin-bottom:8px}
.art a{color:var(--accent);text-decoration:none;font-size:14px}
.art a:hover{text-decoration:underline}
.art .cnt{color:var(--dim);font-size:12px;margin-left:auto}
.art-ic{font-size:16px}
.md{background:var(--panel);border:1px solid var(--border);border-radius:12px;padding:24px 28px;
line-height:1.75;color:#d5dce8;font-size:14.5px}
.md h1,.md h2,.md h3,.md h4{color:var(--pi);margin:22px 0 10px;line-height:1.4}
.md h1{font-size:22px;border-bottom:1px solid var(--border);padding-bottom:8px}
.md h2{font-size:18px;border-bottom:1px solid var(--border);padding-bottom:6px}
.md h3{font-size:15.5px}.md h4{font-size:14px;color:var(--text)}
.md p{margin:10px 0}
.md ul,.md ol{margin:10px 0 10px 22px}
.md li{margin:4px 0}
.md blockquote{margin:12px 0;padding:8px 14px;border-left:3px solid var(--tool);
background:var(--panel2);border-radius:0 8px 8px 0;color:#b9c3d4}
.md pre{background:#0a0e16;border:1px solid var(--border);border-radius:8px;padding:14px;
overflow-x:auto;font:12.5px/1.6 ui-monospace,SFMono-Regular,monospace;margin:12px 0;color:#c9d4e5}
.md code{background:var(--panel2);border:1px solid var(--border);border-radius:4px;
padding:1px 6px;font:12.5px ui-monospace,monospace;color:#e3b341}
.md pre code{background:none;border:none;padding:0;color:inherit}
.md hr{border:none;border-top:1px solid var(--border);margin:20px 0}
.md a{color:var(--accent)}
@media(max-width:800px){.layout{flex-direction:column}aside{width:100%;height:auto;position:static;
border-right:none;border-bottom:1px solid var(--border)}aside nav{display:flex;flex-wrap:wrap;gap:4px}
aside nav a{margin:0}main{padding:16px}}
"""


def inline_md(s):
    """行内标记: 行内代码 / 加粗 / 斜体 / 链接"""
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<b>\1</b>", s)
    s = re.sub(r"([*_])([^*_]+)\1", r"<i>\2</i>", s)
    s = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', s)
    return s


def render_markdown(text, compact=False):
    """零依赖轻量 markdown → HTML(标题/列表/引用/代码块/段落/分隔线)
    compact: 事件流内使用, 标题降级为加粗避免大标题"""
    def head(level, content):
        if compact:
            return f"<p><b>{content}</b></p>"
        return f"<h{level}>{content}</h{level}>"

    lines = text.split("\n")
    out, i, in_code, code_buf = [], 0, False, []
    while i < len(lines):
        line = lines[i]
        if line.strip().startswith("```"):
            if in_code:
                out.append("<pre>" + "".join(code_buf) + "</pre>")
                code_buf, in_code = [], False
            else:
                in_code = True
            i += 1
            continue
        if in_code:
            code_buf.append(line + "\n")
            i += 1
            continue
        s = line.strip()
        if not s:
            i += 1
            continue
        m = re.match(r"^(#{1,4})\s+(.*)$", s)
        if m:
            out.append(head(len(m.group(1)), inline_md(m.group(2))))
            i += 1
            continue
        if re.match(r"^[-*]\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\s*[-*]\s+", lines[i].strip()):
                items.append("<li>" + inline_md(lines[i].strip()[2:]) + "</li>")
                i += 1
            out.append("<ul>" + "".join(items) + "</ul>")
            continue
        if re.match(r"^\d+\.\s+", s):
            items = []
            while i < len(lines) and re.match(r"^\d+\.\s+", lines[i].strip()):
                items.append("<li>" + inline_md(re.sub(r"^\d+\.\s+", "", lines[i].strip())) + "</li>")
                i += 1
            out.append("<ol>" + "".join(items) + "</ol>")
            continue
        if s.startswith(">"):
            out.append("<blockquote>" + inline_md(s.lstrip(">").strip()) + "</blockquote>")
            i += 1
            continue
        if re.match(r"^[-*_]{3,}$", s):
            out.append("<hr>")
            i += 1
            continue
        para = [inline_md(s)]
        i += 1
        while i < len(lines) and lines[i].strip() and not re.match(
                r"^(#{1,4}\s|[-*]\s|\d+\.\s|>|```|[-*_]{3,}$)", lines[i].strip()):
            para.append(inline_md(lines[i].strip()))
            i += 1
        out.append("<p>" + "<br>".join(para) + "</p>")
    if in_code:
        out.append("<pre>" + "".join(code_buf) + "</pre>")
    return "\n".join(out)


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
        return f"<div class='body md'>{render_markdown(content, compact=True)}</div>"
    if not isinstance(content, list):
        return f"<div class='body'>{esc(content)}</div>"
    parts = []
    for b in content:
        if not isinstance(b, dict):
            parts.append(f"<div class='body'>{esc(b)}</div>")
            continue
        t = b.get("type", "")
        if t == "text":
            parts.append(f"<div class='body md'>{render_markdown(b.get('text', ''), compact=True)}</div>")
        elif t in ("thinking", "reasoning"):
            parts.append(f"<details><summary>思考</summary><div>{esc(b.get('text', ''))}</div></details>")
        elif t == "toolCall":
            name = b.get("name", b.get("toolName", "?"))
            args = b.get("arguments", b.get("args", {}))
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {"raw": args}
            if not isinstance(args, dict):
                args = {"raw": str(args)}
            # bash: 展示实际执行的命令(看得见访问了什么/搜了什么)
            if name == "bash" and args.get("command"):
                cmd = str(args["command"]).strip()
                shown = cmd if len(cmd) <= 500 else cmd[:497] + "..."
                parts.append(f'<div class="cmd"><span class="badge b-tool">bash</span>'
                             f'<span class="prompt">$ </span>{esc(shown)}</div>')
            else:
                # 其他工具: 高亮关键参数(路径/URL/搜索词/模式)
                keys = ("path", "file", "url", "query", "pattern", "dir", "filename", "name")
                summ = {k: str(args[k])[:120] for k in keys if k in args}
                extra = json.dumps(summ, ensure_ascii=False) if summ else json.dumps(args, ensure_ascii=False)
                if len(extra) > 200:
                    extra = extra[:197] + "..."
                parts.append(f'<div class="body code"><span class="badge b-tool">{esc(name)}</span> {esc(extra)}</div>')
        elif t == "toolResult":
            data = b.get("data", "")
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False, indent=1)
            data = str(data)
            if len(data) > 800:
                data = data[:797] + "..."
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


def layout(title, days, current_day, body, journal_active=False, artifacts_active=False):
    """共享骨架: header + 侧栏(日记/作品入口 + 按天归档) + main"""
    nav = []
    jcls = ' class="active"' if journal_active else ""
    nav.append(f'<a{jcls} href="journal.html"><span>📓 日记</span><span class="cnt">journal</span></a>')
    acls = ' class="active"' if artifacts_active else ""
    nav.append(f'<a{acls} href="artifacts.html"><span>📦 作品</span><span class="cnt">files</span></a>')
    nav.append('<div class="side-title" style="margin-top:14px">按天归档(过程)</div>')
    for d in days:
        cls = ' class="active"' if (d == current_day and not journal_active) else ""
        href = "index.html" if d == days[0] else f"days/{d}.html"
        cnt = sum(1 for r in ALL_EVENTS if day_of(r.get("timestamp", "")) == d)
        nav.append(f'<a{cls} href="{href}"><span>{d}</span><span class="cnt">{cnt}</span></a>')

    now = datetime.now(timezone.utc)
    updated = now.strftime("%Y-%m-%d %H:%M:%S UTC")
    last_ts = max((r.get("timestamp", "") for r in ALL_EVENTS), default="")
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

    return f"""<!doctype html>
<html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>free agent playground · {title}</title>
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
<nav>{''.join(nav)}</nav>
<div class="foot">每 60 秒自动刷新<br>过程新→旧 · 日记即 journal.md</div>
</aside>
<main>
{body}
</main>
</div></body></html>"""


def events_body(events, current_day):
    events = sorted(events, key=lambda r: r.get("timestamp") or "", reverse=True)
    body = "".join(event_html(r) for r in events)
    return (f"<h2>{current_day} <span class='cnt'>{len(events)} 条事件</span></h2>"
            f"<div class='hint'>最新在前 · 页面每 60 秒自动重载</div>"
            f"<div class='timeline'>{body}</div>")


def journal_body(journal):
    md = render_markdown(journal) if journal.strip() else "<p>日记还是空的。</p>"
    return f"""<div class="journal-page">
<h2>📓 日记 <span class="cnt">journal.md · agent 自写</span></h2>
<div class="md">{md}</div>
</div>"""


# ── 作品集: agent 在 workspace 创作的文件 ─────────────────────────
ARTIFACT_EXCLUDE = {".pi", ".heartbeat", ".seeded", "agent.log", "memory",
                    "lost+found", "__pycache__", ".git"}
TEXT_EXTS = (".md", ".py", ".sh", ".json", ".txt", ".ts", ".yml", ".yaml",
             ".log", ".toml", ".conf", ".html", ".css")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg")


def artifact_files(ws):
    """返回 [(name, size, kind)], kind: md/code/img/text/bin"""
    if not os.path.isdir(ws):
        return []
    items = []
    for name in sorted(os.listdir(ws)):
        if name in ARTIFACT_EXCLUDE:
            continue
        p = os.path.join(ws, name)
        if not os.path.isfile(p):
            continue
        size = os.path.getsize(p)
        low = name.lower()
        if low.endswith(".md"):
            kind = "md"
        elif low.endswith(IMG_EXTS):
            kind = "img"
        elif low.endswith(TEXT_EXTS):
            kind = "code"
        else:
            kind = "bin"
        items.append((name, size, kind))
    return items


def artifacts_page(ws, days):
    items = artifact_files(ws)
    if not items:
        body = "<h2>📦 作品</h2><div class='hint'>还没有存档的作品。</div>"
        return layout("作品", days, days[0] if days else "", body, artifacts_active=True)
    rows = []
    kind_label = {"md": "markdown", "img": "图片", "code": "代码", "bin": "文件"}
    for name, size, kind in items:
        size_s = f"{size/1024:.1f} KB" if size >= 1024 else f"{size} B"
        icon = "🖼" if kind == "img" else ("📄" if kind == "md" else ("⚙️" if kind == "code" else "🗜"))
        rows.append(
            f'<div class="art"><span class="art-ic">{icon}</span>'
            f'<a href="artifacts/{esc(name)}.html"><b>{esc(name)}</b></a>'
            f'<span class="cnt">{kind_label[kind]} · {size_s}</span></div>')
    body = (f"<h2>📦 作品 <span class='cnt'>{len(items)} 个文件</span></h2>"
            f"<div class='hint'>agent 在沙箱里创作的文件 · 点击查看/下载</div>"
            + "".join(rows))
    return layout("作品", days, days[0] if days else "", body, artifacts_active=True)


def artifact_view_page(name, size, kind, ws, days):
    src = os.path.join(ws, name)
    if kind == "img":
        body = (f"<h2>📦 {esc(name)}</h2>"
                f"<div class='art-view'><img src='artifacts/{esc(name)}' alt='{esc(name)}' "
                f"style='max-width:100%;border-radius:10px'></div>")
    elif kind == "md":
        with open(src, errors="replace") as f:
            md = f.read()
        body = f"<h2>📦 {esc(name)}</h2><div class='md'>{render_markdown(md)}</div>"
    else:
        with open(src, errors="replace") as f:
            txt = f.read()[:50000]
        body = (f"<h2>📦 {esc(name)}</h2>"
                f"<div class='hint'>原文预览(前 50KB) · <a href='artifacts/{esc(name)}'>下载原文件</a></div>"
                f"<div class='md'><pre>{esc(txt)}</pre></div>")
    return layout(esc(name), days, days[0] if days else "", body)


def render_artifacts(ws, days, out):
    """复制作品原文件到站点目录, 生成列表页与预览页"""
    if not LOCAL_WS:
        return
    items = artifact_files(ws)
    if not items:
        return
    art_dir = Path(PAGES_REPO) / "artifacts"
    art_dir.mkdir(parents=True, exist_ok=True)
    import shutil
    for name, size, kind in items:
        src = os.path.join(ws, name)
        try:
            shutil.copy2(src, art_dir / name)
        except Exception:
            continue
        if kind != "bin":
            (art_dir / f"{name}.html").write_text(
                artifact_view_page(name, size, kind, ws, days), encoding="utf-8")
    (Path(PAGES_REPO) / "artifacts.html").write_text(artifacts_page(ws, days), encoding="utf-8")


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
    global ALL_EVENTS
    _, events = pull_latest_session()
    journal = pull_file("/workspace/journal.md")
    ALL_EVENTS = events
    days = sorted({day_of(r.get("timestamp", "")) for r in events if r.get("timestamp")}, reverse=True)
    if not days:
        return None

    out = Path(PAGES_REPO)
    (out / "days").mkdir(parents=True, exist_ok=True)
    for d in days:
        day_events = [r for r in events if day_of(r.get("timestamp", "")) == d]
        (out / "days" / f"{d}.html").write_text(
            layout(d, days, d, events_body(day_events, d)))
    latest = days[0]
    (out / "index.html").write_text(
        layout(latest, days, latest, events_body([r for r in events if day_of(r.get("timestamp", "")) == latest], latest)))
    (out / "journal.html").write_text(
        layout("日记", days, latest, journal_body(journal), journal_active=True))
    render_artifacts(LOCAL_WS, days, out)
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
