# coding=utf-8
"""
投资分析模块（重构版）

采用分级处理模式：
1. 第一层：收集新闻和行情数据
2. 第二层：获取新闻正文，每篇独立 AI 分析
3. 第三层：聚合分析结果，生成投资简报
"""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..ai.client import AIClient
from .collector import CollectedData, NewsItem
from .content_fetcher import ContentFetcher, FetchedContent

logger = logging.getLogger(__name__)


@dataclass
class ArticleAnalysis:
    """单篇文章分析结果"""
    title: str
    source: str
    url: str
    content_fetched: bool = False          # 是否成功获取正文
    summary: str = ""                       # 核心摘要
    category: str = ""                      # 分类
    entities: List[str] = field(default_factory=list)  # 涉及实体
    impact_level: str = ""                  # 影响程度
    impact_direction: str = ""              # 影响方向
    impact_duration: str = ""               # 影响周期
    key_data: List[str] = field(default_factory=list)  # 关键数据
    insight: str = ""                       # 投资启示
    follow_up: str = ""                     # 后续关注
    raw_content: str = ""                   # 原始正文
    error: str = ""                         # 错误信息


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    content: str                            # AI 生成的分析内容
    article_analyses: List[ArticleAnalysis] = field(default_factory=list)
    error: str = ""
    tokens_used: int = 0


