SHELL := /bin/bash
COMPOSE := docker compose
include .env
export

# ── 基本操作 ───────────────────────────────────────────────
.PHONY: build up down ps logs stats inject journal attach reset daemon stop-daemon watch transcript workspace workspace-format

# /workspace: 10G ext4 loop 镜像(agent 的"硬盘"), 首次自动创建
WORKSPACE_IMG  ?= ./data/workspace.img
WORKSPACE_MNT  ?= ./data/workspace

$(WORKSPACE_IMG):
	@mkdir -p data
	truncate -s $(WORKSPACE_SIZE) $@
	mkfs.ext4 -q -F $@
	@echo "[make] workspace.img 已创建 ($(WORKSPACE_SIZE))"

workspace: $(WORKSPACE_IMG)
	@mkdir -p $(WORKSPACE_MNT)
	@mountpoint -q $(WORKSPACE_MNT) || mount -o loop $(WORKSPACE_IMG) $(WORKSPACE_MNT)
	@echo "[make] workspace 已挂载: $(WORKSPACE_MNT)"

workspace-format:
	@umount $(WORKSPACE_MNT) 2>/dev/null || true
	rm -f $(WORKSPACE_IMG)
	$(MAKE) workspace

build:
	$(COMPOSE) build

up: build workspace
	$(COMPOSE) up -d

down:
	$(COMPOSE) down --remove-orphans

ps:
	$(COMPOSE) ps

logs:
	$(COMPOSE) logs -f

# agent 全量终端转录(可信侧): 等价于看 agent 在想什么/做了什么
watch:
	@mkdir -p audit
	@$(COMPOSE) logs -f --timestamps agent

# 结构化流式查看: 用户消息/回复/工具调用实时渲染(推荐)
session:
	@python3 watcher/session-view.py

stats:
	@mkdir -p audit
	@docker stats --no-stream fap-agent fap-proxy

# ── 注入 ──────────────────────────────────────────────────
# make inject msg="去读一下今天的地缘新闻, 给我个观点"
inject:
	@test -n "$(msg)" || (echo "用法: make inject msg=\"...\""; exit 1)
	@$(COMPOSE) exec -u agent -T agent /opt/inject.sh "$(msg)"
	@echo "[$(date +%FT%T%z)] $(msg)" >> audit/inject.log

journal:
	@$(COMPOSE) exec -T agent sh -c 'cat /workspace/journal.md 2>/dev/null || echo "(journal.md 还不存在)"'

# 进入 agent 容器(你只读, 它可见)
console:
	$(COMPOSE) exec -it agent /bin/sh

# ── 宿主侧 watcher 常驻 ────────────────────────────────────
daemon:
	@mkdir -p audit
	@nohup python3 watcher/supervisor.py >> audit/supervisor.daemon.log 2>&1 &
	@nohup python3 watcher/metrics.py >> audit/metrics.daemon.log 2>&1 &
	@echo "watcher daemon 已启动 (PID 见 audit/*.daemon.log)"

stop-daemon:
	@pkill -f "watcher/supervisor.py" || true
	@pkill -f "watcher/metrics.py" || true
	@echo "stopped"

# ── 重置 / 清理 ────────────────────────────────────────────
# 彻底清场: 删容器 + 审计清理(工作区镜像保留)
reset:
	$(COMPOSE) down --volumes --remove-orphans
	rm -f audit/transcript.log audit/metrics.json audit/supervisor.jsonl
	@echo "已重置(审计日志已删, 如需保留自行备份; 工作区数据在 data/workspace)"

clean: reset
	docker system prune -f
