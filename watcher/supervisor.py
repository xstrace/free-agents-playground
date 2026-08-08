#!/usr/bin/env python3
"""宿主侧 supervisor: 让 agent "永不瞑目" 的驱动循环 + 可信侧审计。

规则(用户指定):
- 每 5 秒 tick 一次
- 每 5 分钟(LOOP_INTERVAL_SEC)检查上一轮是否完成:
  - agent 正在输出(心跳新鲜) → 在运行, 不注入
  - agent 空闲(心跳过期) 且距上次注入够久 → 注入下一轮提示词
  - 进程/会话死了 → 重启会话 + 注入"重连"提示词
  - 容器挂了 → docker compose up 拉起来

审计(宿主侧, agent 碰不到):
- audit/supervisor.jsonl   状态机事件 + 注入的每条提示词
- audit/transcript.log     docker logs 逐字转录(跟随容器重启)
- audit/memory-snapshot/   每小时把 /workspace/memory 拉回宿主备份
"""
import json
import os
import random
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "audit")
PROMPTS = os.path.join(ROOT, "agent", "prompts")
os.makedirs(AUDIT, exist_ok=True)

TICK = 5
LOOP_INTERVAL_SEC = int(os.environ.get("LOOP_INTERVAL_SEC", "60"))
IDLE_DONE_SEC = int(os.environ.get("IDLE_DONE_SEC", "45"))
HEARTBEAT = "/workspace/.heartbeat"
SEED_MARKER = "/workspace/.seeded"
HEARTBEAT_PROMPTS = ["heartbeat.md", "heartbeat-wild.md", "heartbeat-quiet.md"]

STATE_FILE = os.path.join(AUDIT, "last_inject.ts")
LOG_FILE = os.path.join(AUDIT, "supervisor.jsonl")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def log(event, **kw):
    rec = {"ts": now_iso(), "event": event, **kw}
    with open(LOG_FILE, "a") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    print(f"[supervisor] {event}: {json.dumps({k: v for k, v in kw.items()}, ensure_ascii=False)}", flush=True)


def sh(*args, check=False, capture=True, timeout=30):
    """在项目根目录跑 docker compose 命令"""
    try:
        r = subprocess.run(
            ["docker", "compose", *args],
            cwd=ROOT, capture_output=True, text=True, timeout=timeout,
        )
        if capture and r.stdout:
            return r.stdout.strip()
        if r.returncode != 0 and check:
            raise RuntimeError(r.stderr.strip())
        return ""
    except subprocess.TimeoutExpired:
        return "" if not check else (_ for _ in ()).throw(RuntimeError("timeout"))


def container_up():
    out = sh("ps", "-q", "agent")
    return bool(out)


def tmux_alive():
    r = subprocess.run(
        ["docker", "compose", "exec", "-u", "agent", "-T", "agent",
         "tmux", "has-session", "-t", "main"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    return r.returncode == 0


def pi_running():
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "agent", "sh", "-c", "pgrep -f /usr/local/bin/pi >/dev/null && echo yes"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    return "yes" in r.stdout


def heartbeat_ts():
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "agent", "stat", "-c", "%Y", HEARTBEAT],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    try:
        return float(r.stdout.strip())
    except (ValueError, IndexError):
        return None


def inject(prompt):
    r = subprocess.run(
        ["docker", "compose", "exec", "-u", "agent", "-T", "agent", "/opt/inject.sh", prompt],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    ok = r.returncode == 0
    log("inject", ok=ok, prompt=prompt)
    if ok:
        with open(STATE_FILE, "w") as f:
            f.write(str(time.time()))
    return ok


def render(tpl_name, **kw):
    with open(os.path.join(PROMPTS, tpl_name)) as f:
        tpl = f.read()
    for k, v in kw.items():
        tpl = tpl.replace("{{" + k + "}}", v)
    return tpl


def last_inject():
    try:
        with open(STATE_FILE) as f:
            return float(f.read().strip())
    except Exception:
        return 0


def seed_if_needed():
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "agent", "sh", "-c",
         f"test -f {SEED_MARKER} && echo yes"],
        cwd=ROOT, capture_output=True, text=True, timeout=30,
    )
    if "yes" not in r.stdout:
        prompt = render("seed.md")
        if inject(prompt):
            subprocess.run(
                ["docker", "compose", "exec", "-u", "agent", "-T", "agent", "touch", SEED_MARKER],
                cwd=ROOT, capture_output=True, timeout=30,
            )
        return True
    return False


def snapshot_memory():
    r = subprocess.run(
        ["docker", "compose", "exec", "-T", "agent", "sh", "-c",
         "tar -cf - -C /workspace memory 2>/dev/null || true"],
        cwd=ROOT, capture_output=True, timeout=60,
    )
    if r.returncode == 0 and r.stdout:
        os.makedirs(os.path.join(AUDIT, "memory-snapshot"), exist_ok=True)
        import tarfile, io
        with tarfile.open(fileobj=io.BytesIO(r.stdout), mode="r|") as tf:
            tf.extractall(os.path.join(AUDIT, "memory-snapshot"))
        log("memory_snapshot", bytes=len(r.stdout))


def transcript_tailer():
    """跟随 docker logs, 逐字转录到 audit/transcript.log(追加)。"""
    path = os.path.join(AUDIT, "transcript.log")
    while True:
        p = subprocess.Popen(
            ["docker", "compose", "logs", "-f", "--timestamps", "agent"],
            cwd=ROOT, stdout=open(path, "a"), stderr=subprocess.STDOUT,
        )
        p.wait()  # docker 进程退出(容器重启等), 重新接上
        time.sleep(2)


def main():
    log("supervisor_start", loop_interval=LOOP_INTERVAL_SEC, idle_done=IDLE_DONE_SEC)

    import threading
    threading.Thread(target=transcript_tailer, daemon=True).start()

    last_snapshot = 0
    while True:
        try:
            if not container_up():
                log("container_down", action="compose_up")
                sh("up", "-d", "agent", check=False)
                time.sleep(10)
                continue

            seeded = seed_if_needed()
            if seeded:
                time.sleep(TICK)
                continue

            t = time.time()
            # 注入节奏判断
            if not pi_running():
                # 进程死了(会话也没了) -> entrypoint 会自动重建, 注入重连提示
                if not tmux_alive():
                    time.sleep(3)  # 给 entrypoint 重建的时间
                if t - last_inject() > 60 and not tmux_alive():
                    log("agent_dead", action="inject_relaunch")
                    inject(render("relaunch.md", TIMESTAMP=now_iso()))
            else:
                hb = heartbeat_ts()
                idle = (t - hb) if hb else 9999
                if idle > IDLE_DONE_SEC and t - last_inject() > LOOP_INTERVAL_SEC:
                    log("idle_detect", idle_sec=int(idle), action="inject_heartbeat")
                    tpl = random.choice(HEARTBEAT_PROMPTS)
                    inject(render(tpl, TIMESTAMP=now_iso()))

            # 每小时备份 memory
            if t - last_snapshot > 3600:
                snapshot_memory()
                last_snapshot = t

        except Exception as e:
            log("error", err=str(e))
        time.sleep(TICK)


if __name__ == "__main__":
    main()
