# agent 容器: 只读 rootfs, 唯一可写 = /workspace(10G ext4) + /memory(64m) + /tmp
FROM alpine:3.20

ARG PI_INSTALL=""
ARG PI_CMD=/usr/local/bin/pi

RUN apk add --no-cache bash tmux python3 curl wget ca-certificates openssl git jq \
    nodejs npm libstdc++

COPY entrypoint.sh inject.sh /opt/
COPY prompts/ /opt/prompts/
RUN chmod +x /opt/entrypoint.sh /opt/inject.sh

# 安装 pi agent(earendil-works/pi)
#   PI_INSTALL="stub"  -> 占位 stub(管线测试用)
#   PI_INSTALL="<cmd>" -> 自定义安装命令
#   留空               -> 官方 npm 安装
RUN if [ "${PI_INSTALL}" = "stub" ]; then \
        printf '#!/bin/sh\necho "[pi-stub] 占位模式, 请在 .env 配置真实 pi"\nwhile read -r line; do echo "[pi-stub] 收到: $line"; done\n' > /usr/local/bin/pi; \
        chmod +x /usr/local/bin/pi; \
    elif [ -n "${PI_INSTALL}" ]; then \
        bash -c "${PI_INSTALL}"; \
    else \
        npm install -g --ignore-scripts @earendil-works/pi-coding-agent; \
    fi

# 非 root 运行; /workspace 由宿主 loop 镜像挂载, 启动时 entrypoint 以 root chown 后降权
RUN adduser -D -u 1000 agent
# 注意: 不从镜像 USER 降权, 否则无法 chown 宿主挂载盘; entrypoint 内 su
ENV HOME=/workspace TERM=xterm-256color

ENTRYPOINT ["/opt/entrypoint.sh"]
