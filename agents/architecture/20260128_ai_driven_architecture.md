# TrendRadar 下一阶段：AI 驱动信息整合架构方案（草案）

更新时间：2026-01-28  
目标：在现有 TrendRadar「抓取 → 存储 → 报告 → 通知(邮件)」的数据流基础上，扩展为“以 AI 为核心驱动”的多来源、多任务、多触发范式。

---

## 1. 现状基线（基于仓库当前结构）

现有系统能力（已具备，可复用）：
- **数据源**：热榜平台（`platforms`）、RSS（`rss.feeds`）
- **AI**：统一模型配置（`config/config.yaml: ai`），AI 分析（`ai_analysis`）、翻译（`ai_translation`）
- **推送**：多渠道通知（含 email），已有批量发送/分片逻辑
- **存储**：SQLite + HTML/TXT 快照（本地/远程）

结论：新功能应尽量 **复用“配置驱动 + pipeline + 存储 + 通知”** 的既有结构，只新增“信息源适配器”和“任务调度/触发”层。

---

## 2. 新目标需求拆解（按任务域）

需求域（来自 `agents/tasks/20260128_task.txt`）：

1) **播客**  
- 输入：播客 RSS（含音频 enclosure）  
- 触发：检测到更新立即处理  
- 处理：音频 → 文字（可能中英）→ 按指定 prompt 生成结构化内容  
- 推送：**单独邮件，事件触发即发**

2) **公众号**  
- 输入：指定公众号（每日拉取当天文章）  
- 触发：每天定时  
- 处理：抓取正文 → 按 prompt 输出  
- 推送：**每日聚合一次集中推送**

3) **需要登录/反爬的网站**（Twitter/X、HackerNews、Kickstarter 等）  
- 输入：指定话题/账号/列表/关键词  
- 触发：定时  
- 处理：抓取/检索 → 去重 → 摘要/归纳 → 按 prompt 输出  

4) **投资板块**  
- 输入：投资信号（待定义），可能包含公众号大V、财经网站、公告、研报摘要等  
- 触发：定时  
- 推送：**港股/A股：中午一次；美股：晚上 23:00 一次**

5) **固定话题（不限制来源）**  
- 输入：上述已抓取/检索的内容 +（可扩展）搜索/外部API  
- 触发：定时（建议每日/每小时可配）  
- 输出：围绕话题的“知识整合/洞察/风险点/行动建议”

---

## 3. 总体架构：Source → Normalize → Store → Task Pipelines → Notify

### 3.1 核心设计原则
- **配置驱动**：新增的信息源、prompt、调度策略全部可在 `config/` 中管理（可热更新/重启生效）。
- **可插拔适配器**：不同来源（podcast/wechat/x/…）统一抽象为 `SourceAdapter` 输出标准 `Document`。
- **任务与来源解耦**：同一份文档可被多个“任务”消费（例如：投资任务 + 话题任务共用公众号内容）。
- **幂等与去重**：以 `source_id + item_id + content_hash` 去重；同一内容多次抓取不应重复推送。
- **可追溯**：原始内容、转写文本、AI 结果、推送记录均可落库，便于复盘与调试。

### 3.2 数据对象（建议的标准化模型）
建议新增一套内部标准对象（名称可自行调整）：
- `SourceItem`：来源侧原始条目（标题、URL、发布时间、作者、附件/音频URL、原始HTML/文本、元数据）
- `Document`：标准化文档（已抽取正文纯文本 + 语言检测 + 主题标签 + 结构化字段）
- `Artifact`：派生物（转写文本、翻译文本、摘要、要点、行动建议等）
- `Delivery`：一次推送记录（类型、收件人、主题、内容摘要、发送时间、关联文档/派生物）

落库层：可复用现有 SQLite；必要时新增表（podcast/wechat/artifacts/delivery_log 等）。

---

## 4. 任务/调度层：多触发、多邮件类型

### 4.1 邮件类型（明确与需求一致）
- **Type A：播客事件邮件**  
  - 触发：RSS 发现新 episode 即触发  
  - 频率：事件驱动  
  - 内容：单 episode 全量/要点/时间戳段落（可选）+ AI 结构化输出

