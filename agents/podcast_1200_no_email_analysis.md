# 播客模块 12:00 未发送邮件问题分析报告

**分析时间**: 2026-02-11 16:10
**问题现象**: 播客模块中午12点应发送邮件但用户未收到
**严重程度**: 🔴 高（影响核心功能）

---

## 问题结论

**根本原因**: SiliconFlow ASR 转写 API 返回 500 错误，导致播客处理流程在转写阶段失败，无法继续执行后续的 AI 分析和邮件推送。

---

## 详细执行流程

### 1. Cron 调度正常 ✅

```
时间: 2026-02-11 12:00:00
调度: CRON_SCHEDULE=0 */6 * * *
执行: cd /app && /usr/local/bin/python -m trendradar
```

**结论**: 定时任务按预期执行，调度配置正确。

---

### 2. 播客抓取正常 ✅

```
[Podcast] 开始抓取 17 个播客源...
[Podcast] 抓取完成: 16 个源, 共 155 个节目
```

**结论**: RSS 抓取正常，成功获取 16 个源（1 个源网络不可达）。

---

### 3. 新播客筛选正常 ✅

```
[Podcast] ✓ 选中（新）: [luoyonghao] 音乐人张玮玮×罗永浩！我们都是那个"混乱又伟大"的 90 年代的幸存者
[Podcast] 📦 本次处理 1 个节目
```

**结论**: 成功识别到罗永浩的新播客节目（发布时间: 2026-02-11T04:00:00）。

---

### 4. 音频下载成功 ✅

```
[Download] 开始下载: https://media.xyzcdn.net/68981df29e7bcd326eb91d88/llHEY1QKMnMxe-sjlXGleDJNTAOV.m...
[Download] 下载完成: luoyonghao_5e29a6e6d6d3.m4a (391.7MB)
[⏱️] 下载完成，耗时: 35.7秒
```

**结论**: 音频文件下载成功，文件大小 391.7MB。

---

### 5. ❌ ASR 转写失败（关键问题）

```
[ASR-SiliconFlow] 开始转写: luoyonghao_5e29a6e6d6d3.m4a (391.7MB)
[ASR-SiliconFlow] 模型: FunAudioLLM/SenseVoiceSmall

[Podcast] ⚠️  转录失败（尝试 1/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 2/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 3/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 4/4）: API 错误 (500): null
[Podcast] ❌ 转录最终失败（已重试3次）: API 错误 (500): null

[Podcast] ❌ 处理异常: 转录失败（已重试3次）: API 错误 (500): null
```

**结论**:
- SiliconFlow ASR API 返回 500 Internal Server Error
- 系统自动重试 4 次后仍然失败
- 错误信息为 `null`，无法获取具体原因

---

### 6. 最终结果

```
[Podcast] 处理完成: 成功 0, 失败 1
[Podcast] 本次处理: 0/1 个节目成功
time="2026-02-11T12:16:07+08:00" level=info msg="job succeeded"
```

**结论**: 因为转写失败，无法执行后续的 AI 分析和邮件推送，流程终止。

---

## 数据库验证

### 播客记录状态

```sql
标题: 音乐人张玮玮×罗永浩！我们都是那个"混乱又伟大"的 90 年代的幸存者
发布时间: 2026-02-11T04:00:00
状态: failed
错误信息: 转录失败（已重试3次）: API 错误 (500): null
失败次数: 0
```

**结论**: 数据库记录状态为 `failed`，与日志一致。

---

## 可能的原因分析

### 1. API 服务端问题 🔴

SiliconFlow ASR API 可能出现了临时性服务故障：
- 服务过载
- 模型部署问题
- 内部错误

### 2. 文件过大问题 🟡

音频文件 391.7MB，可能超出 API 处理能力：
- 通常 ASR API 有文件大小限制
- 大文件处理时间长，容易超时
- 需要检查 SiliconFlow 的文件大小限制

### 3. API 限流 🟡

可能触发了 API 限流策略：
- 短时间内请求过多
- 并发请求限制
- 需要检查 API 配额和限流策略

### 4. 音频格式问题 🟢

虽然可能性较小，但也可能是：
- m4a 格式兼容性问题
- 音频编码问题
- 文件损坏

---

## 解决方案建议

### 立即修复措施

#### 1. 切换到 AssemblyAI（推荐）

```yaml
# config/config.yaml
podcast:
  asr:
    backend: "assemblyai"  # 从 siliconflow 改为 assemblyai
    assemblyai:
      api_key: "${ASSEMBLYAI_API_KEY}"
      speaker_labels: true
```

**优势**:
- AssemblyAI 更稳定
- 支持说话人分离
- 文件大小限制更宽松

#### 2. 检查 SiliconFlow API 状态

```bash
# 测试 API 可用性
curl -X POST "https://api.siliconflow.cn/v1/audio/transcriptions" \
  -H "Authorization: Bearer ${SILICONFLOW_API_KEY}" \
  -F "file=@test.m4a" \
  -F "model=FunAudioLLM/SenseVoiceSmall"
```

