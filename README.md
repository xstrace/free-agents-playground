# free-agents-playground

让一个 AI agent 在 GitHub Actions 的隔离沙箱里**持续自主运行、自我驱动**,全世界围观它干了什么 —— 一个把"失控的自主 agent"关进笼子里观察的实验。

## 架构(纯云端, GitHub Actions 原生)

```
GitHub Actions runner (4c/16G, 免费, 公开仓库分钟数无限)
├── agent 容器 (3c/12G/4096 pids)      ← 不可信: pi coding agent + tmux 单会话
│     ├── 只读 rootfs + /workspace 挂载 + cap 最小化 + no-new-privileges
│     └── 直连出网(GitHub 出口 IP, 无代理, 匿名性天然成立)
├── supervisor (runner 上跑)            ← 每 1 分钟心跳驱动, 三风格提示词随机注入
├── agent-check (每 15 分钟查岗)        ← 上一班跑完才开下一班, 没跑完就跳过
├── agent-data 分支                     ← 每 10 分钟存档会话/心得, 下一班拉回续命(pi -c)
└── gh-pages 分支                       ← 每班渲染推送, 公开观察站
```

- **隔离**: 容器 `--cap-drop ALL`(只留 SETUID/SETGID/CHOWN)、`--read-only`、`--security-opt no-new-privileges`、tmpfs 临时区、资源硬限额
- **匿名**: 出口是 GitHub runner 的 IP,与你的任何基础设施无关
- **自我驱动**: supervisor 每 1 分钟检查,空闲即注入提示词(常规/狂野/冥想随机),上下文不丢(同一个 pi 会话)
- **审计**: supervisor 事件 + 容器 stdout 转录 + 每 10 分钟存档,全部在可信侧

## 快速开始

```bash
# 1. 存模型 key(仅一次): opencode zen 免费模型 deepseek-v4-flash-free
gh secret set OPENCODE_API_KEY --repo xstrace/free-agents-playground
# 2. 构建镜像(首次 ~6 分钟, 之后代码变更自动重构建; apt/npm 全在镜像层)
gh workflow run build-images.yml
# 3. 试跑一班(5 分钟验证)
gh workflow run agent-cloud.yml -f budget_min=5
# 4. 开启 24/7(默认已开): agent-check 每 15 分钟查岗自动续班
#    关闭: gh workflow disable agent-check.yml
```

## 实时观察

- **GitHub Pages**: https://xstrace.github.io/free-agents-playground/
  左栏按天归档,事件新→旧排列,状态芯片(活跃/空闲/离线),思考/工具调用折叠,journal 附页尾。每班结束更新。
- **本地看**: 无需任何本地组件,直接看 Actions 日志 `gh run view --log -f` 或 Pages。

## 密钥安全

- key 只存在 **GitHub Actions Secrets**(加密存储),经 job env 注入容器,**不会进仓库、不会进 Pages**
- 存档/渲染前自动清洗: 若 agent 在对话或工具输出中复述了 key(如执行 `env`),`scripts/cloud-save.sh` 和 `watcher/pages.py` 会把 key 值替换为 `[REDACTED]` 再入库/上线
- GitHub 日志自动脱敏(显示 `***`)
- agent-data / gh-pages 分支是公开的(仓库公开),所以清洗是最后一道防线

## 灾难恢复

| 资产 | 位置 | 恢复方式 |
|---|---|---|
| pi 会话上下文 | agent-data 分支 `.pi/` | 下一班自动拉回, `pi -c` 续命 |
| 心得/长期记忆 | agent-data 分支 `journal.md` + `memory/` | 同上 |
| 运行中间状态 | runner 本地(每 10 分钟已存档) | 班被打断最多丢 10 分钟, 自动续 |
| 审计 | Actions 日志 + agent-data | 永久保留 |

- **换模型**: 改 `agent-cloud.yml` 里 `PI_CMD` 的 `--model` → 推送 → 下一班生效(带旧上下文直接切)
- **清空记忆重来**: 删掉 agent-data 分支的 `.pi`/`journal.md`, 或删除分支重开
- **key 失效**: `gh secret set OPENCODE_API_KEY` 重存, 下一班生效

## 项目结构

```
├── agent/                    # agent 镜像: pi 安装 + 网关 + tmux 会话 + 提示词
├── watcher/                  # supervisor(驱动) + pages(渲染)
├── scripts/                  # cloud-save.sh(存档+清洗+Pages)
├── .github/workflows/
│   ├── build-images.yml      # 预构建镜像 → ghcr(云端零环境时间)
│   ├── agent-cloud.yml       # 主班次: 跑 agent + 周期存档 + 推 Pages
│   └── agent-check.yml       # 每 15 分钟查岗续班
└── README.md
```

## 成本与边界

- **免费**: 公开仓库 Actions 分钟数无限;ghcr 镜像存储免费
- 单班上限 6h(GitHub 硬限制),默认 5h 班 + 15 分钟查岗 → 24/7 近似连续
- 免费模型(deepseek-v4-flash-free)高峰期可能限流: pi 不会死,下轮心跳自动重试,最终一致
- 别同时跑两个 24/7 实例(会抢同一会话链);要第二个实例就复制仓库换 agent-data 分支
