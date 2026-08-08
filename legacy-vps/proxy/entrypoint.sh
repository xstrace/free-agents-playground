#!/bin/bash
# 容错版入口: 任何一步失败都不让容器退出, warp-svc 死了会自动重启
set -uo pipefail

warp_ready() { warp-cli --accept-tos status >/dev/null 2>&1; }

echo "[proxy] 启动 warp-svc ..."
/usr/bin/warp-svc --accept-tos &
WARPPID=$!

# 等 warp-svc 就绪
for i in $(seq 1 60); do
    warp_ready && break
    sleep 1
done

# 首次启动: 自动注册免费账户
if [ ! -s /var/lib/cloudflare-warp/reg.json ]; then
    echo "[proxy] 注册新的 WARP 免费账户 ..."
    warp-cli --accept-tos registration new || echo "[proxy] 注册失败(可手动重试)"
fi

# 确保 socks5 代理模式(模式切换会使 svc 重启, 之后要重新等就绪)
CUR_MODE=$(warp-cli --accept-tos settings 2>/dev/null | grep -i "Mode:")
if ! echo "$CUR_MODE" | grep -qi "proxy"; then
    echo "[proxy] 切换模式: ${CUR_MODE:-?} -> Proxy"
    warp-cli --accept-tos mode proxy || echo "[proxy] mode proxy 失败"
    sleep 5
    for i in $(seq 1 60); do
        warp_ready && break
        sleep 1
    done
fi

# 连接(带重试)
echo "[proxy] 连接 WARP ..."
for i in $(seq 1 12); do
    warp-cli --accept-tos connect >/dev/null 2>&1
    sleep 5
    S=$(warp-cli --accept-tos status 2>/dev/null | head -1)
    echo "[proxy] 状态: $S"
    echo "$S" | grep -qiE "connected|connecting" && break
done

echo "[proxy] 启动 dnsmasq (internal 网 DNS) ..."
dnsmasq --conf-file=/etc/dnsmasq.d/fap.conf || echo "[proxy] dnsmasq 启动失败(忽略)"

echo "[proxy] 启动 gost: 127.0.0.1:40000 -> socks5://:1080 http://:8080"
gost -C /etc/gost.yaml

echo "[proxy] gost 退出, 进入保活循环..."
while true; do
    if ! kill -0 "$WARPPID" 2>/dev/null; then
        echo "[proxy] warp-svc 死亡, 重启 ..."
        /usr/bin/warp-svc --accept-tos &
        WARPPID=$!
    fi
    sleep 10
done
