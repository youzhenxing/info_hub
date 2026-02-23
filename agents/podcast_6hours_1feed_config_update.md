# 播客处理配置更新报告

**更新时间**: 2026-02-09 11:30
**更新类型**: 调度频率和处理粒度优化

---

## 更新内容

### 1. 定时触发频率

**之前**: 每2小时触发一次
**现在**: 每6小时触发一次

**配置变更**:
```yaml
# config/config.yaml
poll_interval_minutes: 360  # 120 → 360

# Docker环境变量
CRON_SCHEDULE="0 */6 * * *"  # "0 */2 * * *" → "0 */6 * * *"
```

**触发时间**:
- 今天: 12:00, 18:00, 00:00
- 每天4次（而不是之前的12次）

---

### 2. 每次处理数量

**之前**: 每次最多处理3个播客（来自不同feeds）
**现在**: 每次只处理1个播客（1个feed）

**配置变更**:
```yaml
# config/config.yaml
max_episodes_per_run: 1  # 3 → 1
```

**代码修复**:
```python
# trendradar/podcast/processor.py (第704行)
# 之前（硬编码）
MAX_EPISODES = 3

# 现在（从配置读取）
MAX_EPISODES = self.max_episodes_per_run
```

---

## 验证结果

### 测试日志

```bash
docker exec trendradar-prod python -m trendradar --podcast-only
```

**输出**:
```
[Podcast] 抓取完成: 16 个源, 共 155 个节目
[Podcast] 🔍 第一级筛选：2 天以内的新播客
[Podcast] ✓ 选中（新）: [latent-space] Reddit's AI Answers & Meta's Vibes App
[Podcast] 📦 本次处理 1 个节目  ✅
[Podcast] 开始处理: Reddit's AI Answers & Meta's Vibes App
```

**验证点**：
- ✅ 只处理1个节目（不再是3个）
- ✅ 优先选择2天内的新播客
- ✅ 配置正确加载并生效

---

## 优势分析

### 资源消耗

| 指标 | 之前（2h/3个） | 现在（6h/1个） | 改善 |
|------|---------------|---------------|------|
| 每天触发次数 | 12次 | 4次 | ↓ 67% |
| 每天处理播客数 | 最多36个 | 最多4个 | ↓ 89% |
| API调用成本 | 高 | 低 | ↓ 显著 |

### 处理粒度

| 方面 | 之前 | 现在 | 优势 |
|------|------|------|------|
| Feed循环 | 可能跳过某些feeds | 每个feed更均匀 | 公平性提升 |
| 故障影响 | 一次失败影响3个 | 只影响1个 | 风险降低 |
| 控制精度 | 批量处理 | 精细控制 | 灵活性提升 |

### 维护性

- ✅ 配置集中管理（不再硬编码）
- ✅ 更容易调整参数
- ✅ 更容易监控和调试

---

## Feed覆盖分析

### 之前（每2小时处理3个）

假设16个feeds：
- 第1轮: feed1, feed2, feed3
- 第2轮: feed4, feed5, feed6
- 第3轮: feed7, feed8, feed9
- ...
- 第6轮: feed16, feed1, feed2

**覆盖周期**: 约12小时（6轮×2小时）

### 现在（每6小时处理1个）

同样的16个feeds：
- 第1次: feed1
- 第2次: feed2
- 第3次: feed3
- ...
- 第16次: feed16

**覆盖周期**: 约96小时（16次×6小时 = 4天）

**说明**：
- 虽然覆盖周期变长，但每个feed的处理更均匀
- 对于不紧急的播客内容，这是可以接受的
- 如果需要更快覆盖，可以调整回3个或增加触发频率

---

## 配置对比

### 完整配置对比

```yaml
# 之前的配置
podcast:
  enabled: true
  poll_interval_minutes: 120            # 2小时
  max_episodes_per_run: 3              # 每次最多3个
  new_episode_threshold_days: 2

# 现在的配置
podcast:
  enabled: true
  poll_interval_minutes: 360            # 6小时
  max_episodes_per_run: 1              # 每次只处理1个
  new_episode_threshold_days: 2
```

### Docker环境变量

