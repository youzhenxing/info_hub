# 强制部署流程机制 - 详细说明

## 概述

本文档详细说明了 TrendRadar 项目实施的**强制部署流程机制**，旨在解决频繁绕过标准部署流程的问题，确保代码版本与部署版本的一致性。

**版本**：v5.26.0+
**实施日期**：2026-02-10
**优先级**：P0（必须）

---

## 问题背景

### 频繁出现的违规操作

在实际开发和部署过程中，以下违规操作频繁发生：

1. **直接重启容器**：
   ```bash
   docker restart trendradar-prod
   ```
   - 问题：容器内代码未更新，修改丢失

2. **直接重建容器**：
   ```bash
   cd releases/v5.26.0
   docker compose down && docker compose up -d
   ```
   - 问题：文件可能未同步，volumes 不完整

3. **代码修改后不部署**：
   ```bash
   git add .
   git commit
   ```
   - 问题：代码版本领先于部署版本

### 导致的问题

- ❌ 代码版本与部署版本不一致
- ❌ 生产环境运行未验证的代码
- ❌ 部署通知邮件未发送
- ❌ 版本管理混乱
- ❌ 难以追溯代码变更历史

---

## 解决方案：四层防护机制

### 架构图

```
┌─────────────────────────────────────────────────────────────┐
│                    强制部署流程机制                         │
└─────────────────────────────────────────────────────────────┘
                            │
        ┌─────────────────┼─────────────────┐
        │                 │                 │
        ▼                 ▼                 ▼
   ┌─────────┐      ┌──────────┐    ┌──────────────┐
   │ 第一层  │      │  第二层  │    │    第三层    │
   │部署标记  │◄───►│Git Hook  │◄──►│容器启动验证  │
   └─────────┘      └──────────┘    └──────────────┘
        ▲                 ▲                 ▲
        │                 │                 │
   ┌────────────────────────────────────────┐
   │           第四层：简化工具             │
   │  - 一键部署脚本                       │
   │  - 状态查询脚本                       │
   └────────────────────────────────────────┘
```

---

### 第一层：部署标记文件机制

**目的**：记录当前代码库对应的已部署版本

#### 实施细节

**标记文件位置**：`/home/zxy/Documents/code/TrendRadar/.deployed_version`

**文件格式**：
```yaml
version: "5.26.0"
deployed_at: "2026-02-10T13:27:42+00:00"
deployed_by: "zxy"
commit_hash: "abc123..."
deployment_path: "/home/zxy/Documents/install/trendradar/releases/v5.26.0"
```

**字段说明**：
- `version`：已部署的版本号
- `deployed_at`：部署时间（UTC）
- `deployed_by`：部署者用户名
- `commit_hash`：部署时的 Git commit hash
- `deployment_path`：部署在生产环境的路径

**生成方式**：
- 每次执行 `deploy.sh` 成功后自动生成
- 位置：`deploy/deploy.sh` 第7步（约第283行后）

**Git 管理**：
- 添加到 `.gitignore`，不提交到 Git
- 本地文件，用于追踪部署状态

---

### 第二层：Git Pre-commit Hook 增强

**目的**：在 Git 提交前强制检查版本一致性

#### 实施细节

**Hook 位置**：`.git/hooks/pre-commit`

**验证逻辑**（`deploy/pre-commit-verify.sh` Phase 6）：

```bash
# 1. 读取部署标记
DEPLOYED_VERSION=$(cat .deployed_version | grep "^version:" | ...)
CODE_VERSION=$(cat version)

# 2. 版本比较
if [ "$DEPLOYED_VERSION" != "$CODE_VERSION" ]; then
    # ❌ 阻止提交，提示执行部署
    echo "❌ 代码版本与部署版本不一致"
    echo "请执行：cd deploy && yes \"y\" | bash deploy.sh"
    exit 1
fi

# 3. 检查暂存的文件修改
MODIFIED_FILES=$(git diff --cached --name-only)
AFFECTS_RUNTIME=$(echo "$MODIFIED_FILES" | grep -E "^(trendradar|docker|config|wechat)/")

if [ -n "$AFFECTS_RUNTIME" ]; then
    # ❌ 检测到影响运行时的代码修改
    echo "❌ 这些文件修改后必须重新部署"
    exit 1
fi
```

**检查逻辑**：
1. **版本一致性**：代码版本与部署版本必须一致
2. **文件影响检查**：只检查暂存区的文件（即将提交的）
3. **排除文件**：
   - `.deployed_version`（部署标记本身）
   - `CHANGELOG.md`、`CLAUDE.md`、`AGENTS.md`（文档文件）
   - `*.db`、`*.log`、`*.sqlite`（数据文件）
   - `__pycache__`、`node_modules`（缓存）

**执行时机**：每次 `git commit` 时自动触发

---

### 第三层：容器启动时版本验证

**目的**：容器启动时检测版本不一致并发出警告

#### 实施细节

**验证位置**：`docker/bootstrap.py` main() 函数开始处

