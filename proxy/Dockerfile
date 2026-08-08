# stage 1: 构建 gost(把 warp 本地 socks5 映射到 internal 网的中继)
FROM golang:1.26-bookworm AS gost
RUN go install github.com/go-gost/gost/cmd/gost@latest

# stage 2: 官方 Cloudflare WARP 客户端
FROM debian:bookworm-slim
ENV DEBIAN_FRONTEND=noninteractive

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        curl ca-certificates gnupg dnsmasq iproute2 procps \
    && curl -fsSL https://pkg.cloudflareclient.com/pubkey.gpg \
        | gpg --yes --dearmor --output /usr/share/keyrings/cloudflare-warp-archive-keyring.gpg \
    && echo "deb [signed-by=/usr/share/keyrings/cloudflare-warp-archive-keyring.gpg] https://pkg.cloudflareclient.com/ bookworm main" \
        > /etc/apt/sources.list.d/cloudflare-client.list \
    && apt-get update \
    && apt-get install -y cloudflare-warp \
    && rm -rf /var/lib/apt/lists/*

COPY --from=gost /go/bin/gost /usr/local/bin/gost
COPY entrypoint.sh /usr/local/bin/entrypoint
COPY dnsmasq.conf /etc/dnsmasq.d/fap.conf
COPY gost.yaml /etc/gost.yaml
RUN chmod +x /usr/local/bin/entrypoint

# 持久化 warp 注册凭据(重置时删容器会丢, 需重建)
VOLUME ["/var/lib/cloudflare-warp"]

ENTRYPOINT ["/usr/local/bin/entrypoint"]
