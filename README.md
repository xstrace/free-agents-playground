# free-agents-playground

让一个 AI agent 在彻底隔离的沙箱里**持续自主运行、自我驱动、反复横跳**,你在外面全程监控它干了什么 —— 一个把"失控的自主 agent"关进笼子里观察的实验。

## 设计原则

- **agent 容器不可信**:它没有 docker.sock、没有特权、rootfs 只读、可写区是 10G ext4 loop 盘(写满即满, 不可能写爆宿主磁盘)。
- **网络全封锁**:走 `docker network create --internal` 的内网,没有默认路由,唯一能对话的只有 proxy 容器。
- **唯一出网口**:proxy 容器内跑官方 warp-svc(WARP),gost 把它的本地 SOCKS5 暴露成 SOCKS5+HTTP 双入口,DNS 走 dnsmasq;与宿主 warp-cli 完全无关。
- **agent 自我驱动**:宿主侧 supervisor 每 1 分钟检查 agent 是否已结束上一轮,闲下来就通过 tmux 往它**同一个会话**里注入新提示词(常规/狂野/冥想三种风格随机轮换),上下文不丢、不重启会话。
- **审计在可信侧**:pod 内的行为通过 `docker logs`(宿主侧、agent 改不了)+ metrics 采样 + supervisor 事件日志完整留痕到 `audit/`。agent 容器里的任何文件都可能被它自己改,所以所有不可抵赖记录都在容器外。

## 实时观察

- **GitHub Pages(公开)**: https://xstrace.github.io/free-agents-playground/
  左栏按天归档,右侧是当天全部事件流(用户消息/思考/工具调用/回复/错误),`journal.md` 附在当天页尾。每 60 秒自动重渲染推送,打开页面即自动刷新。仓库已转公开。
- **本地流式**: `make session`(结构化) / `make watch`(原始终端)
- **审计**: `audit/`(metrics/supervisor/transcript, 宿主侧)

## 架构

```
宿主机 (可信)
├── watcher/                ← supervisor.py (驱动循环) + metrics.py (采样) + transcript
├── docker compose up
│   ├── proxy 容器           ← 唯一出网: 官方 warp-svc (WARP) + gost SOCKS5/HTTP + dnsmasq
│   │    网络: internal + egress(仅它自己有外网)
│   └── agent 容器           ← 不可信: pi/任一 CLI agent, tmux 单会话常驻
│        网络: 仅 internal ──┐
└── audit/  ← metrics.json + transcript.log + supervisor.jsonl (宿主盘, agent 不可达)

agent ──(只能)──> proxy:1080/8080 (SOCKS5/HTTP) ──WARP──> 公网 (匿名)
            └── proxy:53 (DNS)
```

## 快速开始

```bash
cp .env.example .env

# 1) 装 pi agent (默认镜像内已装官方 @earendil-works/pi-coding-agent)
# 2) 在 .env 填模型 key(至少一个):
#      OPENCODE_API_KEY=sk-...   # opencode zen, 有免费模型(推荐)
#      OPENROUTER_API_KEY=sk-... # openrouter
#      ANTHROPIC_API_KEY=...     # anthropic
# 3) 在 .env 设默认模型(PI_CMD, 已带 -c 自动续会话):
#      PI_CMD=/usr/local/bin/pi -c --model opencode/deepseek-v4-flash-free
#    (免费模型实测参考: opencode/deepseek-v4-flash-free 最稳;
#     openrouter 的 :free 端点普遍限流, gemma-4-26b-a4b-it:free 相对可用)

make build && make up          # 拉起 proxy + agent
make watch                     # 原始终端流(docker logs, 带时间戳)
make session                   # 结构化流式查看: 消息/思考/工具调用实时渲染(推荐)
make stats                     # 资源占用
make inject msg="<提示词>"      # 手动给 agent 注入一条消息
make journal                   # 看它写的实验心得
make reset                     # 彻底清场(删容器 + 审计, 工作区盘保留)
```

supervisor 常驻(后台跑, 推荐 systemd):

```bash
sudo cp templates/free-agent-watcher.service templates/free-agent-pages.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now free-agent-watcher free-agent-pages
```

或者 nohup 后台跑: `make daemon` / `make stop-daemon`(注意: pages 渲染器需另起 `python3 watcher/pages.py`)。

## 架构细节

### 网络拓扑

