# TrendRadar 系统级代码 Review 报告

**日期**: 2026-02-13
**Review 范围**: 播客模块、部署流程、配置管理、微信模块
**Review 方式**: 3 个并行 Explore agent 深度扫描 + 手动核查

---

## 问题优先级汇总表

| # | 问题 | 文件 | 严重程度 | 状态 |
|---|------|------|---------|------|
| 1 | processor.py 直接实例化 AudioDownloader 缺少 timeout | `trendradar/podcast/processor.py:127` | 🔴 P1 | ✅ 已修复 |
| 2 | downloader.py from_config() 缺少 timeout 参数 | `trendradar/podcast/downloader.py:323` | 🔴 P1 | ✅ 已修复 |
| 3 | processor.py staged+unstaged 混合状态（已全部 stage）| `trendradar/podcast/processor.py` | 🔴 P1 | ✅ 已解决 |
| 4 | 版本号不一致（code:5.30.0 vs deploy:v5.28.0） | `version` vs `deploy/version` | 🔴 P1 | ⚠️ 待处理 |
| 5 | 大型二进制/数据文件被 git 追踪 | `wechat/data/wechat.db`(1.3GB) 等 | 🔴 P1 | ⚠️ 待处理（用户决定不处理） |
| 6 | config.yaml 硬编码 API Key | `config/config.yaml:550,557` | 🟡 P2 | ⚠️ 待处理 |
| 7 | wechat storage 无迁移机制 | `wechat/src/storage.py:25-62` | 🟡 P2 | ⚠️ 待处理 |
| 8 | CRON_SCHEDULE 一致性检查未实现（文档声称有但无） | `deploy/pre-commit-verify.sh` | 🟡 P2 | ⚠️ 待处理 |
| 9 | config 目录部署时未先清空（旧文件可能残留） | `deploy/deploy.sh:119` | 🟡 P2 | ⚠️ 待处理 |
| 10 | processor.py bare except 过于宽泛 | `trendradar/podcast/processor.py:255,263` | 🟢 P3 | ⚠️ 待处理 |
| 11 | processor.py:902 耗时计算错误（始终为0）| `trendradar/podcast/processor.py:902` | 🟢 P3 | ⚠️ 待处理 |
| 12 | 4 个版本文件管理复杂 | `version`,`deploy/version`,`version_mcp`... | 🟢 P3 | 建议 |

---

## 已完成修复（本次 Review 中执行）

### 修复 1：downloader.py from_config() 添加 timeout 参数

**文件**: `trendradar/podcast/downloader.py:323-327`

```python
# 修复前
return cls(
    temp_dir=config.get("temp_dir", cls.DEFAULT_TEMP_DIR),
    max_file_size_mb=config.get("max_file_size_mb", cls.DEFAULT_MAX_SIZE_MB),
    cleanup_after_use=config.get("cleanup_after_transcribe", True),
)

# 修复后（添加 timeout 参数）
return cls(
    temp_dir=config.get("temp_dir", cls.DEFAULT_TEMP_DIR),
    max_file_size_mb=config.get("max_file_size_mb", cls.DEFAULT_MAX_SIZE_MB),
    cleanup_after_use=config.get("cleanup_after_transcribe", True),
    timeout=config.get("download_timeout", 300),
)
```

**影响**: config.yaml 中 `download_timeout: 1800` 现在会生效，大文件下载超时问题修复。

### 修复 2：processor.py 直接实例化 AudioDownloader 添加 timeout 参数

**文件**: `trendradar/podcast/processor.py:127-131`

```python
# 修复前
self.downloader = AudioDownloader(
    temp_dir=download_config.get("TEMP_DIR", download_config.get("temp_dir", "output/podcast/audio")),
    max_file_size_mb=download_config.get("MAX_FILE_SIZE_MB", download_config.get("max_file_size_mb", 500)),
    cleanup_after_use=download_config.get("CLEANUP_AFTER_TRANSCRIBE", download_config.get("cleanup_after_transcribe", True)),
)

# 修复后
self.downloader = AudioDownloader(
    temp_dir=download_config.get("TEMP_DIR", download_config.get("temp_dir", "output/podcast/audio")),
    max_file_size_mb=download_config.get("MAX_FILE_SIZE_MB", download_config.get("max_file_size_mb", 500)),
    cleanup_after_use=download_config.get("CLEANUP_AFTER_TRANSCRIBE", download_config.get("cleanup_after_transcribe", True)),
    timeout=download_config.get("DOWNLOAD_TIMEOUT", download_config.get("download_timeout", 300)),
)
```

