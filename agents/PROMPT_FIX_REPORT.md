# Prompt 模板 JSON 转义修复报告

## 问题描述

**症状**: 投资模块 AI 分析失败，错误信息：`AI 分析失败: '\n  "summary"'`

**影响**:
- 预发版 E2E 测试在投资模块阶段失败
- 无法生成投资简报邮件
- 其他依赖 JSON 格式输出的模块也可能受影响

## 根本原因

Prompt 模板中的 JSON 示例包含了**未转义的花括号** `{}`。

当 Python 的 `str.format()` 方法处理这些模板时：
```python
prompt.format(title=..., source=..., content=...)
```

它会将 JSON 示例中的 `"summary"` 误认为是占位符，导致：
```python
KeyError: '\n  "summary"'
```

### 问题示例

**修复前的 prompt 模板**（`prompts/investment_step1_article.txt`）:
```
```json
{
  "summary": "一句话核心摘要",
  ...
}
```
```

当调用 `prompt.format(...)` 时，Python 尝试将 `{` 和 `}` 之间的内容作为占位符解析，
导致 `\n  "summary"` 被当作占位符名。

## 解决方案

将 JSON 示例中的花括号**转义**：
- `{` → `{{`
- `}` → `}}`

**修复后的 prompt 模板**:
```
```json
{{
  "summary": "一句话核心摘要",
  ...
}}
```
```

Python 的 `str.format()` 会将 `{{` 转义为单个 `{`，`}}` 转义为 `}`，
最终输出正确的 JSON 格式。

## 修复的文件

### 1. `prompts/investment_step1_article.txt`
- **修复内容**: 转义输出格式 JSON 示例中的花括号
- **影响范围**: 投资模块单篇文章分析

### 2. `wechat/prompts/wechat_step2_aggregate.txt`
- **修复内容**: 转义两个 JSON 示例（格式模板 + 具体示例）中的花括号
- **影响范围**: 公众号模块话题聚合分析

### 3. 其他文件检查
- ✅ `prompts/investment_step2_aggregate.txt` - 无问题
- ✅ `wechat/prompts/wechat_step1_summary.txt` - 无问题

## 验证结果

### 调试脚本测试
```bash
python agents/debug_investment_ai.py
```

**结果**: ✅ 成功
- AI 响应长度: 436 字符
- JSON 解析成功
- summary 字段正常提取

### 预发版 E2E 测试
```bash
python agents/prerelease_e2e_test.py
```

**结果**: ✅ 3/4 模块成功
- ✅ 投资模块: 成功 | 📧 已发送 (234.6s)
- ✅ 社区模块: 成功 | 📧 已发送 (75.6s)
- ✅ 播客模块: 成功 | 📧 已发送 (26.8s)
- ⚠️ 公众号模块: 仅因缺少测试数据文件而跳过

**生成的邮件**:
- `investment_prerelease_081329.html` - 包含完整的 AI 分析内容
- `community_prerelease_081444.html` - 社区热点邮件
- `podcast_prerelease_081512.html` - 播客更新邮件

## 技术洞察

`★ Insight ─────────────────────────────────────`
1. **Python str.format() 占位符规则**: 花括号在 format 模板中有特殊含义，
   任何 `{...}` 都会被当作占位符尝试替换，即使是在 JSON 示例中。

2. **Prompt 工程最佳实践**: 当 prompt 模板包含示例代码（JSON、Python、SQL 等）时，
   必须转义花括号或使用 f-string、% 格式化等其他方式。

3. **调试技巧**: `KeyError: '\n  "summary"'` 这种带有换行符和引号的错误信息，
   通常不是用户输入的问题，而是代码将 JSON 内容误当作占位符名的标志。
`─────────────────────────────────────────────────`

## 后续建议

1. **Prompt 模板审查**: 检查所有其他 prompt 文件，确保没有未转义的花括号
2. **编码规范**: 在文档中明确说明 JSON 示例需要转义花括号
3. **自动化检测**: 可以添加测试脚本扫描 prompt 文件中的未转义花括号

## 修复日期

2026-02-02

## 修复人员

Claude Code (Anthropic)
