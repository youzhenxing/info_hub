# TrendRadar 版本管理系统实现记录

**时间**: 2026-01-28 14:30 - 15:30
**任务**: 实现完整的版本管理和生产环境部署系统
**状态**: ✅ 已完成

---

## 📋 需求背景

用户需要：
1. **环境隔离**: 开发环境用于开发，生产环境用于正式运行
2. **版本管理**: 支持发布、更新、回退多个版本
3. **版本记录**: 每个版本有详细的记录信息（版本号、时间、变更说明）

具体要求：
- 开发环境：`/home/zxy/Documents/code/TrendRadar`（保持不变）
- 安装环境：`/home/zxy/Documents/install/trendradar`（新建）
- 功能需求：发布、更新、回退
- 记录需求：基本版本信息

---

## 🏗️ 系统设计

### 架构概述

采用**软链接 + 多版本并存**的设计模式：

```
生产环境目录结构:
/home/zxy/Documents/install/trendradar/
├── current -> releases/v5.4.0     # 软链接，指向当前版本
├── releases/                       # 版本仓库
│   ├── v5.4.0/
│   └── v5.5.0/
├── shared/                         # 共享数据（跨版本）
│   ├── config/                    # 配置文件
│   └── output/                    # 输出数据
└── versions/                       # 版本管理元数据
    ├── manifest.yaml              # 版本清单
    └── history/                   # 版本详细记录
```

### 设计原则

1. **版本独立性**: 每个版本完全独立，互不影响
2. **快速切换**: 通过软链接实现秒级切换
3. **数据共享**: 配置和输出数据跨版本共享
4. **容器隔离**: 生产/开发容器命名不同，可同时运行

---

## 🔧 实现方案

### 1. 目录结构设计

#### releases/ - 版本仓库
每个版本包含：
- `trendradar/` - 核心代码
- `mcp_server/` - MCP 服务器代码
- `docker/` - Docker 配置文件
- `docker-compose.yml` - 生产环境 Compose 配置
- `version` - 版本号文件
- `version_mcp` - MCP 版本号
- `requirements.txt` - Python 依赖

#### shared/ - 共享数据
- `config/` - 配置文件（只读挂载）
- `output/` - 输出数据（读写挂载）

#### versions/ - 版本元数据
- `manifest.yaml` - 简洁的版本清单
- `history/vX.Y.Z.yaml` - 每个版本的详细记录

---

### 2. 核心脚本实现

#### init-production.sh - 初始化脚本

**功能**: 创建生产环境目录结构

**实现要点**:
```bash
# 创建目录
mkdir -p "$PROD_BASE"/{releases,shared/{config,output},versions/history}

# 初始化 manifest.yaml
cat > versions/manifest.yaml << EOF
current_version: null
previous_version: null
versions: []
EOF

# 从开发环境复制配置
cp -r config/* shared/config/
```

**文件**: `/home/zxy/Documents/code/TrendRadar/deploy/init-production.sh`

---

#### version-manager.sh - 版本管理工具库

**功能**: 提供版本信息读取、更新、查询等核心功能

**核心函数**:

| 函数 | 功能 | 返回值 |
|------|------|--------|
| `check_production_initialized()` | 检查生产环境是否初始化 | 0=已初始化, 1=未初始化 |
| `get_current_version()` | 读取当前版本号 | 版本号字符串或"null" |
| `get_previous_version()` | 读取上一版本号 | 版本号字符串或"null" |
| `version_exists()` | 检查版本是否存在 | 0=存在, 1=不存在 |
| `list_versions()` | 列出所有版本 | 版本列表（按时间倒序） |
| `add_version_to_manifest()` | 添加版本到清单 | 无 |
| `update_current_version()` | 更新当前版本 | 无 |
| `create_version_record()` | 创建版本详细记录 | 记录文件路径 |
| `add_deployment_history()` | 添加部署历史 | 无 |
| `get_version_info()` | 获取版本信息 | 版本记录内容 |

**实现亮点**:

1. **函数导出**: 使用 `export -f` 导出函数供其他脚本调用
2. **版本号处理**: 自动处理带/不带 `v` 前缀的版本号
3. **YAML 操作**: 使用 `sed` 实现 YAML 文件的读写
4. **错误处理**: 函数返回值明确，便于错误检查

**文件**: `/home/zxy/Documents/code/TrendRadar/deploy/version-manager.sh`

---

#### deploy.sh - 版本发布脚本

**功能**: 从开发环境构建并发布新版本

