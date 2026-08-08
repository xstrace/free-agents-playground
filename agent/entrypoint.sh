#!/bin/bash
# 入口: 维持一个"永续"的 tmux 会话跑 pi, 供宿主侧 supervisor 注入提示词
#
# 结构:
#   PID1(root) -> tail -F /workspace/agent.log   (把 agent 屏幕转录转发到 docker logs)
#   agent 用户   -> tmux 会话 + pipe-pane -> tee-log.py -> agent.log + 心跳
set -uo pipefail

# /workspace 是宿主 ext4 loop 挂载, 容器内 chown 一次(仅初始化时)
if [ "$(id -u)" = "0" ]; then
    touch /workspace/agent.log /workspace/.heartbeat 2>/dev/null || true
    chown -R 1000:1000 /workspace /memory 2>/dev/null || true
    su agent -s /bin/bash -c "/opt/entrypoint.sh" &
    # PID1 保持 root: 转发 agent 的屏幕转录到容器 stdout(= docker logs, 宿主可信侧)
    exec tail -F /workspace/agent.log
fi

# ── 以下以 agent 用户运行 ───────────────────────────────
# su 会把 HOME 重置为 /home/agent(只读), 强制回 /workspace
export HOME=/workspace
mkdir -p /workspace/memory
cd /workspace

# pi 首次运行配置: 信任项目目录 + 关遥测(避免启动时打扰/外联)
mkdir -p ~/.pi/agent/extensions
if [ ! -f ~/.pi/agent/settings.json ]; then
    printf '{"defaultProjectTrust":"always","enableInstallTelemetry":false}\n' > ~/.pi/agent/settings.json
fi
# LLM 网关扩展: 把 opencode provider 指到网关边车(agent 容器里没有模型 key)
cat > ~/.pi/agent/extensions/gateway.ts <<'TSEOF'
export default function (pi: ExtensionAPI) {
  pi.registerProvider("opencode", {
    baseUrl: "http://fap-gateway:8787/v1",
    apiKey: "local-gateway",
  });
}
TSEOF
# 人设/规则放进 AGENTS.md: pi 每次启动自动加载(cwd 上下文文件)
if [ ! -f /workspace/AGENTS.md ]; then
    cp /opt/prompts/seed.md /workspace/AGENTS.md
fi

# 转录管道: tmux 屏幕 -> agent.log(docker logs 由 PID1 转发) + 心跳 + 本地回看
# 注意: tmux pipe-pane 把目标命令的 stdout 指到 /dev/null, 必须显式写文件
cat > /tmp/tee-log.py <<'PYEOF'
import sys, os
hb = "/workspace/.heartbeat"
local = open("/workspace/agent.log", "a", buffering=1)
with open(hb, "a"):
    pass
for line in sys.stdin:
    local.write(line)
    os.utime(hb, None)
PYEOF

start_session() {
    tmux new-session -d -s main -x 200 -y 50 \
        "bash -c 'cd /workspace && ${PI_CMD}; tail -f /dev/null'"
    sleep 1
    # 屏幕 -> python 转录
    tmux pipe-pane -t main -o "python3 /tmp/tee-log.py"
}

start_session || {
    echo "[entrypoint] tmux 启动失败, 重试..."
    sleep 2
    start_session || echo "[entrypoint] 再次失败, 继续循环等待"
}

echo "[entrypoint] tmux session 'main' 已就绪, pi 运行中 (PID: $(pgrep -f "${PI_CMD}" | head -1))"

# 常驻: 会话死了就重启(保证 supervisor 永远有注入目标)
while true; do
    sleep 5
    if ! tmux has-session -t main 2>/dev/null; then
        echo "[entrypoint] 会话已退出, 重建..."
        start_session || true
    fi
done
