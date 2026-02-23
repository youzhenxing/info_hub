# TrendRadar 播客功能开发 - 迁移说明

## 📋 项目概述

为 TrendRadar 项目添加**播客 MVP 功能**，实现对播客 RSS 的监听、音频下载、ASR 转写、AI 分析和即时邮件推送。

### 核心流程
```
RSS 抓取 → 解析 enclosure → 检测新节目 → 下载音频 → ASR 转写 → AI 分析 → 即时邮件推送 → 清理音频
```

### 技术选型
- **RSS 解析**: `feedparser` (解析 enclosure 音频附件)
- **音频下载**: `requests` 流式下载
- **ASR 转写**: 硅基流动 SenseVoice API (`FunAudioLLM/SenseVoiceSmall`)
- **AI 分析**: 现有 `AIClient` 基于 litellm
- **数据存储**: SQLite (`output/news/podcast.db`)
- **通知方式**: Type A (即时推送，每个新节目单独一封邮件)

---

## ✅ 已完成的工作

### 1. 配置扩展 (`config/config.yaml`)
```yaml
podcast:
  enabled: true
  poll_interval_minutes: 30
  asr:
    api_base: "https://api.siliconflow.cn/v1/audio/transcriptions"
    api_key: ""
    model: "FunAudioLLM/SenseVoiceSmall"
    language: "zh"
  analysis:
    enabled: true
    prompt_file: "podcast_analysis_prompt.txt"
    language: "Chinese"
  notification:
    enabled: true
    channels:
      email: true
  download:
    temp_dir: "output/podcast/audio"
    max_file_size_mb: 500
    cleanup_after_transcribe: true
  feeds:
    - id: "guigu101"
      name: "硅谷101"
      url: "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc"
      enabled: true
```

### 2. 代码文件结构
```
trendradar/podcast/
├── __init__.py           # 模块初始化
├── fetcher.py            # RSS 抓取 + enclosure 解析
├── downloader.py         # 音频下载 + 文件管理
├── transcriber.py        # ASR 转写 (SiliconFlow API)
├── analyzer.py           # AI 内容分析
├── notifier.py           # 即时邮件推送
└── processor.py          # 主处理器 (完整流程编排)

trendradar/storage/
└── podcast_schema.sql    # 数据库 schema

config/
└── podcast_analysis_prompt.txt  # AI 分析提示词
```

### 3. 核心类说明

| 文件 | 类名 | 职责 |
|------|------|------|
| `fetcher.py` | `PodcastParser` | 解析 RSS，提取 enclosure 音频附件 |
| | `PodcastFetcher` | 抓取所有配置的播客源 |
| | `PodcastEpisode` | 节目数据模型 |
| `downloader.py` | `AudioDownloader` | 流式下载音频，支持大小限制 |
| | `DownloadResult` | 下载结果数据类 |
| `transcriber.py` | `ASRTranscriber` | 调用 SiliconFlow SenseVoice API |
| | `TranscribeResult` | 转写结果数据类 |
| `analyzer.py` | `PodcastAnalyzer` | 基于 AIClient 进行内容分析 |
| | `AnalysisResult` | 分析结果数据类 |
| `notifier.py` | `PodcastNotifier` | 即时邮件推送 (Type A) |
| | `NotifyResult` | 推送结果数据类 |
| `processor.py` | `PodcastProcessor` | 主处理器，编排完整流程 |

### 4. 配置加载扩展 (`trendradar/core/loader.py`)
- 添加 `_load_podcast_config()` 函数
- 配置加载到 `config["PODCAST"]` (注意键名是大写)

### 5. CLI 集成 (`trendradar/__main__.py`)
- 添加 `--podcast-only` 参数 (仅运行播客处理)
- 添加 `NewsAnalyzer._run_podcast_processing()` 方法
- 支持环境变量 `SILICONFLOW_API_KEY`

### 6. 数据库 Schema (`trendradar/storage/podcast_schema.sql`)
```sql
CREATE TABLE podcast_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    feed_id TEXT NOT NULL,
    feed_name TEXT,
    title TEXT NOT NULL,
    audio_url TEXT NOT NULL,
    transcript TEXT,
    analysis TEXT,
    status TEXT DEFAULT 'pending',
    -- ... 其他字段
    UNIQUE(feed_id, audio_url)
);
```

---

## ✅ 已修复的问题

### **配置键名大小写不一致** ✅ 已修复

**问题描述**:
- `loader.py` 使用大写键名 (`PODCAST`, `ENABLED`)
- `processor.py` 原来使用小写键名 (`enabled`, `feeds`)

