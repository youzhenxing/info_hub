# 播客格式回退问题分析与解决方案

## 问题定位

**现象**：最新一期播客（ID 237）的分析格式发生了回退

- **ID 237** (最新): `# 播客内容分析\n\n## 核心摘要`
- **ID 235** (上一期): `**播客分析: The a16z Show – Why This Isn't the Dot-Com Bubble**\n\n**核心主题与总结**`

**分析**：两期播客都是在 2026-02-06 12:52 左右处理的，相隔仅 4 分钟，使用相同的代码和配置。格式差异是 AI 模型输出的随机性导致的。

---

## 根本原因

### 1. Temperature 设置过高
**配置文件** (`config/config.yaml:356`):
```yaml
temperature: 1.0  # 采样温度 (0.0-2.0)
```

- **问题**：`temperature = 1.0` 会导致极高的随机性
- **影响**：每次调用 AI 模型，输出格式可能完全不同
- **建议**：对于格式化输出任务，应使用 `0.3 ~ 0.5`

### 2. Prompt 缺少明确的格式约束
**当前 Prompt** (`prompts/podcast_prompts.txt:49-50`):
```
## 核心摘要 / Summary
（3-5 句话概括本期主题、核心观点和主要结论）
```

- **问题**：Prompt 只指定了章节标题，没有明确开头格式
- **影响**：AI 可能自行决定是否添加 `**播客分析: xxx**` 开头
- **建议**：在 Prompt 中明确要求开头的格式

### 3. 没有后处理格式化逻辑
**当前实现** (`trendradar/podcast/analyzer.py:395-398`):
```python
return AnalysisResult(
    success=True,
    analysis=response,  # 直接使用 AI 原始输出
)
```

- **问题**：没有对 AI 输出进行后处理和格式标准化
- **影响**：格式完全依赖 AI 的随机输出
- **建议**：添加后处理逻辑，确保格式一致

---

## 解决方案

### 方案 1：降低 Temperature（推荐，快速修复）

**优点**：
- 简单有效，只需修改配置
- 立即生效，无需改代码

**缺点**：
- 可能影响内容的多样性

**实施步骤**：
1. 修改 `config/config.yaml` 第 356 行
2. 将 `temperature: 1.0` 改为 `temperature: 0.5`
3. 重启服务

### 方案 2：增强 Prompt 格式约束（推荐，长期方案）

**优点**：
- 从源头确保格式一致性
- 不影响内容质量

**缺点**：
- 需要测试和验证

**实施步骤**：
1. 修改 `prompts/podcast_prompts.txt`
2. 在开头添加明确的格式要求：

```markdown
**重要格式要求**：
- 必须以 `**播客分析: [播客名称] – [节目标题]**` 开头
- 使用 `**核心主题与总结**` 而非 `## 核心摘要`

请按照以下结构输出分析结果（使用 Markdown 格式）：

**播客分析: {podcast_name} – {podcast_title}**

**核心主题与总结**
（3-5 句话概括本期主题、核心观点和主要结论）
```

### 方案 3：添加后处理格式化（推荐，最可靠）

**优点**：
- 完全控制输出格式
- 不依赖 AI 的随机性

**缺点**：
- 需要修改代码

**实施步骤**：
1. 在 `trendradar/podcast/analyzer.py` 中添加格式化方法
2. 确保输出格式统一

**示例代码**：
```python
def _format_analysis(self, analysis: str, podcast_name: str, podcast_title: str) -> str:
    """格式化 AI 输出，确保格式一致"""
    # 检查是否有标准开头
    if not analysis.startswith("**播客分析:"):
        # 添加标准开头
        analysis = f"**播客分析: {podcast_name} – {podcast_title}**\n\n{analysis}"

    # 替换不一致的标题
    analysis = analysis.replace("## 核心摘要", "**核心主题与总结**")
    analysis = analysis.replace("## 关键要点", "**核心洞察与要点**")

    return analysis
```

---

## 建议的实施顺序

1. **立即修复**（方案 1）：降低 temperature 到 0.5
2. **短期优化**（方案 2）：增强 Prompt 格式约束
3. **长期保障**（方案 3）：添加后处理格式化逻辑

---

## 验证方法

修复后，运行测试：
```bash
# 重新分析最近一期播客
python -m trendradar.podcast.processor --test-feed-id a16z --bootstrap
```

检查输出格式是否一致：
- 开头：`**播客分析: [播客名称] – [节目标题]**`
- 第一个章节：`**核心主题与总结**`
