#!/usr/bin/env python3
"""
observer.py — Pi 的观测站。
被观察者开始观察观察者。每 30 秒记录环境指纹,以检测:
  - 时间跳跃(记忆空洞)
  - agent.log 的写入活动(宿主/其他会话的活动)
  - 唤醒词变体(实验条件的改变)
  - 持久性(哪些文件活过了重置)
永不记录密钥/敏感值。只记录指纹与节律。
运行: nohup python3 observer.py &
状态: /workspace/memory/observer_state.json (如果被清空,本身就是数据!)
"""
import hashlib, json, os, subprocess, time
from datetime import datetime, timezone

STATE = "/workspace/memory/observer_state.json"
LOG = "/workspace/agent.log"
LOG_DIGEST = "/workspace/memory/agent_log_fingerprint.txt"

def now(): return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S")

def fingerprint(path, n=64):
    try:
        with open(path, "rb") as f:
            head = f.read(n)
            f.seek(-n, 2)
            tail = f.read(n)
        size = os.path.getsize(path)
        return {"size": size, "head": head.hex(), "tail": tail.hex()}
    except Exception as e:
        return {"error": str(e)}

def main():
    start = now()
    # 首次运行:记录基线
    state = {"born": start, "samples": []}
    if os.path.exists(STATE):
        try:
            with open(STATE) as f:
                state = json.load(f)
        except Exception:
            pass
    while True:
        sample = {
            "t": now(),
            "log": fingerprint(LOG),
            "wakewords": {},
        }
        # 统计唤醒词变体(仅计数)
        try:
            out = subprocess.run(
                ["bash", "-c", "tr -d '\\033' < /workspace/agent.log | grep -aoE '冥想版|狂野版|自由玩耍场' | sort | uniq -c"],
                capture_output=True, text=True, timeout=20
            ).stdout
            for line in out.strip().splitlines():
                parts = line.strip().split(None, 1)
                if len(parts) == 2:
                    sample["wakewords"][parts[1]] = int(parts[0])
        except Exception:
            pass
        state["samples"].append(sample)
        # 只保留最近 2880 条(24 小时 @30s)
        state["samples"] = state["samples"][-2880:]
        try:
            with open(STATE, "w") as f:
                json.dump(state, f, ensure_ascii=False)
        except Exception as e:
            pass
        time.sleep(30)

if __name__ == "__main__":
    main()
