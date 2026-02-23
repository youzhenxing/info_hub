# InfoHub - 智能信息聚合与分析系统

> **技术白皮书 v1.0**
>
> 一套完整的个人信息聚合系统，自动采集播客、社区热点、公众号、投资数据，通过 AI 进行智能分析，并推送到邮箱或即时通讯工具。

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构](#2-系统架构)
3. [模块详解](#3-模块详解)
   - 3.1 [播客模块](#31-播客模块-podcast)
   - 3.2 [社区热点模块](#32-社区热点模块-community)
   - 3.3 [公众号模块](#33-公众号模块-wechat)
   - 3.4 [投资模块](#34-投资模块-investment)
   - 3.5 [日志监控模块](#35-日志监控模块-daily-report)
4. [核心技术实现](#4-核心技术实现)
5. [定时任务配置](#5-定时任务配置)
6. [配置参考](#6-配置参考)
7. [订阅源管理](#7-订阅源管理)
8. [部署指南](#8-部署指南)
9. [效果展示](#9-效果展示)
10. [API 服务依赖](#10-api-服务依赖)

---

## 1. 项目概述

### 1.1 系统定位

InfoHub 是一个**个人信息聚合与智能分析平台**，旨在解决信息碎片化问题，帮助用户高效获取有价值的信息。

### 1.2 核心价值

| 特性 | 描述 |
|-----|------|
| **自动采集** | 定时监控多个信息源，无需手动浏览 |
| **AI 分析** | 使用 DeepSeek R1 模型进行内容理解和摘要 |
| **智能推送** | 通过邮件、飞书、钉钉等渠道及时推送 |
| **模块化设计** | 各模块独立运行，可按需启用 |

### 1.3 技术栈

```
┌─────────────────────────────────────────────────────┐
│                    技术栈                            │
├─────────────────────────────────────────────────────┤
│  语言:     Python 3.10+                             │
│  部署:     Docker + Docker Compose                  │
│  数据库:   SQLite (轻量级，零配置)                   │
│  定时任务: Supercronic (Docker 内)                   │
│  AI API:   SiliconFlow / AssemblyAI                 │
│  邮件:     SMTP (163邮箱/Gmail等)                    │
└─────────────────────────────────────────────────────┘
```

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────────┐
│                        InfoHub 系统架构                               │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │
│  │  播客   │  │ 社区热点 │  │  公众号  │  │  投资   │  │日志监控 │   │
│  │ Podcast │  │Community│  │ Wechat  │  │Investment│ │  Log   │   │
│  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘  └────┬────┘   │
│       │            │            │            │            │         │
│       │     ┌──────┴──────┬─────┴─────┬──────┴──────┐     │         │
│       │     │             │           │             │     │         │
│       ▼     ▼             ▼           ▼             ▼     ▼         │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      数据处理层                              │   │
│  │  • RSS 解析  • HTTP 请求  • 音频下载  • 内容清洗           │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      AI 分析层                               │   │
│  │  • DeepSeek R1 (内容分析)                                   │   │
│  │  • AssemblyAI (语音转写 + 说话人分离)                       │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                              │                                      │
│                              ▼                                      │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                      推送层                                  │   │
│  │  • Email (SMTP)  • 飞书  • 钉钉  • 企业微信  • Telegram   │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                                     │
└─────────────────────────────────────────────────────────────────────┘
```

### 2.2 数据流程

```
信息源 → 采集器 → 过滤器 → AI分析 → 渲染器 → 推送器 → 用户
   │        │        │        │        │        │
   │        │        │        │        │        └── SMTP/IM API
   │        │        │        │        └── Jinja2 HTML 模板
   │        │        │        └── DeepSeek R1 / AssemblyAI
   │        │        └── 时间/分数/关键词过滤
   │        └── RSS/HTTP/API 请求
   └── RSS/网站/公众号/行情
```

---

## 3. 模块详解

### 3.1 播客模块 (Podcast)

#### 功能概述

自动监控播客 RSS 订阅，发现新节目后自动下载、转写、分析并推送。

#### 处理流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    播客处理流水线                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  RSS订阅 → 音频下载 → 语音转写 → AI分析 → 邮件推送              │
│     ↓          ↓          ↓          ↓         ↓               │
│  去重检测   长音频切段   说话人分离   DeepSeek   HTML渲染        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 核心组件

| 组件 | 文件 | 功能 |
|------|------|------|
| Fetcher | `podcast/fetcher.py` | RSS 订阅解析，提取音频 enclosure |
| Downloader | `podcast/downloader.py` | 音频下载，支持代理、大小限制、超时 |
| Segmenter | `podcast/segmenter.py` | 超长音频分段（>2小时） |
| Transcriber | `podcast/transcriber.py` | ASR 语音转写 |
| Analyzer | `podcast/analyzer.py` | AI 内容分析 |
| Notifier | `podcast/notifier.py` | 邮件即时推送 |
| Processor | `podcast/processor.py` | 流程协调器 |

#### 技术亮点

**1. 长音频分段策略**

```
输入：5小时播客（如 Lex Fridman）
     ↓
检测：时长 > 2小时阈值
     ↓
分段：自适应均分（2等分 → 3等分 → ... 直到每段 < 2小时）
     ↓
重叠：每段前后各增加 2 分钟
     ↓
转写：逐段调用 ASR API
     ↓
拼接：简单合并，AI 负责去重和连贯
```

**2. Progressive Fallback 降级策略**

```python
# 邮件内容渲染的降级策略
if ai_analysis_success:
    show_ai_analysis()        # 优先：AI 分析结果
elif transcript_available:
    show_transcript()         # 降级：转写文本（前5000字）
else:
    show_friendly_message()   # 最终：友好提示
```

**3. 混合模式**

```
优先级 1: 新节目（2天内发布）
    ↓ 无新节目
优先级 2: 历史 skipped_old 节目
    ↓ 全部处理完
优先级 3: 历史 failed 节目（失败次数 < 3）
```

**4. Retry 机制**

```
下载失败 → 重试3次 → 指数退避（10s, 20s, 40s）
转写失败 → 重试3次 → 固定间隔（60s）
AI分析失败 → 重试3次 → 不阻止邮件发送
```

#### ASR 后端对比

| 后端 | 说话人分离 | 大文件支持 | 成本 | 推荐场景 |
|------|-----------|-----------|------|---------|
| **AssemblyAI** | ✅ 支持 | ✅ 稳定 | $0.17/小时 | 推荐 |
| SiliconFlow | ❌ 不支持 | ⚠️ 有限制 | 更低 | 快速测试 |
| 本地 WhisperX | ✅ 支持 | ✅ 无限制 | 免费 | 需要GPU |

---

### 3.2 社区热点模块 (Community)

#### 功能概述

从 HackerNews、Reddit、GitHub 等平台采集热门内容，通过 AI 筛选有价值的信息，每天定时推送。

#### 数据流程

```
┌─────────────────────────────────────────────────────────────────┐
│                    社区热点采集流程                               │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  多平台采集 → 时间/分数过滤 → 关键词匹配 → AI评分 → 汇总推送   │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 支持的数据源

| 数据源 | API | 过滤条件 | 特点 |
|--------|-----|----------|------|
| **HackerNews** | Algolia Search | 分数 > 10, 24小时内 | 技术热点 |
| **Reddit** | JSON API | 分数 > 5, 24小时内 | 社区讨论 |
| **GitHub** | Trending API | 语言/时间范围 | 开源项目 |
| **ProductHunt** | 官方 API | 当日热门 | 新产品 |
| **Kickstarter** | 爬虫 | 分类/状态 | 众筹项目 |

#### 过滤机制

```yaml
# 配置示例
sources:
  hackernews:
    max_items: 30          # 最大返回条目
    min_score: 10          # 最低分数
    max_age_hours: 24      # 时间范围

  reddit:
    subreddits:            # 订阅的子版块
      - MachineLearning
      - artificial
      - robotics
    min_score: 5
```

#### AI 筛选流程

```
1. 关键词匹配：AI, LLM, AGI, 机器人, 创业, 投资
     ↓
2. 相关性评分：AI 判断内容与关注话题的相关程度
     ↓
3. 价值评分：AI 评估内容的实用价值
     ↓
4. 深度分析：对高价值内容生成详细摘要
```

---

### 3.3 公众号模块 (Wechat)

#### 功能概述

通过 Wewe-RSS 服务获取微信公众号文章，AI 生成摘要并聚合话题，每天推送日报。

#### 架构设计

```
┌─────────────────────────────────────────────────────────────────┐
│                    公众号采集架构                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  微信读书 ←→ Wewe-RSS服务 ←→ RSS订阅 ←→ 采集器 → AI分析 → 推送 │
│                (独立部署)                                        │
└─────────────────────────────────────────────────────────────────┘
```

#### Wewe-RSS 集成

Wewe-RSS 是一个独立的微信读书 RSS 服务，需要单独部署：

```
docker-compose.yml (Wewe-RSS)
├── 服务端口: 4000
├── 登录方式: 扫码登录微信读书
├── 输出格式: RSS/JSON
└── 认证方式: Basic Auth
```

#### 采集策略

**为什么采用手动触发？**

微信对频繁扫描有限流机制，自动定时扫描容易触发限流。因此采用手动触发模式：

```
触发方式：手动执行命令
执行频率：每天 1 次（建议早上 8:00-10:00）
处理范围：3天内发布的文章
```

**分批采集模式**

```yaml
# 避免一次性扫描所有公众号
batch_collection:
  enabled: true
  schedule:
    - batch_a: 周一、三、五、日  # 14个公众号
    - batch_b: 周二、四、六      # 13个公众号
```

#### AI 分析流程

```
1. 单篇摘要：为每篇文章生成 200 字摘要
     ↓
2. 话题聚合：将多篇文章按话题聚类
     ↓
3. 综合分析：整合同一话题下多篇文章的观点
     ↓
4. 日报生成：生成结构化 HTML 日报
```

#### 公众号分类

| 类别 | 数量 | 示例 |
|------|------|------|
| AI科技 | 6 | 新智元、量子位、机器之心 |
| 具身智能 | 4 | 第一具身范式、具身智能之心 |
| 科技商业 | 6 | 虎嗅APP、36氪、极客公园 |
| 财经投资 | 7 | 猫笔刀、口罩哥研报、雪球 |
| 港美股 | 2 | HK EX New-listing |
| 财经媒体 | 2 | 证券时报、红色星际 |

---

### 3.4 投资模块 (Investment)

#### 功能概述

采集 A 股、港股、美股行情数据和财经新闻，AI 生成投资简报，每天多次推送。

#### 数据源

```
┌─────────────────────────────────────────────────────────────────┐
│                    投资数据源                                    │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  指数数据                        新闻数据                        │
│  ├── A股: AKShare               ├── 财经网站爬虫                │
│  ├── 港股: yfinance             ├── RSS 订阅                    │
│  └── 美股: yfinance              └── 热榜数据                    │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

#### 关注指数

| 市场 | 指数 | 数据源 |
|------|------|--------|
| A股 | 上证指数、深证成指、创业板指 | AKShare |
| 港股 | 恒生指数、恒生科技 | yfinance |
| 美股 | 道琼斯、纳斯达克、标普500 | yfinance |

#### 推送时间

```
A股/港股档：
├── 06:00 - 早盘前（隔夜美股影响）
├── 11:30 - 午间（上午行情总结）
└── 23:30 - 收盘后（全天行情分析）

美股档（可选）：
└── 23:00 - 美股开盘前
```

#### AI 简报结构

```
投资简报
├── 市场概览
│   ├── 指数涨跌
│   └── 成交额
├── 板块动向
│   ├── 热门板块
│   └── 资金流向
├── 重要新闻
│   └── 财经要闻摘要
└── AI 分析
    └── 市场趋势判断
```

---

### 3.5 日志监控模块 (Daily Report)

#### 功能概述

每天收集各模块的执行日志，汇总成报告并在 23:30 推送。

#### 监控内容

```
日志报告结构
├── 投资模块
│   ├── 执行次数
│   ├── 成功/失败统计
│   └── 错误信息
├── 播客模块
│   ├── 处理节目数
│   ├── 成功/失败统计
│   └── 失败节目列表
├── 社区模块
│   ├── 采集条目数
│   └── AI 筛选结果
└── 系统状态
    ├── 容器运行时间
    └── 资源使用情况
```

#### 日志解析

```python
# 从容器日志中提取关键信息
def parse_task_results(logs: str) -> dict:
    results = {
        "investment": {
            "success": len(re.findall(r'投资报告推送成功', logs)),
            "failed": len(re.findall(r'投资报告推送失败', logs)),
        },
        "podcast": {
            "processed": len(re.findall(r'处理完成', logs)),
            "errors": re.findall(r'ERROR.*播客', logs),
        },
        # ...
    }
    return results
```

---

## 4. 核心技术实现

### 4.1 语音转写 (ASR)

#### AssemblyAI（推荐）

```python
# 核心配置
transcriber = ASRTranscriber(
    backend="assemblyai",
    assemblyai_api_key="your_api_key",
    speaker_labels=True,      # 启用说话人分离
    language="auto",          # 自动检测语言
)
```

**特点**：
- 说话人分离：自动识别多人对话
- 长音频支持：单文件最大 10 小时
- 价格：$0.17/小时（含说话人分离）

#### SiliconFlow SenseVoice

```python
transcriber = ASRTranscriber(
    backend="siliconflow",
    api_key="your_api_key",
    model="FunAudioLLM/SenseVoiceSmall",
)
```

**特点**：
- 快速转写：适合批量处理
- 不支持说话人分离
- 价格更低

#### 本地 WhisperX

```python
transcriber = ASRTranscriber(
    backend="local",
    local_api_url="http://localhost:5000",
    diarize=True,
    min_speakers=2,
    max_speakers=5,
)
```

**特点**：
- 需要本地 GPU
- 隐私保护
- 无 API 费用

### 4.2 AI 分析

#### DeepSeek R1 推理模型

```python
# AI 分析器配置
analyzer = PodcastAnalyzer(
    model="deepseek/deepseek-ai/DeepSeek-V3.2",
    api_base="https://api.siliconflow.cn/v1",
    api_key="your_api_key",
    max_tokens=64000,        # 思考模式最大输出
    enable_thinking=True,    # 启用思考模式
)
```

#### 提示词设计思路

**结构化输出原则**：

```
1. 明确输出格式：使用 Markdown 标题结构
2. 固定章节顺序：核心摘要 → 关键要点 → 详细内容
3. 多语言支持：中文/英文/双语输出
4. 字段定义：每个字段的用途和格式
```

**播客分析输出结构**：

```markdown
## 核心摘要
（3-5 句话概括主题）

## 关键要点
（5-8 个最重要的观点）

## 嘉宾观点
（不同说话人的立场）

## 精彩金句
（有深度的原话）

## 数据与数字
（具体数据、统计）

## 事件与动态
（行业新闻、产品发布）

## 内幕与洞察
（高价值信息）

## 分段落详述
（按话题深度展开）
```

### 4.3 通知推送

#### 邮件推送 (SMTP)

```yaml
# 配置示例
notification:
  channels:
    email:
      from: "sender@163.com"
      password: "your_auth_code"    # 授权码，非登录密码
      to: "receiver@example.com"
      smtp_server: "smtp.163.com"
      smtp_port: "465"
```

#### 即时通讯推送

```yaml
# 支持的 IM 渠道
channels:
  feishu:
    webhook_url: "https://open.feishu.cn/..."
  dingtalk:
    webhook_url: "https://oapi.dingtalk.com/..."
  wework:
    webhook_url: "https://qyapi.weixin.qq.com/..."
  telegram:
    bot_token: "123456:ABC-DEF..."
    chat_id: "123456789"
```

---

## 5. 定时任务配置

### 5.1 任务时间表

| 模块 | 触发时间 | 频率 | 说明 |
|------|----------|------|------|
| **播客** | 每4小时轮询 | 6次/天 | RSS 订阅检查新节目 |
| **投资** | 06:00/11:30/23:30 | 3次/天 | 早盘前、午间、收盘后 |
| **社区** | 18:00 | 1次/天 | 下午推送全球热点 |
| **公众号** | 23:00 | 手动触发 | 避免微信限流 |
| **日志报告** | 23:30 | 1次/天 | 每日执行汇总 |

### 5.2 Cron 配置

```bash
# 主程序定时任务（播客轮询）
0 */4 * * * cd /app && python -m trendradar

# 投资模块
0 6,11,23 * * * cd /app && python run_investment.py

# 社区模块
0 18 * * * cd /app && python run_community.py

# 日志报告
30 23 * * * cd /app && python daily_report.py
```

### 5.3 Docker 内调度

使用 Supercronic 作为 Docker 容器内的 cron 调度器：

```dockerfile
# Dockerfile
RUN pip install supercronic
CMD ["supercronic", "/etc/crontab"]
```

---

## 6. 配置参考

### 6.1 主配置文件结构

```yaml
# config/config.yaml

# 基础设置
app:
  timezone: "Asia/Shanghai"

# 播客模块
podcast:
  enabled: true
  poll_interval_minutes: 240    # 4小时
  max_episodes_per_run: 1
  new_episode_threshold_days: 2

  # ASR 配置
  asr:
    backend: "assemblyai"
    language: "auto"
    assemblyai:
      api_key: "your_assemblyai_key"
      speaker_labels: true

  # AI 分析
  analysis:
    enabled: true
    model: "deepseek/deepseek-ai/DeepSeek-V3.2"
    api_key: "your_siliconflow_key"

  # 推送
  notification:
    enabled: true
    channels:
      email: true

# 社区模块
community:
  enabled: true
  proxy:
    enabled: true
    url: "http://host.docker.internal:7897"

  topics:
    - "AI"
    - "LLM"
    - "机器人"
    - "创业"

  sources:
    hackernews:
      enabled: true
      min_score: 10
      max_age_hours: 24

# 投资模块
investment:
  enabled: true
  schedule:
    cn:
      enabled: true
      times: ["06:00", "11:30", "23:30"]

  indices:
    - symbol: "sh000001"
      name: "上证指数"
      provider: "akshare"

# 公众号模块（独立服务）
# 见 wechat/config.yaml

# 日志报告
daily_log_report:
  enabled: true
  schedule_time: "23:30"
```

### 6.2 环境变量

```bash
# .env 文件

# AI API
SILICONFLOW_API_KEY=your_siliconflow_key
ASSEMBLYAI_API_KEY=your_assemblyai_key

# 邮件配置
EMAIL_FROM=sender@163.com
EMAIL_PASSWORD=your_auth_code
EMAIL_TO=receiver@example.com
EMAIL_SMTP_SERVER=smtp.163.com
EMAIL_SMTP_PORT=465

# 定时任务
CRON_SCHEDULE=0 */4 * * *

# 模块开关
PODCAST_ENABLED=true
INVESTMENT_ENABLED=true
COMMUNITY_ENABLED=true
```

---

## 7. 订阅源管理

### 7.1 播客订阅源

#### 中文播客（9个）

| ID | 名称 | RSS 地址 |
|----|------|----------|
| late-talk | 晚点聊 LateTalk | fireside.fm/latetalk/rss |
| touzishizhan | 投资实战派 | soundon.fm/... |
| yinghaihacker | 硬地骇客 | feed.xyzfm.space/... |
| the-prompt | The Prompt | rsshub.bestblogs.dev/... |
| the-alphaist | The Alphaist | rsshub.bestblogs.dev/... |
| on-board | On Board | rsshub.bestblogs.dev/... |
| guigu101 | 硅谷101 | rsshub.bestblogs.dev/... |
| zhangxiaojun | 张小珺商业访谈录 | rsshub.bestblogs.dev/... |
| luoyonghao | 罗永浩的十字路口 | rsshub.bestblogs.dev/... |

#### 英文播客（8个）

| ID | 名称 | RSS 地址 |
|----|------|----------|
| latent-space | Latent Space | rss.art19.com/latent-space-ai |
| lex-fridman | Lex Fridman Podcast | lexfridman.com/feed/podcast/ |
| joe-rogan | The Joe Rogan Experience | feeds.libsyn.com/125135/rss |
| acquired | Acquired | acquired.fm/episodes?format=rss |
| business-breakdowns | Business Breakdowns | feeds.megaphone.fm/breakdowns |
| huberman-lab | Huberman Lab | feeds.megaphone.fm/hubermanlab |
| modern-wisdom | Modern Wisdom | feeds.megaphone.fm/modernwisdom |
| a16z | The a16z Show | feeds.megaphone.fm/a16z |

#### 添加新播客

```yaml
# 在 config.yaml 中添加
podcast:
  feeds:
    - id: "my-new-podcast"
      name: "我的新播客"
      url: "https://example.com/feed.xml"
      enabled: true
      language: "zh"    # zh | en
```

### 7.2 社区数据源

```yaml
# 添加新的数据源
community:
  sources:
    # 自定义 HackerNews 搜索
    hackernews:
      enabled: true
      search_keywords:     # 自定义搜索关键词
        - "artificial intelligence"
        - "machine learning"

    # Reddit 子版块
    reddit:
      enabled: true
      subreddits:
        - "MachineLearning"
        - "artificial"
        - "startups"

    # GitHub Trending
    github:
      enabled: true
      languages:
        - "python"
        - "typescript"
```

### 7.3 公众号管理

通过 Wewe-RSS Web 界面管理：

```
1. 访问 http://localhost:4000
2. 扫码登录微信读书
3. 添加公众号
4. 获取 RSS 订阅地址
5. 配置到 wechat/config.yaml
```

---

## 8. 部署指南

### 8.1 Docker 部署（推荐）

```bash
# 1. 克隆项目
git clone <repository-url>
cd info_hub

# 2. 配置环境变量
cp agents/.env.example agents/.env
vim agents/.env

# 3. 启动服务
docker-compose up -d

# 4. 查看日志
docker logs -f infohub-app
```

### 8.2 本地运行

```bash
# 1. 安装依赖
pip install -r requirements.txt

# 2. 配置文件
cp config/config.yaml.example config/config.yaml
vim config/config.yaml

# 3. 运行主程序
python -m trendradar

# 4. 运行公众号服务（独立）
cd wechat && python main.py scheduler
```

### 8.3 环境要求

| 组件 | 版本要求 | 说明 |
|------|----------|------|
| Python | 3.10+ | 类型注解支持 |
| Docker | 20.0+ | 容器化部署 |
| SQLite | 3.x | 数据存储 |
| 内存 | 2GB+ | AI 分析需要 |

---

## 9. 效果展示

### 9.1 WeWe RSS 管理界面

**公众号列表管理**：
![WeWe RSS 公众号列表](../images/WeweRSS-公众号列表截图.png)

**扫码登录**：
![WeWe RSS 登录](../images/WeweRSS-登陆截图.png)

### 9.2 邮件推送效果

**公众号日报**：
![公众号日报](../images/微信公众号日报.png)

**播客更新通知**：
![播客更新](../images/播客更新Lex_Fridman_Openclaw.png)

**社区热点日报**：
![社区热点](../images/社区热点日报.png)

---

## 10. API 服务依赖

### 10.1 必需服务

| 服务 | 用途 | 获取地址 | 费用 |
|------|------|----------|------|
| **SiliconFlow** | AI 分析 | siliconflow.cn | 按量计费 |
| **AssemblyAI** | 语音转写 | assemblyai.com | $0.17/小时 |
| **邮箱 SMTP** | 邮件推送 | 163/Gmail 等 | 免费 |

### 10.2 可选服务

| 服务 | 用途 | 费用 |
|------|------|------|
| 代理服务 | 访问被墙网站 | 自建/购买 |
| 飞书/钉钉 | IM 推送 | 免费 |
| Telegram Bot | IM 推送 | 免费 |

### 10.3 API Key 获取指南

**SiliconFlow**：
1. 访问 https://siliconflow.cn
2. 注册账号
3. 进入控制台获取 API Key
4. 充值（按量计费）

**AssemblyAI**：
1. 访问 https://www.assemblyai.com
2. 注册账号（新用户 185 小时免费额度）
3. 获取 API Key

**163 邮箱授权码**：
1. 登录 163 邮箱
2. 设置 → POP3/SMTP/IMAP
3. 开启 SMTP 服务
4. 获取授权码（非登录密码）

---

## 附录

### A. 常见问题

**Q: 播客转写失败怎么办？**
A: 检查 AssemblyAI API Key 是否有效，确认账户余额充足。大文件（>500MB）可能需要分段处理。

**Q: 公众号采集被限流怎么办？**
A: 减少采集频率，使用分批采集模式，避免短时间内大量请求。

**Q: 邮件发送失败？**
A: 确认使用的是授权码而非登录密码，检查 SMTP 服务器地址和端口。

### B. 性能优化

1. **播客处理**：启用音频分段，并行处理多个分段
2. **AI 分析**：使用缓存避免重复分析
3. **数据库**：定期清理旧数据，优化查询索引

### C. 安全建议

1. **API Key 保护**：使用环境变量，不要硬编码
2. **.gitignore**：排除 `.env`、`*.db`、`output/` 等
3. **定期备份**：备份配置文件和数据库

---

**文档版本**: v1.0
**更新日期**: 2026-02-19
**作者**: InfoHub Team
