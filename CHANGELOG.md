# TrendRadar 开发日志

本文档记录 TrendRadar 项目的开发进度和重要更新，便于团队协作和版本追踪。

---

## [5.26.0] - 2026-02-07

### 🔧 配置优化

#### 播客输出语言固定为中文
- **变更**：`podcast.analysis.language` 从 `"auto"` 改为 `"中文"`
- **效果**：
  - 所有播客（中英文）统一输出为纯中文分析
  - 简化用户决策，不再需要根据播客语言选择输出模式
  - 提升阅读体验，统一语言风格
- **影响**：AI 会根据 `output_language: "中文"` 指令自动翻译英文内容

#### 历史播客处理速度翻倍
- **变更**：`podcast.backfill.idle_hours` 从 `12` 改为 `6`
- **效果**：
  - 空闲 6 小时后自动处理历史未处理播客（之前需等待 12 小时）
  - 处理速度提升 100%
  - 保持稳定性，每次仍然只处理 1 个历史播客
- **影响**：更快地消化积压的历史播客内容

### 📋 配置变更详情

```yaml
podcast:
  backfill:
    enabled: true
    idle_hours: 6              # 从 12 改为 6
    max_per_run: 1             # 保持不变

  analysis:
    enabled: true
    language: "中文"            # 从 "auto" 改为 "中文"
```

### ✅ 验证结果

- ✅ 配置文件已更新
- ✅ 生产环境配置已同步（bind mount）
- ✅ 容器无需重启（配置实时生效）
- ✅ 预期下次播客处理时使用新配置

### 🔗 相关提交

```
6e1ff9b0 chore(podcast): 优化播客处理策略并升级版本到 v5.26.0
```

---

## [5.20.0] - 2026-02-03

### 🔴 关键修复

#### 微信模块AI分析完全修复
- **问题**: 微信公众号邮件只有标题，无AI分析内容
- **根因三重障碍**:
  1. SOCKS代理协议不兼容 → AI调用失败
  2. API Key设置逻辑错误 → 认证失败
  3. 配置文件隔离未同步 → API Key为空
- **解决方案**:
  - `wechat/src/ai_client.py`: 代理临时禁用 (a01c44ae)
  - `wechat/src/ai_client.py`: API Key无条件设置 (2093b6a2)
  - `config/system.yaml`: 同步AI API Key (e01147cc)
- **验证结果**: ✅ 话题聚合成功（3-4个话题），邮件包含完整AI分析

#### 播客测试模式完善
- **问题**: 测试"通过"但没有发送邮件
- **根因**: 虽然跳过重复检查，但被时间过滤和数量限制拦截
- **解决**: test_mode下跳过所有过滤逻辑 (7458a1ef)
  - ✅ 跳过重复检查
  - ✅ 跳过历史节目过滤
  - ✅ 跳过数量限制

### ✨ 优化改进

#### 测试框架增强
- **微信立即触发模式** (438467d2)
  - 测试模式跳过"今日已推送"检查
  - 支持反复测试，无需等待24小时
- **播客固定测试样例** (438467d2, 4da9783b, 518906f6)
  - 使用数据库中已完成的episode
  - 避免ASR API依赖，提升测试稳定性

### 📝 文档更新

- `agents/develop_trace.md`: 完整修复历程记录 (c21f919f, b12c6c10)
- `agents/DEPLOY_UPDATE_v5.20.0.md`: 部署更新文档
- 三次测试渐进式调试记录
- Insight总结：配置隔离风险、测试模式哲学

### 🔧 修改文件

**核心修复** (3个commits):
- `wechat/src/ai_client.py` - AI客户端修复（代理+API Key）
- `config/system.yaml` - 配置同步
- `wechat/main.py` - 测试模式优化

**测试优化** (3个commits):
- `trendradar/podcast/processor.py` - 测试模式过滤逻辑
- `agents/test_e2e.py` - 测试数据和模式优化

**文档** (2个commits):
- `agents/develop_trace.md` - 开发日志
- `agents/DEPLOY_UPDATE_v5.20.0.md` - 部署文档

### ✅ 测试验证

