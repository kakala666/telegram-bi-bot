# bi-bot-platform 部署指南（Agent 专用）

> 本文档面向 AI Agent，指导你协助人类将 bi-bot-platform 部署到 Linux 服务器。
> 项目是一个 Telegram 双向消息转发 Bot 平台，基于 Python 3.11+ / aiogram 3 / SQLAlchemy 2 / SQLite(默认) 或 PostgreSQL。

---

## 0. 前置信息收集

部署前你需要让人类提供以下信息：

| 信息项 | 说明 | 示例 |
|--------|------|------|
| 服务器 IP / SSH 连接方式 | 用于登录服务器 | `ssh root@1.2.3.4` |
| 操作系统 | 推荐 Ubuntu 22.04+ / Debian 12+ | `lsb_release -a` |
| Python 版本 | 要求 >= 3.11 | `python3 --version` |
| MASTER_BOT_TOKEN | 主 Bot 的 Telegram Token | 从 @BotFather 获取 |
| ADMIN_USER_IDS | 管理员 Telegram User ID（逗号分隔） | `123456789,987654321` |
| 数据库选择 | SQLite（简单）或 PostgreSQL（生产推荐） | — |
| 域名（可选） | 如果需要 Webhook 模式 | — |

如果人类没有主动提供，你应该逐项询问。

---

## 1. 服务器环境准备

### 1.1 系统更新 & 基础工具

```bash
sudo apt update && sudo apt upgrade -y
sudo apt install -y git curl wget build-essential
```

### 1.2 安装 Python 3.11+

检查现有版本：

```bash
python3 --version
```

如果低于 3.11，安装：

```bash
sudo apt install -y software-properties-common
sudo add-apt-repository ppa:deadsnakes/ppa -y
sudo apt update
sudo apt install -y python3.11 python3.11-venv python3.11-dev
```

### 1.3 （可选）安装 PostgreSQL

仅当人类选择 PostgreSQL 时执行：

```bash
sudo apt install -y postgresql postgresql-contrib
sudo systemctl enable postgresql
sudo systemctl start postgresql

# 创建数据库和用户
sudo -u postgres psql -c "CREATE USER bibot WITH PASSWORD 'CHANGE_ME_STRONG_PASSWORD';"
sudo -u postgres psql -c "CREATE DATABASE bibot OWNER bibot;"
```

提醒人类将密码替换为强密码。

---

## 2. 部署代码

### 2.1 创建部署用户（推荐）

```bash
sudo useradd -m -s /bin/bash bibot
sudo su - bibot
```

### 2.2 克隆代码

```bash
cd /home/bibot
git clone <仓库地址> bi-bot-platform
cd bi-bot-platform/bi-bot-platform
```

> 注意项目结构：仓库根目录下有 `bi-bot-platform/` 子目录，实际代码在里面。
> 工作目录应为 `/home/bibot/bi-bot-platform/bi-bot-platform/`（包含 `pyproject.toml` 的那一层）。

如果人类是手动上传代码（scp / sftp），确保最终目录结构为：

```
/home/bibot/bi-bot-platform/
├── alembic.ini
├── pyproject.toml
├── .env              # 待创建
├── app/
│   ├── launcher.py   # 入口
│   ├── config.py
│   ├── database/
│   ├── master_bot/
│   ├── sub_bot/
│   ├── repositories/
│   └── services/
├── data/             # SQLite 数据目录（自动创建）
├── logs/             # 日志目录（自动创建）
└── tests/
```

### 2.3 创建虚拟环境 & 安装依赖

```bash
python3.11 -m venv .venv
source .venv/bin/activate

# 基础安装（SQLite）
pip install -e .

# 如果使用 PostgreSQL，额外安装：
pip install -e ".[postgres]"
```

---

## 3. 配置环境变量

### 3.1 创建 .env 文件

```bash
cp .env.example .env
```

### 3.2 生成 Fernet 加密密钥

```bash
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

将输出的密钥填入 `.env` 的 `TOKEN_ENCRYPTION_KEY`。

### 3.3 编辑 .env

最终 `.env` 应包含以下内容（根据人类提供的信息填写）：

```ini
# 主机器人配置
MASTER_BOT_TOKEN=<人类提供的 Token>
ADMIN_USER_IDS=<人类提供的管理员 ID>

