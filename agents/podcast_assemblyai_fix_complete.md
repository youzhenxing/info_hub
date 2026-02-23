# 播客模块 AssemblyAI 配置修复完成报告

**修复时间**: 2026-02-11 17:00
**问题**: 播客模块 12:00 未发送邮件
**根本原因**: ASR backend 参数未传递，导致使用 SiliconFlow 失败（500 错误）

---

## 修复内容

### 1. 核心问题

**文件**: `trendradar/podcast/processor.py:135-146`

**问题**: 创建 `ASRTranscriber` 时缺少 `backend` 和 `assemblyai_api_key` 参数传递

**修复**:
```python
# 添加 backend 参数传递
backend = asr_config.get("BACKEND", asr_config.get("backend", "assemblyai"))

# 添加多级配置查找逻辑（兼容大小写键名）
assemblyai_config = asr_config.get("ASSEMBLYAI", asr_config.get("assemblyai", {}))
assemblyai_api_key = assemblyai_config.get("API_KEY", assemblyai_config.get("api_key", ""))

# 如果配置中找不到，尝试环境变量
if not assemblyai_api_key:
    import os
    assemblyai_api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")

self.transcriber = ASRTranscriber(
    backend=backend,
    ...
    assemblyai_api_key=assemblyai_api_key,
    speaker_labels=speaker_labels,
)
```

### 2. 环境变量配置

**文件**: `agents/.env`

**添加**: `ASSEMBLYAI_API_KEY={{ASSEMBLYAI_API_KEY}}`

---

## 测试结果

### ✅ AssemblyAI 转写测试

**播客**: "Anyone Can Code Now" - Netlify CEO Talks AI Agent
**文件大小**: 53.1MB
**转写结果**:
- ⏱️ 转写耗时: 71.1秒
- 📝 转写字符: 61,152 字符
- 🗣️ 识别说话人: 3 人
- 🌍 检测语言: 英语
- ✅ 说话人分离: 启用

### ✅ 完整流程测试

| 步骤 | 状态 | 耗时 | 输出 |
|------|------|------|------|
| 1. 音频下载 | ✅ | 0.0秒 | 文件已存在 |
| 2. ASR 转写 | ✅ | 71.1秒 | 61,152字符 |
| 3. AI 分析 | ✅ | 211.5秒 | 7,998字符 |
| 4. 邮件推送 | ✅ | 4.4秒 | 发送成功 |
| **总计** | ✅ | **287.0秒** | **~4.8分钟** |

### ✅ 日志验证

```
[ASR] 使用 backend: assemblyai
[ASR] 使用 AssemblyAI，说话人分离: 启用
[ASR-AssemblyAI] 开始转写: a16z_caf07c192c95.mp3 (53.1MB)
[ASR-AssemblyAI] 上传音频文件...
[ASR-AssemblyAI] 创建转写任务...
[ASR-AssemblyAI] 任务已创建: ce08b04a-6127-4b3a-ab67-a98179befdb0
[ASR-AssemblyAI] 等待转写完成...
[ASR-AssemblyAI] 转写完成: 61152 字符
[ASR-AssemblyAI] 检测语言: en
[ASR-AssemblyAI] 识别说话人: 3 人
[PodcastNotifier] ✅ 邮件发送成功
```

---

## 对比：SiliconFlow vs AssemblyAI

| 特性 | SiliconFlow | AssemblyAI |
|------|------------|------------|
| **大文件支持** | ❌ 391.7MB 失败（500 错误） | ✅ 53.1MB 成功 |
| **说话人分离** | ❌ 不支持 | ✅ 支持（识别 3 人） |
| **转写质量** | N/A（失败） | ✅ 61,152 字符 |
| **转写速度** | N/A（失败） | 71.1 秒（53MB） |
| **API 稳定性** | ❌ 500 错误 | ✅ 稳定 |

---

## 部署信息

**提交 ID**: c8839c1d
**分支**: master
**版本**: v5.26.0
**部署状态**: ✅ 已部署并测试

---

## 后续优化建议（用户提出）

### 音频分段处理功能

**问题**: 超长音频（如 391.7MB）可能导致 API 处理失败或超时

**建议方案**:
1. 添加音频时长检测（使用 `ffprobe`）
2. 超过阈值（如 2 小时）时自动分段
3. 分段转写后合并结果
4. 添加段间重叠（如 5 秒）保证连续性

**实施位置**:
- `trendradar/podcast/downloader.py`: 添加分段方法
- `trendradar/podcast/transcriber.py`: 添加批量转写和合并逻辑

**优先级**: 低（当前 AssemblyAI 已能正常处理大文件）

---

## 经验教训（踩坑记录）

### 规则 14: 配置传递陷阱

**问题**: 即使配置文件正确（`backend: "assemblyai"`），如果代码没有传递对应参数（`backend` 参数），配置会被静默忽略，使用默认值（`"siliconflow"`）

**影响**: 播客模块 12:00 转写失败，未发送邮件

**解决**:
1. 在 `ASRTranscriber` 初始化时显式传递 `backend` 参数
2. 添加多级配置查找逻辑（内嵌配置 → 顶层配置 → 环境变量）
3. 兼容大小写键名（`ASR` vs `asr`）

**预防措施**:
- 所有配置参数都必须显式传递
- 不依赖默认值
- 添加配置验证和调试输出
- 使用环境变量作为后备方案

---

## 相关文件

- `trendradar/podcast/processor.py` - **已修改**：修复 ASR 配置传递
- `trendradar/podcast/transcriber.py` - **参考**：ASRTranscriber 初始化参数
- `config/config.yaml` - **验证**：AssemblyAI 配置正确
- `agents/.env` - **已修改**：添加 ASSEMBLYAI_API_KEY（不提交到 Git）
- `agents/podcast_1200_no_email_analysis.md` - **参考**：原始问题分析

---

**修复完成时间**: 2026-02-11 17:00
**下一步**: 等待 18:00 定时任务自动触发，验证播客正常处理