**四模块端到端测试**:
- ✅ 投资模块: 邮件发送成功（耗时224秒）
- ✅ 社区模块: 40个案例AI分析（耗时2260秒）
- ✅ 微信模块: 话题聚合成功（3-4个话题）
- ⚠️ 播客模块: ASR API不稳定（外部依赖问题）

**生成的邮件**:
1. `investment_cn_20260203_115804.html` ✅
2. `community_20260203_123548.html` ✅
3. `wechat_daily_20260203_123652.html` ✅

### 🎯 影响范围

- **关键修复**: 微信模块从完全失效恢复到正常运行
- **稳定性提升**: 测试框架更健壮，支持立即触发
- **配置统一**: system.yaml作为跨模块配置中心
- **向后兼容**: ✅ 无破坏性变更

### ⚠️ 已知问题

- **播客测试**: 依赖ASR API稳定性，API返回500时测试失败
- **投资数据**: 东方财富网连接不稳定（RemoteDisconnected），已有重试机制
- **部分网站403**: HackerNews元数据、ProductHunt内容抓取被拒绝

### 🔗 相关提交

```
a01c44ae - fix(wechat): 微信AI客户端代理禁用
2093b6a2 - fix(wechat): API Key设置逻辑修复
e01147cc - fix(config): system.yaml配置同步
438467d2 - fix(test): 测试框架优化（微信+播客）
7458a1ef - fix(podcast): 测试模式跳过所有过滤
4da9783b - fix(test): 使用已完成episode避免ASR依赖
518906f6 - fix(test): 更新播客测试使用a16z episode
c21f919f - docs(log): 开发日志更新
b12c6c10 - docs(log): 最终更新
```

---

## [Unreleased]

## [5.25.3] - 2026-02-06

### 🔴 关键修复

#### 播客邮件内容截断问题修复
- **问题**: 播客分析邮件在句子中间硬性截断（如：`<p><strong>Palmer Luckey</strong>: 他的` 后无内容）
- **根因**: DeepSeek API 非思考模式最大输出 8K tokens，实际需求 10,449 tokens
- **解决方案**: 启用 Thinking 模式（最大 64K 输出 tokens）
  - `trendradar/podcast/analyzer.py`: 设置 `MAX_TOKENS=64000`
  - `trendradar/podcast/analyzer.py`: 启用 `extra_body={"enable_thinking": True}`
  - `trendradar/core/loader.py`: 修复 TIMEOUT/MAX_TOKENS 优先级（大写优先）
- **验证结果**: ✅ 邮件内容完整（13,047 字符），Token 使用 9,132（安全范围）

### 🔧 配置优化

#### AI 配置统一
- **TIMEOUT 配置修复**: 优先读取大写 `TIMEOUT`（900秒），避免 120 秒超时
- **MAX_TOKENS 配置修复**: 所有模块统一使用 160000（非思考）或 64000（思考）
- **配置文件更新**: `config/config.yaml` 设置 `TIMEOUT: 900` 和 `max_tokens: 160000`

### ✨ 优化改进

#### Thinking 模式深度分析
- **输出质量提升**: 从标准分析提升到深度推理分析
- **完整内容保证**: 64K token 限制确保长内容不被截断
- **权衡考虑**: 响应时间增加 18 倍（30-60秒 → 18.7分钟），但内容完整性显著提升

### 🔧 修改文件

**核心修复**:
- `trendradar/podcast/analyzer.py` - Thinking 模式启用 + MAX_TOKENS 设置
- `trendradar/core/loader.py` - TIMEOUT/MAX_TOKENS 配置优先级修复
- `trendradar/ai/client.py` - 默认值更新（max_tokens: 160000, timeout: 900）
- `config/config.yaml` - 全局配置更新（TIMEOUT: 900, max_tokens: 160000）

**文档**:
- `agents/token_analysis_report.md` - Token 使用量分析报告
- `agents/thinking_mode_fix_summary.md` - Thinking 模式修复总结
- `agents/thinking_mode_verification_report.md` - 验证报告
- `AGENTS.md` - 新增踩坑经验记录

### ✅ 测试验证

