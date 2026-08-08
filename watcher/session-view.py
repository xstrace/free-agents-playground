#!/usr/bin/env python3
"""宿主侧: 流式查看 pi 正在做什么(结构化, 非原始 TUI 字节)。

读取 pi 会话 JSONL(自动跟随最新会话文件), 把 user/assistant/tool 事件
渲染成可读流。用法: make session   (Ctrl+C 退出)
"""
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SESS_GLOB = "/workspace/.pi/agent/sessions/*/*.jsonl"

ESC = "\033["
C_USER, C_ASSIST, C_TOOL, C_DIM, C_ERR, C_RESET = (
    f"{ESC}36m", f"{ESC}32m", f"{ESC}33m", f"{ESC}90m", f"{ESC}31m", f"{ESC}0m",
)


def exec_out(*args):
    r = subprocess.run(args, cwd=ROOT, capture_output=True, text=True, timeout=30)
    return r.stdout.strip()


def latest_session():
    out = exec_out("docker", "compose", "exec", "-u", "agent", "-T", "agent",
                   "sh", "-c", f"ls -t {SESS_GLOB} 2>/dev/null | head -1")
    return out


def fmt_content(content):
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = []
        for b in content:
            t = b.get("type", "")
            if t == "text":
                parts.append(b.get("text", ""))
            elif t in ("thinking", "reasoning"):
                parts.append(f"{C_DIM}[思考] {b.get('text', '')[:400]}{C_RESET}")
            elif t == "toolCall":
                args = json.dumps(b.get("arguments", b.get("args", {})), ensure_ascii=False)[:200]
                parts.append(f"{C_TOOL}[调用 {b.get('name', b.get('toolName', '?'))}] {args}{C_RESET}")
            elif t == "toolResult":
                data = str(b.get("data", ""))[:200]
                parts.append(f"{C_TOOL}[结果] {data}{C_RESET}")
            else:
                parts.append(str(b)[:200])
        return "\n".join(parts)
    return str(content)[:200]


def render(line):
    try:
        r = json.loads(line)
    except json.JSONDecodeError:
        return None
    raw_ts = r.get("timestamp") or r.get("ts") or ""
    ts = raw_ts[11:19] if len(raw_ts) > 19 else raw_ts
    t = r.get("type")
    if t == "message":
        m = r.get("message", {})
        role = m.get("role")
        content = fmt_content(m.get("content"))
        if not content:
            return None
        if role == "user":
            return f"{C_USER}[{ts} 用户]{C_RESET} {content}"
        if role == "assistant":
            return f"{C_ASSIST}[{ts} Pi]{C_RESET} {content}"
        return f"[{ts} {role}] {content}"
    if t == "error":
        return f"{C_ERR}[{ts} 错误]{C_RESET} {str(r)[:200]}"
    if t == "model_change":
        return f"{C_DIM}[{ts} 模型切换] {r.get('model')}{C_RESET}"
    return None


def main():
    path = latest_session()
    if not path:
        print("还没找到 pi 会话文件(pi 启动后会自动创建), 稍等重试...")
        sys.exit(1)
    print(f"{C_DIM}跟随会话: {path}{C_RESET}\n", file=sys.stderr)
    p = subprocess.Popen(
        ["docker", "compose", "exec", "-u", "agent", "-T", "agent", "tail", "-f", "-n", "+1", path],
        cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    try:
        for line in p.stdout:
            out = render(line)
            if out:
                print(out, flush=True)
    except KeyboardInterrupt:
        p.kill()


if __name__ == "__main__":
    main()
