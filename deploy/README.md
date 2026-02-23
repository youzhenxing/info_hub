# TrendRadar 版本管理系统

TrendRadar 版本管理系统提供了完整的生产环境部署、版本更新和回退功能。

## 📋 系统概述

### 环境区分

- **开发环境**: `/home/zxy/Documents/code/TrendRadar`
  - 用于日常开发、测试和调试
  - 可以自由修改代码和配置
  - 使用 `docker-compose.yml` 启动开发容器

- **生产环境**: `/home/zxy/Documents/install/trendradar`
  - 用于正式运行和生产服务
  - 支持多版本管理和快速切换
  - 每个版本独立部署，互不影响

### 目录结构

```
/home/zxy/Documents/install/trendradar/
├── current -> releases/v5.4.0     # 软链接，指向当前运行版本
├── releases/                       # 所有已发布版本
│   ├── v5.4.0/                    # 版本 5.4.0
│   │   ├── trendradar/            # 核心代码
│   │   ├── mcp_server/            # MCP 服务器
│   │   ├── docker/                # Docker 配置
│   │   ├── docker-compose.yml     # 生产环境 Compose 文件
│   │   ├── version                # 版本号文件
│   │   ├── version_mcp            # MCP 版本号
│   │   └── requirements.txt       # Python 依赖
│   ├── v5.5.0/                    # 版本 5.5.0
│   └── ...
├── shared/                         # 跨版本共享数据
│   ├── config/                    # 配置文件（共享）
│   │   ├── config.yaml
│   │   ├── frequency_words.txt
│   │   └── ...
│   └── output/                    # 输出数据（共享）
│       ├── html/
│       ├── news/
│       └── rss/
└── versions/                       # 版本管理信息
    ├── manifest.yaml              # 版本清单
    └── history/                   # 版本详细记录
        ├── v5.4.0.yaml
        └── v5.5.0.yaml
```

---

## 🚀 快速开始

### 1. 初始化生产环境

第一次使用时需要初始化生产环境：

```bash
cd /home/zxy/Documents/code/TrendRadar
./deploy/init-production.sh
```

这会创建完整的目录结构和初始配置文件。

### 2. 发布第一个版本

从开发环境发布版本到生产环境：

```bash
# 确保版本号正确
cat version
# 输出: 5.4.0

# 发布版本
trend deploy
```

输出示例：
```
═══════════════════════════════════════════════
  TrendRadar 版本发布
═══════════════════════════════════════════════

📦 准备发布版本: v5.4.0
   MCP 版本: v3.1.7

🔨 构建 Docker 镜像...
  ✓ Docker 镜像构建完成

📁 创建版本目录...
  ✓ 文件复制完成

🐳 生成 Docker Compose 配置...
  ✓ Docker Compose 配置已生成

📝 创建版本记录...
  ✓ 版本记录已创建

✅ 版本发布完成！
```

### 3. 切换到新版本

发布后，新版本已准备就绪但未启用。使用 `update` 命令切换：

```bash
trend update v5.4.0
```

### 4. 查看版本状态

```bash
# 查看所有版本
trend versions

# 查看生产环境状态
trend production

# 查看特定版本详情
trend version-info v5.4.0
```

---

## 📖 命令详解

### `trend deploy` - 发布新版本

从开发环境构建并发布新版本到生产环境。

**执行流程**：
1. 读取开发环境的版本号（`version` 文件）
2. 构建 Docker 镜像（带版本标签）
3. 创建版本发布目录 `releases/vX.Y.Z/`
4. 复制必要文件（代码、配置、依赖）
5. 生成生产环境 `docker-compose.yml`
6. 创建版本记录文件
7. 更新版本清单

**注意事项**：
- 版本号自动从 `version` 文件读取
- 如果版本已存在，会询问是否覆盖
- 发布后不会自动切换，需手动执行 `trend update`
- Docker 镜像命名格式：`trendradar:vX.Y.Z`

**使用示例**：
```bash
# 检查当前版本号
cat version

# 发布版本
trend deploy

# 如果需要发布新版本，先更新版本号
echo "5.5.0" > version
trend deploy
```

---

### `trend update <version>` - 更新到指定版本

将生产环境切换到指定版本。

**执行流程**：
1. 检查目标版本是否存在
2. 停止当前运行的容器
3. 更新 `current` 软链接指向新版本
4. 更新版本清单（current_version、previous_version）
5. 启动新版本容器
6. 记录部署历史

**注意事项**：
- 版本号可以带 `v` 前缀也可以不带（自动处理）
- 切换前会要求确认操作
- 共享配置和数据不受影响
- 容器命名：`trendradar-prod`、`trendradar-mcp-prod`