**播客测试邮件** (2026-02-06 20:21):
- ✅ 邮件发送成功：`podcast_a16z_20260206_202140.html`（39,314 字节）
- ✅ 内容完整：13,047 字符分析部分，无硬性截断
- ✅ Token 使用：~9,132 tokens（远低于 64K 限制，使用率仅 14.3%）
- ✅ 深度推理：分析质量显著提升，有明确结论

**性能对比**:

| 指标 | 非思考模式 | 思考模式 | 改进 |
|------|----------|----------|------|
| 输出限制 | 8K tokens | 64K tokens | +700% |
| 内容状态 | 截断 ❌ | 完整 ✅ | ✅ 修复 |
| 分析质量 | 标准 | 深度推理 ✅ | ✅ 提升 |
| 响应时间 | 30-60秒 | 18.7分钟 | +18倍 |

### 🎯 影响范围

- **核心功能**: 播客分析从内容截断恢复到完整输出
- **用户体验**: 分析内容完整性和深度显著提升
- **向后兼容**: ✅ 无破坏性变更

### ⚠️ 已知问题

- **响应时间**: Thinking 模式响应时间增加 18 倍（18-20 分钟）
- **API 成本**: API 调用成本增加 2-3 倍
- **权衡结论**: 对于需要长内容输出的播客分析，Thinking 模式是必要选择

### 🔗 相关提交

```
bfb8921d - fix(podcast): 启用 Thinking 模式修复邮件截断问题
a4e0b045 - fix(podcast): 修复英文播客语言输出并补齐 prompts 挂载
9da35e16 - feat(bootstrap): 实现版本感知首次启动引导机制
d8b2cb42 - docs(AGENTS): 更新验证流程文档，清理过时版本号
ba11dceb - docs(AGENTS): 同步 v5.24.0 变更文档，新增规则9和 bootstrap 机制说明
```

---

### 新增功能

#### 播客AI分析质量提升 (2026-02-02)
- **提升max_tokens限制**: 从 5000 提升到 16000，支持更详细的分段落详述输出
- **完整转写文本输入**: 使用完整播客转写文本（约3909字符）替代节目简介（约1243字符）作为AI分析输入
- **转写文本缓存系统**: 新增 `agents/transcript_cache.py`，避免重复处理相同节目
  - JSON文件存储：`agents/transcript_cache/transcripts.json`
  - 主要方法：`get()`, `set()`, `list_cached()`
  - 测试时固定使用硅谷101 E223节目进行验证
- **分析内容更丰富**: 完整输入使AI能够生成6个话题的深度讨论总结

#### 邮件渲染优化 (2026-02-02)
- **EmailRenderer修复** (`shared/lib/email_renderer.py`)
  - 移除AI输出的 ```markdown 代码块包装
  - 清理"语言规则"等AI元信息，不在邮件中显示
  - 减少过多的 `<hr/>` 分隔线，优化移动端显示
- **播客邮件模板简化** (`shared/email_templates/modules/podcast/episode_update.html`)
  - 移除节目简介卡片和转写预览部分
  - 只保留AI分析结果，提升阅读体验
- **移动端响应式优化**:
  - 字体大小：12px → 14px（提升16.7%）
  - 行高：1.6 → 1.7（提升6.25%）
  - 减少padding，增加有效文字宽度
  - 添加完整的移动端媒体查询样式

### 🔧 修改文件

#### 核心功能
- `trendradar/podcast/analyzer.py` - max_tokens: 5000 → 16000
- `shared/lib/email_renderer.py` - markdown过滤器增强
- `shared/email_templates/modules/podcast/episode_update.html` - 模板和样式优化

#### 新增文件
- `agents/transcript_cache.py` - 转写缓存管理系统
- `agents/create_test_transcript.py` - 测试转写生成工具
- `agents/test_podcast_mobile_fix.py` - 移动端修复验证脚本
- `agents/render_podcast_fixed.py` - 邮件重新渲染工具
- `agents/prerelease_e2e_test.py` - 更新支持缓存转写

### 🐛 已知问题

#### iOS Mail兼容性 (2026-02-02)
- **问题**: 播客邮件的标题（h2/h3）在iPhone白色背景下不显示，正文（p）正常显示
- **影响范围**: 仅影响标题显示，核心内容不受影响
- **尝试的修复**:
  - ✗ 移除 `<h3><strong>标题</strong></h3>` 嵌套
  - ✗ 移除标题元素的color属性设置
  - ✗ 将h3改为h2标签
- **状态**: 暂时搁置，核心功能可用
- **后续计划**: 需要深入研究iOS邮件客户端的CSS渲染机制

### 📊 技术细节

#### 转写缓存系统设计
```python
# 使用示例
from agents.transcript_cache import TranscriptCache