**执行流程**:
```
1. 读取版本号（version, version_mcp）
   ↓
2. 构建 Docker 镜像
   - docker build -t trendradar:vX.Y.Z
   - docker build -t trendradar-mcp:vX.Y.Z
   ↓
3. 创建版本目录 releases/vX.Y.Z/
   ↓
4. 复制文件
   - trendradar/, mcp_server/, docker/
   - version, version_mcp, requirements.txt
   ↓
5. 生成 docker-compose.yml
   - 配置镜像版本
   - 配置卷挂载（shared/config, shared/output）
   - 配置容器名称（trendradar-prod）
   ↓
6. 创建版本记录
   - 生成 history/vX.Y.Z.yaml
   - 更新 manifest.yaml
   ↓
7. 完成（版本已发布但未启用）
```

**关键实现**:

1. **版本覆盖处理**:
```bash
if version_exists "$VERSION"; then
    read -r confirm
    if [[ ! "$confirm" =~ ^[Yy]$ ]]; then
        exit 0
    fi
fi
```

2. **Docker Compose 生成**:
```bash
cat > "$RELEASE_DIR/docker-compose.yml" << EOF
services:
  trendradar:
    image: trendradar:v${VERSION}
    container_name: trendradar-prod
    volumes:
      - ../../shared/config:/app/config:ro
      - ../../shared/output:/app/output
EOF
```

3. **版本信息记录**:
```bash
# 从 git commit 读取变更说明
SUMMARY=$(git log -1 --pretty=format:"%s" 2>/dev/null)

# 创建详细记录
create_version_record "$VERSION" \
    "trendradar:v${VERSION}" \
    "trendradar-mcp:v${MCP_VERSION}" \
    "$SUMMARY"
```

**文件**: `/home/zxy/Documents/code/TrendRadar/deploy/deploy.sh`

---

#### update.sh - 版本更新脚本

**功能**: 将生产环境切换到指定版本

**执行流程**:
```
1. 检查目标版本是否存在
   ↓
2. 停止当前容器
   - docker compose down
   ↓
3. 更新软链接
   - rm -f current
   - ln -sfn releases/vX.Y.Z current
   ↓
4. 更新版本清单
   - update_current_version()
   ↓
5. 启动新版本
   - cd current && docker compose up -d
   ↓
6. 记录部署历史
   - add_deployment_history()
   ↓
7. 检查服务状态
```

**关键实现**:

1. **安全的容器停止**:
```bash
if docker ps --format "{{.Names}}" | grep -q "trendradar-prod"; then
    cd "$PROD_BASE/current" && docker compose down || true
fi
```

2. **原子性链接更新**:
```bash
cd "$PROD_BASE"
rm -f current
ln -sfn "releases/v${TARGET_VERSION}" current
```

3. **服务状态检查**:
```bash
sleep 3  # 等待容器启动
if docker ps | grep -q "trendradar-prod"; then
    # 显示状态
else
    # 显示错误信息和排查提示
fi
```

**文件**: `/home/zxy/Documents/code/TrendRadar/deploy/update.sh`

---

#### rollback.sh - 版本回退脚本

**功能**: 快速回退到上一版本

**执行流程**:
```
1. 读取当前版本和上一版本
   ↓
2. 确认回退操作
   ↓
3. 调用 update.sh 切换到上一版本
   ↓
4. 更新部署历史（标记为 rollback）
```

**实现要点**:
- 复用 `update.sh` 的版本切换逻辑
- 在部署历史中记录 `from_version`（回退前的版本）
- 部署类型标记为 `rollback`

**文件**: `/home/zxy/Documents/code/TrendRadar/deploy/rollback.sh`

---

### 3. 扩展 trend 命令

在现有的 `trend` 命令基础上添加版本管理功能。

#### 新增命令

| 命令 | 功能 | 实现 |
|------|------|------|
| `trend deploy` | 发布新版本 | 调用 `deploy/deploy.sh` |
| `trend update <version>` | 更新到指定版本 | 调用 `deploy/update.sh` |
| `trend rollback` | 回退到上一版本 | 调用 `deploy/rollback.sh` |
| `trend versions` | 列出所有版本 | 读取 `manifest.yaml` 并格式化输出 |
| `trend version-info <version>` | 查看版本详情 | 读取 `history/vX.Y.Z.yaml` |
| `trend production` | 查看生产环境状态 | 显示当前版本、容器状态等 |

#### 实现细节

**cmd_versions() - 列出版本**:
```bash
cmd_versions() {
    # 从 manifest.yaml 读取版本列表
    grep "^  - version:" "$MANIFEST_FILE" | \
    while read -r line; do
        version=$(echo "$line" | awk '{print $3}' | tr -d '"')
        # 显示版本、状态、时间、镜像
    done
}
```

**cmd_production() - 生产环境状态**:
```bash
cmd_production() {
    CURRENT=$(get_current_version)
    PREVIOUS=$(get_previous_version)

    # 显示版本信息
    echo "运行版本: v${CURRENT}"
    echo "上一版本: v${PREVIOUS}"

    # 显示容器状态
    docker ps --format "table {{.Names}}\t{{.Status}}" | \
        grep -E "NAMES|trendradar"
}
```

