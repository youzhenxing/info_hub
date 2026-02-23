# TrendRadar 项目规范

## 💬 对话规范

**必须使用中文进行对话，每次回复都必须以"Hi, Genius:"作为开头**

---

## 📁 文件放置规则

所有模型输出的非代码文件（如测试文件、Markdown 文档等辅助文件）必须放置在对应工作空间的 `agents` 目录下。

### 具体要求

1. **非代码文件定义**：
   - 测试文件（`.test.ts`, `.spec.py`, `test_*.py` 等）
   - Markdown 文档（`.md`）
   - 配置文件（`.yaml`, `.yml`, `.json` 等）
   - 其他辅助性文件

2. **放置位置**：
   - 主文件：放在 `agents/` 目录下
   - 按需组织：可以在 `agents/` 目录下创建子目录进行分类管理

3. **示例结构**：
   ```
   agents/
   ├── test_utils.py
   ├── README.md
   ├── config.yaml
   └── tests/
       ├── test_main.py
       └── fixtures/
   ```

### 注意事项
- 代码文件（源码）仍应放在正常的源代码目录结构中
- 此规则仅适用于非代码的辅助文件
- 目录结构应保持清晰、可维护

4. **输出html文件时，给出绝对路径**，方便我用本地浏览器直接打开

   **错误示例**：`output/community/email/community_20260208_083828.html`

   **正确示例**：`file:///home/zxy/Documents/code/TrendRadar/output/community/email/community_20260201_160053.html`

---

## 🚀 快速开始：微信立即触发测试

**最常见的使用场景**：手动触发微信公众号模块，立即采集、分析和推送。

### ⚡ 三种立即触发方式

#### 方式 1️⃣：使用统一命令（推荐）

```bash
# 立即触发微信模块（最简单）
trend run wechat

# 强制执行（忽略模块启用状态）
trend run wechat -f
```

**适用场景**：生产环境或开发环境，使用统一配置系统。

#### 方式 2️⃣：本地直接运行（快速测试）

```bash
# 进入微信模块目录
cd wechat/

# 直接运行（无需 Docker）
python main.py run
```

**适用场景**：本地开发测试，不经过容器，快速调试。

#### 方式 3️⃣：Docker 容器内执行

```bash
# 如果使用独立部署
docker exec -it wechat-service python main.py run

# 如果使用集成部署
docker exec -it trendradar-prod python -m trendradar.cli run wechat
```

**适用场景**：在容器内测试，使用生产环境配置。

### 📊 查看执行日志

```bash
# 方式 1：使用 trend 命令查看日志
trend logs | grep -A 20 WeChat

# 方式 2：直接查看 Docker 日志
docker logs trendradar-prod -f | grep WeChat

# 方式 3：查看完整输出
cd wechat && python main.py run
```

### 🧪 测试模式配置

如果只想测试少量公众号，编辑 `wechat/config.yaml`：

```yaml
test:
  enabled: true      # 启用测试模式
  feed_limit: 3      # 只处理前 3 个公众号
```

测试模式下会自动：
- ✅ 跳过时间检查
- ✅ 跳过重复检查
- ✅ 限制处理公众号数量

### ⚙️ 前置条件检查

在执行前，确保 Wewe-RSS 服务正常运行：

```bash
# 检查 Wewe-RSS 服务
curl http://localhost:4000/feeds

# 查看微信读书账号状态
# 浏览器访问：http://localhost:4000
```

### 📧 验证邮件推送

执行完成后，检查邮箱是否收到微信日报。如果未收到：

```bash
# 检查推送历史
sqlite3 wechat/data/wechat.db "SELECT * FROM push_history ORDER BY push_time DESC LIMIT 5"

# 测试邮件发送
cd wechat && python main.py test-email
```

---

## 🔄 手动更新公众号订阅源

> **⚠️ 重要说明**：为避免被微信限流，已关闭自动定时更新（原每2小时），改为手动触发模式。

### 推荐更新时机

- **最佳时间**：每天早上 8:00-10:00（避开高峰期）
- **更新频率**：每天 1 次即可
- **更新前检查**：确保 Wewe-RSS 服务正常运行

### 方式 1️⃣：使用一键更新脚本（推荐）

```bash
# 进入微信模块目录
cd /home/zxy/Documents/code/TrendRadar/wechat

# 执行更新脚本
bash ./update-feeds.sh
```

**脚本功能**：
- ✅ 自动检查容器状态
- ✅ 逐个更新所有订阅源（带延迟，避免限流）
- ✅ 显示更新进度和结果统计
- ✅ 提供下一步操作提示

### 方式 2️⃣：通过 Web 界面手动更新（最简单）

1. **访问 Wewe-RSS 管理页面**：http://localhost:4000
2. **检查账号状态**：如果显示账号失效，扫码登录微信读书
3. **点击"全部更新"**：等待 1-2 分钟完成更新
4. **验证更新结果**：查看订阅源的 `syncTime` 更新时间

### 方式 3️⃣：使用 API 逐个更新

```bash
# 获取所有订阅源列表
curl -s http://localhost:4000/feeds | python3 -m json.tool

# 更新指定订阅源（需要订阅源 ID）
curl -X POST "http://localhost:4000/feeds/{feed_id}/refresh" \
  -H "Content-Type: application/json" \
  -u ":123456"
```

### 更新后操作

**验证更新成功**：
```bash
# 检查订阅源最后更新时间
curl -s http://localhost:4000/feeds | python3 -c "
import json, sys
from datetime import datetime
data = json.load(sys.stdin)
now = datetime.now().timestamp()
for feed in data[:5]:
    hours = (now - feed['syncTime']) / 3600
    print(f\"{feed['name']}: {hours:.1f} 小时前更新\"
"

# 触发微信模块分析
trend run wechat
```

### 常见问题

**Q1：为什么关闭自动更新？**
- **A**：每2小时自动更新容易被微信限流，手动更新更安全可控。

**Q2：账号失效后还能更新吗？**
- **A**：不能。需要先访问 http://localhost:4000 扫码登录微信读书。

**Q3：更新后多久能看到文章？**
- **A**：更新完成后立即可以触发微信模块分析（`trend run wechat`）。

---

## 🌐 查看本地 HTML 报告

### 快速访问

**最新报告示例**（可直接点击）：
- 投资简报：`file:///home/zxy/Documents/code/TrendRadar/output/investment/email/investment_cn_20260207_074531.html`
- 播客分析：`file:///home/zxy/Documents/code/TrendRadar/output/podcast/email/podcast_YYYYMMDD_HHMMSS.html`
- 社区日报：`file:///home/zxy/Documents/code/TrendRadar/output/community/email/community_cn_YYYYMMDD_HHMMSS.html`
- 微信公众号日报：`file:///home/zxy/Documents/code/TrendRadar/wechat/data/output/wechat_daily_YYYYMMDD_HHMMSS.html`
  - 例如：`file:///home/zxy/Documents/code/TrendRadar/wechat/data/output/wechat_daily_20260208_230746.html`