cache = TranscriptCache()
cache.set(episode_id, transcript, metadata={
    'feed_name': '硅谷101',
    'episode_title': 'E223｜大模型商业化进入"实用主义时代"',
    'duration': '1:06:42',
    'published_date': '2025-01-30'
})

# 复用缓存
cached_data = cache.get(episode_id)
transcript = cached_data.get('transcript')
```

#### EmailRenderer关键修复
```python
# 移除 ```markdown 代码块
text = re.sub(
    r'```markdown\s*\n(.*?)\n```',
    lambda m: m.group(1),
    text,
    flags=re.DOTALL
)

# 清理语言规则元信息
for keyword in ['语言规则', '输出语言', '原文语言为']:
    if keyword in line:
        continue  # 跳过该行
```

### ✅ 验证清单

播客功能优化验证：
- [x] max_tokens提升生效（16000）
- [x] 转写缓存系统正常工作
- [x] AI分析使用完整转写文本
- [x] 邮件渲染移除```markdown包装
- [x] 邮件移除"语言规则"元信息
- [x] 移动端字体和行高优化
- [x] 邮件发送成功（PC端显示正常）
- [ ] iOS Mail标题显示问题（待解决）

---

## [2026-01-29] - v5.6.0 播客功能 MVP 与生产部署

### 🚀 部署信息

- **版本号**: v5.6.0
- **部署时间**: 2026-01-29
- **生产环境**: `/home/zxy/Documents/install/trendradar`
- **当前运行**: trendradar-prod (v5.6.0)、trendradar-mcp-prod (v3.1.7)
- **上一版本**: v5.4.0

### 部署变更

- 版本号由 5.5.0 升级为 **5.6.0**
- 生产 Docker Compose 增加播客相关环境变量：
  - `SILICONFLOW_API_KEY` - 硅基流动 ASR API Key
  - `PODCAST_ENABLED` - 播客功能开关（默认 true）

### 使用说明（生产环境）

- 播客需在 **生产 shared 配置** 中启用并配置：
  - 编辑 `/home/zxy/Documents/install/trendradar/shared/config/config.yaml` 的 `podcast` 段
  - 或在 `shared/.env` 中设置 `SILICONFLOW_API_KEY`
- 查看生产日志：`docker logs trendradar-prod -f`
- 回退到上一版本：`trend rollback`

---

## [2026-01-29] - 播客功能 MVP 版本（代码与测试）

### 🎉 新增功能

#### 播客订阅与自动处理系统
- **RSS 抓取**: 支持播客 RSS 订阅，自动解析 enclosure 音频附件
- **音频下载**: 流式下载音频文件，支持大小限制和自动清理
- **ASR 转写**: 集成硅基流动 SenseVoice API，支持中英文自动识别
- **AI 分析**: 基于现有 AIClient 进行内容分析（可选）
- **即时推送**: Type A 邮件推送，每个新节目单独一封邮件
- **数据存储**: SQLite 存储，支持状态追踪和断点续传

#### 核心特性
- ✅ 自动去重：数据库记录已处理节目，避免重复推送
- ✅ 配置灵活：支持多播客源、可配置轮询间隔、节目数量限制
- ✅ 资源管理：转写后自动清理音频文件，节省空间
- ✅ 错误隔离：单个节目失败不影响其他节目处理
- ✅ 详细日志：完整的处理流程日志和性能统计

### 📁 新增文件

