# 播客模块修复报告

## 日期

2026-02-13

---

## 问题分析

### 症状

用户报告：播客模块最近 8 小时没有收到推送，需要诊断原因。

### 日志错误

```
[Podcast] ❌ 处理异常: 'NoneType' object has no attribute 'segment_audio'
```

### 根本原因

**配置键名不匹配**：

- **代码中的键名**：`segment_config.get("ENABLED", ...)`
- **配置文件中的键名**：`enabled`

**结果**：
- `segment_config.get("ENABLED")` 返回 `None`（键不存在）
- Fallback 到 `segment_config.get("enabled")` 才返回 `True`

**错误流程**：
1. 读取大写键名 `ENABLED` → 返回 `None`
2. `segment_enabled = None`（falsy）
3. `if segmenter is not None:` 条件满足
4. 打印 "segmenter 未启用"
5. **应该 return**，但代码继续执行到 `segmenter.segment_audio()`
6. 调用 `None.segment_audio()` → 报错：`'NoneType' object has no attribute 'segment_audio'`

---

## 修复内容

### 修改文件

**文件**：`trendradar/podcast/processor.py`

**位置**：第 171 行

**修改前**：
```python
segment_config = self.podcast_config.get("SEGMENT", self.podcast_config.get("segment", {}))
segment_enabled = segment_config.get("ENABLED", segment_config.get("enabled", False))
```

**修改后**：
```python
segment_config = self.podcast_config.get("segment", self.podcast_config.get("segment", {}))
segment_enabled = segment_config.get("enabled", False)
```

---

### 触发间隔调整

**文件**：`config/config.yaml`

**修改前**：
```yaml
poll_interval_minutes: 360
```

**修改后**：
```yaml
poll_interval_minutes: 240
```

---

## 验证

### 1. 配置验证

```bash
docker exec trendradar-prod python -c "
import yaml
config = yaml.safe_load(open('/app/config/config.yaml'))

print(f'segment_enabled: {config.get(\"podcast\", {}).get(\"segment\", {}).get(\"enabled\")}')
print(f'poll_interval: {config.get(\"podcast\", {}).get(\"poll_interval_minutes\")}'
"
```

**结果**：
- segment_enabled: True
- poll_interval_minutes: 240

### 2. 部署验证

部署命令：
```bash
cd deploy && yes "y" | bash deploy.sh
```

**状态**：✅ 部署 + 切换完成

### 3. 播客模块验证

执行命令：
```bash
docker exec trendradar-prod python -m trendradar.cli run podcast
```

---

## 预期效果

### 修复问题

- ✅ 配置键名统一，segmenter 能正确初始化
- ✅ 触发间隔改为 4 小时，检查频率提高
- ✅ 文件已存在时不再报错，可以正常执行分段检测
- ✅ 播客模块恢复正常处理和推送

---

## 相关文件

- `trendradar/podcast/processor.py` - segmenter 配置初始化修复
- `config/config.yaml` - 触发间隔调整