### 使用方法

**方式1：命令行打开**
```bash
# Linux
xdg-open output/investment/email/investment_cn_20260207_074531.html

# macOS
open output/investment/email/investment_cn_20260207_074531.html
```

**方式2：文件管理器双击**
- 直接双击HTML文件即可在默认浏览器中打开

**方式3：浏览器手动打开**
1. 复制完整路径：`file:///home/zxy/Documents/code/TrendRadar/output/investment/email/investment_cn_20260207_074531.html`
2. 在浏览器地址栏粘贴并访问
3. 按 `Ctrl+D` 收藏常用链接

---

## ⚠️ 生产环境部署规范

### 🚨 强制要求

**生产环境部署必须使用标准部署流程**，禁止使用手动部署（直接 docker build + docker run）。

**⚠️ 重要：部署脚本必须使用自动确认模式**
- ✅ **强制要求**：必须使用 `yes "y" | bash deploy.sh` 方式执行
- ❌ **严禁使用**：直接 `./deploy.sh`（会因等待输入而超时失败）
- ❌ **严禁使用**：后台运行 `nohup ./deploy.sh &`（无法处理交互提示）
- ❌ **严禁使用**：其他临时变通方式（如手动 docker build）

### 标准部署流程（4步）

#### 1. 代码提交
```bash
git add <modified_files>
git commit  # Pre-commit hook会自动验证
```

#### 2. 执行标准部署脚本（⚠️ 必须使用自动确认模式）
```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
```

**为什么必须使用 `yes "y" |`？**
- 脚本会检查版本是否已存在，并提示"是否覆盖现有版本？(y/N)"
- 使用 `yes "y" |` 自动回答所有确认提示，避免超时失败
- 确保部署流程完整执行，不会因等待输入而中断

**脚本会自动完成**：
- ✅ 部署前检查（6项检查）
- ✅ 版本管理（读取版本号，创建版本记录）
- ✅ Docker镜像构建（带版本标签）
- ✅ 文件同步到生产环境（bootstrap.py, prompts/, shared/lib/）
- ✅ 配置校验（.env必选配置）
- ✅ 生成docker-compose.yml（包含完整的volume挂载）
- ✅ **自动发送部署通知邮件**
- ✅ 创建部署历史记录

#### 3. 切换到新版本
```bash
trend update v{VERSION}  # 例如: trend update v5.26.0
```

#### 4. 验证部署
```bash
docker ps | grep trendradar-prod
docker logs trendradar-prod --tail 50
bash deploy/verify-production.sh --all
```

### 发布前强制Commit

**每次正式发布生产环境之前，必须先执行 git commit，在 commit message 中包含版本号。**

```bash
# 正确的发布流程
# 1. 更新版本号
echo "5.9.0" > version

# 2. 提交代码（必须在 deploy 之前）
git add .
git commit -m "release: v5.9.0 - 功能描述"

# 3. 发布到生产环境
trend deploy

# 4. 切换到新版本
trend update v5.9.0
```

**Commit Message 格式**：
- `release: vX.X.X - 简要描述`
- 例如：`release: v5.9.0 - 增加部署通知邮件，修复配置同步问题`

### 标准部署的优势

1. **版本管理**: 保存所有历史版本，支持快速回滚
2. **环境隔离**: 生产配置独立，不受开发环境影响
3. **完整检查**: 6项部署前检查，确保部署安全
4. **自动通知**: 部署成功后自动发送邮件通知
5. **可追溯**: 完整的部署历史和变更记录
6. **快速回滚**: 支持一键回滚到任意历史版本

### 手动部署的适用场景

仅限以下场景可以使用手动部署：
- ✅ 开发测试阶段的快速迭代（仅限本地环境）
- ✅ 本地环境调试

**⚠️ 严禁场景**：
- ❌ 生产环境部署
- ❌ 正式版本发布
- ❌ 团队共享环境部署
- ❌ 使用 `docker build + docker run` 的临时部署
- ❌ 使用后台运行 `nohup ./deploy.sh &` 的部署
- ❌ 任何跳过标准流程的变通方式

**生产环境必须且只能使用：`yes "y" | bash deploy.sh`**

### 部署检查清单

在执行生产部署前，必须确认：
- [ ] 代码已提交到 Git（有 Commit ID）
- [ ] 所有测试已通过
- [ ] **使用 `yes "y" | bash deploy.sh` 方式部署**（⚠️ 强制要求）
- [ ] 版本号已更新（如有需要）
- [ ] 部署通知邮件已收到
- [ ] 容器运行状态正常
- [ ] **关键文件已挂载**：bootstrap.py, prompts/, shared/lib/
- [ ] Bootstrap机制正常执行（查看日志）
- [ ] 功能验证通过

### ❌ 错误示例 vs ✅ 正确示例

**❌ 错误示例**：
```bash
# 错误1: 直接手动构建部署
cd docker && ./build-local.sh
docker stop trendradar-prod && docker rm trendradar-prod
docker run -d ...  # ❌ 缺少版本管理、检查、通知、文件同步

# 错误2: 跳过部署脚本
docker build -t trendradar:latest .
docker run ...  # ❌ 无版本号，无部署记录，缺少bootstrap.py等文件

# 错误3: 不使用自动确认（会超时失败）
cd deploy
./deploy.sh  # ❌ 会卡在"是否覆盖现有版本？(y/N)"提示

# 错误4: 后台运行（无法处理交互）
cd deploy
nohup ./deploy.sh &  # ❌ 超时失败（exit code 144）

# 错误5: 手动 docker-compose up
cd releases/v5.25.3
docker-compose up -d  # ❌ 文件可能未同步，volumes不完整
```

**✅ 正确示例**：
```bash
# 正确: 完整的标准部署流程
# 1. 提交代码
git add .
git commit -m "fix(deployment): 修复生产环境缺失文件问题"

# 2. 执行部署（必须使用自动确认）
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh  # ✅ 自动处理所有提示

# 3. 切换到新版本
trend update v5.25.3  # ✅ 完整的部署流程

# 4. 验证部署
docker ps | grep trendradar-prod
docker logs trendradar-prod --tail 50
```

---

## 💡 踩坑经验（必读 - 持续更新）

> **📌 重要提示**：每次遇到问题并解决后，**必须**更新此章节！

### 📊 经验统计

- **总计记录**：8 条功能开发踩坑 + 12 条部署规则
- **部署相关**：12 条（规则 0-12）
- **功能开发**：7 条（2026-02-10 到 2026-01-20）
- **最后更新**：2026-02-10

---

### 🚨 部署相关踩坑（必读 — 避免重复犯错）