**验证逻辑**：
```python
def main():
    app_version = os.getenv("APP_VERSION", "")

    # 读取代码版本标记
    code_version_marker = "/app/.deployed_version"
    if os.path.exists(code_version_marker):
        with open(code_version_marker, 'r') as f:
            marker_data = yaml.safe_load(f)

        deployed_version = marker_data.get('version', '').replace('v', '')
        container_version = app_version.replace('v', '')

        if deployed_version != container_version:
            # ⚠️ 版本不一致警告
            log.warning(f"[Bootstrap] ⚠️ 版本不一致警告！")
            log.warning(f"[Bootstrap]   代码标记版本: {deployed_version}")
            log.warning(f"[Bootstrap]   容器运行版本: {container_version}")
            log.warning(f"[Bootstrap]   建议：执行部署重新部署")
```

**Volume 挂载**：
- 在 `deploy/deploy.sh` 中添加 volume 挂载
- 将开发环境的 `.deployed_version` 挂载到容器

```bash
volumes:
  - $DEV_BASE/.deployed_version:/app/.deployed_version:ro
```

**执行时机**：每次容器启动时自动检查

---

### 第四层：简化部署操作工具

**目的**：提供一键部署脚本，减少手动操作失误

#### 工具 1：一键部署脚本

**文件**：`deploy/quick-deploy.sh`

**功能**：
1. 检查代码状态（确保代码已提交）
2. 执行部署（自动确认模式）
3. 切换到新版本
4. 验证部署

**使用方法**：
```bash
cd deploy
./quick-deploy.sh
```

**执行流程**：
```
[Step 1/5] 检查代码状态
  ✓ 检测到代码修改

[Step 2/5] 读取版本信息
  ✓ 当前版本: v5.26.0

[Step 3/5] 执行部署
  ✓ 部署成功，生成 .deployed_version

[Step 4/5] 切换到新版本
  ✓ 已切换到 v5.26.0

[Step 5/5] 验证部署
  ✓ 容器运行正常
```

#### 工具 2：状态查询脚本

**文件**：`deploy/check-deploy-status.sh`

**功能**：
- 显示代码版本
- 显示部署版本
- 检查版本一致性
- 显示 Git 状态
- 显示容器状态

**使用方法**：
```bash
cd deploy
./check-deploy-status.sh
```

**输出示例**：
```
═══════════════════════════════════════════════
  TrendRadar 部署状态
═══════════════════════════════════════════════

📦 代码版本:
  版本号: 5.26.0
  最后提交: 2026-02-10 21:27:33 +0800

🚀 部署版本:
  版本号: 5.26.0
  部署时间: 2026-02-10T21:28:00+00:00
  生产环境: 5.26.0

🔍 版本一致性:
  ✓ 代码版本与部署版本一致

📝 Git状态:
  ✓ 工作区干净

🐳 容器状态:
  容器运行: ✓
  容器版本: 5.26.0

═══════════════════════════════════════════════
```

---

## 完整工作流程

### 正常开发流程

```bash
# 1. 修改代码
vim trendradar/core/some_module.py

# 2. 提交代码（会被 pre-commit hook 拦截）
git add .
git commit
# ❌ 错误：代码版本与部署版本不一致
# 提示：必须先执行部署

# 3. 执行部署
cd deploy
yes "y" | bash deploy.sh
# ✅ 部署成功，自动生成 .deployed_version

# 4. 切换版本
trend update v5.27.0

# 5. 提交代码（现在会成功）
git add .deployed_version
git commit -m "feat: 新功能"
# ✅ 提交成功
```

### 一键部署流程（推荐）

```bash
# 使用一键部署脚本
cd deploy
./quick-deploy.sh

# 脚本会自动完成：
# 1. 检查代码状态
# 2. 执行部署
# 3. 切换版本
# 4. 验证部署

# 然后提交
git add .deployed_version
git commit
```

### 仅文档修改（无需部署）

```bash
# 修改文档
vim CLAUDE.md

# 提交（pre-commit hook 会检测到仅文档修改，允许提交）
git add .
git commit -m "docs: 更新文档"
# ✅ 提交成功，无需部署
```

---

## 防护机制对比

| 场景 | 无防护机制 | 有防护机制 |
|------|-----------|-----------|
| 修改代码后直接提交 | ❌ 可能导致生产运行未验证代码 | ✅ Pre-commit hook 拦截，强制要求先部署 |
| 直接 docker restart | ⚠️ 代码不更新，修改丢失 | ⚠️ 修改丢失，但容器启动时会有版本不一致警告 |
| 容器重建（docker compose up） | ⚠️ 可能文件未同步 | ✅ volume 挂载确保文件完整 |
| 版本追踪 | ❌ 无法知道代码版本与部署版本关系 | ✅ 清晰的版本一致性检查 |

---

## 技术要点

### 1. 版本号格式统一

**重要**：确保版本号格式一致

- **version 文件**：`5.26.0`（无 v 前缀）
- **.deployed_version**：`"5.26.0"`（YAML 字符串）
- **容器环境变量**：`APP_VERSION=5.26.0`（无 v 前缀）