**修复方案**:
所有配置读取都已修改为支持大小写兼容:
```python
# processor.py 中的修复
asr_config = self.podcast_config.get("ASR", self.podcast_config.get("asr", {}))
api_key = asr_config.get("API_KEY", asr_config.get("api_key", ""))
```

### **AI 分析接口调用错误** ✅ 已修复

**问题描述**:
- `AIClient.chat()` 需要 `messages` 参数（消息列表格式）
- `analyzer.py` 使用了不存在的 `system_prompt` 和 `user_prompt` 参数

**修复方案**:
```python
# 构建消息列表
messages = []
if self.system_prompt:
    messages.append({"role": "system", "content": self.system_prompt})
messages.append({"role": "user", "content": user_prompt})

# 调用 AI
response = client.chat(messages=messages)
```

### **缺少 tenacity 依赖** ✅ 已修复

**问题**: litellm 需要 tenacity 模块  
**解决**: `pip install tenacity`

### **邮件配置读取错误** ✅ 已修复

**问题**: `processor.py` 从错误的位置读取邮件配置（`NOTIFICATION.CHANNELS.EMAIL`）

**解决方案**:
```python
# processor.py - 从 config 根级别读取邮件配置
email_config = {
    "FROM": self.config.get("EMAIL_FROM", ""),
    "PASSWORD": self.config.get("EMAIL_PASSWORD", ""),
    "TO": self.config.get("EMAIL_TO", ""),
    "SMTP_SERVER": self.config.get("EMAIL_SMTP_SERVER", ""),
    "SMTP_PORT": self.config.get("EMAIL_SMTP_PORT", ""),
}
```

### **send_to_email 参数名错误** ✅ 已修复

**问题**: 使用了错误的参数名 `smtp_server` 和 `smtp_port`

