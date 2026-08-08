#!/usr/bin/env python3
"""宿主侧 supervisor: 让 agent "永不瞑目" 的驱动循环 + 可信侧审计。

规则:
- 每 5 秒 tick 一次
- 每 LOOP_INTERVAL_SEC(默认 60)检查上一轮是否完成:
  - agent 正在输出(心跳新鲜) → 在运行, 不注入
  - agent 空闲(心跳过期) 且距上次注入够久 → 注入下一轮提示词(三风格随机)
  - 进程/会话死了 → 重启会话 + 注入"重连"提示词
  - 容器挂了 → 拉起(VPS: docker compose up; 云端 FAP_CLOUD=1: 跑 data/restart-agent.sh)

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

CLOUD = os.environ.get("FAP_CLOUD") == "1"
CT = "fap-agent"
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


def agent_exec(args, user="agent", timeout=30):
    """进 agent 容器跑命令(VPS 用 compose exec, 云端用 docker exec)"""
    if CLOUD:
        cmd = ["docker", "exec", "-u", user, CT, *args]
    else:
        cmd = ["docker", "compose", "exec", "-u", user, "-T", "agent", *args]
    return subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=timeout)


def sh(*args, timeout=60):
    try:
        r = subprocess.run(
            ["docker", "compose", *args], cwd=ROOT,
            capture_output=True, text=True, timeout=timeout,
        )
        return r.stdout.strip() if r.stdout else r.returncode
    except subprocess.TimeoutExpired:
        return -1


def container_up():
    if CLOUD:
        r = subprocess.run(["docker", "ps", "-q", "-f", f"name={CT}"],
                           capture_output=True, text=True, timeout=30)
        return bool(r.stdout.strip())
    return bool(sh("ps", "-q", "agent"))


def container_start():
    """容器挂了时拉起"""
    if CLOUD:
        script = os.path.join(ROOT, "data", "restart-agent.sh")
        if os.path.exists(script):
            subprocess.run(["bash", script], cwd=ROOT, timeout=120)
        else:
            log("error", err="云端模式缺 data/restart-agent.sh")
    else:
        sh("up", "-d", "agent")


def tmux_alive():
    return agent_exec(["tmux", "has-session", "-t", "main"]).returncode == 0


def pi_running():
    r = agent_exec(["sh", "-c", "pgrep -f /usr/local/bin/pi >/dev/null && echo yes"], user="root")
    return "yes" in r.stdout


def heartbeat_ts():
    r = agent_exec(["stat", "-c", "%Y", HEARTBEAT], user="root")
    try:
        return float(r.stdout.strip())
    except (ValueError, IndexError):
        return None


def inject(prompt):
    r = agent_exec(["/opt/inject.sh", prompt], user="agent")
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
    r = agent_exec(["sh", "-c", f"test -f {SEED_MARKER} && echo yes"], user="root")
    if "yes" not in r.stdout:
        prompt = render("seed.md")
        if inject(prompt):
            agent_exec(["touch", SEED_MARKER], user="agent")
        return True
    return False


def snapshot_memory():
    r = agent_exec(["sh", "-c", "tar -cf - -C /workspace memory 2>/dev/null || true"], user="root", timeout=60)
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
        if CLOUD:
            p = subprocess.Popen(
                ["docker", "logs", "-f", "--timestamps", CT],
                cwd=ROOT, stdout=open(path, "a"), stderr=subprocess.STDOUT,
            )
        else:
            p = subprocess.Popen(
                ["docker", "compose", "logs", "-f", "--timestamps", "agent"],
                cwd=ROOT, stdout=open(path, "a"), stderr=subprocess.STDOUT,
            )
        p.wait()
        time.sleep(2)


def main():
    log("supervisor_start", loop_interval=LOOP_INTERVAL_SEC, idle_done=IDLE_DONE_SEC, cloud=CLOUD)

    import threading
    threading.Thread(target=transcript_tailer, daemon=True).start()

    last_snapshot = 0
    while True:
        try:
            if not container_up():
                log("container_down", action="restart")
                container_start()
                time.sleep(10)
                continue

            seeded = seed_if_needed()
            if seeded:
                time.sleep(TICK)
                continue

            t = time.time()
            if not pi_running():
                if not tmux_alive():
                    time.sleep(3)
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

            if t - last_snapshot > 3600:
                snapshot_memory()
                last_snapshot = t

        except Exception as e:
            log("error", err=str(e))
        time.sleep(TICK)


if __name__ == "__main__":
    main()