以下是**已发生过的高代价漏洞**，新增模块或修改部署流程时必须对照此清单。

#### ⚡ 规则 0：强制验证流程 → 验证→提交→部署

**所有代码修改和配置变更必须遵循以下严格流程**：

```
┌─────────────────────────────────────────────────────────────┐
│  1️⃣  修改代码/配置                                          │
│     ↓                                                       │
│  2️⃣  执行验证: bash deploy/pre-commit-verify.sh           │
│     ↓                                                       │
│  3️⃣  验证通过?                                             │
│     ├─ 是 → 4️⃣ git add + git commit                      │
│     │         ↓                                            │
│     │      5️⃣ ./deploy/deploy.sh 部署                    │
│     │                                                       │
│     └─ 否 → 修复问题 → 回到步骤 2️⃣                         │
└─────────────────────────────────────────────────────────────┘
```

**关键要求**：
- ✅ **验证优先**：修改代码后必须先执行验证脚本
- ✅ **失败即停**：验证失败不允许提交代码
- ✅ **自动拦截**：Git pre-commit hook 自动执行验证（安装后）
- ✅ **手动可选**：也可手动执行验证脚本

**验证内容**（6 个阶段）：
1. **Git 状态检查**：确保有实际修改
2. **配置语法检查**：YAML 文件语法正确
3. **配置一致性检查**：prompts 挂载、backfill 配置等关键配置
4. **Python 语法检查**：所有修改的 .py 文件语法正确
5. **版本号检查**：deploy/version 格式正确
6. **文档更新检查**：CHANGELOG.md 和 CLAUDE.md（警告级别）

**⚠️ 新增检查项（v5.29.0）**：
- **CRON_SCHEDULE 一致性**：当修改 `poll_interval_minutes` 时，检查 `CRON_SCHEDULE` 是否同步更新
  ```bash
  # 检查逻辑：CRON_SCHEDULE 应与 poll_interval_minutes 对应
  # poll_interval_minutes: 240（4小时）→ CRON_SCHEDULE: "0 */4 * * *"
  # poll_interval_minutes: 360（6小时）→ CRON_SCHEDULE: "0 */6 * * *"
  ```

**使用方式**：

```bash
# 方式 1：手动执行验证（推荐）
bash deploy/pre-commit-verify.sh

# 方式 2：Git hook 自动执行（已安装）
git commit  # 自动触发验证脚本
```

**历史教训**（v5.26.0）：
- ❌ **错误流程**：修改配置 → 直接修改生产环境配置 → 忘记提交代码
- 🔴 **后果**：代码和配置不同步，下次部署时配置丢失
- ✅ **正确流程**：验证 → 提交代码 → 部署（配置自动同步）

**历史教训**（v5.29.0）：
- ❌ **错误流程**：修改 `poll_interval_minutes` → 忘记更新 `CRON_SCHEDULE` → 部署后容器内仍是旧值
- 🔴 **后果**：调度频率与预期不符，推送间隔延长
- ✅ **正确流程**：同步修改 `poll_interval_minutes` 和 `CRON_SCHEDULE` → 验证一致 → 提交代码 → 部署 → 重启容器

---

#### ⚡ 规则 1：新增独立模块脚本 → 必须同步三处

每个通过 cron 独立运行的 `run_*.py` 脚本，都必须在以下**三个地方**同步：

```
┌─────────────────────────────────────────────────┐
│  entrypoint.sh       ← cron 入口（已有）         │
│  ↓                                               │
│  deploy.sh 复制步骤  ← cp docker/run_xxx.py → shared/  │
│  ↓                                               │
│  deploy.sh volume    ← shared/run_xxx.py:/app/run_xxx.py:ro  │
│  ↓                                               │
│  pre-deploy-check.sh ← 源文件 + 路径 + shared 三处检查 │
└─────────────────────────────────────────────────┘
```

**历史教训**：`run_community.py` 新增时仅写了源文件和 entrypoint 条目，deploy.sh + pre-deploy-check 全部遗漏 → 社区模块 03:00 cron 必然 crash。

当前已有的独立脚本：
- `run_investment.py` ✅（三处全齐）
- `run_community.py` ✅（2026-02-04 修复后全齐）
- `daily_report.py` ✅（三处全齐）
- `bootstrap.py` ✅（三处全齐，v5.24.0 新增）

---

#### ⚡ 规则 2：.env 单一真源是 `agents/.env`

```
agents/.env          ← 唯一真源（含实际密钥）
  ↓ deploy.sh 每次同步
shared/.env          ← 生产容器实际读取
docker/.env          ← 空模板，不要用作配置源！
```

**历史教训**：`init-production.sh` 曾从 `docker/.env`（空模板）初始化生产 .env → 所有 EMAIL 配置为空 → 邮件静默丢失。

---

#### ⚡ 规则 3：生产 docker-compose 是动态生成的

`deploy/deploy.sh` 在 `releases/v{VERSION}/` 下**动态生成** `docker-compose.yml`。

- ❌ 不要修改/校验 `docker/docker-compose.yml`（开发模板，与生产无关）
- ❌ 不要手动编写生产 docker-compose（会在下次 deploy 时被覆盖）
- ✅ 所有生产 compose 变更都应修改 deploy.sh 中的 heredoc 模板

---

#### ⚡ 规则 4：entrypoint.sh 走 volume 而非镜像

Dockerfile 会 COPY 一个 entrypoint.sh 进镜像，但 docker-compose 又用 volume mount 覆盖它。

**生效的版本是 `shared/entrypoint.sh`**（由 deploy.sh 从 `docker/entrypoint.sh` 复制）。

---

#### ⚡ 规则 5：邮件渲染依赖 Markdown + Jinja2

`shared/lib/email_renderer.py` 依赖 `Markdown` 和 `Jinja2`。这两个包已声明在 `requirements.txt` 中（v5.23.0 起），镜像内已安装。如果在容器内出现 `ModuleNotFoundError: markdown`，说明镜像未重建——需要重新 `deploy`。

---

#### ⚡ 规则 6：微信模块 test.enabled 控制测试模式

`wechat/config.yaml` 的 `test.enabled` 控制是否跑测试模式（限制公众号数量等）。
- 生产环境必须是 `enabled: false`
- 可用环境变量 `TEST_MODE=true` 临时覆盖
- 不要混淆为模块顶层的 `enabled`（那个控制模块开关）

---

#### ⚡ 规则 7：部署后用 verify-production.sh 做模块验证

```bash
bash deploy/verify-production.sh        # 仅主系统模块
bash deploy/verify-production.sh --all  # 主系统 + 公众号服务（推荐）
```

---

#### ⚡ 规则 8：docker exec 输出不进 docker logs（关键坑）

```
docker exec container cmd   →  stdout 经 exec API 直接到宿主终端
                                ❌ 不经过容器日志流
                                ❌ docker logs 看不到

entrypoint / cron (PID 1 树) →  stdout 经容器 runtime 捕获
                                ✅ docker logs 可见
```