class InvestmentAnalyzer:
    """投资分析器（分级处理模式）"""

    def __init__(self, config: Dict[str, Any], ai_config: Dict[str, Any] = None):
        """
        初始化投资分析器

        Args:
            config: investment.analysis 配置字典
            ai_config: 全局 AI 配置字典（作为默认值）
        """
        self.config = config
        self.ai_config = ai_config or {}
        self.enabled = config.get("enabled", True)
        self.language = config.get("language", "Chinese")
        
        # 分级处理配置（支持大写和小写键名）
        self.fetch_content = config.get("FETCH_CONTENT", config.get("fetch_content", True))
        self.max_articles_to_analyze = config.get("MAX_ARTICLES", config.get("max_articles", 15))
        self.content_fetch_delay = config.get("CONTENT_FETCH_DELAY", config.get("content_fetch_delay", 1.0))

        # 加载提示词（step1: 单篇分析，step2: 聚合分析）
        self.article_prompt = self._load_prompt("investment_step1_article.txt")
        self.aggregate_prompt = self._load_prompt("investment_step2_aggregate.txt")

        # 初始化组件
        self.ai_client = self._init_ai_client()
        self.content_fetcher = ContentFetcher(config)

    def _load_prompt(self, prompt_file: str) -> str:
        """加载提示词文件"""
        possible_paths = [
            Path("prompts") / prompt_file,
            Path("config") / "prompts" / prompt_file,
            Path(__file__).parent.parent.parent / "prompts" / prompt_file,
        ]

        for path in possible_paths:
            if path.exists():
                try:
                    return path.read_text(encoding="utf-8")
                except Exception as e:
                    logger.warning(f"读取提示词文件 {path} 失败: {e}")

        return ""

    def _init_ai_client(self) -> AIClient:
        """初始化 AI 客户端"""
        model = (self.config.get("MODEL") or self.config.get("model") or 
                 self.ai_config.get("MODEL") or self.ai_config.get("model", ""))
        api_base = (self.config.get("API_BASE") or self.config.get("api_base") or 
                    self.ai_config.get("API_BASE") or self.ai_config.get("api_base", ""))
        api_key = (self.config.get("API_KEY") or self.config.get("api_key") or 
                   self.ai_config.get("API_KEY") or self.ai_config.get("api_key", ""))

        client_config = {
            "model": model,
            "api_base": api_base,
            "api_key": api_key,
            "temperature": self.ai_config.get("temperature", 0.7),
            "max_tokens": self.ai_config.get("max_tokens", 4000),
            "timeout": self.ai_config.get("timeout", 600),  # ✅ 从 120 提高到 600（10分钟），提高实时性
        }

        return AIClient(client_config)

    def analyze(self, data: CollectedData) -> AnalysisResult:
        """
        对收集的数据进行分级 AI 分析

        处理流程：
        1. 筛选重要新闻
        2. 获取新闻正文
        3. 单篇 AI 分析
        4. 聚合生成简报

        Args:
            data: 收集的投资数据

        Returns:
            AnalysisResult: 分析结果
        """
        if not self.enabled:
            return AnalysisResult(
                success=False,
                content="",
                error="AI 分析功能未启用",
            )

        # 验证 AI 配置
        is_valid, error_msg = self.ai_client.validate_config()
        if not is_valid:
            return AnalysisResult(
                success=False,
                content="",
                error=f"AI 配置无效: {error_msg}",
            )

        try:
            # ========== 第一层：筛选重要新闻 ==========
            logger.info("[第一层] 筛选重要新闻...")
            important_news = self._select_important_news(data.news)
            logger.info(f"  筛选出 {len(important_news)} 条重要新闻")
            
            # ========== 第二层：获取正文并单篇分析 ==========
            article_analyses = []
            
            if self.fetch_content and important_news:
                logger.info("[第二层] 获取正文并分析...")
                for i, news in enumerate(important_news, 1):
                    try:
                        analysis = self._analyze_single_article(news, i, len(important_news))
                        article_analyses.append(analysis)
                    except Exception as e:
                        logger.error(f"  [{i}] 分析失败: {news.title[:30]}... - {e}")
                        # 创建一个失败的分析结果
                        article_analyses.append(ArticleAnalysis(
                            title=news.title,
                            source=news.source,
                            url=news.url,
                            error=str(e)
                        ))
            
            # ========== 第三层：聚合分析 ==========
            logger.info("[第三层] 聚合分析生成简报...")
            content = self._generate_aggregate_report(data, article_analyses)
            
            logger.info(f"分析完成，简报长度: {len(content)} 字符")

            return AnalysisResult(
                success=True,
                content=content,
                article_analyses=article_analyses,
            )

        except Exception as e:
            logger.error(f"AI 分析失败: {e}")
            return AnalysisResult(
                success=False,
                content="",
                error=str(e),
            )

    def _select_important_news(self, news_list: List[NewsItem]) -> List[NewsItem]:
        """
        筛选重要新闻
        
        优先选择：
        1. 命中关注概念的新闻
        2. 来源权重高的新闻
        """
        if not news_list:
            return []
        
        # 按重要性排序
        def importance_score(news: NewsItem) -> int:
            score = 0
            # 命中概念加分
            score += len(news.matched_concepts) * 10
            # 权威来源加分
            if news.source in ["华尔街见闻", "财联社", "金十数据", "第一财经"]:
                score += 5
            return score
        
        sorted_news = sorted(news_list, key=importance_score, reverse=True)
        
        return sorted_news[:self.max_articles_to_analyze]

    def _analyze_single_article(self, news: NewsItem, index: int, total: int) -> ArticleAnalysis:
        """
        单篇文章分析
        
        Args:
            news: 新闻条目
            index: 当前索引
            total: 总数
        """
        logger.info(f"  [{index}/{total}] {news.title[:40]}...")
        
        analysis = ArticleAnalysis(
            title=news.title,
            source=news.source,
            url=news.url,
        )
        
        # 获取正文
        content = news.summary or ""
        if news.url and self.fetch_content:
            try:
                fetched = self.content_fetcher.fetch(news.url, news.source)
                if fetched.success and fetched.content:
                    content = fetched.content
                    analysis.content_fetched = True
                    analysis.raw_content = content[:2000]  # 保存前 2000 字
            except Exception as e:
                logger.warning(f"    获取正文失败: {e}")
        
        if not content:
            content = news.title
        
        # AI 分析
        if self.article_prompt:
            try:
                ai_result = self._call_article_ai(news.title, news.source, content)
                self._parse_article_result(ai_result, analysis)
            except Exception as e:
                logger.warning(f"    AI 分析失败: {e}")
                analysis.summary = content[:200]
                analysis.error = str(e)
        else:
            # 无提示词，使用简单摘要
            analysis.summary = content[:200]
        
        return analysis

    def _call_article_ai(self, title: str, source: str, content: str) -> str:
        """调用 AI 分析单篇文章"""
        # 截断过长内容
        if len(content) > 6000:
            content = content[:6000] + "...[内容已截断]"
        
        # 填充提示词
        prompt = self.article_prompt.format(
            title=title,
            source=source,
            content=content
        )
        
        messages = [
            {"role": "user", "content": prompt}
        ]
        
        return self.ai_client.chat(messages)

    def _parse_article_result(self, result: str, analysis: ArticleAnalysis) -> None:
        """解析单篇文章 AI 分析结果"""
        try:
            # 提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                json_str = result
            
            # 修复常见 JSON 错误
            json_str = self._fix_json(json_str)
            
            data = json.loads(json_str)
            
            analysis.summary = data.get("summary", "")
            analysis.category = data.get("category", "")
            analysis.entities = data.get("entities", [])
            
            impact = data.get("impact", {})
            analysis.impact_level = impact.get("level", "")
            analysis.impact_direction = impact.get("direction", "")
            analysis.impact_duration = impact.get("duration", "")
            
            analysis.key_data = data.get("key_data", [])
            analysis.insight = data.get("insight", "")
            analysis.follow_up = data.get("follow_up", "")
            
        except json.JSONDecodeError:
            # JSON 解析失败，提取文本摘要
            analysis.summary = self._extract_text_summary(result)
        except Exception as e:
            analysis.error = str(e)

    def _fix_json(self, json_str: str) -> str:
        """尝试修复常见的 JSON 格式错误"""
        json_str = json_str.strip()
        
        # 查找 JSON 对象
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = json_str[start:end+1]
        
        # 移除尾部多余逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        return json_str

    def _extract_text_summary(self, text: str) -> str:
        """从文本中提取摘要"""
        # 移除 markdown 代码块
        text = re.sub(r'```.*?```', '', text, flags=re.DOTALL)
        text = text.strip()
        
        # 取前 200 字
        return text[:200] if text else ""

    def _generate_aggregate_report(
        self,
        data: CollectedData,
        article_analyses: List[ArticleAnalysis]
    ) -> str:
        """
        聚合分析生成投资简报
        
        Args:
            data: 收集的数据
            article_analyses: 单篇分析结果
        """
        # 构建聚合数据
        aggregate_data = {
            "market_data": {},
            "money_flow": {},
            "news_analyses": [],
        }
        
        # 添加行情数据
        if data.market_snapshot:
            aggregate_data["market_data"]["indices"] = [
                {
                    "name": idx.name,
                    "symbol": idx.symbol,
                    "price": idx.price,
                    "change_pct": idx.change_pct,
                }
                for idx in data.market_snapshot.indices
            ]
            
            if data.market_snapshot.northbound:
                nb = data.market_snapshot.northbound
                aggregate_data["money_flow"]["northbound"] = {
                    "total": nb.total,
                    "sh_connect": nb.sh_connect,
                    "sz_connect": nb.sz_connect,
                }
            
            aggregate_data["money_flow"]["sector_flows"] = [
                {
                    "name": s.name,
                    "change_pct": s.change_pct,
                    "net_flow": s.net_flow,
                }
                for s in data.market_snapshot.sector_flows[:10]
            ]
        
        # 添加新闻分析结果
        for analysis in article_analyses:
            if analysis.summary:
                aggregate_data["news_analyses"].append({
                    "title": analysis.title,
                    "source": analysis.source,
                    "category": analysis.category,
                    "summary": analysis.summary,
                    "entities": analysis.entities,
                    "impact": {
                        "level": analysis.impact_level,
                        "direction": analysis.impact_direction,
                    },
                    "key_data": analysis.key_data,
                    "insight": analysis.insight,
                })
        
        # 调用聚合 AI
        return self._call_aggregate_ai(aggregate_data)

    def _call_aggregate_ai(self, aggregate_data: Dict) -> str:
        """调用聚合分析 AI"""
        data_json = json.dumps(aggregate_data, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": self.aggregate_prompt},
            {"role": "user", "content": f"以下是今日的市场数据和新闻分析：\n\n```json\n{data_json}\n```"},
        ]
        
        response = self.ai_client.chat(messages)
        return self._clean_response(response)

    def _clean_response(self, response: str) -> str:
        """清理 AI 响应内容"""
        content = response.strip()

        # 去除 ```markdown ... ``` 包装
        if content.startswith("```markdown"):
            content = content[11:]
            if content.endswith("```"):
                content = content[:-3]
            content = content.strip()

        # 去除 ``` ... ``` 包装
        elif content.startswith("```") and content.endswith("```"):
            lines = content.split("\n")
            if len(lines) > 2:
                content = "\n".join(lines[1:-1])

        return content

    @classmethod
    def from_config(cls, config: Dict[str, Any]) -> "InvestmentAnalyzer":
        """从配置创建分析器实例"""
        investment_config = config.get("INVESTMENT", config.get("investment", {}))
        analysis_config = investment_config.get("ANALYSIS", investment_config.get("analysis", {}))
        ai_config = config.get("AI", config.get("ai", {}))

        return cls(analysis_config, ai_config)