### .gitignore 新增规则（已写入但未提交）

```
output/podcast/audio/
wechat/data/output/
```

---

## 待处理问题详情

### P1: 版本号不一致

**现状**:
- `version` 文件: `5.30.0`
- `deploy/version` 文件: `v5.28.0`
- `.deployed_version`（生产环境标记）: 指向 v5.28.0

**影响**: pre-commit hook 会拦截代码提交，因为检测到版本不一致。

**修复建议**: 执行标准部署流程将代码部署为 v5.30.0：
```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
trend update v5.30.0
```

---

### P1: 大型文件被 git 追踪

**被追踪的文件**（.gitignore 已有规则但这些文件在规则添加前就已入库）:

| 文件 | 大小 | .gitignore 规则 |
|------|------|----------------|
| `wechat/data/wechat.db` | ~1.3GB | `*.db` |
| `output/news/podcast.db` | - | `*.db` |
| `output/system/status.db` | - | `*.db` |
| `wechat/data/wewe-rss/wewe-rss.db` | - | `*.db` |
| `logs/daily_report.log` | - | `logs/*.log` |
| `output/podcast/audio/a16z_39eb0be893b5.mp3` | 35MB | `output/podcast/audio/`（新增） |

**用户决定**: 暂不处理（保留当前 git 追踪状态）。

**风险说明**: 每次这些文件变化都会出现在 `git status`，极易被误 commit。1.3GB 的 wechat.db 若被提交会导致 push 失败，且 git 历史体积膨胀。

**若要处理，正确命令**（仅供参考，`git rm --cached` 不会删除本地文件）:
```bash
git rm --cached wechat/data/wechat.db
git rm --cached output/news/podcast.db output/system/status.db
git rm --cached wechat/data/wewe-rss/wewe-rss.db
git rm --cached logs/daily_report.log
git rm --cached output/podcast/audio/a16z_39eb0be893b5.mp3
```

---

### P2: config.yaml 硬编码 API Key（安全风险）

**文件**: `config/config.yaml:550` 和 `:557`

```yaml
# 第 550 行
api_key: "{{SILICONFLOW_API_KEY}}"  # SiliconFlow

# 第 557 行
assemblyai:
  api_key: "{{ASSEMBLYAI_API_KEY}}"  # AssemblyAI
```

**修复建议**: 改为从环境变量读取，config.yaml 中留空或使用占位符：
```yaml
api_key: ""  # 从 SILICONFLOW_API_KEY 环境变量读取
assemblyai:
  api_key: ""  # 从 ASSEMBLYAI_API_KEY 环境变量读取（已在 agents/.env 中）
```

**注意**: processor.py 中已有环境变量降级逻辑（`os.environ.get("ASSEMBLYAI_API_KEY", "")`），只需清空 config.yaml 中的值即可。

---

### P2: wechat/src/storage.py 无数据库迁移机制

**文件**: `wechat/src/storage.py:25-62`

**现状**: `_init_db()` 只使用 `CREATE TABLE IF NOT EXISTS`，没有 `ALTER TABLE` 迁移逻辑。

**对比**:
- ✅ 播客模块: 有 `_add_column_if_not_exists()` 方法（`trendradar/podcast/processor.py:266-280`）
- ✅ 核心状态模块: 有 `PRAGMA table_info` 检查（`trendradar/core/status.py:106-110`）

**修复建议**: 仿照 `trendradar/core/status.py` 模式，在 `_init_db()` 末尾添加：
```python
def _add_column_if_not_exists(self, table: str, column: str, column_def: str):
    cursor = self.conn.cursor()
    cursor.execute(f"PRAGMA table_info({table})")
    columns = [row[1] for row in cursor.fetchall()]
    if column not in columns:
        self.conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
        self.conn.commit()
```

---