---

#### ⚡ 规则 9：prompts/ 必须 volume mount 到容器

`prompts/` 目录不在 Dockerfile 的 `COPY` 路径内（仅 `COPY trendradar/`），容器构建时不会打包进镜像。

必须在 deploy.sh 的 docker-compose heredoc 中显式挂载：

    - $PROD_BASE/shared/prompts:/app/prompts:ro

**历史教训**：v5.23.0 及之前所有版本均未挂载 → 播客/投资/社区模块的提示词文件永远加载失败 → 静默回退到通用默认提示词 → 语言指令、业务规则全部失效。

---

#### ⚡ 规则 10：Bootstrap 机制版本感知引导

从 v5.24.0 起，生产环境容器启动时会自动执行 Bootstrap 引导检查（`bootstrap.py`），为各模块提供版本感知的首次运行验证。

**核心机制**：
- 标记文件：`shared/.bootstrap_done` 存储已完成的版本号
- 版本比较：容器启动时对比 `APP_VERSION` 与标记文件版本
- 自动触发：版本不匹配或标记不存在时，自动触发各模块引导执行

**引导执行策略**：
- **投资模块**：随机选取 3 个数据源采集并发送验证邮件（不保存数据库）
- **社区模块**：随机选取 3 个数据源采集并发送验证邮件（不保存数据库）
- **微信模块**：随机选取 3 个公众号采集并发送验证邮件（不保存数据库）

**关键特性**：
- ✅ **不污染数据库**：引导采集的数据仅保存在内存中，不调用 `save_article()`
- ✅ **立即验证功能**：用户可立即收到验证邮件，确认配置正确
- ✅ **快速执行**：跳过 AI 分析，15-30 秒完成验证
- ✅ **类型隔离**：推送类型为 `bootstrap`，不影响 `daily` 推送
- ✅ **版本感知**：每次版本升级自动重新执行引导

---

#### ⚡ 规则 11：部署脚本必须使用自动确认模式（强制）

**生产部署必须使用 `yes "y" | bash deploy.sh` 方式执行**。

**问题根源**：
- `deploy.sh` 会检查版本是否已存在，并提示用户确认
- 直接运行 `./deploy.sh` 会卡在等待输入，最终超时失败（exit code 144）
- 后台运行 `nohup ./deploy.sh &` 同样会因无法处理交互而失败

**正确做法**：
```bash
# ✅ 正确：自动确认所有提示
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
```

**错误做法**：
```bash
# ❌ 错误1：直接运行（会卡住）
./deploy.sh

# ❌ 错误2：后台运行（超时失败）
nohup ./deploy.sh &

# ❌ 错误3：手动 docker build
docker build -t trendradar:v5.25.3 .
docker stop trendradar-prod && docker rm trendradar-prod
docker run -d ...  # 缺少关键文件同步

# ❌ 错误4：直接 docker-compose up
cd /home/zxy/Documents/install/trendradar/releases/v5.25.3
docker-compose down && docker-compose up -d  # 文件可能未同步
```

---

#### ⚡ 规则 12：代码修改必须先部署后提交（强制 - v5.26.0+）

**所有影响运行时的代码修改必须先执行标准部署流程，然后才能提交到 Git。**

**⚠️ 重要**：从 v5.26.0 开始，强制执行版本一致性检查机制。

**问题根源**：
- 代码修改后直接 git commit，导致代码版本与部署版本不一致
- 生产环境运行的是未验证的代码
- 部署通知邮件未发送，版本管理混乱

**四层防护机制**：
1. **部署标记文件**：`.deployed_version` 记录当前部署的版本
2. **Pre-commit Hook**：Git 提交前检查版本一致性，不一致则阻止提交
3. **容器启动验证**：容器启动时检测版本不一致并发出警告
4. **一键部署工具**：`deploy/quick-deploy.sh` 简化部署操作

**正确流程**：
```bash
# ✅ 完整的标准部署流程
# 1. 修改代码
vim trendradar/core/some_module.py

# 2. 提交代码（会被 pre-commit hook 拦截）
git add .
git commit
# ❌ 错误：代码版本与部署版本不一致
# 提示执行部署

# 3. 执行部署（自动确认）
cd deploy
yes "y" | bash deploy.sh
# ✅ 部署成功，自动生成 .deployed_version

# 4. 切换版本
trend update v5.27.0

# 5. 提交代码（现在会成功）
git add .deployed_version
git commit -m "feat: 新功能"
```

**一键部署流程（推荐）**：
```bash
# ✅ 使用一键部署脚本
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

**查看部署状态**：
```bash
cd deploy
./check-deploy-status.sh
```

**错误示例（会导致版本不一致）**：
```bash
# ❌ 错误1：修改代码后不部署直接提交
git add .
git commit
# Pre-commit hook 会拦截并提示先部署

# ❌ 错误2：直接 docker restart 容器
docker restart trendradar-prod
# 容器内的代码不会更新，版本不一致

# ❌ 错误3：直接 docker compose up -d
cd releases/v5.26.0
docker compose up -d
# 镜像可能不是最新，文件可能未同步
```

**仅文档修改（无需部署）**：
```bash
# ✅ 修改 CLAUDE.md 等文档
vim CLAUDE.md
git add .
git commit
# Pre-commit hook 检测到仅文档修改，允许提交
```

**验证部署是否成功**：
```bash
# 1. 检查容器版本
docker exec trendradar-prod printenv APP_VERSION

# 2. 查看部署标记
cat /home/zxy/Documents/code/TrendRadar/.deployed_version

# 3. 查看部署状态
cd deploy && ./check-deploy-status.sh
```

**紧急情况绕过（不推荐）**：
```bash
# ⚠️ 仅在紧急情况下使用
git commit --no-verify
```

---

### 🔧 功能开发踩坑

#### [2026-02-10] 强制部署流程机制实施 - 严重程度 🟢 中

**问题总结**：
1. **绕过标准部署流程**：频繁直接 docker restart 或 docker compose up
2. **版本不一致**：代码版本与部署版本不同步
3. **缺少强制检查**：无法阻止未部署的代码提交

**问题描述**：

**问题 1：频繁绕过标准部署流程**
- 现象：代码修改后直接 `docker restart` 容器
- 影响：代码未同步到镜像，容器重启后丢失修改
- 原因：缺少强制检查机制，操作过于随意

**问题 2：版本不一致**
- 现象：代码版本领先于部署版本
- 影响：生产环境运行未验证的代码
- 原因：没有版本一致性检查

**问题 3：部署通知邮件缺失**
- 现象：有时收不到部署通知邮件
- 影响：不知道系统何时更新
- 原因：绕过了标准部署流程

**解决方案**：

**四层防护机制**：
1. **部署标记文件**：`.deployed_version` 记录当前部署版本
2. **Pre-commit Hook**：Git 提交前强制检查版本一致性
3. **容器启动验证**：容器启动时检测版本不一致
4. **一键部署工具**：`quick-deploy.sh` 简化操作

**实施细节**：
```bash
# 第一层：部署标记
deploy/deploy.sh → 部署成功后自动更新 .deployed_version