- **Type B：公众号 & 门户网站 日报聚合**  
  - 触发：每天固定时间（建议可配多个时段）  
  - 内容：当天新增文章/重要内容聚合 + 话题分组

- **Type C：投资板块分市场定时**  
  - 触发：港股/A股（中午），美股（23:00）  
  - 内容：投资信号汇总 + 风险提示 +（明确声明）非投资建议/仅供参考

### 4.2 调度实现建议（不写代码的落地建议）
两种落地路径（按部署形态选择）：

1) **GitHub Actions / Cron 驱动（轻量）**  
- 用多个 workflow/cron 触发不同任务入口（podcast / daily / invest_cn / invest_us）  
- 优点：简单；缺点：事件触发（播客）不够实时（除非高频 cron，成本与配额压力）。

2) **Docker 常驻调度（推荐）**  
- 通过内部 scheduler（APScheduler/自研简单调度）实现：
  - 定时任务（日报、投资）
  - 轮询任务（podcast RSS 每 N 分钟检测更新）
- 优点：满足“更新即触发”；缺点：需要常驻服务与日志运维。

建议：先实现 **Docker 常驻调度**，GitHub Actions 作为备选/补充。

---

## 5. Prompt 与模型：配置化 + 可按任务/来源覆盖

### 5.1 Prompt 管理
现有已经支持 `ai_analysis.prompt_file`、`ai_translation.prompt_file`。建议扩展为：
- 按“任务”维度管理：podcast/wechat/topic/invest 等
- 按“来源”可覆盖：同任务不同来源可用不同 prompt（例如：播客更偏口语转要点；公众号偏结构化综述）

推荐目录结构（示例）：
- `config/prompts/podcast.md`
- `config/prompts/wechat_daily.md`
- `config/prompts/topic_digest.md`
- `config/prompts/invest_cn.md`
- `config/prompts/invest_us.md`

### 5.2 模型选择
你可提供 SiliconFlow（或其他）API。建议的模型策略：
- **转写**：Whisper/ASR 专用模型（不走通用 chat 模型）
- **总结/结构化**：通用大模型（可复用现有 LiteLLM 配置）
- **翻译**：可选（若转写/正文是英文，可直接用翻译 prompt 或在总结 prompt 内要求双语输出）

建议支持“任务级”模型覆盖：
- 全局默认：`ai.model`
- 任务覆盖：`tasks.<task>.ai.model`（如 podcast 用更长上下文/更强模型）

---

## 6. 信息源适配器方案（关键风险与落地路径）

### 6.1 播客（Podcast RSS + 音频转写）
推荐流程：
1. 订阅 RSS → 抓取新 episode（enclosure 音频 URL）
2. 下载音频（可做缓存/断点续传/大小限制）
3. ASR 转写（Whisper API）
4. 语言检测（或由模型自行判断）
5. 按 `podcast` prompt 输出结构化结果（标题/摘要/要点/时间戳段落可选）
6. 生成 **Type A** 邮件并发送

工程注意点：
- 音频较大：需要 **大小上限**、**超时**、**失败重试**、**降级策略**（只发“未转写成功 + 原始链接”）
- 去重：episode GUID/链接 + 发布日期 + 音频 URL hash
- 存储：保留原始元信息与转写文本，便于复查

### 6.2 公众号（WeChat）
这是最大不确定性/风险点，建议先选定可行数据获取方式。

可选路径（按推荐顺序）：
1) **公众号 → RSS 的第三方服务**（稳定但可能付费）  
- 输入：RSS feed（本质上变成“普通 RSS 文本源”）  
- 优点：与现有 RSS 管道天然兼容

2) **网页抓取（搜狗/镜像站）**  
- 风险：反爬、可用性不稳定、内容缺失

3) **浏览器自动化（Puppeteer/Playwright）**  
- 风险：维护成本最高，需要登录态、验证码、IP/指纹等对抗

建议阶段策略：
- **第一阶段**：先跑通“公众号 RSS 化”的方案（最小可用）
- **第二阶段**：再评估是否自建自动化抓取

### 6.3 Twitter/X、Kickstarter 等登录站
建议抽象成“AuthenticatedSourceAdapter”，支持：
- Cookie/Token 注入（通过环境变量/密文管理）
- 失败降级（只保留抓取元信息或跳过）
- 限速与重试

