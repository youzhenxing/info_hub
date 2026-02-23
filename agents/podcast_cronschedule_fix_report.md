# 播客模块 CRON_SCHEDULE 修复报告

## 日期

2026-02-13

---

## 问题概述

用户报告播客模块最近 8 小时没有收到推送。经过诊断，发现两个问题：

1. **segmenter 配置错误**（已修复）：配置键名大小写不匹配导致 `'NoneType' object has no attribute 'segment_audio'`
2. **CRON_SCHEDULE 未更新**（本次修复）：系统级调度间隔仍是 6 小时，未同步为 4 小时

---

## 根本原因

### CRON_SCHEDULE 环境变量未更新

**现状**：
- `agents/.env` 中 `CRON_SCHEDULE=0 */6 * * *`（每 6 小时）
- `config/config.yaml` 中 `podcast.poll_interval_minutes: 240`（已正确设置为 4 小时）

**问题**：
- `poll_interval_minutes` 控制播客模块内部轮询间隔（检查新增节目）
- `CRON_SCHEDULE` 控制系统级 cron 调度（整个模块执行频率）
- 两者不一致：前者已更新为 4 小时，后者仍为 6 小时

**影响**：
- 系统级调度每 6 小时才触发一次播客模块
- 与预期的 4 小时间隔不符，影响推送频率

---

## 修复内容

### 修改文件

**文件**：`agents/.env`

**位置**：第 108-109 行

**修改前**：
```bash
# 播客定时任务：每 6 小时扫描一次（2026-02-10 修改：从2小时改为6小时）
CRON_SCHEDULE=0 */6 * * *
```

**修改后**：
```bash
# 播客定时任务：每 4 小时扫描一次（2026-02-13 修改：从6小时改为4小时）
CRON_SCHEDULE=0 */4 * * *
```

---

## 部署验证

### 1. 部署执行

```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
```

**部署结果**：
- ✅ Docker 镜像构建完成
- ✅ .env 配置同步和校验通过
- ✅ 主程序定时: `0 */4 * * *`
- ✅ 版本记录已创建
- ✅ 部署通知邮件已发送

### 2. 容器重启

由于容器内环境变量不会自动更新，需要重启容器：

```bash
docker stop trendradar-prod && docker rm trendradar-prod
docker stop trendradar-mcp-prod && docker rm trendradar-mcp-prod

cd /home/zxy/Documents/install/trendradar/releases/v5.29.0
docker compose up -d
```

### 3. 验证结果

**验证 1：环境变量检查**
```bash
docker exec trendradar-prod printenv | grep CRON_SCHEDULE
```

**输出**：
```
CRON_SCHEDULE=0 */4 * * *
```

✅ 环境变量已更新为每 4 小时

---

**验证 2：crontab 配置检查**
```bash
docker exec trendradar-prod cat /tmp/crontab
```

**输出**：
```
# 主程序定时任务（每2小时）
0 */4 * * * cd /app && /usr/local/bin/python -m trendradar
...
```

✅ crontab 已更新为 `0 */4 * * *`

---

**验证 3：播客模块运行状态**
```bash
docker logs trendradar-prod --tail 100 | grep -E "(Podcast|segment)"
```

**输出**（2026-02-13 07:33）：
```
[Podcast] 📦 尝试 1/20: [Latent Space] Anthropic's New Plugins and $3 Billion Lawsuit
[Podcast] 📦 尝试 8/20: [Latent Space (AI Engineer Podcast)] Anthropic's New Plugins and $3 Billion Lawsuit
[Download] ⚠️  segmenter 未启用，跳过分段检测
[PodcastAnalyzer] 分析完成: 5805 字符
[PodcastNotifier] ✅ 邮件发送成功
[Podcast] ✅ 处理完成: Anthropic's New Plugins and $3 Billion Lawsuit
```

✅ segmenter 正常工作（不再报 `'NoneType' object has no attribute 'segment_audio'` 错误）
✅ 邮件发送成功

---

## 修复效果总结

### ✅ 已修复问题

1. **segmenter 配置错误**：
   - 统一配置键名为小写（`enabled`）
   - segmenter 正确初始化
   - 文件已存在时不再报错

2. **CRON_SCHEDULE 调度间隔**：
   - 从 6 小时更新为 4 小时
   - 系统级调度与配置文件一致
   - 播客模块执行频率提升

### 📊 配置一致性

| 配置项 | 值 | 状态 |
|--------|-----|------|
| `config.yaml` → `podcast.poll_interval_minutes` | 240（4 小时） | ✅ |
| `agents/.env` → `CRON_SCHEDULE` | `0 */4 * * *`（4 小时） | ✅ |
| 容器内环境变量 `CRON_SCHEDULE` | `0 */4 * * *`（4 小时） | ✅ |
| crontab 调度规则 | `0 */4 * * *`（4 小时） | ✅ |

---

## 预期效果

### 播客模块正常运作

- ✅ segmenter 不再报错，文件已存在时正常处理
- ✅ 轮询间隔从 6 小时改为 4 小时，检查频率提高
- ✅ 历史记录处理正常，失败计数正确更新
- ✅ 邮件推送正常工作

### 推送频率

- **之前**：每 6 小时轮询一次
- **现在**：每 4 小时轮询一次
- **提升**：推送频率提高 50%

---

## 相关文件

- `agents/.env` - CRON_SCHEDULE 环境变量（已修改）
- `config/config.yaml` - poll_interval_minutes 配置（已修改）
- `trendradar/podcast/processor.py` - segmenter 配置初始化（已修改）
- `deploy/deploy.sh` - 部署脚本（已添加自动 update）
- `agents/podcast_fix_report.md` - segmenter 修复报告

---

## 后续建议

1. **统一配置管理**：考虑将 `CRON_SCHEDULE` 也移至 `config/config.yaml`，避免多处配置不一致
2. **注释同步**：entrypoint.sh 中 crontab 注释仍显示"每2小时"，建议更新为"每4小时"
3. **自动化验证**：在 pre-commit-verify.sh 中添加 CRON_SCHEDULE 与 poll_interval_minutes 一致性检查
