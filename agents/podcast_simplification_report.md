# 播客处理逻辑简化 - 改动总结

## 概述

将播客处理逻辑从复杂的状态机（pending/skipped_old/backfill等）简化为清晰的2级筛选+循环遍历机制。

**改动时间**: 2026-02-09
**影响范围**: `trendradar/podcast/processor.py`, `trendradar/core/loader.py`, `config/config.yaml`

---

## 核心逻辑变化

### 简化前（复杂）
- 状态管理：7种状态（pending/skipped_old/downloading/transcribing/analyzing/completed/failed）
- 选择逻辑：per-feed限制 + backfill机制 + deploy_time保护
- 中间状态更新：每个步骤都更新DB状态
- **问题**：153个节目卡在中间状态，逻辑复杂难以维护

### 简化后（简洁）
- 状态管理：只有2种状态（completed/failed）
- 选择逻辑：2级时间筛选 + 循环遍历feeds
  - 第一级：2天内的新播客，循环遍历feeds，每个取1个，最多3个
  - 第二级：超过2天的老播客，继续循环遍历feeds补齐，直到3个
- 只在结束时保存到DB（completed/failed）
- **优势**：逻辑清晰，每个feed公平处理，无状态堆积

---

## 文件改动详情

### 1. `trendradar/podcast/processor.py`

#### 新增方法

**`_select_episodes_to_process()`** (第~710行)
- 核心简化逻辑
- 2级时间筛选（2天内 / 超过2天）
- 循环遍历feeds，每个feed最多取1个
- 最多选择3个节目

**`_cleanup_stuck_episodes()`** (第~686行)
- 清理旧的中间状态（pending/skipped_old/downloading等）
- 简化版兼容性维护

#### 简化方法

**`run()`** (第~790行)
- 移除复杂的新节目检测循环
- 移除 per-feed限制、deploy_time保护等
- 调用 `_select_episodes_to_process()` 一次性选择要处理的节目

**`process_episode()`** (第~536行)
- 步骤从5步改为4步（移除中间状态更新）
- 只在结束时调用 `_save_episode(episode, "completed/failed")`
- 添加 `episode.error_message` 属性支持

**`_save_episode()`** (第~370行)
- 只支持 `completed` 和 `failed` 两种状态
- `completed`：设置 `notify_time`
- `failed`：保存 `error_message`
- 其他状态调用时会被忽略并打印警告

#### 保留的方法（未修改）
- `_is_new_episode()` - 判断是否已处理
- `_bootstrap_select_episode()` - Bootstrap模式选择
- `_build_transcript_with_metadata()` - 构建转写元数据
- 其他辅助方法

#### 不再使用的配置参数
- `max_new_per_feed` - 改为全局 `max_episodes_per_run`
- `backfill_enabled` - 移除backfill机制
- `backfill_idle_hours` - 移除
- `backfill_max_per_run` - 移除
- `min_publish_time` - 移除
- `_deploy_time` - 移除部署时间保护

### 2. `trendradar/core/loader.py`

**`_load_podcast_config()`** (第~619行)
- 新增配置键：
  - `MAX_EPISODES_PER_RUN`: 每次最多处理3期
  - `NEW_EPISODE_THRESHOLD_DAYS`: 新播客阈值（天）
- 移除旧的配置键：`protection`, `backfill`

### 3. `config/config.yaml`

**简化配置** (第~528行)
```yaml
podcast:
  enabled: true
  poll_interval_minutes: 120            # RSS 轮询间隔（分钟）

  # 简化后的处理参数
  max_episodes_per_run: 3              # 每次最多处理 3 期
  new_episode_threshold_days: 2        # 新播客阈值（天）

  # ASR、分析、通知、下载配置保持不变...
```

移除的配置块：
- `protection` (包含 max_new_per_feed, min_publish_time)
- `backfill` (包含 enabled, idle_hours, max_per_run)

### 4. 数据库清理SQL

**`agents/clean_podcast_intermediate_states.sql`**
- 清理中间状态：pending (62), skipped_old (91), downloading/transcribing (2)
- **保留**：completed (5), failed (11)
- 清理后状态分布：
  - completed: 5
  - failed: 166 (11 + 62 + 91 + 2)

---

## 验证结果

### 配置验证
```
✓ MAX_EPISODES_PER_RUN: 3
✓ NEW_EPISODE_THRESHOLD_DAYS: 2
✓ 旧配置键已移除: protection, backfill, max_new_per_feed
```

### 方法验证
```
✓ 方法存在: _select_episodes_to_process
✓ 方法存在: _cleanup_stuck_episodes
✓ 方法存在: _save_episode
✓ 方法存在: process_episode
✓ 方法存在: run
```

---

## 部署说明

### 1. 代码部署
已完成以下文件修改：
- `trendradar/podcast/processor.py`
- `trendradar/core/loader.py`
- `config/config.yaml`

### 2. 数据库迁移（重要！）
**在部署后立即执行SQL清理脚本**：
```bash
sqlite3 /home/zxy/Documents/code/TrendRadar/output/news/podcast.db < /home/zxy/Documents/code/TrendRadar/agents/clean_podcast_intermediate_states.sql
```

或手动执行：
```sql
UPDATE podcast_episodes
SET status = 'failed', error_message = '简化版迁移：清理旧中间状态'
WHERE status IN ('pending', 'skipped_old', 'downloading', 'transcribing', 'analyzing', 'notifying');
```

### 3. 重启服务
```bash
docker-compose down
docker-compose up -d
```

---

## 预期效果

### 处理流程
```
每2小时 cron触发:
1. 抓取所有RSS feeds
2. 第一级筛选：2天内的新播客
   - 循环遍历16个feeds
   - 每个feed取1个未处理的
   - 最多3个
3. 第二级筛选（如果第一级不够3个）：
   - 继续遍历feeds
   - 从超过2天的老播客中取1个未处理的
   - 补齐到3个
4. 处理选中的3个节目
5. 完成后记录到DB（completed/failed）
```

### 关键特性
- ✅ 每次最多处理3个节目
- ✅ 每个feed最多取1个（公平性）
- ✅ 优先处理2天内的新播客
- ✅ 只在结束时记录到DB
- ✅ 无状态堆积，逻辑清晰

---

## 向后兼容性

### 数据库兼容
- 已处理的记录（completed/failed）完全保留
- `_is_new_episode()` 仍能正确识别已处理记录
- 不会重复处理已完成的播客

### 配置兼容
- 旧配置键自动忽略
- 新配置键有合理的默认值
- ASR、分析、通知、下载等配置保持不变

---

## 风险评估

### 低风险
- 代码改动集中在processor.py内部
- 核心方法（fetcher/transcriber/analyzer/notifier）未修改
- 配置简化但向下兼容

### 需要注意
- ⚠️ 数据库清理必须保留completed/failed记录
- ⚠️ 新旧逻辑切换期可能有一次重复处理（极低概率）
- ⚠️ 2天阈值是动态的，每次运行都会重新计算

---

## 后续优化建议

1. **监控指标**：
   - 每次处理的节目数（应≤3）
   - 2天内新播客的处理比例
   - 各feed的处理公平性

2. **参数调优**：
   - `max_episodes_per_run`：可根据API成本调整（1-5）
   - `new_episode_threshold_days`：可根据需要调整（1-7天）

3. **数据清理**：
   - 定期清理completed时间过久的记录（如保留30天）
   - 避免.DB文件无限增长