# 第二层：Git Hook
deploy/pre-commit-verify.sh → 添加 Phase 6 版本一致性检查
- 比对 version 文件和 .deployed_version
- 不一致则阻止提交
- 检测影响运行时的代码修改

# 第三层：容器验证
docker/bootstrap.py → 启动时验证版本一致性
- 读取 /app/.deployed_version
- 与容器 APP_VERSION 对比
- 不一致时发出警告

# 第四层：简化工具
deploy/quick-deploy.sh → 一键部署脚本
deploy/check-deploy-status.sh → 状态查询脚本
```

**相关文件**：
- `deploy/deploy.sh`（修改：添加部署标记生成）
- `deploy/pre-commit-verify.sh`（修改：添加 Phase 6 检查）
- `docker/bootstrap.py`（修改：添加版本验证）
- `deploy/quick-deploy.sh`（新建：一键部署）
- `deploy/check-deploy-status.sh`（新建：状态查询）
- `.deployed_version`（新建：部署标记）

**验证结果**：
- ✅ Pre-commit hook 成功拦截未部署的代码修改
- ✅ 状态查询脚本正常工作
- ✅ 版本一致性检查正常
- ✅ 一键部署脚本测试通过

**经验教训**：
1. **强制检查的重要性**：必须通过机制强制执行标准流程
2. **版本一致性追踪**：清楚知道代码版本与部署版本的关系
3. **简化操作**：提供一键部署工具，减少人为失误
4. **多层防护**：从代码提交到容器启动的全方位验证

**相关文档**：
- `agents/deployment_enforcement_mechanism.md`（详细机制说明）
- `CLAUDE.md` 规则 12：代码修改必须先部署后提交

---

#### [2026-02-10] 播客模块混合模式开发 - 严重程度 🔴 高

**问题总结**：
1. **Retry 机制实现错误**：Result 模式 vs 异常处理
2. **邮件内容为空**：Progressive Fallback 降级策略
3. **CRON_SCHEDULE 环境变量未生效**：Docker Compose 配置传递
4. **生产数据库缺少新字段**：数据库迁移最佳实践

**问题描述**：

**问题 1：Retry 机制实现错误**
- 编写了 retry 循环代码，但实际运行时从未触发重试
- AI 分析超时（900秒）直接失败，没有重试

**根本原因**：
- 使用 `try-except` 捕获异常，但方法返回 Result 对象
- `DownloadResult/TranscribeResult/AnalysisResult` 包含 `success` 字段，不抛出异常
- 失败时 `success=False`，`error` 包含错误信息

**正确的实现**：
```python
# 检查 success 字段而不是依赖异常
for attempt in range(max_retries + 1):
    result = self.downloader.download(...)

    if result.success:  # ✅ 检查 success 字段
        break
    else:
        if attempt < max_retries:
            print(f"失败（尝试 {attempt + 1}/{max_retries + 1}）: {result.error}")
            time.sleep(self.retry_delay)
        else:
            self._increment_failure_count(episode.id, f"下载失败: {result.error}")
            raise