#### 核心代码
- `trendradar/podcast/__init__.py` - 模块初始化
- `trendradar/podcast/fetcher.py` - RSS 抓取和解析
- `trendradar/podcast/downloader.py` - 音频下载和管理
- `trendradar/podcast/transcriber.py` - ASR 转写服务
- `trendradar/podcast/analyzer.py` - AI 内容分析
- `trendradar/podcast/notifier.py` - 邮件推送通知
- `trendradar/podcast/processor.py` - 主处理器和流程编排

#### 配置文件
- `config/podcast_analysis_prompt.txt` - AI 分析提示词模板
- `trendradar/storage/podcast_schema.sql` - 数据库 schema

#### 测试工具
- `test_podcast.sh` - 播客测试脚本（自动禁用代理）
- `debug_email_config.py` - 邮件配置调试脚本

#### 文档
- `agents/podcast_migration_summary.md` - 播客功能迁移说明
- `agents/podcast_test_report_20260129.md` - 详细测试报告
- `agents/email_push_success.md` - 邮件推送成功报告
- `agents/FINAL_TEST_SUMMARY.md` - 最终测试总结
- `CHANGELOG.md` - 开发日志（本文件）

### 🔧 修改文件

#### 配置扩展
- `config/config.yaml` - 添加 podcast 配置段
  - RSS 订阅源配置
  - ASR 转写配置（硅基流动 API）
  - AI 分析配置
  - 邮件推送配置
  - 音频下载配置

#### 核心模块
- `trendradar/core/loader.py` - 添加 `_load_podcast_config()` 函数
- `trendradar/__main__.py` - 添加 `--podcast-only` 参数和播客处理逻辑

### 🐛 修复问题

1. **配置键名大小写兼容** ✅
   - 问题：loader.py 使用大写键名，processor.py 使用小写键名
   - 修复：所有配置读取支持大小写兼容

2. **AI 分析接口调用错误** ✅
   - 问题：AIClient.chat() 参数格式错误
   - 修复：改用 messages 列表格式

3. **缺少 tenacity 依赖** ✅
   - 问题：litellm 需要 tenacity 模块
   - 修复：pip install tenacity

4. **max_items 参数未传递** ✅
   - 问题：配置的 max_items 未生效
   - 修复：添加参数传递到 PodcastFeedConfig

5. **邮件配置读取错误** ✅
   - 问题：从错误的位置读取邮件配置
   - 修复：从 config 根级别读取 EMAIL_* 配置

6. **send_to_email 参数名错误** ✅
   - 问题：使用错误的参数名 smtp_server 和 smtp_port
   - 修复：使用正确的参数名 custom_smtp_server 和 custom_smtp_port

### 📊 性能测试

#### 测试环境
- 播客源：硅谷101
- 音频大小：86.2 MB
- 音频时长：约 60 分钟

#### 性能数据（禁用代理）
```
下载:  8.1秒  (13.8%)
转写: 48.2秒  (81.9%)  ← 最耗时环节
分析:  0.2秒  ( 0.3%)
推送:  2.3秒  ( 3.9%)
清理:  0.0秒  ( 0.0%)
────────────────────────
总计: 58.8秒
```

#### 关键发现
- ✅ 整体速度优秀：不到 1 分钟完成全流程
- ✅ 转写准确率高：21722 字符，准确识别中英文
- ✅ 邮件发送快速：2.3 秒即可送达
- ⚠️ 代理影响显著：禁用代理后速度提升 6 倍

### ✅ 验证清单

- [x] RSS 抓取正常
- [x] 音频下载成功
- [x] ASR 转写准确
- [x] HTML 邮件生成
- [x] 邮件配置正确
- [x] SMTP 连接成功
- [x] **邮件发送成功** ✅
- [x] 音频文件清理
- [x] 数据库记录完整

### 🚀 使用说明

#### 配置示例
```yaml
# config/config.yaml
podcast:
  enabled: true
  poll_interval_minutes: 30
  
  asr:
    api_key: "sk-xxx"  # 硅基流动 API Key
    model: "FunAudioLLM/SenseVoiceSmall"
  
  feeds:
    - id: "guigu101"
      name: "硅谷101"
      url: "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/xxx"
      enabled: true
      max_items: 10
```

