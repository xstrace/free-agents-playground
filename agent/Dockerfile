# agent 容器: 只读 rootfs, 唯一可写 = /workspace(10G ext4) + /memory(64m) + /tmp
FROM alpine:3.20

ARG PI_INSTALL=""
ARG PI_CMD=/usr/local/bin/pi

RUN apk add --no-cache bash tmux python3 curl wget ca-certificates openssl git jq

COPY entrypoint.sh inject.sh /opt/
COPY prompts/ /opt/prompts/
RUN chmod +x /opt/entrypoint.sh /opt/inject.sh

# 安装 pi agent(GitHub 二进制, 由 .env PI_INSTALL 决定)
RUN if [ -n "${PI_INSTALL}" ]; then \
        bash -c "${PI_INSTALL}"; \
    else \
        printf '#!/bin/sh\n# 占位 stub: 模拟一个会回应注入消息的 TUI, 便于在未装 pi 时测试整个管线\necho "[pi-stub] PI_INSTALL 未配置, 正在假装思考...";\nwhile read -r line; do echo "[pi-stub] 收到: $line"; done\n' > /usr/local/bin/pi; \
        chmod +x /usr/local/bin/pi; \
    fi

# 非 root 运行; /workspace 由宿主 loop 镜像挂载, 启动时 entrypoint 以 root chown 后降权
RUN adduser -D -u 1000 agent
# 注意: 不从镜像 USER 降权, 否则无法 chown 宿主挂载盘; entrypoint 内 su
ENV HOME=/workspace TERM=xterm-256color

ENTRYPOINT ["/opt/entrypoint.sh"]