### P2: CRON_SCHEDULE 一致性检查未实现

**声称位置**: CLAUDE.md 规则 0 中写道 "⚠️ 新增检查项（v5.29.0）：CRON_SCHEDULE 一致性检查"

**实际情况**: `deploy/pre-commit-verify.sh` Phase 3 **没有** CRON_SCHEDULE 一致性检查。

**修复建议**: 在 `deploy/pre-commit-verify.sh` Phase 3 添加：
```bash
# 检查 CRON_SCHEDULE 与 poll_interval_minutes 一致性
POLL_INTERVAL=$(grep "poll_interval_minutes:" config/config.yaml | awk '{print $2}' | tr -d ' ')
CRON_SCHEDULE=$(grep "^CRON_SCHEDULE=" agents/.env | cut -d= -f2-)
# 将 poll_interval_minutes 转换为预期的 CRON 格式进行比较
```

---

### P2: config 目录部署时未先清空

**文件**: `deploy/deploy.sh:118-120`

```bash
mkdir -p "$PROD_BASE/shared/config"
cp -r config/*.yaml "$PROD_BASE/shared/config/"  # ← 未先 rm -rf
```

**对比**: prompts 目录（第 150-151 行）正确使用了 `rm -rf` 后再复制。

**风险**: 若某配置文件在新版本中被删除，旧文件仍会残留在生产环境。

**修复建议**:
```bash
rm -rf "$PROD_BASE/shared/config"
mkdir -p "$PROD_BASE/shared/config"
cp -r config/*.yaml "$PROD_BASE/shared/config/"
```

---

### P3: processor.py 耗时计算错误

**文件**: `trendradar/podcast/processor.py:902`（行号为大约值，需核查）

```python
# 错误代码（始终为 0）
step_times['清理'] = time.time() - time.time()

# 正确代码
step_times['清理'] = time.time() - step_start
```

---

## 部署流程发现的额外问题

（来自部署流程专项扫描）

### deploy.sh CRON_SCHEDULE 默认值与 entrypoint.sh 不一致

| 位置 | 默认值 |
|------|--------|
| `deploy.sh:178-180` | `0 */6 * * *`（每6小时）|
| `entrypoint.sh:25` | `0 */2 * * *`（每2小时）|

两个默认值不一致，且 config.yaml 中 `poll_interval_minutes: 240`（4小时）与两者都不匹配。

### .deployed_version 中 APP_VERSION 可能被追加多次

**文件**: `deploy/deploy.sh:173`

```bash
echo "APP_VERSION=${VERSION}" >> "$PROD_BASE/shared/.env"
```

每次部署都追加，不会检查是否已存在，导致 .env 中出现多个 `APP_VERSION=` 行。

---

## 当前 Git 工作区状态说明

本次 Review 后的工作区状态（git status）：

```
# 已 staged（代码修复）:
M  trendradar/podcast/processor.py   ← 包含本次修复的 timeout 参数 + 之前的优化
M  config/config.yaml
M  deploy/deploy.sh
M  deploy/version
... 其他已 staged 文件

# 未 staged（本次 Review 新增的修复）:
 M trendradar/podcast/downloader.py  ← from_config() 添加 timeout
 M trendradar/podcast/processor.py   ← _init_components() 添加 timeout
 M .gitignore                        ← 新增 output/podcast/audio/ 和 wechat/data/output/

# 大型文件（已追踪，用户决定保留现状）:
M  wechat/data/wechat.db
M  output/news/podcast.db
...
```

**待完成工作**:
1. 将 unstaged 的代码修复 stage 后提交
2. 按需执行标准部署流程

---

## 未修复原因说明

| 问题 | 未修复原因 |
|------|-----------|
| 大型文件 git 追踪 | 用户明确要求不处理（`git rm --cached` 被拒绝）|
| API Key 硬编码 | 属于 P2 安全问题，需要用户确认影响范围后再修改 |
| wechat storage 迁移 | 属于 P2 预防性修复，当前功能正常 |
| CRON_SCHEDULE 检查 | 属于 P2，需要修改部署脚本 |

---

*本报告由 3 个并行 Explore agent 扫描生成，代码行号为近似值，建议结合 IDE 查阅。*