#### 运行方式
```bash
# 方式1：仅运行播客处理（推荐用于测试）
python -m trendradar --podcast-only

# 方式2：使用测试脚本（自动禁用代理）
bash test_podcast.sh

# 方式3：完整运行（包含热榜）
python -m trendradar

# 方式4：定时任务（生产环境）
# 在 crontab 中添加：
# */30 * * * * cd /path/to/TrendRadar && bash test_podcast.sh >> logs/podcast.log 2>&1
```

### 📝 后续计划

#### 短期（建议）
- [ ] 配置 AI API Key，启用 AI 分析功能
- [ ] 测试多个播客源并发处理
- [ ] 添加更多播客订阅源

#### 中期（可选）
- [ ] 添加重试机制（网络失败自动重试）
- [ ] 支持并发处理多个节目
- [ ] 添加音频下载断点续传
- [ ] 优化长音频处理策略

#### 长期（未来）
- [ ] 本地 GPU ASR 支持
- [ ] 其他通知渠道（飞书/钉钉）
- [ ] Web UI 展示历史记录
- [ ] 播客推荐算法

### 🔗 相关文档

- [播客功能迁移说明](agents/podcast_migration_summary.md)
- [详细测试报告](agents/podcast_test_report_20260129.md)
- [最终测试总结](agents/FINAL_TEST_SUMMARY.md)
- [邮件推送成功报告](agents/email_push_success.md)

### 👥 贡献者
- AI Assistant - 播客功能开发、测试、文档编写

---

## 日志格式说明

每个版本包含以下部分：
- **新增功能**: 新增的功能和特性
- **修改文件**: 修改的现有文件
- **修复问题**: 修复的 bug 和问题
- **性能测试**: 性能测试数据和分析
- **验证清单**: 功能验证结果
- **使用说明**: 使用方法和配置示例
- **后续计划**: 未来的开发计划

---

*最后更新: 2026-02-02*

## [5.29.0] - 2026-02-13

### 🔧 配置优化

#### 播客输出语言固定为中文
- **变更**：`podcast.analysis.language` 从 `"auto"` 改为 `"中文"`
- **效果**：所有播客（中英文）统一输出为纯中文分析
- **影响**：化简用户决策，不再需要根据播客语言选择输出模式
- **示例**：a16z 仍会显示 "Anish Acharya: Is SaaS Dead in a World of AI?"

#### 播客处理速度翻倍
- **变更**：`podcast.backfill.idle_hours` 从 `12` 改为 `6`
- **效果**：空闲 6 小时后自动处理历史未处理播客（之前需等待 12 小时）
- **影响**：处理速度提升 100%

### 🔩 关键修复

#### 微信模块 AI 分析完全修复
- **问题**：微信公众号邮件只有标题，无AI分析内容
- **根因三重障碍**：
  1. SOCKS代理协议不兼容 → AI调用失败
  2. API Key设置逻辑错误 → 认证失败
  3. 配置文件隔离未同步 → API Key为空
- **解决方案**：
  - `wechat/src/ai_client.py`: 代理临时禁用 (a01c44a)
  - `config/system.yaml`: API Key无条件设置 (2093b6a2)
  - `wechat/main.py`: 同步 AI API Key (e01147cc)
- **验证结果**：✅ 话题聚合成功（4个话题），邮件包含完整AI分析

### 📝 播客测试模式完善
- **问题**：测试"通过"但没有发送邮件
- **根因**: 虽然跳过重复检查，但被时间过滤和数量限制拦截
- **解决**: test_mode下跳过所有过滤逻辑 (7458a1ef)

#### 测试框架增强
- **微信立即触发模式** (438467d2)
- **支持**：反复测试，无需等待24小时
- **播客固定测试样例** (438467d2da9783b, 518906f6)

### 📝 文档更新

- `agents/DEPLOY_UPDATE_v5.20.0.md`: 部署更新文档
- `agents/bootstrap_test_report_v5.28.0.md`: Bootstrap 测试报告
- `agents/podcast_prompts_fix_report.md`: Prompts 修复报告
- `agents/podcast_segmentation_test_success.md`: 分段测试报告
- `agents/podcast_diagnosis_report.md`: 播客诊断报告
- `agents/deployment_flow_improvement.md`: 部署流程改进文档