```bash
# 之前
docker run -e CRON_SCHEDULE="0 */2 * * *" trendradar:local

# 现在
docker run -e CRON_SCHEDULE="0 */6 * * *" trendradar:local
```

---

## 性能预估

### 日处理能力

**之前**:
- 每天触发: 12次
- 每次处理: 最多3个
- 日处理能力: 最多36个播客

**现在**:
- 每天触发: 4次
- 每次处理: 最多1个
- 日处理能力: 最多4个播客

### 成本节约

假设每个播客处理成本 = C（包括下载、ASR、AI分析、邮件）

- 之前日成本: 36C
- 现在日成本: 4C
- **节约成本**: 89%

### 风险降低

- 单次失败影响范围: 3个 → 1个（↓ 67%）
- 故障恢复时间: 约2小时 → 约6小时（但只影响1个播客）

---

## 调整建议

### 如果需要更快处理

**选项1**: 保持6小时，但每次处理2-3个
```yaml
max_episodes_per_run: 2  # 或 3
```

**选项2**: 保持每次1个，但缩短间隔
```yaml
poll_interval_minutes: 180  # 3小时
CRON_SCHEDULE="0 */3 * * *"
```

**选项3**: 中等配置
```yaml
poll_interval_minutes: 240  # 4小时
max_episodes_per_run: 2     # 每次2个
```

### 如果需要更慢处理

**选项**: 进一步降低频率
```yaml
poll_interval_minutes: 720  # 12小时
CRON_SCHEDULE="0 */12 * * *"
```

---

## 监控建议

### 关键指标

1. **处理成功率**
   ```sql
   SELECT
     DATE(first_crawl_time) as date,
     COUNT(*) as total,
     SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) as completed,
     ROUND(SUM(CASE WHEN status='completed' THEN 1 ELSE 0 END) * 100.0 / COUNT(*), 2) as success_rate
   FROM podcast_episodes
   WHERE first_crawl_time >= date('now', '-7 days')
   GROUP BY DATE(first_crawl_time);
   ```

2. **Feed覆盖均匀度**
   ```sql
   SELECT
     feed_id,
     COUNT(*) as total_processed,
     SUM(CASE WHEN first_crawl_time >= datetime('now', '-7 days') THEN 1 ELSE 0 END) as last_7_days
   FROM podcast_episodes
   WHERE status = 'completed'
   GROUP BY feed_id
   ORDER BY last_7_days DESC;
   ```

3. **处理耗时分布**
   ```bash
   # 查看日志中的处理耗时
   docker logs trendradar-prod | grep "处理完成，总耗时"
   ```

---

## 部署清单

### 修改的文件

1. ✅ `config/config.yaml` - 配置参数更新
2. ✅ `trendradar/podcast/processor.py` - 代码修复（硬编码→配置读取）
3. ✅ Docker容器 - CRON_SCHEDULE环境变量更新

### 验证清单

- [x] 配置文件正确加载
- [x] 只处理1个节目
- [x] Cron调度改为6小时
- [x] 容器正常运行
- [x] 手动测试通过

---

## 下次运行

**预计时间**: 今天12:00
**预期行为**: 处理1个播客（2天内的新播客）

**监控命令**:
```bash
# 实时监控日志
docker logs trendradar-prod -f --since 1m | grep "\[Podcast\]"

# 检查处理结果
sqlite3 /home/zxy/Documents/code/TrendRadar/output/news/podcast.db \
  "SELECT feed_id, title, status, first_crawl_time \
   FROM podcast_episodes \
   WHERE first_crawl_time >= datetime('now', '-1 hour') \
   ORDER BY first_crawl_time DESC;"
```

---

## 总结

✅ **配置更新成功**: 从2小时/3个改为6小时/1个
✅ **代码修复完成**: MAX_EPISODES从配置读取
✅ **验证测试通过**: 只处理1个节目
✅ **容器重启成功**: 新配置已生效

**生产状态**: 🟢 正常运行
**下次触发**: 今天12:00
**预期效果**: 资源消耗降低89%，风险降低67%

---

**报告生成时间**: 2026-02-09 11:30
**报告生成人**: Claude (Sonnet 4.5)
**配置版本**: v5.4.0 + podcast_6h_1feed
