# 播客模块失败次数阈值修改报告

## 概述

将失败feed被永久性忽略的失败次数阈值从 3 次改为 20 次。

---

## 修改内容

### 文件：`trendradar/podcast/processor.py`

#### 1. 修改 `_get_unprocessed_history_episodes` 方法（第 371-397 行）

**修改位置**：第 377 行（注释）和第 392 行（SQL 查询）

**修改内容**：
```python
# 修改前
# 2. 失败次数 < 3（避免无限重试永久失败的项目）
# AND (failure_count IS NULL OR failure_count < 3)

# 修改后
# 2. 失败次数 < 20（避免无限重试永久失败的项目）
# AND (failure_count IS NULL OR failure_count < 20)
```

**影响**：历史未处理节目过滤条件，失败次数 >= 20 的节目不再出现在候选池中。

#### 2. 修改 `_increment_failure_count` 方法（第 429-457 行）

**修改位置**：第 452 行（失败次数检查）

**修改内容**：
```python
# 修改前
if row and row[0] >= 3:
    print(f"[Podcast] ⚠️  节目 ID {episode_id} 失败次数已达 {row[0]}，将永久忽略")

# 修改后
if row and row[0] >= 20:
    print(f"[Podcast] ⚠️  节目 ID {episode_id} 失败次数已达 {row[0]}，将永久忽略")
```

**影响**：当节目失败次数达到 20 次时，输出警告信息并将该节目标记为永久忽略。

---

## 行为变化

### 修改前
```
失败次数 >= 3 → 永久忽略，不再尝试
```

### 修改后
```
失败次数 >= 20 → 永久忽略，不再尝试
```

### 说明

- **3 次 → 20 次**：增加重试机会，避免因为临时网络问题或 API 限流导致播客被过早放弃
- **永久忽略**：失败次数达到阈值后，该节目不再出现在候选池中
- **实际影响**：假设每 6 小时运行一次，20 次失败相当于 5 天后永久放弃该节目（更合理的重试周期）

---

## 验证方法

### 查看数据库中的失败次数

```bash
# 查看所有播客的失败次数
sqlite3 output/news/podcast.db "
SELECT feed_id, feed_name, title, failure_count, status
FROM podcast_episodes
WHERE failure_count > 0
ORDER BY failure_count DESC
LIMIT 20
"
```

### 测试验证

```bash
# 运行播客模块
python -m trendradar.cli run podcast

# 观察日志，确认失败次数 >= 20 的节目被忽略
# 关键日志：
# - "[Podcast] ⚠️  节目 ID XXX 失败次数已达 20，将永久忽略"
```

---

## 修改日期

2026-02-12