**使用示例**：
```bash
# 切换到版本 5.5.0
trend update v5.5.0
# 或
trend update 5.5.0

# 查看当前版本
trend production
```

---

### `trend rollback` - 回退到上一版本

快速回退到上一个版本，用于紧急恢复。

**执行流程**：
1. 从 `manifest.yaml` 读取上一版本号
2. 调用 `trend update` 切换到上一版本
3. 记录回退操作

**注意事项**：
- 只能回退到上一个版本（不能跨版本回退）
- 如果需要回退到更早版本，使用 `trend update`
- 回退前会要求确认操作

**使用示例**：
```bash
# 回退到上一版本
trend rollback

# 输出：
# ⚠️  准备回退版本
#    当前版本: v5.5.0
#    回退到: v5.4.0
# ❓ 确认要回退到版本 v5.4.0吗？(y/N)
```

---

### `trend versions` - 列出所有版本

显示所有已部署版本及其状态。

**输出信息**：
- 版本号
- 发布时间
- 状态（active/inactive）
- Docker 镜像
- 当前版本标记（✓）

**使用示例**：
```bash
trend versions

# 输出：
# ═══════════════════════════════════════════════
#   已部署版本
# ═══════════════════════════════════════════════
#
# ✓ v5.5.0 (active)
#   发布时间: 2026-01-28T14:30:00+00:00
#   Docker 镜像: trendradar:v5.5.0
#
#   v5.4.0 (inactive)
#   发布时间: 2026-01-28T11:00:00+00:00
#   Docker 镜像: trendradar:v5.4.0
```

---

### `trend version-info <version>` - 查看版本详情

显示指定版本的详细信息。

**输出内容**：
- 版本号和状态
- 发布时间、部署时间
- 变更说明
- Docker 镜像信息
- 部署历史记录

**使用示例**：
```bash
trend version-info v5.5.0

# 输出完整的版本记录 YAML 文件内容
```

---

### `trend production` - 生产环境状态

显示生产环境的当前状态。

**输出信息**：
- 当前运行版本
- 上一版本
- 容器运行状态
- 可用的版本列表

**使用示例**：
```bash
trend production

# 输出：
# ═══════════════════════════════════════════════
#   生产环境状态
# ═══════════════════════════════════════════════
#
# 📊 当前状态:
#    运行版本: v5.5.0
#    上一版本: v5.4.0
#
# 🐳 容器状态:
# NAMES                STATUS
# trendradar-prod      Up 2 hours
# trendradar-mcp-prod  Up 2 hours
```

---

## 🔄 工作流程示例

### 场景 1: 日常开发和发布

```bash
# 1. 在开发环境开发新功能
cd /home/zxy/Documents/code/TrendRadar
# ... 编写代码、测试 ...

# 2. 测试通过后，更新版本号
echo "5.6.0" > version

# 3. 发布到生产环境
trend deploy

# 4. 查看所有版本
trend versions

# 5. 切换到新版本
trend update v5.6.0

# 6. 检查生产环境状态
trend production
docker logs trendradar-prod -f
```

---

### 场景 2: 紧急回退

```bash
# 发现生产环境有问题
trend production

# 快速回退到上一版本
trend rollback

# 确认服务恢复正常
trend production
docker logs trendradar-prod | tail -50
```

---

### 场景 3: 跨版本切换

```bash
# 查看所有可用版本
trend versions

# 切换到特定版本（比如 5.4.0）
trend update v5.4.0

# 验证版本
trend production
```

---

## 📝 版本信息文件格式

### manifest.yaml（版本清单）

位置：`/home/zxy/Documents/install/trendradar/versions/manifest.yaml`

```yaml
current_version: "5.5.0"
previous_version: "5.4.0"
versions:
  - version: "5.5.0"
    released_at: "2026-01-28T14:30:00+00:00"
    status: "active"
    image: "trendradar:v5.5.0"
  - version: "5.4.0"
    released_at: "2026-01-28T11:00:00+00:00"
    status: "inactive"
    image: "trendradar:v5.4.0"
```

---

### vX.Y.Z.yaml（版本详细记录）

位置：`/home/zxy/Documents/install/trendradar/versions/history/vX.Y.Z.yaml`

```yaml
version: "5.5.0"
released_at: "2026-01-28T14:30:00+00:00"
deployed_at: "2026-01-28T14:35:00+00:00"
deployed_by: "zxy"
status: "active"

changes:
  summary: "增强 AI 分析控制能力与配置版本管理"
  details: []

images:
  main: "trendradar:v5.5.0"
  mcp: "trendradar-mcp:v3.1.7"

deployment_history:
  - action: "deployed"
    timestamp: "2026-01-28T14:35:00+00:00"
    from_version: null
    success: true
  - action: "updated"
    timestamp: "2026-01-28T15:00:00+00:00"
    from_version: "5.4.0"
    success: true
```