# 数据库配置
# SQLite（默认）：
DATABASE_URL=sqlite+aiosqlite:///data/bot.db
# PostgreSQL（如果选择了 PG）：
# DATABASE_URL=postgresql+asyncpg://bibot:PASSWORD@localhost:5432/bibot

# 安全配置
TOKEN_ENCRYPTION_KEY=<上一步生成的 Fernet Key>

# 广告默认配置
DEFAULT_AD_TEXT=Powered by @YourPlatformBot
DEFAULT_AD_URL=https://t.me/YourPlatformBot

# 广播配置
BROADCAST_RATE_LIMIT=20

# 子Bot配置
MAX_BOTS_PER_USER=3
MESSAGE_MAP_RETENTION_DAYS=30

# 日志配置
LOG_LEVEL=INFO
LOG_FILE=logs/bot.log
```

### 3.4 关键校验

你应该帮人类检查：

1. `MASTER_BOT_TOKEN` 格式：`数字:字母数字混合`，例如 `123456:ABC-DEF...`
2. `ADMIN_USER_IDS` 是纯数字，多个用逗号分隔
3. `TOKEN_ENCRYPTION_KEY` 是有效的 Fernet key（44 字符 base64 字符串，以 `=` 结尾）
4. 如果用 PostgreSQL，确认 `DATABASE_URL` 中的用户名、密码、主机、端口、数据库名都正确

---

## 4. 初始化数据库

应用启动时会自动执行 `Base.metadata.create_all()`，所以首次启动会自动建表。

如果需要使用 Alembic 迁移（后续版本升级时）：

```bash
source .venv/bin/activate
cd /home/bibot/bi-bot-platform  # pyproject.toml 所在目录

# 如果用 PostgreSQL，需要先修改 alembic.ini 中的 sqlalchemy.url
# 或者设置环境变量让 alembic 读取

alembic upgrade head
```

> 注意：`alembic.ini` 中默认写死了 `sqlite+aiosqlite:///data/bot.db`。
> 如果使用 PostgreSQL，需要将 `alembic.ini` 中的 `sqlalchemy.url` 改为对应的 PG 连接串。

---

## 5. 手动测试启动

先手动运行一次，确认没有报错：

```bash
source .venv/bin/activate
cd /home/bibot/bi-bot-platform
python -m app.launcher
```

预期输出：

```
2025-xx-xx xx:xx:xx | INFO     | app.launcher | 恢复所有活跃子Bot...
2025-xx-xx xx:xx:xx | INFO     | app.launcher | 恢复完成: ...
2025-xx-xx xx:xx:xx | INFO     | app.launcher | Starting master bot polling...
```

确认无报错后 `Ctrl+C` 停止。

常见错误排查：

| 错误 | 原因 | 解决 |
|------|------|------|
| `ModuleNotFoundError: No module named 'app'` | 没有 `pip install -e .` | 在 pyproject.toml 目录执行 `pip install -e .` |
| `ValidationError: MASTER_BOT_TOKEN` | .env 未配置或 Token 为空 | 检查 .env 文件 |
| `InvalidToken` (cryptography) | TOKEN_ENCRYPTION_KEY 无效 | 重新生成 Fernet key |
| `Unauthorized` (aiogram) | Bot Token 错误或被撤销 | 在 @BotFather 检查 Token |
| `OperationalError: unable to open database` | data/ 目录权限问题 | `mkdir -p data && chmod 755 data` |

---

## 6. 配置 systemd 服务（生产运行）

### 6.1 创建 service 文件

```bash
sudo tee /etc/systemd/system/bibot.service > /dev/null << 'EOF'
[Unit]
Description=Bi-Bot Telegram Platform
After=network.target
# 如果使用 PostgreSQL，取消下面的注释：
# After=network.target postgresql.service

[Service]
Type=simple
User=bibot
Group=bibot
WorkingDirectory=/home/bibot/bi-bot-platform
ExecStart=/home/bibot/bi-bot-platform/.venv/bin/python -m app.launcher
Restart=always
RestartSec=10

# 环境变量（也可以依赖 .env 文件）
# EnvironmentFile=/home/bibot/bi-bot-platform/.env

# 安全加固
NoNewPrivileges=true
ProtectSystem=strict
ReadWritePaths=/home/bibot/bi-bot-platform/data /home/bibot/bi-bot-platform/logs

[Install]
WantedBy=multi-user.target
EOF
```

