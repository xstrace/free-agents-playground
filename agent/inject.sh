#!/bin/bash
# 宿主 supervisor 调用: 向 pi 的同一个会话注入一条消息(Enter 发送)
# 用法: inject.sh "提示词内容"
set -euo pipefail

# tmux server 属于 agent 用户, root 调用时降权(提示词走 stdin, 避免引号地狱)
if [ "$(id -u)" = "0" ]; then
    exec su agent -s /bin/bash -c '/opt/inject.sh' <<< "${1:-}"
fi

if [ $# -eq 0 ]; then
    MSG="$(cat)"
else
    MSG="$1"
fi

if ! tmux has-session -t main 2>/dev/null; then
    echo "[inject] 会话不存在" >&2
    exit 1
fi

# 用 paste-buffer 注入, 内容里的特殊字符/开头 - 都不会被 tmux 解析
tmux load-buffer -b inject - <<< "$MSG"
tmux paste-buffer -t main -b inject -d
tmux send-keys -t main Enter
echo "[inject] ok: ${MSG:0:80}..."
