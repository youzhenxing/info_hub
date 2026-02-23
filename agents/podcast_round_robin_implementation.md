# 播客模块轮询机制实现报告

## 概述

实现了播客模块的轮询机制，当处理失败时自动尝试下一个候选 feed，直到成功推送指定数量或达到尝试上限。

---

## 修改内容

### 文件：`trendradar/podcast/processor.py`

#### 1. 新增 `_build_candidate_pool` 方法（第 916-987 行）

构建统一候选池，包含 RSS 新节目、RSS 老节目和历史未处理节目。

**功能特性**：
- 去重机制：跳过数据库已处理的节目，同一音频 URL 只保留一个候选
- 来源分类：`rss_new`（2天内）、`rss_old`（超过2天）、`history`（历史未处理）
- 优先级排序：新节目优先（`rss_new > rss_old > history`）
- 数量统计：输出各类候选数量

#### 2. 修改 `run` 方法（第 1124-1208 行）

实现边选择边处理的轮询逻辑。

**核心改动**：
- Bootstrap 模式：保持原有逻辑不变
- 正常模式：使用候选池 + 轮询处理

**轮询机制**：
```
while success_count < target_count and attempt_count < max_attempts and candidates:
    1. 取出第一个候选
    2. 处理节目
    3. 如果成功，增加成功计数
    4. 如果失败，记录失败计数，继续下一个候选
```

**参数**：
- `target_count`：`max_episodes_per_run`（目标成功数量）
- `max_attempts`：20（最大尝试次数）
- `failure_count`：失败次数达到 3 后永久忽略

---

## 行为变化

### 修改前
```
1. 选择一批节目（最多 max_episodes_per_run）
2. 逐个处理
3. 如果某个失败，不会尝试下一个候选
4. 返回处理结果
```

### 修改后
```
1. 构建候选池（RSS新节目 + RSS老节目 + 历史未处理）
2. 循环处理：
   - 取出第一个候选
   - 处理节目
   - 成功则计数，失败则继续下一个
3. 直到：
   - 成功数量达到 target_count，或
   - 尝试次数达到 max_attempts，或
   - 候选池耗尽
4. 返回处理结果
```

---

## 验证方法

### 1. 本地测试

```bash
# 测试播客模块
cd /home/zxy/Documents/code/TrendRadar
python -m trendradar.cli run podcast

# 查看日志输出，验证轮询逻辑
# 关键输出：
# - "🎯 候选池构建完成"
# - "📦 尝试 X/20"
# - "✅ 成功推送 (Y/3)"
# - "轮询结果: 尝试 X 个候选，成功 Y 个"
```

### 2. 容器测试

```bash
# 部署到生产环境
cd deploy
yes "y" | bash deploy.sh

# 切换版本
trend update v5.29.0

# 查看容器日志
docker logs trendradar-prod -f | grep -E "Podcast|候选|尝试|轮询"
```

---

## 验证场景

| 场景 | 预期行为 |
|------|---------|
| 第1个节目失败 | 继续尝试第2个候选 |
| 前3个都失败 | 继续尝试第4个候选 |
| 成功推送1个 | 继续尝试直到达到 max_episodes_per_run |
| 尝试20个候选未成功 | 停止轮询，返回部分结果 |
| 候选池耗尽 | 停止轮询，返回已处理结果 |

---

## 关键日志示例

```
[Podcast] 🎯 候选池构建完成: 50 个候选
[Podcast]    - RSS新节目: 2
[Podcast]    - RSS老节目: 10
[Podcast]    - 历史未处理: 38
[Podcast] 🎯 目标: 成功推送 1 个节目
[Podcast] 🎯 限制: 最多尝试 20 个候选

[Podcast] 📦 尝试 1/20: [LateTalk] 访谈...
[Podcast]    来源: rss_new
...
[Podcast] ❌ 处理失败: 下载失败: Network unreachable

[Podcast] 📦 尝试 2/20: [Modern Wisdom] ...
[Podcast]    来源: history
...
[Podcast] ✅ 成功推送 (1/1)

[Podcast] ═══════════════════════════════════════
[Podcast] 轮询结果: 尝试 2 个候选，成功 1 个
[Podcast] ═══════════════════════════════════════
```

---

## 回滚方案

如果修改导致问题，可以通过以下方式回滚：

```bash
# 恢复备份文件
cp trendradar/podcast/processor.py.backup trendradar/podcast/processor.py

# 重新部署
cd deploy
yes "y" | bash deploy.sh
trend update v5.29.0
```

---

## 修改文件列表

- `trendradar/podcast/processor.py` - 主要修改文件
- `trendradar/podcast/processor.py.backup` - 原始备份文件

---

## 修改日期

2026-02-12
