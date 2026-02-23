# coding=utf-8
"""
播客内容分析器

使用 AI 对转写文本进行结构化分析
支持使用播客专用的 AI 配置（DeepSeek R1 等）
"""

import os
from pathlib import Path
from typing import Optional
from dataclasses import dataclass


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    analysis: str = ""          # Markdown 格式的分析结果
    token_count: int = 0        # 使用的 token 数量
    error: Optional[str] = None


class PodcastAnalyzer:
    """
    播客内容分析器

    使用 AI 大模型对播客转写文本进行深度分析
    支持播客专用的 AI 配置或复用全局 AI 配置
    """

    DEFAULT_PROMPT_FILE = "podcast_prompts.txt"
    DEFAULT_LANGUAGE = "Chinese"

    def __init__(
        self,
        ai_config: dict,
        analysis_config: dict,
        prompt_file: str = DEFAULT_PROMPT_FILE,
        language: str = DEFAULT_LANGUAGE,
        config_dir: str = "config",
        prompts_dir: str = "prompts",
    ):
        """
        初始化分析器

        Args:
            ai_config: AI 模型配置（全局配置或播客专用配置）
            analysis_config: 分析配置（来自 config.yaml 的 podcast.analysis 段）
            prompt_file: 提示词文件名
            language: 输出语言（auto 表示跟随播客语言）
            config_dir: 配置文件目录
            prompts_dir: 提示词文件目录
        """
        self.ai_config = ai_config
        self.analysis_config = analysis_config
        self.prompt_file = prompt_file
        self.language = language or self.DEFAULT_LANGUAGE
        self.config_dir = Path(config_dir)
        self.prompts_dir = Path(prompts_dir)

        # 加载提示词模板
        self.system_prompt, self.user_prompt_template = self._load_prompt()

    def _load_prompt(self) -> tuple[str, str]:
        """
        加载提示词模板

        优先从 prompts 目录加载，其次从 config 目录加载

        Returns:
            (system_prompt, user_prompt_template) 元组
        """
        # 尝试多个可能的路径
        possible_paths = [
            self.prompts_dir / self.prompt_file,      # prompts/podcast_prompts.txt
            self.config_dir / self.prompt_file,       # config/podcast_prompts.txt
            Path("prompts") / self.prompt_file,       # 相对路径 prompts/
            Path("config") / self.prompt_file,        # 相对路径 config/
        ]

        for prompt_path in possible_paths:
            if prompt_path.exists():
                try:
                    content = prompt_path.read_text(encoding="utf-8")
                    print(f"[PodcastAnalyzer] 加载提示词: {prompt_path}")
                    return self._parse_prompt_content(content)
                except Exception as e:
                    print(f"[PodcastAnalyzer] 加载提示词失败 ({prompt_path}): {e}")

        print(f"[PodcastAnalyzer] 警告: 提示词文件不存在，使用默认提示词")
        return self._get_default_prompts()

    def _parse_prompt_content(self, content: str) -> tuple[str, str]:
        """
        解析提示词文件内容

        格式：
        [system]
        系统提示词...

        [user]
        用户提示词模板...
        """
        system_prompt = ""
        user_prompt = ""

        current_section = None
        lines = []

        for line in content.split("\n"):
            stripped = line.strip()

            # 跳过注释行
            if stripped.startswith("#"):
                continue

            # 检测段落标记
            if stripped.lower() == "[system]":
                if current_section == "user":
                    user_prompt = "\n".join(lines).strip()
                current_section = "system"
                lines = []
            elif stripped.lower() == "[user]":
                if current_section == "system":
                    system_prompt = "\n".join(lines).strip()
                current_section = "user"
                lines = []
            else:
                lines.append(line)

        # 处理最后一个段落
        if current_section == "system":
            system_prompt = "\n".join(lines).strip()
        elif current_section == "user":
            user_prompt = "\n".join(lines).strip()

        return system_prompt, user_prompt

    def _get_default_prompts(self) -> tuple[str, str]:
        """获取默认提示词（完整版本，包含语言规则和中英双语样例）"""

        system_prompt = """你是一位专业的播客内容分析师，擅长从对话中提炼关键信息和深度洞察。

你的任务是对播客转写文本进行深度分析和结构化总结。请注意：
1. 转写文本可能包含说话人标签，如 [SPEAKER_00]、[SPEAKER_01]
2. 保持客观中立，忠实于原文内容
3. 提炼核心观点，而非简单复述，禁止做简单的篇幅压缩，关键是寻找重要信息并如实记录
4. **语言规则**：
   - 中文播客 → 仅输出中文摘要
   - 英文播客 → 输出中英双语，每个章节先提供完整的英文版本，再提供完整的中文版本"""

        user_prompt = """请分析以下播客内容：

## 播客信息
- 播客名称：{podcast_name}
- 节目标题：{podcast_title}
- 原文语言：{source_language}
- 输出语言：{output_language}

## 转写文本
{transcript}

---

请按照以下结构输出分析结果（使用 Markdown 格式）：

**重要输出要求**：
- 当输出语言为"中文"时，仅输出中文内容
- 当输出语言为"中英双语"时，每个章节必须提供**完整的英文版本**和**完整的中文版本**
- 英文版本在前，中文版本在后
- 确保翻译准确，中文表达自然流畅
- 专业术语（如公司名、产品名、人名）保留英文并附中文翻译

## 核心摘要 / Summary
（3-5 句话概括本期主题、核心观点和主要结论）

## 关键要点 / Key Points
（列出 5-8 个最重要的观点、信息或洞察，每条 1-2 句话）

## 嘉宾观点 / Guest Opinions
（分别总结不同说话人的主要观点和立场，如有多位说话人）

## 精彩金句 / Notable Quotes
（记录有启发性、有深度的原话，至少3~5句，上不设限）

## 关键词 / Tags
（在一行内用逗号分隔列出关键技术、公司、人物、事件、概念等，如：AI, 创业, Marc Andreessen, 人口下降, 生产力）

## 信息提取 / Key Information
（提取对话中的高价值具体信息，分为以下三类）

## 数据与数字 / Data & Numbers
（提取对话中提到的具体数据、统计、百分比、金额、时间节点等可量化信息）
- [数据内容] — 来源/背景说明
- ...（列出所有提到的关键数据）

## 事件与动态 / Events & News
（提取提到的具体事件、行业动态、公司新闻、产品发布、人事变动等）
- [事件描述] — 时间/相关方
- ...（列出所有提到的重要事件）

## 内幕与洞察 / Insider Insights
（提取未公开的信息、行业内幕、独家爆料、非公开数据、预测判断等高价值信息）
- [内幕信息] — 信息来源（如某嘉宾透露）
- ...（列出所有独家或内幕信息）

## 分段落详述 / Detailed Discussion
（将全文按讨论话题划分为 3-6 个主要段落，**深度提炼**每个段落的核心内容）

**重要要求**：
- 讨论概要必须包含**具体的观点、论据和结论**，而非泛泛描述
- 发言摘要必须提炼**实质性内容**（具体数据、案例、判断、预测），而非仅描述"某人认为..."
- 每条发言摘要至少200字(篇幅不限)，包含该说话人的**核心论点 + 支撑论据/案例**

格式要求：
## 话题1: [话题标题]
**讨论概要**: （概括这一段讨论的核心问题、主要观点和得出的结论，要有实质内容，篇幅不限）

**发言摘要**:
- **[说话人姓名/角色]**: （详细提炼此人在该话题的核心观点，包括：1）主要论点是什么；2）用什么数据/案例/逻辑支撑；3）得出什么结论或建议。篇幅不限，确保内容完整）
- **[说话人姓名/角色]**: （同上要求，内容详实完整）

## 话题2: [话题标题]
...（依此类推，每个话题都要有充实的内容）

**内容质量标准**：
1. 避免空洞表述如"探讨了..."、"分析了..."、"认为..."，要写出**具体探讨/分析/认为的内容是什么**
2. 发言摘要要能让读者**不看原文也能了解核心信息**
3. 包含对话中提到的**具体数据、人名、公司名、事件、时间点**
4. 重要:体现说话人的**独特视角和专业见解**

---

**中英双语输出样例参考**（当输出语言为中英双语时）：

## 核心摘要 / Summary

This episode of The a16z Show features a deep dive into the transformative impact of AI on technology, society, and the economy. Marc Andreessen argues that we are living through a historically significant moment, comparable to major shifts like the fall of the Berlin Wall, driven by AI's rapid advancements. He discusses the interplay between AI, declining global population, and economic productivity, emphasizing the importance of adaptability, agency, and education in preparing for an AI-driven future. The conversation also touches on the cultural and geopolitical shifts shaping this era.

本集《a16z播客》深入探讨了AI对科技、社会和经济的变革性影响。马克·安德烈森认为，我们正处在一个具有历史意义的时代转折点，其影响力可与柏林墙倒塌等重大历史事件相媲美，这一切都源于AI的迅猛发展。他论述了AI与全球人口下降、经济生产率之间的相互作用，强调了适应力、自主权和教育对于迎接AI未来的重要性。对话还涉及塑造这个时代文化与地缘政治变迁的主题。

## 关键要点 / Key Points

1. **Historical Significance**: We are experiencing a moment comparable to the fall of the Berlin Wall, driven by AI advancements.
**历史意义**：我们正在经历一个可与柏林墙倒塌相媲美的历史时刻，由AI技术进步推动。

2. **Demographic Challenge**: Declining global population is a major economic headwind.
**人口挑战**：全球人口下降是重大经济逆风。

3. **AI as Solution**: AI can compensate for declining workforce and drive productivity.
**AI作为解决方案**：AI可以弥补劳动力下降并推动生产率增长。
"""

        return system_prompt, user_prompt

    def _detect_language(self, text: str) -> str:
        """检测文本语言"""
        # 简单的语言检测：统计中文字符比例
        chinese_chars = sum(1 for c in text if '\u4e00' <= c <= '\u9fff')
        total_chars = len(text.replace(" ", "").replace("\n", ""))
        
        if total_chars == 0:
            return "中文"
        
        chinese_ratio = chinese_chars / total_chars
        
        if chinese_ratio > 0.3:
            return "中文"
        else:
            return "英文"

    def analyze(
        self,
        transcript: str,
        podcast_name: str,
        podcast_title: str,
        detected_language: str = "",
    ) -> AnalysisResult:
        """
        分析播客内容

        Args:
            transcript: 转写文本
            podcast_name: 播客名称
            podcast_title: 节目标题
            detected_language: ASR 检测到的语言（可选）

        Returns:
            AnalysisResult 对象
        """
        if not transcript:
            return AnalysisResult(
                success=False,
                error="转写文本为空，无法分析"
            )

        # 检查转写文本长度
        if len(transcript) < 100:
            return AnalysisResult(
                success=False,
                error=f"转写文本太短 ({len(transcript)} 字符)，可能转写失败"
            )

        # 确定输出语言
        if self.language.lower() == "auto":
            if detected_language:
                # 确定原文语言
                source_language = "中文" if detected_language == "zh" else "英文"
                # 确定输出语言：中文播客→仅中文，英文播客→中英双语
                output_language = "中文" if detected_language == "zh" else "中英双语"
            else:
                detected = self._detect_language(transcript)
                source_language = detected  # "中文" 或 "英文"
                output_language = "中文" if detected == "中文" else "中英双语"
            print(f"[PodcastAnalyzer] 原文语言: {source_language}, 输出语言: {output_language}")
        else:
            output_language = self.language
            # 如果language不是auto，需要从transcript检测原文语言
            source_language = self._detect_language(transcript)
            print(f"[PodcastAnalyzer] 原文语言: {source_language}, 输出语言: {output_language}")

        print(f"[PodcastAnalyzer] 开始分析: {podcast_title}")
        print(f"[PodcastAnalyzer] 转写文本长度: {len(transcript)} 字符")

        # 限制转写文本长度，避免超出模型上下文窗口
        # DeepSeek R1 支持 64K 上下文，保留 50000 字符（约 2-3 小时内容）
        max_transcript_length = 50000
        transcript_for_analysis = transcript
        if len(transcript) > max_transcript_length:
            # 保留开头 70% 和结尾 25%，中间截断
            head_len = int(max_transcript_length * 0.7)
            tail_len = int(max_transcript_length * 0.25)
            transcript_for_analysis = (
                transcript[:head_len] +
                f"\n\n[...中间内容已截断，原文共 {len(transcript)} 字符...]\n\n" +
                transcript[-tail_len:]
            )
            print(f"[PodcastAnalyzer] 文本已截断: {len(transcript)} → {len(transcript_for_analysis)} 字符")

        try:
            # 尝试导入 AIClient
            from trendradar.ai.client import AIClient

            # 创建 AI 客户端（设置最大 max_tokens）
            # Thinking 模式：默认 32K，最大 64K 输出 tokens
            # 参考：https://api-docs.deepseek.com/
            ai_config_enhanced = self.ai_config.copy()
            if not ai_config_enhanced.get("MAX_TOKENS") and not ai_config_enhanced.get("max_tokens"):
                # 设置为 64000（思考模式的最大输出限制）
                ai_config_enhanced["MAX_TOKENS"] = 64000

            # 调试：打印配置
            print(f"[DEBUG] self.ai_config keys: {list(self.ai_config.keys())}")
            print(f"[DEBUG] TIMEOUT in self.ai_config: {'TIMEOUT' in self.ai_config}")
            print(f"[DEBUG] TIMEOUT in ai_config_enhanced: {'TIMEOUT' in ai_config_enhanced}")
            print(f"[DEBUG] ai_config_enhanced TIMEOUT: {ai_config_enhanced.get('TIMEOUT')}")

            client = AIClient(ai_config_enhanced)

            # 构建用户提示词
            user_prompt = self.user_prompt_template.format(
                podcast_name=podcast_name,
                podcast_title=podcast_title,
                transcript=transcript_for_analysis,
                source_language=source_language,
                output_language=output_language,
            )

            # 构建消息列表
            messages = []
            if self.system_prompt:
                messages.append({"role": "system", "content": self.system_prompt})
            messages.append({"role": "user", "content": user_prompt})

            # 调用 AI（启用 Thinking 模式以获得更大的输出 token 限制）
            # 思考模式：默认 32K，最大 64K 输出 tokens（非思考模式最大仅 8K）
            # 参考：https://api-docs.deepseek.com/
            print(f"[PodcastAnalyzer] 使用模型: {self.ai_config.get('model', 'default')}")
            print(f"[PodcastAnalyzer] Thinking 模式: 已启用 (最大输出: 64K tokens)")

            response = client.chat(
                messages=messages,
                extra_body={"enable_thinking": True}
            )

            if not response:
                return AnalysisResult(
                    success=False,
                    error="AI 返回空响应"
                )

            print(f"[PodcastAnalyzer] 分析完成: {len(response)} 字符")

            # 标准化输出格式
            normalized_analysis = self._normalize_analysis_format(
                analysis=response,
                podcast_name=podcast_name,
                podcast_title=podcast_title,
            )

            return AnalysisResult(
                success=True,
                analysis=normalized_analysis,
            )

        except ImportError as e:
            return AnalysisResult(
                success=False,
                error=f"无法导入 AIClient: {e}"
            )

        except Exception as e:
            return AnalysisResult(
                success=False,
                error=f"分析失败: {e}"
            )

    def _normalize_analysis_format(
        self,
        analysis: str,
        podcast_name: str,
        podcast_title: str,
    ) -> str:
        """
        标准化 AI 输出格式，确保一致性

        Args:
            analysis: AI 原始输出
            podcast_name: 播客名称
            podcast_title: 节目标题

        Returns:
            标准化后的分析文本
        """
        lines = analysis.split("\n")
        result_lines = []
        i = 0

        # 跳过开头的空行和违规标题
        while i < len(lines):
            line = lines[i].strip()

            # 跳过空行
            if not line:
                i += 1
                continue

            # 移除违规的标题格式
            if line in ["# 播客内容分析"]:
                i += 1
                continue

            # 移除 "**播客分析:" 开头（保留后面的内容）
            if line.startswith("**播客分析:") or line.startswith("**播客分析："):
                i += 1
                continue

            # 找到第一个有效内容行
            break

        # 如果第一个有效标题不是 "## 核心摘要"，插入标准标题
        if i < len(lines):
            first_line = lines[i].strip()
            if not first_line.startswith("## 核心摘要"):
                result_lines.append("## 核心摘要 / Summary")
                result_lines.append("")  # 空行

        # 添加剩余内容
        result_lines.extend(lines[i:])

        # 标准化标题格式
        normalized_lines = []
        for line in result_lines:
            stripped = line.strip()

            # 替换不一致的标题
            if stripped == "## 核心摘要":
                normalized_lines.append("## 核心摘要 / Summary")
            elif stripped == "## 关键要点":
                normalized_lines.append("## 关键洞察 / Key Insights")
            elif stripped == "## 嘉宾观点":
                normalized_lines.append("## 发言者角色与主要立场")
            else:
                normalized_lines.append(line)

        return "\n".join(normalized_lines)

    @classmethod
    def from_config(cls, config: dict) -> "PodcastAnalyzer":
        """
        从配置字典创建分析器

        优先使用 podcast.analysis 下的专用 AI 配置，
        如果没有则回退到全局 ai 配置

        Args:
            config: 完整配置字典

        Returns:
            PodcastAnalyzer 实例
        """
        # 获取全局 AI 配置
        global_ai_config = config.get("AI", config.get("ai", {}))

        # 获取播客配置（兼容大小写）
        podcast_config = config.get("PODCAST", config.get("podcast", {}))
        analysis_config = podcast_config.get("ANALYSIS", podcast_config.get("analysis", {}))

        # 构建 AI 配置：优先使用 analysis 下的专用配置
        ai_config = global_ai_config.copy()

        # 如果 analysis 配置了专用的模型/API，则覆盖全局配置（兼容大小写）
        if analysis_config.get("MODEL") or analysis_config.get("model"):
            ai_config["MODEL"] = analysis_config.get("MODEL") or analysis_config.get("model")
            ai_config["model"] = ai_config["MODEL"]  # 同步到小写
        if analysis_config.get("API_BASE") or analysis_config.get("api_base"):
            ai_config["API_BASE"] = analysis_config.get("API_BASE") or analysis_config.get("api_base")
            ai_config["api_base"] = ai_config["API_BASE"]
        if analysis_config.get("API_KEY") or analysis_config.get("api_key"):
            ai_config["API_KEY"] = analysis_config.get("API_KEY") or analysis_config.get("api_key")
            ai_config["api_key"] = ai_config["API_KEY"]

        return cls(
            ai_config=ai_config,
            analysis_config=analysis_config,
            prompt_file=analysis_config.get("PROMPT_FILE") or analysis_config.get("prompt_file", cls.DEFAULT_PROMPT_FILE),
            language=analysis_config.get("LANGUAGE") or analysis_config.get("language", cls.DEFAULT_LANGUAGE),
        )