可行性提示：
- HackerNews：已有 RSS，可直接复用
- Twitter/X：优先使用官方 API（若有权限），否则需要第三方/Nitter（不稳定）
- Kickstarter：可能存在页面结构频繁变化与登录态问题

---

## 7. 投资板块：先定义“信号”再编码

建议你先把“投资信号”定义为配置化规则（便于迭代），例如：
- **事件类**：融资/并购/财报/监管/政策
- **情绪类**：某主题热度飙升（跨平台频次/排名）
- **价格类（可选）**：指数/标的日内波动阈值（若引入行情API）

输出建议：
- 明确区分：**事实摘要** vs **推测/观点** vs **风险提示**
- 对每条建议给出“证据链来源”（链接列表）
- 声明：非投资建议（合规/免责）

---

## 8. 固定话题（跨来源知识整合）

推荐做法：
- 输入：当天所有 `Document`（来自 RSS/公众号/登录站）+ 历史窗口（如 7 天）
- 处理：
  - 话题聚类（简单关键词/embedding 皆可，先用轻量规则）
  - 证据摘取（每个要点附来源）
  - 输出结构：背景 → 最新进展 → 关键参与者 → 风险/机会 → 接下来关注点
- 推送：可以并入日报（Type B）或单独一封（可配）

---

## 9. 配置草案（建议在 `config/config.yaml` 扩展）

以下为“形状建议”，不强制照抄：

```yaml
tasks:
  podcast:
    enabled: true
    poll_interval_minutes: 10
    feeds:
      - id: "podcast_x"
        name: "Podcast X"
        rss_url: "..."
    asr:
      provider: "siliconflow"
      model: "whisper-large-v3"   # 示例
      max_audio_mb: 200
    prompt_file: "prompts/podcast.md"
    delivery:
      type: "email_immediate"

  wechat_daily:
    enabled: true
    source:
      mode: "rss_proxy"           # rss_proxy | web_crawl | browser_automation
      feeds: [...]
    schedule: "0 20 * * *"
    prompt_file: "prompts/wechat_daily.md"
    delivery:
      type: "email_daily_digest"

  investment:
    enabled: true
    cn_schedule: "0 12 * * 1-5"
    us_schedule: "0 23 * * 1-5"
    prompt_file_cn: "prompts/invest_cn.md"
    prompt_file_us: "prompts/invest_us.md"
    sources: [...]
```

---

## 10. 分期实施建议（可直接拆成 coding 迭代）

### Phase 0：架构铺垫（先做“可扩展”底座）
- 增加“任务”概念与统一入口（podcast/daily/invest/topic）
- Prompt 管理升级：支持任务级 prompt 与可覆盖
- 新增投递类型：immediate vs digest（按邮件类型分流）
- 增加 delivery_log（避免重复发）

### Phase 1：播客 MVP（最高确定性、最能体现 AI 驱动）
- RSS 轮询检测新 episode
- 音频下载与 ASR 转写
- prompt 结构化输出
- Type A 即时邮件

### Phase 2：公众号 MVP（取决于数据源方案）
- 先接 RSS 代理服务（最小成本）
- 每日聚合推送（Type B）

### Phase 3：登录站/社交站（按可行性逐个接入）
- 先接“无需登录”的数据源（HN、公开 RSS）
- 再评估 Twitter/Kickstarter 的方案与维护成本

### Phase 4：投资板块（先规则化信号，再做深度）
- 先做“信息汇总 + 风险提示”的 MVP
- 再逐步引入行情/更复杂信号

---

## 11. 关键不确定性 & 需要提前做的决策

1) **公众号来源**：是否接受第三方 RSS 代理（付费/稳定）？若否，需接受更高维护成本。  
2) **播客转写服务**：SiliconFlow Whisper 是否可用/成本可控？（建议先跑 1-2 个播客验证）  
3) **部署形态**：是否以 Docker 常驻为主？（决定“更新即触发”的实现方式）  
4) **Twitter 数据**：是否有官方 API 权限？若无，替代方案的不稳定性需要接受。  
5) **投资信号定义**：先用“信息总结型”还是需要“可量化信号”？