### 6.2 启动服务

```bash
sudo systemctl daemon-reload
sudo systemctl enable bibot
sudo systemctl start bibot
```

### 6.3 检查状态

```bash
sudo systemctl status bibot
sudo journalctl -u bibot -f --no-pager -n 50
```

### 6.4 常用运维命令

```bash
# 重启
sudo systemctl restart bibot

# 停止
sudo systemctl stop bibot

# 查看日志（应用自身日志）
tail -f /home/bibot/bi-bot-platform/logs/bot.log

# 查看日志（systemd journal）
sudo journalctl -u bibot --since "1 hour ago"
```

---

## 7. 安全加固

部署完成后，提醒人类做以下安全措施：

### 7.1 文件权限

```bash
# .env 只有 bibot 用户可读
chmod 600 /home/bibot/bi-bot-platform/.env

# data 目录权限
chmod 700 /home/bibot/bi-bot-platform/data
```

### 7.2 防火墙

Bot 使用 polling 模式（主动拉取），不需要开放入站端口。只需确保出站 443 端口（HTTPS）可用：

```bash
# 如果使用 ufw
sudo ufw allow OpenSSH
sudo ufw enable
# 不需要额外开放端口，polling 模式只有出站流量
```

### 7.3 数据库备份（SQLite）

```bash
# 创建备份脚本
sudo tee /home/bibot/backup.sh > /dev/null << 'EOF'
#!/bin/bash
BACKUP_DIR="/home/bibot/backups"
mkdir -p "$BACKUP_DIR"
cp /home/bibot/bi-bot-platform/data/bot.db "$BACKUP_DIR/bot_$(date +%Y%m%d_%H%M%S).db"
# 保留最近 7 天的备份
find "$BACKUP_DIR" -name "bot_*.db" -mtime +7 -delete
EOF

chmod +x /home/bibot/backup.sh

# 添加 crontab，每天凌晨 3 点备份
(crontab -l 2>/dev/null; echo "0 3 * * * /home/bibot/backup.sh") | crontab -
```

---

## 8. 版本升级流程

当代码有更新时：

```bash
sudo su - bibot
cd /home/bibot/bi-bot-platform

# 拉取最新代码
git pull origin main

# 更新依赖
source .venv/bin/activate
pip install -e .

# 如果有数据库迁移
alembic upgrade head

# 重启服务
exit  # 退出 bibot 用户
sudo systemctl restart bibot
```

---

## 9. 部署验证清单

部署完成后，按顺序验证：

1. `systemctl status bibot` — 服务状态为 `active (running)`
2. `journalctl -u bibot -n 20` — 无 ERROR 日志，能看到 `Starting master bot polling...`
3. 在 Telegram 中向主 Bot 发送 `/start` — 应收到欢迎消息
4. 发送 `/register <子Bot Token>` — 应成功注册子 Bot
5. 向注册的子 Bot 发送消息 — Owner 应收到转发的消息
6. Owner 回复消息 — 用户应收到回复
7. `tail -f logs/bot.log` — 日志正常记录

---

## 10. 架构要点速查（供 Agent 理解上下文）

- 入口文件：`app/launcher.py` → `asyncio.run(main())`
- 配置加载：`app/config.py` → Pydantic `Settings`，从 `.env` 读取
- 数据库：`app/database/engine.py` 创建异步引擎，`app/database/models.py` 定义 6 张表
- Master Bot：`app/master_bot/` — 处理注册、管理、广播、广告、管理员面板
- Sub Bot：`app/sub_bot/` — 处理消息转发、用户欢迎、广播发送
- Bot 注册表：`app/sub_bot/registry.py` — 管理所有子 Bot 的生命周期，启动时自动恢复
- 服务层：`app/services/` — 加密、验证、转发、广告注入、广播、清理
- 日志：stdout + `logs/bot.log`，aiogram/sqlalchemy 日志被压制到 WARNING 级别
- 定时任务：`CleanupService` 每 24 小时清理过期消息映射和广播任务
- 运行模式：polling（长轮询），不需要 Webhook / 公网端口