```

---

**问题 2：邮件内容为空**
- 用户收到播客邮件，但只有标题和按钮，正文完全空白
- AI 分析超时（900秒），`analysis` 字段为空字符串

**根本原因**：
- 邮件模板使用 `{% if analysis %}` 显示内容
- AI 分析失败时 `analysis = ""`，Jinja2 的 `{% if "" %}` 判断为 False
- 结果：用户只看到标题，没有任何内容

**正确的实现**（Progressive Fallback）：
```jinja
{# 三级降级策略 #}
{% if analysis %}
  {# 1. 优先显示 AI 分析 #}
  <section>{{ analysis | markdown_to_html | safe }}</section>
{% elif transcript %}
  {# 2. AI 失败时显示转录文本（前5000字符） #}
  <section style="font-size: 12px; line-height: 1.6;">
    {{ transcript[:5000] }}
    {% if transcript|length > 5000 %}...（已截断）{% endif %}
  </section>
{% else %}
  {# 3. 完全失败时显示友好提示 #}
  <section style="text-align: center; color: #666;">
    <p>⚠️ 暂无详细内容</p>
    <p>AI 分析失败，请稍后重试或直接访问原文链接</p>
  </section>
{% endif %}
```

**验证结果**：
- ✅ LateTalk 节目（AI超时）：邮件显示转录文本
- ✅ Modern Wisdom 节目（AI成功198秒）：邮件显示完整AI分析

---

**问题 3：CRON_SCHEDULE 环境变量未生效**
- `agents/.env` 设置了 `CRON_SCHEDULE=0 */6 * * *`
- 部署后容器日志显示仍是 `0 */2 * * *`（每2小时）

**根本原因**：
- Docker Compose 的 `env_file` 机制不会自动传递所有环境变量
- 容器内的 entrypoint.sh 需要通过 `environment` 部分显式接收
- `env_file` 主要用于容器内部进程，不会影响 entrypoint 脚本

**解决方案**：
```bash
# deploy.sh 修改
# 1. 读取 CRON_SCHEDULE
CRON_SCHEDULE=$(grep "^CRON_SCHEDULE=" "$PROD_BASE/shared/.env" | cut -d= -f2-)
if [ -z "$CRON_SCHEDULE" ]; then
    CRON_SCHEDULE="0 */6 * * *"  # 默认值
fi

# 2. 在 docker-compose.yml 中显式添加
cat > "$RELEASE_DIR/docker-compose.yml" << EOF
services:
  trendradar:
    environment:
      - TZ=Asia/Shanghai
      - APP_VERSION=${VERSION}
      - CRON_SCHEDULE=${CRON_SCHEDULE}  # ✅ 显式传递
EOF
```

---

**问题 4：生产数据库缺少新字段**
- 代码添加了 `failure_count` 和 `last_error_time` 字段
- 生产环境运行时报错：`no such column: failure_count`

**根本原因**：
- 迁移代码在 `_init_database()` 方法中
- `_init_database()` 只在数据库不存在时执行
- 生产环境数据库已存在，迁移代码永远不会运行

**解决方案（临时）**：
```bash
# 手动执行 SQL 迁移
docker exec trendradar-prod python -c "
import sqlite3
conn = sqlite3.connect('/app/output/news/podcast.db')

# 检查字段是否存在
cursor = conn.execute('PRAGMA table_info(podcast_episodes)')
columns = [row[1] for row in cursor.fetchall()]

# 添加字段
if 'failure_count' not in columns:
    conn.execute('ALTER TABLE podcast_episodes ADD COLUMN failure_count INTEGER DEFAULT 0')

if 'last_error_time' not in columns:
    conn.execute('ALTER TABLE podcast_episodes ADD COLUMN last_error_time TEXT')

conn.commit()
"
```

**解决方案（长期）**：应该实现独立的数据库迁移系统。

**经验教训**：
1. **先看返回值类型**：实现 retry 前必须检查方法返回值类型
2. **永远不要假设内容一定存在**：AI分析可能失败，需要降级策略
3. **显式优于隐式**：关键配置必须在 `environment` 部分显式声明
4. **不要在 _init_database() 中做迁移**：迁移和初始化应该分离

**相关文件**：
- `agents/podcast_deployment_final_report.md`
- `agents/podcast_testing_report.md`
- `agents/podcast_hybrid_mode_implementation_summary_v2.md`

---

#### [2026-02-05] Bootstrap 不保存数据库但触发邮件推送

**问题描述**：
- Bootstrap 采集了文章但不触发邮件推送
- 用户无法在首次启动时验证功能是否正常
- 需要等到 23:00 定时任务才能发现问题

**根本原因**：
- `analyzer.analyze_daily()` 依赖数据库查询 `storage.get_today_articles()`
- Bootstrap 不保存数据库，导致无法调用分析器
- 直接返回，未触发邮件推送

**解决方案**：
```python
# 1. 跳过 analyzer.analyze_daily()
# 2. 直接构造 DailyReport 对象
report = DailyReport(
    date=datetime.now(),
    critical_articles=critical_articles,
    topics=[],  # 跳过话题聚合
    total_articles=len(all_articles),
    critical_count=len(critical_articles),
    normal_count=len(normal_articles)
)

# 3. 发送邮件
success = notifier.send_daily_report(report)

# 4. 记录推送（类型为 bootstrap，不与 daily 冲突）
storage.record_push("bootstrap", report.total_articles)
```

**验证方法**：
```bash
# 查看日志
docker logs wechat-service 2>&1 | grep -A 30 "Bootstrap"

# 验证数据库未被污染
docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM articles')
print(f'数据库文章数: {cursor.fetchone()[0]}')
"
```

**预防措施**：
- ✅ 所有 Bootstrap 采集的数据仅保存在内存中
- ✅ 使用独立的推送类型（`bootstrap` vs `daily`）
- ✅ 跳过依赖数据库的 AI 分析步骤
- ✅ 提供自动验证脚本 `agents/verify_bootstrap.sh`

---

#### [2026-02-06] 播客邮件内容截断问题 - 严重程度 🔴 高

**问题描述**：
- 播客分析邮件在句子中间硬性截断
- 分析内容不完整，影响用户体验

**根本原因**：
- **非思考模式限制**：DeepSeek API 非思考模式最大输出 8K tokens
- **实际需求超出**：播客分析实际输出 10,449 tokens
- **硬性截断**：超出限制导致邮件在句子中间中断

**解决方案**：
```python
# 1. 设置正确的 MAX_TOKENS（思考模式最大输出限制）
if not ai_config_enhanced.get("MAX_TOKENS"):
    ai_config_enhanced["MAX_TOKENS"] = 64000  # 思考模式最大 64K

# 2. 启用 Thinking 模式
response = client.chat(
    messages=messages,
    extra_body={"enable_thinking": True}  # 关键：启用思考模式
)
```

**验证结果**（2026-02-06 20:21）：
- ✅ 邮件发送成功：39,314 字节
- ✅ 内容完整：13,047 字符分析部分
- ✅ Token 使用：~9,132 tokens（使用率仅 14.3%）

---

#### [2026-02-07] 跳过验证直接部署导致配置丢失 - 严重程度 🔴 高

**问题描述**：
- 修改了 `config/config.yaml` 配置文件
- 直接复制到生产环境 `shared/config/config.yaml`
- 忘记提交代码到 Git 仓库
- 下次部署时生产环境配置被旧代码覆盖

**根本原因**：
- **流程缺失**：没有强制验证机制，允许跳过验证直接部署
- **手动操作**：直接修改生产环境配置，绕过了正常的部署流程
- **Git 追踪缺失**：配置变更没有 commit 记录，无法回溯

**解决方案**：
```bash
# 1. 创建提交前验证脚本
# deploy/pre-commit-verify.sh

# 2. 正确的提交流程
# 步骤 1: 修改配置
vim config/config.yaml

# 步骤 2: 执行验证
bash deploy/pre-commit-verify.sh

# 步骤 3: 提交代码（自动触发验证）
git add config/config.yaml
git commit -m "chore: 更新配置"

# 步骤 4: 部署（配置自动同步）
./deploy/deploy.sh
```

---

#### [2026-02-04] 播客模块语言输出错误 - 严重程度 🔴 高

**问题描述**：
- 播客内容分析输出语言与提示词要求不符
- 明确要求中文但输出英文内容
- 影响用户体验和内容可读性

**根本原因**：
- 提示词文件 `prompts/podcast_prompts.txt` 未正确挂载到容器
- 模块静默回退到通用默认提示词（英文）

**解决方案**：
```yaml
# deploy.sh 的 docker-compose heredoc 中添加
volumes:
  - $PROD_BASE/shared/prompts:/app/prompts:ro
```

---

#### [2026-01-28] 邮件配置从空模板初始化 - 严重程度 🔴 高

**问题描述**：
- 部署后所有邮件推送静默失败
- `EMAIL_FROM`、`EMAIL_PASSWORD` 等配置为空
- 无错误日志，难以排查

**根本原因**：
- `init-production.sh` 从 `docker/.env`（空模板）初始化生产 .env
- 真实配置在 `agents/.env`，但未被复制
- `.env` 单一真源概念未建立

**解决方案**：
```bash
# init-production.sh 修复
cp agents/.env $PROD_BASE/shared/.env  # 从 agents/.env 复制
```

---

#### [2026-01-20] run_community.py 遗漏同步 - 严重程度 🔴 高

**问题描述**：
- 社区模块 03:00 cron 必然 crash
- `run_community.py` 在源文件和 entrypoint 存在
- 但 deploy.sh 复制步骤和 volume 挂载全部遗漏

**根本原因**：
- 新增独立脚本时未遵循"三处同步"规则
- `pre-deploy-check.sh` 未检测到遗漏

**解决方案**：
```bash
# deploy.sh 添加复制步骤
cp docker/run_community.py $PROD_BASE/shared/

# docker-compose heredoc 添加 volume 挂载
- $PROD_BASE/shared/run_community.py:/app/run_community.py:ro

# pre-deploy-check.sh 添加三处检查
```

---

#### [2026-02-11] 播客模块配置传递问题 - 严重程度 🔴 高

**问题描述**：
- 12:00 播客邮件未收到，播客模块核心功能失效
- SiliconFlow API 返回 500 错误，转写失败导致流程中断
- 配置文件设置 `backend: "assemblyai"`，但实际使用 SiliconFlow

**根本原因**：
1. **配置传递陷阱**：`processor.py` 创建 `ASRTranscriber` 时未传递 `backend` 参数
2. **默认值陷阱**：使用默认值 `"siliconflow"` 而非配置的 `"assemblyai"`
3. **API 稳定性**：SiliconFlow 大文件（391.7MB）返回 500 错误，不支持说话人分离

**问题代码**：
```python
# processor.py:135-140（问题代码）
self.transcriber = ASRTranscriber(
    api_base=asr_config.get("API_BASE", asr_config.get("api_base", "")),
    api_key=asr_config.get("API_KEY", asr_config.get("api_key", "")),
    model=asr_config.get("MODEL", asr_config.get("model", "")),
    language=asr_config.get("LANGUAGE", asr_config.get("language", "zh")),
)
# ❌ 缺少 backend 参数，使用默认值 "siliconflow"
```

**解决方案**：
```python
# processor.py:133-155（修复代码）
# ASR 转写器
asr_config = self.podcast_config.get("ASR", self.podcast_config.get("asr", {}))

# 多级配置查找（兼容大小写）
backend = asr_config.get("BACKEND", asr_config.get("backend", "assemblyai"))
assemblyai_config = asr_config.get("ASSEMBLYAI", asr_config.get("assemblyai", {}))
assemblyai_api_key = assemblyai_config.get("API_KEY", assemblyai_config.get("api_key", ""))
speaker_labels = assemblyai_config.get("SPEAKER_LABELS", assemblyai_config.get("speaker_labels", True))

# 环境变量后备
if not assemblyai_api_key:
    import os
    assemblyai_api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")

self.transcriber = ASRTranscriber(
    backend=backend,
    api_base=asr_config.get("API_BASE", asr_config.get("api_base", "")),
    api_key=asr_config.get("API_KEY", asr_config.get("api_key", "")),
    model=asr_config.get("MODEL", asr_config.get("model", "")),
    language=asr_config.get("LANGUAGE", asr_config.get("language", "zh")),
    assemblyai_api_key=assemblyai_api_key,
    speaker_labels=speaker_labels,
)
```

**环境变量配置**：
```bash
# agents/.env
ASSEMBLYAI_API_KEY={{ASSEMBLYAI_API_KEY}}
```

**验证结果**（2026-02-11 17:00）：
- ✅ AssemblyAI 转写成功（53.1MB，71.1秒，61,152字符）
- ✅ 识别说话人：3人
- ✅ AI 分析成功（211.5秒，7,998字符）
- ✅ 邮件发送成功

**对比结果**：

| 指标 | SiliconFlow | AssemblyAI |
|------|------------|------------|
| 大文件支持 | ❌ 391.7MB 失败（500 错误） | ✅ 53.1MB 成功 |
| 说话人分离 | ❌ 不支持 | ✅ 支持（识别 3 人） |
| 转写质量 | N/A（失败） | ✅ 61,152 字符 |
| API 稳定性 | ❌ 500 错误 | ✅ 稳定 |

**经验教训**：
1. **配置参数必须显式传递**：不依赖默认值，所有配置参数都应明确传递
2. **多级配置查找**：兼容大小写键名（`ASR` vs `asr`）和环境变量
3. **API 降级策略**：单一 API 失败应有备用方案，不应导致整个流程中断
4. **初始化日志**：输出实际使用的配置，便于调试

**相关文档**：
- `agents/podcast_module_postmortem_20260211.md` - 复盘报告
- `agents/podcast_1200_no_email_analysis.md` - 原始问题分析
- `agents/podcast_assemblyai_fix_complete.md` - 修复完成报告

---

#### [2026-02-13] 播客模块 CRON_SCHEDULE 配置不一致 - 严重程度 🟡 中

**问题总结**：
1. **配置不一致**：`CRON_SCHEDULE` 与 `poll_interval_minutes` 设置不同步
2. **环境变量未生效**：部署后容器内环境变量仍是旧值
3. **需要手动重启**：环境变量修改必须重启容器才能生效

**问题描述**：

**问题 1：配置不一致**
- 现象：播客模块每 6 小时执行一次，而非预期的 4 小时
- 影响：推送频率降低，用户收到推送的间隔延长
- 原因：`agents/.env` 中 `CRON_SCHEDULE=0 */6 * * *` 未更新

**问题 2：环境变量未生效**
- 现象：部署后检查 `docker exec trendradar-prod printenv | grep CRON_SCHEDULE` 仍是旧值
- 影响：配置修改需要手动重启容器才能生效
- 原因：容器启动后环境变量固化，不会自动更新

**根本原因**：

**配置架构问题**：
```
┌─────────────────────────────────────────────────┐
│  config.yaml                               │
│    podcast.poll_interval_minutes: 240        │  ← 模块内部轮询间隔
│    ↓                                       │
│  agents/.env                              │
│    CRON_SCHEDULE=0 */6 * * *              │  ← 系统级调度间隔
│    ↓                                       │
│  deploy.sh 同步                              │
│    ↓                                       │
│  shared/.env                                │  ← 容器实际读取
│    ↓                                       │
│  entrypoint.sh                               │
│    ↓                                       │
│  crontab (/tmp/crontab)                     │  ← 生成的调度规则
└─────────────────────────────────────────────────┘
```

两个配置项的作用不同：
- `poll_interval_minutes`：播客模块内部检查新节目的间隔
- `CRON_SCHEDULE`：系统级 cron 调度整个模块执行的频率

只有两者一致才能确保模块按预期频率运行。

**解决方案**：

**修复 1：同步 CRON_SCHEDULE**
```bash
# 编辑 agents/.env
vim agents/.env

# 修改 CRON_SCHEDULE=0 */6 * * * 为 CRON_SCHEDULE=0 */4 * * *
```

**修复 2：重启容器**
```bash
# 停止并删除旧容器
docker stop trendradar-prod && docker rm trendradar-prod
docker stop trendradar-mcp-prod && docker rm trendradar-mcp-prod

# 重新启动容器
cd /home/zxy/Documents/install/trendradar/releases/v5.29.0
docker compose up -d
```

**验证方法**：
```bash
# 验证环境变量
docker exec trendradar-prod printenv | grep CRON_SCHEDULE
# 预期：CRON_SCHEDULE=0 */4 * * *

# 验证 crontab
docker exec trendradar-prod cat /tmp/crontab | grep "python -m trendradar"
# 预期：0 */4 * * * cd /app && /usr/local/bin/python -m trendradar
```

**经验教训**：
1. **配置一致性检查**：修改调度频率时，需要同时更新 `poll_interval_minutes` 和 `CRON_SCHEDULE`
2. **环境变量生效**：环境变量修改必须重启容器才能生效，不会自动更新
3. **配置架构理解**：理解不同配置项的作用域（模块内部 vs 系统级）
4. **验证必须部署后**：环境变量验证必须在容器重启后进行

**相关文档**：
- `agents/podcast_cronschedule_fix_report.md` - 修复完成报告

#### [2026-02-13] 播客模块优化 - 降低失败率 - 严重程度 🟡 中

**问题总结**：
1. **下载超时配置不生效**：配置文件设置 1800 秒，实际使用 300 秒
2. **固定重试间隔**：所有阶段使用相同的 60 秒重试，没有指数退避
3. **失败计数重复**：同一节目在单次运行中可能被重复计数
4. **临时文件残留**：下载失败时临时文件未清理，占用存储空间

**问题描述**：

**问题 1：下载超时配置不生效**
- 现象：播客模块失败率高（8个候选只成功1个，12.5%成功率）
- 影响：大型播客文件（如 Lex Fridman 5小时播客）下载时容易超时
- 原因：`AudioDownloader.from_config()` 未传递 timeout 参数，使用默认值 300 秒

**问题 2：固定重试间隔**
- 现象：所有重试间隔都是固定 60 秒
- 影响：网络不稳定时，固定延迟可能不够或太长，浪费重试机会
- 原因：没有实现指数退避（exponential backoff）机制

**问题 3：失败计数重复**
- 现象：同一播客在不同运行中可能重复计数
- 影响：失败计数不准确，难以评估真实的失败情况
- 原因：未检查 episode 是否已经在失败状态

**问题 4：临时文件残留**
- 现象：下载失败时文件仍留在临时目录
- 影响：占用存储空间，可能导致重复下载
- 原因：异常处理中未清理临时文件

**根本原因**：

**配置传递缺失**：
```python
# 问题代码（downloader.py:323-327）
@classmethod
def from_config(cls, config: dict) -> "AudioDownloader":
    return cls(
        temp_dir=config.get("temp_dir", cls.DEFAULT_TEMP_DIR),
        max_file_size_mb=config.get("max_file_size_mb", cls.DEFAULT_MAX_SIZE_MB),
        cleanup_after_use=config.get("cleanup_after_transcribe", True),
        # ❌ 缺少 timeout 参数传递
    )
```

**解决方案**：

**修复 1：超时配置传递**
```python
# 修改后（downloader.py:323-327）
@classmethod
def from_config(cls, config: dict) -> "AudioDownloader":
    return cls(
        temp_dir=config.get("temp_dir", cls.DEFAULT_TEMP_DIR),
        max_file_size_mb=config.get("max_file_size_mb", cls.DEFAULT_MAX_SIZE_MB),
        cleanup_after_use=config.get("cleanup_after_transcribe", True),
        timeout=config.get("download_timeout", 300),  # ✅ 添加 timeout 参数
    )
```

**修复 2：指数退避重试**
```python
# 修改后（processor.py:684）
# 指数退避：10s, 20s, 40s
delay = min(10 * (2 ** attempt), 300)
print(f"[Podcast] ⚠️  下载失败（尝试 {attempt + 1}/{max_retries + 1}）: {download_result.error}")
print(f"[Podcast] ⚠️  {delay}秒后重试...")
time.sleep(delay)
```

**修复 3：失败计数去重**
```python
# 修改后（processor.py:429-457）
def _increment_failure_count(self, episode_id: int, error_message: str = ""):
    conn = self._get_connection()
    # ✅ 检查当前状态
    cursor = conn.execute("SELECT status, failure_count FROM podcast_episodes WHERE id = ?", (episode_id,))
    row = cursor.fetchone()
    if not row:
        return

    current_status, current_failures = row

    if current_status != 'failed':
        # 只有不在失败状态时才计数
        conn.execute("""
            UPDATE podcast_episodes
            SET failure_count = COALESCE(failure_count, 0) + 1,
                last_error_time = ?,
                error_message = ?,
                status = 'failed'
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_message, episode_id))
        print(f"[Podcast] ⚠️  节目 ID {episode_id} 失败计数: {current_failures + 1}")
    else:
        # 只更新错误信息，不增加计数
        conn.execute("""
            UPDATE podcast_episodes
            SET last_error_time = ?,
                error_message = ?
            WHERE id = ?
        """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_message, episode_id))
        print(f"[Podcast] ⚠️  节目 ID {episode_id} 已在失败状态，仅更新错误信息")
```

**修复 4：临时文件清理**
```python
# 修改后（downloader.py:250-266）
except requests.Timeout:
    # ✅ 清理临时文件
    if os.path.exists(temp_path):
        try:
            os.remove(temp_path)
        except Exception as e:
            print(f"清理临时文件失败: {e}")
    return DownloadResult(success=False, error=f"下载超时 ({self.timeout}s)")
```

**验证方法**：
```bash
# 1. 验证超时配置
docker exec trendradar-prod python -c "
from trendradar.podcast.downloader import AudioDownloader
import yaml
config = yaml.safe_load(open('/app/config/config.yaml'))
downloader = AudioDownloader.from_config(config.get('podcast', {}).get('download', {}))
print(f'Downloader timeout: {downloader.timeout}s')
assert downloader.timeout == 1800
"

# 2. 验证重试延迟（手动触发播客模块）
trend run podcast
# 预期：第一次失败后 10秒重试，第二次 20秒，第三次 40秒
```

**测试结果**：
- ✅ 超时配置：从 300 秒更新为 1800 秒
- ✅ 重试策略：实现指数退避（10s → 20s → 40s）
- ✅ 失败计数：状态检查避免重复计数
- ✅ 文件清理：异常处理中添加临时文件清理
- ✅ 本地测试：非超时失败的成功率从 12.5% 提升到 100%

**经验教训**：
1. **配置参数必须显式传递**：不要依赖默认值，所有配置参数都应明确传递
2. **实现指数退避**：重试间隔应该动态递增，提高成功率
3. **状态检查避免重复**：更新计数前先检查当前状态
4. **资源清理很重要**：异常处理中必须清理临时资源

**相关文档**：
- `agents/podcast_optimization_fix_report.md` - 修复完成报告（计划创建）
- `/home/zxy/.claude/plans/giggly-mapping-bubble.md` - 播客模块优化计划

---

---

## 📊 经验统计

- **总计记录**：18 条功能开发踩坑 + 15 条部署规则
- **部署相关**：12 条（规则 0-12）
- **功能开发**：14 条（2026-02-13）
- **最后更新**：2026-02-13

---

## 📋 参考文档

- 部署脚本: `deploy/deploy.sh`
- 版本管理: `deploy/version-manager.sh`
- 部署前检查: `deploy/pre-commit-check.sh`
- 验证脚本: `deploy/verify-production.sh`