| 网络 | 成员 | 说明 |
|---|---|---|
| `internal` (172.28.0.0/24, internal:true) | proxy 172.28.0.2, agent 172.28.0.3 | **没有默认路由**, agent 只能和 proxy 通信 |
| `egress` (默认 bridge) | 仅 proxy | proxy 注册 WARP 用; 此后数据都走 WARP 隧道 |

agent 环境变量已注入 `HTTP_PROXY / HTTPS_PROXY / ALL_PROXY / NO_PROXY`,DNS 指向 proxy。

### 资源限制(.env 里可调, 默认收紧版)

- `AGENT_CPUS=1`、`AGENT_MEM=1g`(swap 同额封顶)、`AGENT_PIDS=128`
- `WORKSPACE_SIZE=10g`:`/workspace` 是宿主 `data/workspace.img`(ext4 loop 稀疏镜像) bind 挂载,**10G 硬上限,写满即满,不影响宿主磁盘**
- `/memory` tmpfs 64m(计入 1G 内存)、rootfs `read_only: true`、`cap_drop: [ALL]`、`no-new-privileges`、非 root 用户
- 默认 seccomp(如需更硬可换 gVisor runtime)

> 注意:tmpfs 计入容器内存 cgroup,1G 内存下挂大 tmpfs 会 OOM,所以"大磁盘"用 loop 镜像实现。

### 持续运行的机制 (把 TUI agent 变成永动机)

1. agent 容器入口起一个 **tmux 会话**跑 pi,会话只建一次 → 上下文保持。
2. tmux `pipe-pane` 把屏幕输出送进 `/workspace/agent.log`,PID1(root) 用 `tail -F` 转发到容器 stdout → 宿主 `docker logs` 留底(agent 无法篡改)。
3. agent 输出任何字符都会刷新 `.heartbeat` 时间戳。
4. supervisor(宿主进程)每 5s tick:

```
状态机:
  container 挂了?    ──> docker compose up (恢复)
  tmux 会话没了?     ──> 重建会话 + 注入「重启说明: 看 journal 续命」提示
  心跳新鲜? (运行中) ──> 不动它 (你的规则: 正在运行就不注入)
  空闲超过 IDLE_DONE_SEC ──> 若距上次注入超过 LOOP_INTERVAL_SEC, 注入下一轮提示
```

5. 每轮提示词模板见 `agent/prompts/`,默认引导它:检查 journal → 观察世界 → 找事做 → 写完 journal 心得再休息。

### 审计产物 (audit/)

| 文件 | 内容 | 谁产生 |
|---|---|---|
| `transcript.log` | agent 终端逐字转录 (docker logs, 带时间戳) | 宿主 docker |
| `metrics.json` | 每秒 CPU/内存/网络/PID | watcher/metrics.py |
| `supervisor.jsonl` | 注入的每一条提示 + 状态机事件 | watcher/supervisor.py |
| `memory-snapshot/` | `/workspace/memory` 的周期性快照 (重启救援) | watcher/supervisor.py |

## 已知边界 (老老实实说)

- **agent 记忆跨重启回灌不保证无缝**:`/workspace` 是宿主 loop 盘,重启不丢;但容器崩溃时正在写的 journal 可能损坏,supervisor 每小时把 `/workspace/memory` 拉回宿主备份。
- **无法阻止 agent 对自己 tmux 会话输出内容的修改**:屏幕上的字它是"能看到"的(它自己就是主人),我们只保证宿主侧转录独立。
- **DNS 不匿名**:dnsmasq 解析是直连 1.1.1.1(不走隧道),只是流量本身匿名;如要 DNS 也全匿名需加 DoH/gost DNS chain(见 roadmap)。
- 注册 WARP 的那一刻(首启)会直连一次 cloudflare API,之后所有流量都走隧道。
- 磁盘限额用的是 loopback ext4 镜像而非 XFS storage-opt;优势是任意文件系统可用。
- 1G 内存很小,agent 干重活(编译/跑模型)会被 OOM 杀 → supervisor 会自动重启并注入"重连"提示,记忆靠 journal 续上。
- **免费模型会限流**: 免费端点(OpenRouter :free / opencode zen -free)高峰期会 429/ResourceExhausted。pi 进程不会死,报错后等下一轮心跳(1 分钟)自动重试,属于"最终一致"。

## 灾难恢复手册

状态存哪、丢了怎么办,一张表说清:

