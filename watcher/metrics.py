#!/usr/bin/env python3
"""宿主侧资源采样: 每秒 docker stats + 每 5s 工作区磁盘使用 -> audit/metrics.json"""
import json
import os
import subprocess
import time
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AUDIT = os.path.join(ROOT, "audit")
os.makedirs(AUDIT, exist_ok=True)
OUT = os.path.join(AUDIT, "metrics.json")

INTERVAL = int(os.environ.get("METRICS_INTERVAL", "5"))


def stats(name):
    r = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{json .}}", name],
        capture_output=True, text=True, timeout=20,
    )
    if r.returncode == 0 and r.stdout.strip():
        try:
            return json.loads(r.stdout)
        except json.JSONDecodeError:
            return None
    return None


def workspace_usage():
    """data/workspace.img(10G loop) 的使用情况"""
    try:
        r = subprocess.run(
            ["df", "-B1", "--output=size,used", os.path.join(ROOT, "data", "workspace.img")],
            capture_output=True, text=True, timeout=10,
        )
        lines = r.stdout.strip().splitlines()
        if len(lines) >= 2:
            size, used = lines[1].split()
            return {"disk_bytes": int(size), "disk_used": int(used)}
    except Exception:
        pass
    return {}


def main():
    print(f"[metrics] -> {OUT} (每 {INTERVAL}s)", flush=True)
    with open(OUT, "a") as f:
        while True:
            rec = {
                "ts": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                "agent": stats("fap-agent"),
                "proxy": stats("fap-proxy"),
                **workspace_usage(),
            }
            f.write(json.dumps(rec) + "\n")
            f.flush()
            time.sleep(INTERVAL)


if __name__ == "__main__":
    main()