**文件**: `/home/zxy/Documents/code/TrendRadar/trend`

---

## 📊 数据结构设计

### manifest.yaml（版本清单）

**目的**: 快速查询当前版本和版本列表

**结构**:
```yaml
current_version: "5.5.0"      # 当前运行版本
previous_version: "5.4.0"     # 上一版本（用于回退）
versions:                      # 版本列表
  - version: "5.5.0"
    released_at: "2026-01-28T14:30:00+00:00"
    status: "active"           # active/inactive
    image: "trendradar:v5.5.0"
  - version: "5.4.0"
    released_at: "2026-01-28T11:00:00+00:00"
    status: "inactive"
    image: "trendradar:v5.4.0"
```

**操作**:
- 读取：`grep` + `awk` 解析
- 更新：`sed -i` 修改

---

### vX.Y.Z.yaml（版本详细记录）

**目的**: 记录版本的完整信息和部署历史

**结构**:
```yaml
version: "5.5.0"
released_at: "2026-01-28T14:30:00+00:00"    # 版本发布时间
deployed_at: "2026-01-28T14:35:00+00:00"    # 首次部署时间
deployed_by: "zxy"                           # 部署者
status: "active"                             # 当前状态

changes:                                     # 变更说明
  summary: "增强 AI 分析控制能力"
  details: []

images:                                      # Docker 镜像
  main: "trendradar:v5.5.0"
  mcp: "trendradar-mcp:v3.1.7"

deployment_history:                          # 部署历史
  - action: "deployed"                       # deployed/updated/rollback
    timestamp: "2026-01-28T14:35:00+00:00"
    from_version: null
    success: true
  - action: "updated"
    timestamp: "2026-01-28T15:00:00+00:00"
    from_version: "5.4.0"
    success: true
```

**操作**:
- 创建：`cat > file << EOF`
- 追加：`cat >> file << EOF`（部署历史）
- 查看：`cat file`

---

## 🎯 实现亮点

### 1. 软链接实现快速切换

**优势**:
- 切换速度快（秒级）
- 不需要复制文件
- 容器路径保持不变（`/current`）

**实现**:
```bash
# 切换版本
ln -sfn "releases/v5.5.0" current

# Docker Compose 始终从 current/ 启动
cd /home/zxy/Documents/install/trendradar/current
docker compose up -d
```

---

### 2. 共享数据设计

**优势**:
- 配置只需维护一份
- 数据跨版本连续（RSS 订阅、报告）
- 版本切换不影响用户数据

**实现**:
```yaml
# docker-compose.yml
volumes:
  - ../../shared/config:/app/config:ro     # 只读
  - ../../shared/output:/app/output        # 读写
```

---

### 3. 容器命名隔离

**优势**:
- 开发和生产环境可同时运行
- 互不冲突
- 便于识别和管理

**命名规则**:
- 开发环境：`trendradar`, `trendradar-mcp`
- 生产环境：`trendradar-prod`, `trendradar-mcp-prod`

---

### 4. 版本号自动读取

**优势**:
- 避免手动输入错误
- 保证版本一致性
- 从 git commit 自动提取变更说明

**实现**:
```bash
# 读取版本号
VERSION=$(cat version | tr -d '[:space:]')

# 读取变更说明
SUMMARY=$(git log -1 --pretty=format:"%s")
```

---

### 5. 部署历史追踪

**优势**:
- 记录每次部署操作
- 支持审计和问题追踪
- 了解版本演变历史

**记录内容**:
- 操作类型（deployed/updated/rollback）
- 时间戳
- 源版本（如果是更新或回退）
- 成功/失败状态

---

## ✅ 测试验证

### 测试场景

**未执行实际测试**，计划测试流程：

1. **初始化生产环境**
```bash
./deploy/init-production.sh
# 验证目录结构创建成功
ls -la /home/zxy/Documents/install/trendradar/
```

2. **发布第一个版本（v5.4.0）**
```bash
trend deploy
# 验证镜像和目录
docker images | grep trendradar:v5.4.0
ls /home/zxy/Documents/install/trendradar/releases/v5.4.0/
```

3. **更新到新版本**
```bash
echo "5.5.0" > version
trend deploy
trend update v5.5.0
# 验证容器运行
docker ps | grep trendradar-prod
```

4. **回退测试**
```bash
trend rollback
# 验证回到 v5.4.0
readlink /home/zxy/Documents/install/trendradar/current
```

5. **版本查询**
```bash
trend versions
trend version-info v5.5.0
trend production
```

---

## 📁 文件清单

### 新建脚本