**比较时统一去掉 v 前缀**：
```bash
CODE_VER_NUM=$(echo "$CODE_VERSION" | sed 's/^v//')
DEPLOYED_VER_NUM=$(echo "$DEPLOYED_VERSION" | sed 's/^v//')
```

### 2. Git暂存区 vs 工作区

**关键**：只检查暂存区的文件（即将提交的），不检查工作区

```bash
# ✅ 正确：只检查暂存区
MODIFIED_FILES=$(git diff --cached --name-only)

# ❌ 错误：检查工作区（会包含数据库等不需要提交的文件）
MODIFIED_FILES=$(git diff --name-only)
```

### 3. Volume 挂载路径

**注意**：开发环境和生产环境的路径必须可访问

```bash
# deploy.sh 中的挂载配置
volumes:
  - $DEV_BASE/.deployed_version:/app/.deployed_version:ro
  #   ↑ 开发环境路径                ↑ 容器内路径
```

**路径映射**：
- 开发环境：`/home/zxy/Documents/code/TrendRadar/.deployed_version`
- 容器内：`/app/.deployed_version`

### 4. Pre-commit Hook 执行时机

**触发时机**：每次 `git commit` 时自动执行

**绕过方法**（仅紧急情况）：
```bash
git commit --no-verify
```

⚠️ **警告**：不应作为常规操作使用

---

## 验证测试

### 测试场景 1：正常部署流程

**步骤**：
1. 修改代码：`echo "# test" >> trendradar/__init__.py`
2. 尝试提交：`git add . && git commit`
3. 预期：❌ 被 pre-commit hook 拦截
4. 执行部署：`cd deploy && yes "y" | bash deploy.sh`
5. 切换版本：`trend update v5.26.0`
6. 提交代码：`git add .deployed_version && git commit`
7. 预期：✅ 提交成功

**结果**：✅ 测试通过

### 测试场景 2：仅文档修改

**步骤**：
1. 修改文档：`echo "# test" >> CLAUDE.md`
2. 提交代码：`git add . && git commit`
3. 预期：✅ 提交成功（pre-commit hook 检测到仅文档修改）

**结果**：✅ 测试通过

### 测试场景 3：容器启动验证

**步骤**：
1. 修改 `.deployed_version` 为不同版本
2. 重启容器：`docker restart trendradar-prod`
3. 查看日志：`docker logs trendradar-prod | grep "版本不一致"`
4. 预期：⚠️ 显示版本不一致警告

**结果**：✅ 测试通过

---

## 常见问题

### Q1: 如何检查当前版本状态？

**答**：使用状态查询脚本
```bash
cd deploy
./check-deploy-status.sh
```

### Q2: 版本不一致时如何解决？

**答**：执行完整部署流程
```bash
# 方式1：一键部署（推荐）
cd deploy
./quick-deploy.sh

# 方式2：手动部署
cd deploy
yes "y" | bash deploy.sh
trend update v5.26.0
```

### Q3: 紧急修复如何快速提交？

**答**：使用 `--no-verify` 绕过检查（不推荐）
```bash
git commit --no-verify -m "hotfix: 紧急修复"
```

⚠️ **警告**：紧急修复后也应尽快补上部署流程

### Q4: 为什么 .deployed_version 要在 .gitignore 中？

**答**：
- 部署标记是本地文件，记录本地部署状态
- 不同开发者的部署环境可能不同
- 提交到 Git 会导致冲突和管理困难

### Q5: 容器启动时提示版本不一致怎么办？

**答**：
1. 检查代码版本：`cat version`
2. 检查部署标记：`cat .deployed_version`
3. 如果不一致，执行部署流程
4. 如果一致，可以忽略警告（可能是时间差）

---

## 后续优化建议

### 短期（1-2周）

- [ ] 添加监控告警：版本不一致时发送通知
- [ ] 完善日志记录：详细记录版本检查过程
- [ ] 优化错误提示：更明确的修复指引

### 中期（1-2个月）

- [ ] 集成到 CI/CD：自动化流水线中的版本检查
- [ ] Web UI 可视化：版本状态管理界面
- [ ] 回滚保护：防止回滚到过旧版本

### 长期（3-6个月）

- [ ] 多环境支持：开发、测试、生产环境隔离
- [ ] 灰度发布：金丝雀发布、蓝绿部署
- [ ] 自动化测试：部署前自动执行测试套件

---

## 相关文档

- **项目规范**：`CLAUDE.md`
- **部署规则**：`CLAUDE.md` 规则 12
- **部署脚本**：`deploy/deploy.sh`
- **验证脚本**：`deploy/pre-commit-verify.sh`
- **Bootstrap 机制**：`docker/bootstrap.py`

---

## 更新日志

- **2026-02-10**：v5.26.0 - 初始实施
  - 实施四层防护机制
  - 添加部署标记文件
  - 增强 Git Pre-commit Hook
  - 添加容器启动验证
  - 创建简化部署工具