**解决方案**:
```python
# notifier.py - 使用正确的参数名
success = send_to_email(
    from_email=from_email,
    password=password,
    to_email=to_email,
    report_type=subject,
    html_file_path=str(html_file),
    custom_smtp_server=smtp_server,  # 正确的参数名
    custom_smtp_port=smtp_port_int,   # 正确的参数名
)

---

## 📝 TODO 清单

### ✅ 已完成

- [x] **修复配置键名大小写问题** ✅
- [x] **修复邮件配置读取问题** ✅
- [x] **修复 send_to_email 参数错误** ✅
- [x] **端到端测试** ✅
- [x] **验证完整流程** ✅
  - RSS 抓取 ✅ 正常
  - 音频下载 ✅ 正常（8.1秒）
  - ASR 转写 ✅ 正常（48秒，21722 字符）
  - AI 分析 ⚠️ 需要配置 AI API Key
  - **邮件推送 ✅ 成功发送（2.3秒）**

### 🔴 高优先级（需要用户配置）

- [ ] **配置 AI API Key**
  ```yaml
  # config/config.yaml
  ai:
    model: "deepseek/deepseek-chat"
    api_key: "sk-..."  # 填入您的 AI API Key
  ```
  或使用环境变量：
  ```bash
  export AI_API_KEY="sk-..."
  ```

### 📊 性能测试结果

**测试环境**: 硅谷101播客，单节目（86.2MB音频）

#### 使用代理（慢）：
- 总耗时: **363.4秒**（约6分钟）
- 转写: 345.6秒（95.1%）← 被代理拖慢

#### 禁用代理（快）✅：
- 总耗时: **56.0秒**（不到1分钟）
- 下载: 7.8秒（13.9%）
- 转写: 48.0秒（85.6%）← **最耗时环节**
- 分析: 0.3秒（0.4%）
- 推送: 0.0秒（0.0%）

**性能提升**: 禁用代理后速度提升 **6.5倍**！

### 🎯 使用建议

1. **推荐运行方式**：使用 `test_podcast.sh` 脚本（自动禁用代理）
   ```bash
   bash test_podcast.sh
   ```

2. **限制测试数量**：在配置文件中设置 `max_items: 1`
   ```yaml
   podcast:
     feeds:
       - id: "guigu101"
         max_items: 1  # 只测试最新1个节目
   ```

3. **预期耗时**：单个 80-100MB 音频约需 1 分钟处理

### 🟡 中优先级 (后续优化)

- [ ] **添加重试机制**
  - 网络请求失败自动重试
  - ASR API 调用失败处理
  - AI 分析失败降级策略

- [ ] **错误处理增强**
  - 更详细的错误日志
  - 失败节目状态跟踪
  - 异常情况告警

- [ ] **性能优化**
  - 并发处理多个节目
  - 音频下载断点续传
  - 数据库连接池

### 🟢 低优先级 (可选)

- [ ] **本地 GPU 支持**
  - 当前仅支持 SiliconFlow API
  - 后续可添加本地 ASR 模型
  - GPU 空闲检测与自动切换

- [ ] **其他通知渠道**
  - 当前仅支持邮件
  - 可扩展到飞书/钉钉等

- [ ] **Web UI 展示**
  - 播客列表查看
  - 转写结果浏览
  - 分析历史记录

---

## 🧪 测试命令

### 1. 语法检查
```bash
cd /home/zxy/Documents/code/TrendRadar
python -m py_compile trendradar/podcast/*.py
```

### 2. 配置验证
```python
# 验证配置是否正确加载
python -c "
from trendradar.core.loader import load_config
config = load_config()
podcast = config.get('PODCAST', {})
print('ENABLED:', podcast.get('ENABLED'))
print('FEEDS:', podcast.get('FEEDS', []))
"
```

### 3. 端到端运行
```bash
# 确保 config.yaml 中 podcast.enabled: true
# 且至少有一个 feed.enabled: true

# 设置 API Key
export SILICONFLOW_API_KEY="sk-your-api-key"

# 运行
python -m trendradar --podcast-only
```

---

## 🔧 配置说明

### 硅基流动 API
- **API 文档**: 用户提供的任务文件中有详细说明
- **Endpoint**: `https://api.siliconflow.cn/v1/audio/transcriptions`
- **Model**: `FunAudioLLM/SenseVoiceSmall`
- **支持**: 中英文自动识别
- **API Key**: 通过环境变量 `SILICONFLOW_API_KEY` 或配置文件设置

### 测试播客源
- **硅谷101**: `https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc`
- **张小珺**: `https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/626b46ea9cbbf0451cf5a962`
- **罗永浩**: `https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/68981df29e7bcd326eb91d88`

---

## 📦 依赖项

已安装的依赖:
```
feedparser   # RSS 解析
requests     # HTTP 请求
litellm      # AI 模型统一接口
```

如需重新安装:
```bash
pip install feedparser requests litellm
```

---

## 🎯 下一步行动

### 立即执行 (修复 bug)
1. 修改 `trendradar/podcast/processor.py:78-135` 的 `_init_components()` 方法
2. 所有配置读取改为大小写兼容形式
3. 运行端到端测试验证

### 测试检查点
运行测试时确认以下输出:
```
[Podcast] ═══════════════════════════════════════
[Podcast] 开始播客处理流程
[Podcast] ═══════════════════════════════════════
[Podcast] 发现 N 个新节目
[Podcast] 开始处理: 某某节目
...
```

### 成功标准
- ✅ 配置正确加载（不再报 "播客功能未启用"）
- ✅ RSS 抓取成功
- ✅ 音频下载完成
- ✅ ASR 转写返回文本
- ⚠️ AI 分析生成摘要（需配置 AI API Key）
- ✅ 邮件正常发送

---

## 🔧 问题排查指南

### 问题1: "未设置 API Key，无法进行转写"

**原因**: 硅基流动 API Key 未配置

**解决方案**:
```yaml
# config/config.yaml
podcast:
  asr:
    api_key: "{{SILICONFLOW_API_KEY}}"
```

### 问题2: "转写速度很慢（5-6分钟）"

**原因**: 系统代理配置影响（socks 代理）

**解决方案**: 使用 `test_podcast.sh` 脚本运行，会自动禁用代理
```bash
bash test_podcast.sh
```

### 问题3: "AI 分析失败: Authentication Fails"

**原因**: AI API Key 未配置

**解决方案**:
```yaml
# config/config.yaml
ai:
  model: "deepseek/deepseek-chat"
  api_key: "sk-your-ai-api-key"
```

### 问题4: "没有发现新节目"

**原因**: 数据库中已存在该节目

**解决方案**: 清理数据库重新测试
```bash
rm -f output/news/podcast.db
python -m trendradar --podcast-only
```

---

## 📚 代码设计亮点

1. **模块化架构**: 每个组件职责单一，易于测试和维护
2. **配置驱动**: 所有行为可通过配置文件控制
3. **状态追踪**: 数据库记录节目处理状态，支持断点续传
4. **错误隔离**: 单个节目失败不影响其他节目处理
5. **资源清理**: 音频文件转写后自动删除，节省空间

---

## 📞 联系与支持

- **原始任务文件**: `agents/tasks/20260128_task.txt`
- **架构文档**: `agents/architecture/`
- **用户偏好**: 播客 MVP → API 优先 → 后续添加本地 GPU

---

*生成时间: 2026-01-29*
*项目路径: /home/zxy/Documents/code/TrendRadar*