---

## 🔧 高级用法

### 手动管理生产环境

```bash
# 进入生产环境目录
cd /home/zxy/Documents/install/trendradar/current

# 查看日志
docker logs trendradar-prod -f

# 手动触发一次抓取
docker exec trendradar-prod python manage.py run

# 进入容器
docker exec -it trendradar-prod /bin/bash

# 重启容器
docker compose restart
```

---

### 清理旧版本

```bash
# 查看所有版本
trend versions

# 手动删除不需要的版本
rm -rf /home/zxy/Documents/install/trendradar/releases/v5.3.0

# 清理 Docker 镜像
docker rmi trendradar:v5.3.0
docker rmi trendradar-mcp:v3.1.6
```

---

### 备份和恢复

```bash
# 备份生产环境配置
tar -czf trendradar-backup-$(date +%Y%m%d).tar.gz \
  /home/zxy/Documents/install/trendradar/shared/config/

# 备份版本清单
cp /home/zxy/Documents/install/trendradar/versions/manifest.yaml \
   /home/zxy/Documents/install/trendradar/versions/manifest.yaml.backup

# 恢复配置
tar -xzf trendradar-backup-20260128.tar.gz -C /
```

---

## ⚠️ 注意事项

### 1. 配置文件管理

- 配置文件位于 `shared/config/`，所有版本共享
- 如果不同版本需要不同配置，需要手动管理
- 建议在版本切换前备份配置文件

### 2. 数据持久化

- 输出数据位于 `shared/output/`，所有版本共享
- 切换版本不会影响已生成的数据
- RSS 订阅、HTML 报告等数据保持连续

### 3. Docker 镜像

- 每个版本使用独立的 Docker 镜像
- 镜像命名格式：`trendradar:vX.Y.Z`
- 旧版本镜像会占用磁盘空间，可定期清理

### 4. 容器命名

- 生产环境容器：`trendradar-prod`、`trendradar-mcp-prod`
- 开发环境容器：`trendradar`、`trendradar-mcp`
- 两套环境可以同时运行，互不冲突

### 5. 版本回退

- `trend rollback` 只能回退到上一版本
- 如需回退到更早版本，使用 `trend update vX.Y.Z`
- 回退前建议查看版本历史：`trend versions`

---

## 🐛 故障排查

### 问题 1: 版本切换后服务无法启动

**症状**：
```bash
trend update v5.5.0
# 容器启动失败
```

**排查步骤**：
```bash
# 1. 查看容器日志
docker logs trendradar-prod

# 2. 检查配置文件
cat /home/zxy/Documents/install/trendradar/shared/config/config.yaml

# 3. 检查端口占用
netstat -tlnp | grep 8080

# 4. 回退到稳定版本
trend rollback
```

---

### 问题 2: Docker 镜像构建失败

**症状**：
```bash
trend deploy
# Docker 构建失败
```

**排查步骤**：
```bash
# 1. 检查 Dockerfile
cat docker/Dockerfile

# 2. 手动构建测试
cd /home/zxy/Documents/code/TrendRadar
docker build -t trendradar:test -f docker/Dockerfile .

# 3. 检查磁盘空间
df -h

# 4. 清理 Docker 缓存
docker system prune -a
```

---

### 问题 3: 版本记录丢失

**症状**：
```bash
trend versions
# 显示版本不完整
```

**解决方案**：
```bash
# 查看 manifest.yaml
cat /home/zxy/Documents/install/trendradar/versions/manifest.yaml

# 查看版本目录
ls -la /home/zxy/Documents/install/trendradar/releases/

# 如果版本目录存在但记录丢失，可以手动重建
# （参考 deploy.sh 中的版本记录创建逻辑）
```

---

## 📚 相关文档

- [trend 命令行工具指南](../agents/trend-command-guide.md)
- [版本管理系统实现记录](../agents/version-management-system.md)
- [Docker 部署指南](../agents/docker-deployment-fix.md)

---

## 🆘 获取帮助

```bash
# 查看 trend 命令帮助
trend help

# 查看版本管理相关命令
trend help | grep -A 5 "版本管理"
```

如有问题，请查看：
- 部署脚本源码：`/home/zxy/Documents/code/TrendRadar/deploy/`
- 版本记录文件：`/home/zxy/Documents/install/trendradar/versions/`
- Docker 日志：`docker logs trendradar-prod`
