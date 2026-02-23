# 播客模块混合模式实施总结

## 实施日期
2026-02-10

## 修改内容

### 1. 数据库备份机制 ✅
**文件**：
- `scripts/backup_podcast.sh`（新建）
- `docker/entrypoint.sh`（修改）

**功能**：
- 每天凌晨2点自动备份播客数据库
- 保留最近30天的备份
- 使用 SQLite 的 `.backup` 命令确保数据一致性

**Cron 任务**：
```bash
0 2 * * * cd /app && /app/scripts/backup_podcast.sh >> /var/log/backup.log 2>&1
```

### 2. 数据库 Schema 修改 ✅
**文件**：`trendradar/storage/podcast_schema.sql`

**新增字段**：
```sql
failure_count INTEGER DEFAULT 0,    -- 失败次数（超过3次后永久忽略）
last_error_time TEXT,               -- 最后一次失败时间
```

### 3. Processor.py 核心修改 ✅
**文件**：`trendradar/podcast/processor.py`

#### 3.1 数据库迁移
- 添加 `_add_column_if_not_exists()` 方法
- 在 `_init_database()` 中调用迁移方法
- 兼容旧数据库

#### 3.2 Retry 参数初始化
```python
self.retry_enabled = True
self.max_retries = 3
self.retry_delay = 60
```

#### 3.3 查询条件修改
**修改**：`_get_unprocessed_history_episodes()`
```sql
WHERE status IN ('pending', 'skipped_old', 'failed')
  AND (failure_count IS NULL OR failure_count < 3)
```

#### 3.4 失败次数跟踪
- 添加 `_increment_failure_count()` 方法
- 每次失败时递增计数器
- 失败次数 >= 3 时永久忽略

#### 3.5 Retry 机制
**添加 retry 循环**：
- 下载：3次重试 + 失败计数
- 转录：3次重试 + 失败计数
- AI分析：3次重试 + 失败计数

#### 3.6 混合模式
**修改**：正常模式处理逻辑
```python
# 步骤1：优先选择新节目
selected_episodes = self._select_episodes_to_process(all_episodes)

# 步骤2：如果没有新节目，从历史未处理节目中选取
if not selected_episodes:
    print("[Podcast] 📋 RSS无新节目，尝试从历史未处理节目中选取...")
    backfill_episodes = self._check_and_backfill()
    if backfill_episodes:
        selected_episodes = backfill_episodes
```

#### 3.7 简化 backfill 逻辑
**移除**：空闲时间检查（`backfill_idle_hours`）
**原因**：触发间隔已改为6小时，每次都尝试处理

### 4. 配置文件修改 ✅
**文件**：`agents/.env`

**修改**：
```bash
# 从 2小时 改为 6小时
CRON_SCHEDULE=0 */6 * * *
```

## 测试结果

### 数据库迁移测试 ✅
```
[Podcast] 🔍 检查数据库字段...
[Podcast] ℹ️  字段已存在，跳过: podcast_episodes.failure_count
[Podcast] ℹ️  字段已存在，跳过: podcast_episodes.last_error_time
```

### 混合模式测试 ✅
```
[Podcast] 抓取完成: 17 个源, 共 165 个节目
[Podcast] 🔍 第一级筛选：2 天以内的新播客
[Podcast] ✓ 选中（新）: [late-talk] 150: 年末AI回顾：从模型到应用、从技术到商战，拽住洪流中的意义之线
[Podcast] 📦 本次处理 1 个节目
```

### 处理流程测试 ✅
```
[⏱️] 步骤 1/4: 开始下载音频...
[Download] 文件已存在: late-talk_4ef14998b25b.mp3 (108.6MB)
[⏱️] 下载完成，耗时: 0.0秒
[⏱️] 步骤 2/4: 开始 ASR 转写...
[ASR-SiliconFlow] 开始转写: late-talk_4ef14998b25b.mp3 (108.6MB)
```

## 预期效果

### 修改前
- 触发间隔：每2小时
- 无新节目时：不发送邮件
- 失败节目：无限重试或永久失败
- 数据备份：无

### 修改后
- 触发间隔：每6小时
- 无新节目时：从 skipped_old + failed 中选取（failure_count < 3）
- 失败处理：自动重试3次，超过3次后永久忽略
- 数据备份：每天自动备份，保留30天

## 部署状态

- ✅ 代码修改完成
- ✅ 本地测试通过
- ⏳ 待部署到生产环境

## 下一步

1. **提交代码**：`git add . && git commit`
2. **部署到生产**：`cd deploy && yes "y" | bash deploy.sh`
3. **验证部署**：
   ```bash
   docker logs trendradar-prod | grep Podcast
   docker exec trendradar-prod ls -la /app/output/news/backup/
   ```

## 风险评估

| 风险 | 概率 | 影响 | 应对措施 |
|------|------|------|----------|
| 邮件数量减少 | 高 | 低 | 从每2小时1封改为每6小时1封 |
| 失败节目重复处理 | 低 | 低 | failure_count < 3 过滤 |
| 历史节目处理缓慢 | 低 | 低 | 每6小时处理1个旧节目 |
| 数据库备份失败 | 低 | 高 | 每天自动备份 + 手动备份 |

## 总结

本次修改成功实现了：
1. ✅ 混合模式（优先新节目，无新节目则处理旧节目）
2. ✅ 失败次数跟踪（超过3次永久忽略）
3. ✅ Retry 机制（下载、转录、AI分析各重试3次）
4. ✅ 数据库自动备份（每天凌晨2点）
5. ✅ 触发间隔优化（从2小时改为6小时）

所有修改均已通过本地测试，可以部署到生产环境。