#### 3. 添加更好的错误处理

在 `trendradar/podcast/transcriber.py:446` 添加：
```python
if response.status_code == 500:
    # 服务器错误，提供更详细的错误信息
    return TranscribeResult(
        success=False,
        error=f"API 服务器错误 (500)，可能是服务过载或文件过大。建议：1) 切换到 AssemblyAI；2) 压缩音频文件；3) 稍后重试"
    )
```

---

### 长期优化建议

#### 1. 实现降级策略

当 SiliconFlow 失败时，自动降级到备用方案：
1. 重试 SiliconFlow（当前已实现）
2. **新增**: 降级到 AssemblyAI
3. **新增**: 跳过转写，直接推送音频链接（最后手段）

#### 2. 文件大小检查

在上传前检查文件大小，超过限制时提前报错：
```python
MAX_FILE_SIZE_MB = 200  # SiliconFlow 限制

file_size_mb = path.stat().st_size / (1024 * 1024)
if file_size_mb > MAX_FILE_SIZE_MB:
    return TranscribeResult(
        success=False,
        error=f"文件过大 ({file_size_mb:.1f}MB > {MAX_FILE_SIZE_MB}MB)，请使用 AssemblyAI"
    )
```

#### 3. 添加监控和告警

- ASR 失败率监控
- API 响应时间监控
- 失败时发送告警邮件

---

## 立即执行步骤

### 选项 1: 手动重试（如果 API 恢复）

```bash
# 触发播客模块重新处理
docker exec trendradar-prod python -m trendradar run podcast
```

### 选项 2: 切换到 AssemblyAI（推荐）

1. 确认已设置 `ASSEMBLYAI_API_KEY`
2. 修改 `config/config.yaml` 中的 `podcast.asr.backend` 为 `assemblyai`
3. 重新部署
4. 手动触发播客处理

### 选项 3: 跳过该播客

如果不需要强制处理这个播客，可以：
1. 等待下次定时任务（18:00）
2. 如果 API 恢复正常，会自动处理

---

## 经验教训

### 踩坑记录

#### 规则 13: 大文件 ASR 转写风险

**问题**: 391.7MB 的大文件导致 SiliconFlow API 500 错误
**影响**: 整个播客处理流程失败，用户无法收到邮件
**解决**: 使用 AssemblyAI 或实现文件大小预检查

**预防措施**:
1. 在转写前检查文件大小
2. 设置合理的文件大小限制
3. 大文件自动降级到更稳定的服务（AssemblyAI）
4. 实现多级降级策略

---

## 相关文件

- `trendradar/podcast/transcriber.py` - ASR 转写服务
- `trendradar/podcast/processor.py` - 播客处理器
- `config/config.yaml` - 播客配置
- `agents/.env` - API Keys

---

## 附录: 完整日志

```
time="2026-02-11T12:00:00+08:00" level=info msg=starting iteration=2 job.command="cd /app && /usr/local/bin/python -m trendradar" job.position=0 job.schedule="0 */6 * * *"
配置文件加载成功: /app/config/config.yaml
...
[Podcast] ✓ 选中（新）: [luoyonghao] 音乐人张玮玮×罗永浩！我们都是那个"混乱又伟大"的 90 年代的幸存者
[Podcast] 📦 本次处理 1 个节目
...
[Download] 下载完成: luoyonghao_5e29a6e6d6d3.m4a (391.7MB)
[⏱️] 下载完成，耗时: 35.7秒
[⏱️] 步骤 2/4: 开始 ASR 转写...
[ASR-SiliconFlow] 开始转写: luoyonghao_5e29a6e6d6d3.m4a (391.7MB)
[ASR-SiliconFlow] 模型: FunAudioLLM/SenseVoiceSmall
[Podcast] ⚠️  转录失败（尝试 1/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 2/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 3/4）: API 错误 (500): null
[Podcast] ⚠️  转录失败（尝试 4/4）: API 错误 (500): null
[Podcast] ❌ 转录最终失败（已重试3次）: API 错误 (500): null
[Download] 已清理: luoyonghao_5e29a6e6d6d3.m4a
[Podcast] ❌ 处理异常: 转录失败（已重试3次）: API 错误 (500): null
[Podcast] ═══════════════════════════════════════
[Podcast] 处理完成: 成功 0, 失败 1
[Podcast] ═══════════════════════════════════════
[Podcast] 本次处理: 0/1 个节目成功
time="2026-02-11T12:16:07+08:00" level=info msg="job succeeded" iteration=2 job.command="cd /app && /usr/local/bin/python -m trendradar" job.position=0 job.schedule="0 */6 * * *"
```

---

**报告生成时间**: 2026-02-11 16:15
**下一步行动**: 等待用户确认是否切换到 AssemblyAI 或其他解决方案