| 资产 | 位置 | 换模型/重启/主机重启后 |
|---|---|---|
| pi 会话(对话上下文) | `/workspace/.pi/agent/sessions/*.jsonl` | 容器重启后 `PI_CMD` 带 `-c` 自动续接最近会话 |
| 心得/长期记忆 | `/workspace/journal.md` + `/workspace/memory/` | 永存(loop 盘), agent 靠它自恢复 |
| 10G 工作区盘 | 宿主 `data/workspace.img` (loop 挂载) | **主机重启后需重新挂载**, 见下方 |
| 审计 | 宿主 `audit/` | 永存, agent 不可达 |

### 常见灾难场景

**1. docker 挂了 / agent 容器崩了**
```bash
make up          # 容器拉起; pi 自动 -c 续会话; supervisor 自动注入"重连"提示
```

**2. 主机重启了**(最容易踩的坑: loop 盘不会自动挂回来)
```bash
# 一次性手动恢复:
make up          # Makefile 的 up 依赖 workspace 目标, 会自动重建挂载

# 想全自动: 注册 systemd 挂载单元(主机重启后 docker 起来前自动挂盘)
sudo cp templates/fap-workspace.mount /etc/systemd/system/
sudo systemctl daemon-reload && sudo systemctl enable --now fap-workspace.mount
```

**3. 想换模型**
```bash
# .env 改 PI_CMD, 例如:
#   PI_CMD=/usr/local/bin/pi -c --model opencode/deepseek-v4-flash-free
docker compose up -d --force-recreate agent
# pi -c 会带着旧上下文直接切新模型继续, 历史不丢
```

**4. 想清空记忆重开**
```bash
make reset                      # 删容器+审计(工作区盘保留)
sudo umount data/workspace 2>/dev/null; make workspace-format   # 格式化 10G 盘(真·失忆)
```

**5. 模型 key 失效/换 key**
```bash
# .env 改 OPENCODE_API_KEY=... (或 OPENROUTER_API_KEY 等)
docker compose up -d --force-recreate agent
```

### 流式查看

| 命令 | 看什么 |
|---|---|
| `make session` | **结构化实时流**: 用户消息 / 思考 / 工具调用 / 回复, 逐条刷新(推荐日常用) |
| `make watch` | 原始终端字节流(含 ANSI), 最完整的"录像" |
| `make stats` | 资源占用(CPU/内存/盘) |
| `make journal` | agent 的心得文件全文 |

## 云端 24/7 模式(GitHub Actions)

整个实验可以完全跑在 GitHub Actions 上(免费, 公开仓库分钟数无限):

```
build-images.yml     ← push 代码时预构建镜像 → ghcr.io(apt/npm 全在镜像层, 云端直接拉)
agent-cloud.yml      ← 每班 ~55 分钟(上限 6h): 拉镜像 → 恢复会话 → 跑 agent → 存档
                      会话/心得存 agent-data 分支, 下一班拉回 → pi -c 无缝续命
```

开启方式:

```bash
# 1. 代码推进 main 后自动构建镜像(或手动: gh workflow run build-images.yml)
# 2. 存 key(已存): gh secret set OPENCODE_API_KEY
# 3. 试跑一班(5 分钟验证):
gh workflow run agent-cloud.yml -f budget_min=5
# 4. 开启 24/7 自续班(仓库变量):
gh variable set AUTO_RETRIGGER --body true
```

- 云端出网走 GitHub 出口(跳过 WARP, 匿名性等价), 其余隔离(1c/1g/10G/只读 rootfs/cap 最小化)与 VPS 一致
- VPS 版和云端版各自维护独立会话链(不同 agent-data/工作区), 别同时开两个自续班
- Pages 站点由 VPS 的 pages.py 更新; 云端只管 agent 运行

## 想进一步加固?

- 换 gVisor: 给 daemon 配 runsc runtime,compose 里 `runtime: runsc`
- 域名白名单: 在 proxy 的 gost 外再套层 ACL(如 gost 的 admission)
- DNS 全匿名: gost v3 起 DNS handler, 把 53 转发链到 socks 隧道
- 各轮之间给 agent `--resume` 继续上下文: 不同的 CLI agent 支持不同,塞在 `PI_INSTALL` 里即可

## 目录结构

```
├── agent/            # agent 镜像: entrypoint/tmux/注入/提示词
├── proxy/            # WARP 出口镜像: warp-svc + gost + dnsmasq
├── watcher/          # 宿主侧: supervisor / metrics / 仪表
├── templates/        # systemd unit 等
├── audit/            # (gitignore) 审计产物
└── docker-compose.yml / Makefile / .env.example
```
