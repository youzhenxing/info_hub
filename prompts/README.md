# TrendRadar Prompt 文档

本目录包含各模块使用的 AI 分析 prompt 文件。

## 📁 文件命名规范

多阶段任务的 prompt 文件使用统一命名格式：
```
$模块_step序号_阶段描述.txt
```

例如：
- `investment_step1_article.txt` - 投资模块第1阶段：单篇分析
- `investment_step2_aggregate.txt` - 投资模块第2阶段：聚合分析
- `wechat_step1_summary.txt` - 公众号模块第1阶段：文章摘要

## 📁 文件列表

### 主目录 prompts/

| 文件 | 大小 | 使用模块 | 用途 | 代码位置 |
|------|------|----------|------|----------|
| `community_prompts.txt` | 4.8K | 社区监控 | HackerNews/Reddit 等社区内容分析 | `trendradar/community/analyzer.py` |
| `podcast_prompts.txt` | 4.2K | 播客监控 | 播客转写文本结构化总结 | `trendradar/podcast/analyzer.py` |
| `investment_step1_article.txt` | 1.4K | 投资模块 | **Step1**: 单篇财经新闻文章分析 | `trendradar/investment/analyzer.py:77` |
| `investment_step2_aggregate.txt` | 1.9K | 投资模块 | **Step2**: 多篇新闻聚合分析 | `trendradar/investment/analyzer.py:78` |

### 公众号模块 wechat/prompts/

| 文件 | 大小 | 使用模块 | 用途 | 代码位置 |
|------|------|----------|------|----------|
| `wechat_step1_summary.txt` | 2.2K | 公众号 | **Step1**: 单篇文章深度摘要 | `wechat/src/analyzer.py:28` |
| `wechat_step2_aggregate.txt` | 3.2K | 公众号 | **Step2**: 多篇文章话题聚合（JSON 输出） | `wechat/src/analyzer.py:29` |

## 🔧 配置方式

### 模块专用配置（推荐）

各模块通过 config.yaml 配置 prompt 文件路径：

```yaml
# 播客模块
podcast:
  analysis:
    prompt_file: "podcast_prompts.txt"

# 社区模块
community:
  analysis:
    prompt_file: "community_prompts.txt"

# 投资模块（代码中硬编码，不支持配置文件修改）
# trendradar/investment/analyzer.py:77-78
#   - step1: investment_step1_article.txt
#   - step2: investment_step2_aggregate.txt

# 公众号模块（代码中硬编码，不支持配置文件修改）
# wechat/src/analyzer.py:28-29
#   - step1: wechat_step1_summary.txt
#   - step2: wechat_step2_aggregate.txt
```

## 📝 Prompt 设计原则

### 1. 播客模块 (podcast_prompts.txt)
- **输入**：播客转写文本（包含说话人标签）
- **语言识别**：中文播客 → 中文，英文播客 → 中英双语
- **输出格式**：Markdown 结构化总结
- **核心特性**：说话人观点识别、关键洞察提取

### 2. 社区模块 (community_prompts.txt)
- **核心理念**：总结不是让内容更抽象，而是找到关键信息和 insight
- **重点**：提取具体数据、公司名、产品名、融资金额
- **避免**：泛泛而谈的抽象总结
- **输出格式**：Markdown，强调具体信息

### 3. 投资模块 (两阶段处理)
1. **investment_step1_article.txt**：单篇新闻文章分析
2. **investment_step2_aggregate.txt**：多篇新闻聚合分析

**特点**：
- 数据驱动的专业金融分析
- 市场情绪和资金流向判断
- 识别投资机会与风险

### 4. 公众号模块 (两阶段处理)
1. **wechat_step1_summary.txt**：单篇文章深度摘要
2. **wechat_step2_aggregate.txt**：多篇文章话题聚合

**特点**：
- **唯一输出 JSON 的模块**
- 结构化信息提取：数据、事件、内幕洞察
- 支持来源追溯和 Insight 分类

## 🚀 添加新 Prompt

### 方式1：配置文件修改（适用于播客、社区）

1. 在 `prompts/` 目录创建新文件，如 `new_prompts.txt`
2. 修改 `config/config.yaml`：
   ```yaml
   module:
     analysis:
       prompt_file: "new_prompts.txt"
   ```

### 方式2：代码硬编码（适用于投资、公众号）

修改对应模块的 `analyzer.py`：
```python
self.new_prompt = self._load_prompt("new_prompts.txt")
```

## ⚠️ 注意事项

1. **文件编码**：所有 prompt 文件必须使用 UTF-8 编码
2. **变量占位符**：使用 `{variable_name}` 格式，如 `{content}`、`{topics}`
3. **文件位置**：
   - 主模块：`prompts/` 目录
   - 公众号：`wechat/prompts/` 目录
4. **备份机制**：投资模块保留了旧版 `investment_daily.txt` 作为 fallback

## 📊 Prompt 性能优化建议

1. **Token 使用**：保持 prompt 简洁，避免不必要的冗余
2. **结构化输出**：明确要求 Markdown 或 JSON 格式
3. **示例驱动**：在 prompt 中包含正确/错误示例
4. **多语言支持**：播客模块的智能语言识别机制
5. **数据强调**：社区模块强调具体数据而非抽象总结

## 🔍 相关代码

- 播客分析器：`trendradar/podcast/analyzer.py`
- 社区分析器：`trendradar/community/analyzer.py`
- 投资分析器：`trendradar/investment/analyzer.py`
- 公众号分析器：`wechat/src/analyzer.py`
- AI 客户端：`wechat/src/ai_client.py`

## 📅 变更历史

- **2026-02-02**: 删除废弃的 `investment_module_prompt.txt`
- **2026-02-02**: 创建本 README 文档
- **2026-01-31**: 更新 `community_prompts.txt`
- **2026-02-01**: 创建 `investment_article.txt` 和 `investment_aggregate.txt`