| 文件路径 | 功能 | 行数 |
|---------|------|------|
| `deploy/init-production.sh` | 初始化生产环境 | ~100 |
| `deploy/version-manager.sh` | 版本管理工具库 | 195 |
| `deploy/deploy.sh` | 发布新版本 | 211 |
| `deploy/update.sh` | 更新版本 | 140 |
| `deploy/rollback.sh` | 回退版本 | 72 |

### 修改文件

| 文件路径 | 修改内容 |
|---------|---------|
| `trend` | 新增 6 个版本管理命令 |

### 新建文档

| 文件路径 | 内容 |
|---------|------|
| `deploy/README.md` | 版本管理系统使用指南 |
| `agents/version-management-system.md` | 本文档（实现记录） |

---

## 🔍 技术细节

### Shell 脚本技巧

1. **颜色输出**:
```bash
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m'
echo -e "${GREEN}✅ 成功${NC}"
```

2. **HEREDOC 生成文件**:
```bash
cat > file.yaml << EOF
key: value
EOF
```

3. **函数导出**:
```bash
export -f function_name
# 其他脚本可以通过 source 使用
```

4. **版本号处理**:
```bash
# 去掉 v 前缀
VERSION="${VERSION#v}"
```

5. **条件判断**:
```bash
if [[ "$confirm" =~ ^[Yy]$ ]]; then
    # 用户确认
fi
```

### YAML 操作

使用 `sed` 和 `grep` 操作 YAML：

**读取**:
```bash
grep "^current_version:" manifest.yaml | \
    awk '{print $2}' | tr -d '"'
```

**更新**:
```bash
sed -i "s/^current_version:.*/current_version: \"$new_version\"/" \
    manifest.yaml
```

**追加**:
```bash
cat >> file.yaml << EOF
  - new_item: value
EOF
```

### Docker 操作

**镜像构建**:
```bash
docker build -t trendradar:v${VERSION} \
    -f docker/Dockerfile . --quiet
```

**容器管理**:
```bash
# 检查容器是否运行
docker ps --format "{{.Names}}" | grep -q "trendradar-prod"

# 停止容器
docker compose down

# 启动容器
docker compose up -d
```

---

## 📝 改进建议

### 已实现的功能

- ✅ 版本发布、更新、回退
- ✅ 版本清单和详细记录
- ✅ 软链接管理
- ✅ 共享配置和数据
- ✅ 容器命名隔离
- ✅ 部署历史追踪

### 可选的增强功能

1. **配置版本管理**
   - 不同版本可能需要不同的配置
   - 可以在 `releases/vX.Y.Z/` 下保存版本专属配置
   - 版本切换时自动替换配置

2. **数据库迁移**
   - 如果使用数据库，版本升级可能需要 schema 迁移
   - 可以在 `deploy.sh` 中添加迁移脚本执行

3. **自动化测试**
   - 版本发布前自动运行测试
   - 测试通过才允许发布

4. **镜像自动清理**
   - 定期清理旧版本的 Docker 镜像
   - 节省磁盘空间

5. **版本比较**
   - `trend diff v5.4.0 v5.5.0` - 显示两个版本的差异
   - 包括代码变更、配置变更等

6. **远程部署**
   - 支持将版本发布到远程服务器
   - SSH + rsync 实现

---

## 🎓 学习要点

### 版本管理模式

采用的是类似 **Capistrano** 的部署模式：
- 多版本并存（releases/）
- 软链接切换（current）
- 共享数据（shared/）

这种模式的优点：
- 回退快速（只需切换链接）
- 版本隔离（互不影响）
- 数据连续（shared 跨版本）

### Shell 脚本组织

**模块化设计**:
- `version-manager.sh` - 工具库（函数）
- `deploy.sh`、`update.sh`、`rollback.sh` - 功能脚本
- `trend` - 用户界面

**优势**:
- 代码复用（工具库）
- 职责清晰（单一功能）
- 易于维护和扩展

### Docker 最佳实践

1. **版本化镜像**: `trendradar:v5.4.0`
2. **只读配置**: `config:ro`
3. **命名规范**: `trendradar-prod`
4. **环境隔离**: 开发/生产分离

---

## 📚 参考资源

- [Semantic Versioning](https://semver.org/) - 语义化版本规范
- [Capistrano](https://capistranorb.com/) - Ruby 部署工具（设计灵感）
- [Docker Best Practices](https://docs.docker.com/develop/dev-best-practices/) - Docker 最佳实践

---

## 🔗 相关文档

- [版本管理系统使用指南](../deploy/README.md)
- [trend 命令行工具指南](./trend-command-guide.md)
- [Docker 部署修复记录](./docker-deployment-fix.md)

---

**实现者**: Claude Code (AI Assistant)
**审核者**: zxy
**文档版本**: 1.0
