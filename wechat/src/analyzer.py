"""
AI 分析器 - 生成文章摘要和话题聚合
"""

import logging
import json
import re
import threading
from typing import List, Optional
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from .models import Article, Topic, DataNumber, EventNews, InsiderInsight, TopicSource, DailyReport, FeedType
from .config_loader import ConfigLoader
from .ai_client import AIClient
from .storage import Storage

logger = logging.getLogger(__name__)


class WechatAnalyzer:
    """微信公众号文章 AI 分析器"""
    
    def __init__(self, config: ConfigLoader, storage: Storage):
        self.config = config
        self.storage = storage
        self.ai_client = AIClient(config.ai)
        
        # 加载提示词（step1: 单篇摘要，step2: 话题聚合）
        self.summary_prompt = self._load_prompt("wechat_step1_summary.txt")
        self.topic_prompt = self._load_prompt("wechat_step2_aggregate.txt")
    
    def _load_prompt(self, filename: str) -> str:
        """加载提示词文件"""
        # 获取 wechat/prompts 目录（相对于本文件的路径）
        wechat_dir = Path(__file__).parent.parent
        prompt_path = wechat_dir / "prompts" / filename
        if prompt_path.exists():
            return prompt_path.read_text(encoding='utf-8')
        
        # 返回默认提示词
        if "summary" in filename:
            return self._default_summary_prompt()
        else:
            return self._default_topic_prompt()
    
    def _default_summary_prompt(self) -> str:
        """默认文章摘要提示词"""
        return """请对以下文章生成一个简洁的摘要，包含以下要点：

1. **核心观点**：文章的主要论点或结论（1-2句话）
2. **关键信息**：重要的数据、事实或事件（2-3点）
3. **价值判断**：为什么这篇文章值得关注

要求：
- 摘要总长度控制在 200 字以内
- 保留原文中的具体数据和关键术语
- 用中文输出

文章内容：
{content}"""
    
    def _default_topic_prompt(self) -> str:
        """默认话题聚合提示词"""
        return """请分析以下多篇公众号文章，按话题进行聚类分析。

要求：
1. 识别 2-5 个主要话题
2. 每个话题包含：
   - 话题名称（简短有力）
   - 话题描述（1-2句话概述）
   - 相关文章列表（标题）
   - 综合分析（整合多篇文章的观点，150字以内）

输出格式（JSON）：
```json
{
  "topics": [
    {
      "name": "话题名称",
      "description": "话题描述",
      "articles": ["文章1标题", "文章2标题"],
      "analysis": "综合分析内容"
    }
  ]
}
```

文章列表：
{content}"""
    
    def analyze_daily(self) -> DailyReport:
        """
        分级处理分析今日文章，生成每日报告
        
        处理流程：
        1. 第一层：采集所有文章
        2. 第二层：对每篇文章单独 AI 分析（生成摘要）
        3. 第三层：基于单篇摘要进行话题聚合
        
        Returns:
            每日报告数据
        """
        from datetime import datetime
        
        logger.info("开始生成每日报告（分级处理模式）")
        
        # ========== 第一层：获取今日文章 ==========
        critical_articles = self.storage.get_today_articles(FeedType.CRITICAL)
        normal_articles = self.storage.get_today_articles(FeedType.NORMAL)
        
        logger.info(f"今日文章: 第一类 {len(critical_articles)} 篇, 第二类 {len(normal_articles)} 篇")
        
        # ========== 第二层：单篇文章 AI 分析（线程池并发） ==========
        # 合并所有需要分析的文章
        all_articles = list(critical_articles) + list(normal_articles)
        total_count = len(all_articles)

        # 过滤出需要分析的文章（ai_summary 为空）
        articles_to_process = [(article, idx + 1, total_count)
                              for idx, article in enumerate(all_articles)
                              if not article.ai_summary]

        if articles_to_process:
            logger.info(f"[第二层] 并发分析 {len(articles_to_process)}/{total_count} 篇文章...")

            progress_lock = threading.Lock()
            completed_count = [0]

            def process_article(article, idx, total):
                """处理单篇文章的辅助函数（在线程池中运行）"""
                try:
                    summary = self._generate_summary(article)
                    self.storage.update_ai_summary(article.id, summary)
                    with progress_lock:
                        completed_count[0] += 1
                        logger.info(f"  [{completed_count[0]}/{len(articles_to_process)}] {article.title[:30]}...")
                    return (article, summary, None)
                except Exception as e:
                    with progress_lock:
                        completed_count[0] += 1
                        logger.error(f"  [{completed_count[0]}/{len(articles_to_process)}] 失败: {article.title[:30]}... - {e}")
                    return (article, None, e)

            # 使用线程池并发分析（5个线程平衡并发和API限流）
            with ThreadPoolExecutor(max_workers=5) as executor:
                futures = {
                    executor.submit(process_article, article, idx, total): article
                    for article, idx, total in articles_to_process
                }

                for future in as_completed(futures):
                    article, summary, error = future.result()
                    if not error:
                        # 更新文章对象的 ai_summary
                        article.ai_summary = summary
        else:
            logger.info("[第二层] 所有文章已有摘要，跳过分析")
        
        # ========== 第三层：话题聚合（基于单篇摘要） ==========
        topics = []
        if normal_articles:
            logger.info(f"[第三层] 话题聚合分析...")
            try:
                topics = self._aggregate_topics(normal_articles)
                logger.info(f"  话题聚合完成: {len(topics)} 个话题")
            except Exception as e:
                logger.error(f"  话题聚合失败: {e}")
        
        # 构建所有文章列表（用于完整列表展示）
        all_articles = critical_articles + normal_articles
        # 按公众号和发布时间排序
        all_articles.sort(key=lambda a: (a.feed_name, a.published_at or datetime.min), reverse=False)
        
        # 构建报告
        report = DailyReport(
            date=datetime.now(),
            critical_articles=critical_articles,
            topics=topics,
            all_articles=all_articles,
            total_articles=len(critical_articles) + len(normal_articles),
            critical_count=len(critical_articles),
            normal_count=len(normal_articles)
        )
        
        logger.info(f"每日报告生成完成: {report.total_articles} 篇文章")
        
        return report
    
    def _generate_summary(self, article: Article) -> str:
        """
        为单篇文章生成 AI 摘要
        
        Args:
            article: 文章对象
        
        Returns:
            AI 生成的摘要
        """
        # 准备文章内容
        content = self._prepare_content(article)
        
        # 调用 AI
        summary = self.ai_client.summarize(content, self.summary_prompt)
        
        return summary.strip()
    
    def _aggregate_topics(self, articles: List[Article], max_retries: int = 3) -> List[Topic]:
        """
        对多篇文章进行话题聚合分析（带重试机制）
        
        Args:
            articles: 文章列表
            max_retries: 最大重试次数
        
        Returns:
            话题列表
        """
        if not articles:
            return []
        
        # 准备文章列表文本
        articles_text = self._prepare_articles_for_topic(articles)
        
        # 带重试的 AI 调用和解析
        for attempt in range(max_retries):
            try:
                # 调用 AI（使用 Thinking 模式）
                result = self.ai_client.analyze_topics_with_thinking(articles_text, self.topic_prompt)
                
                # 解析结果
                topics = self._parse_topic_result(result, articles)
                
                # 如果成功解析出多个话题，返回
                if len(topics) > 1 or (len(topics) == 1 and topics[0].name != "今日资讯汇总"):
                    return topics
                    
                # 如果只有默认话题且还有重试次数，继续重试
                if attempt < max_retries - 1:
                    logger.warning(f"话题聚合结果不理想，重试 ({attempt + 2}/{max_retries})...")
                    
            except Exception as e:
                if attempt < max_retries - 1:
                    logger.warning(f"话题聚合出错，重试 ({attempt + 2}/{max_retries}): {e}")
                else:
                    logger.error(f"话题聚合最终失败: {e}")
        
        # 所有重试都失败，返回最后一次的结果或默认话题
        return self._create_default_topics(articles)
    
    def _prepare_content(self, article: Article) -> str:
        """准备文章内容用于 AI 分析"""
        from bs4 import BeautifulSoup
        
        # 移除 HTML 标签
        if article.content:
            soup = BeautifulSoup(article.content, 'lxml')
            text = soup.get_text(separator='\n', strip=True)
        else:
            text = article.summary or article.title
        
        # 截断过长的内容
        max_length = 8000  # 大约 4000 tokens
        if len(text) > max_length:
            text = text[:max_length] + "...[内容已截断]"
        
        return f"标题：{article.title}\n\n正文：\n{text}"
    
    def _prepare_articles_for_topic(self, articles: List[Article]) -> str:
        """
        准备多篇文章用于话题聚合
        
        优先使用 AI 摘要（第二层分析结果），确保聚合时有丰富的素材
        """
        from bs4 import BeautifulSoup
        
        parts = []
        for i, article in enumerate(articles, 1):
            # 优先使用 AI 摘要（分级处理的关键！）
            if article.ai_summary:
                content = article.ai_summary
            elif article.summary:
                content = article.summary
            elif article.content:
                soup = BeautifulSoup(article.content, 'lxml')
                content = soup.get_text(separator=' ', strip=True)[:800]
            else:
                content = ""
            
            parts.append(f"""
【文章{i}】
来源：{article.feed_name}
标题：{article.title}
AI摘要：{content}
""")
        
        return "\n".join(parts)
    
    def _fix_json(self, json_str: str) -> str:
        """
        尝试修复常见的 JSON 格式错误
        """
        # 移除可能的前后缀文字
        json_str = json_str.strip()
        
        # 查找 JSON 对象的开始和结束
        start = json_str.find('{')
        end = json_str.rfind('}')
        if start != -1 and end != -1 and end > start:
            json_str = json_str[start:end+1]
        
        # 修复常见错误
        # 1. 移除尾部多余的逗号
        json_str = re.sub(r',\s*}', '}', json_str)
        json_str = re.sub(r',\s*]', ']', json_str)
        
        # 2. 修复未转义的引号
        # 这是一个简化的修复，可能不适用于所有情况
        
        # 3. 修复缺失的引号（常见于键名）
        json_str = re.sub(r'(\{|,)\s*([a-zA-Z_][a-zA-Z0-9_]*)\s*:', r'\1"\2":', json_str)
        
        # 4. 替换单引号为双引号
        # 只在值位置替换，避免破坏字符串内容
        
        return json_str
    
    def _create_default_topics(self, articles: List[Article]) -> List[Topic]:
        """
        创建默认话题（当 JSON 解析失败时使用）
        按公众号分组显示文章
        """
        from collections import defaultdict
        
        # 按公众号分组
        feed_groups = defaultdict(list)
        for article in articles:
            feed_groups[article.feed_name].append(article)
        
        topics = []
        for feed_name, feed_articles in feed_groups.items():
            # 为每个公众号创建一个话题
            sources = [
                TopicSource(
                    title=a.title,
                    key_contribution=a.ai_summary[:100] + "..." if a.ai_summary and len(a.ai_summary) > 100 else (a.ai_summary or ""),
                    url=a.url,
                    feed_name=a.feed_name
                )
                for a in feed_articles[:5]  # 最多显示5篇
            ]
            
            topic = Topic(
                name=f"{feed_name}资讯",
                highlight=f"来自{feed_name}的{len(feed_articles)}篇文章",
                articles=feed_articles,
                sources=sources
            )
            topics.append(topic)
        
        return topics
    
    def _parse_topic_result(
        self,
        result: str,
        articles: List[Article]
    ) -> List[Topic]:
        """解析 AI 返回的话题聚合结果（带 JSON 修复）"""
        topics = []
        
        try:
            # 尝试提取 JSON
            json_match = re.search(r'```json\s*(.*?)\s*```', result, re.DOTALL)
            if json_match:
                json_str = json_match.group(1)
            else:
                # 尝试查找 JSON 对象
                json_str = result
            
            # 尝试直接解析
            try:
                data = json.loads(json_str)
            except json.JSONDecodeError:
                # 尝试修复 JSON
                logger.info("尝试修复 JSON...")
                fixed_json = self._fix_json(json_str)
                data = json.loads(fixed_json)
            
            for topic_data in data.get('topics', []):
                # 匹配相关文章
                related_articles = []
                article_titles = topic_data.get('articles', [])
                
                # 如果有 sources 字段，从中提取文章标题
                if not article_titles and topic_data.get('sources'):
                    article_titles = [s.get('title', '') for s in topic_data.get('sources', [])]
                
                for title in article_titles:
                    for article in articles:
                        if title in article.title or article.title in title:
                            related_articles.append(article)
                            break
                
                # 解析数据与数字
                data_numbers = []
                for item in topic_data.get('data_numbers', []):
                    data_numbers.append(DataNumber(
                        content=item.get('content', ''),
                        context=item.get('context', ''),
                        source=item.get('source', '')
                    ))
                
                # 解析事件与动态
                events_news = []
                for item in topic_data.get('events_news', []):
                    events_news.append(EventNews(
                        content=item.get('content', ''),
                        time=item.get('time', ''),
                        parties=item.get('parties', ''),
                        source=item.get('source', '')
                    ))
                
                # 解析内幕与洞察
                insider_insights = []
                for item in topic_data.get('insider_insights', []):
                    insider_insights.append(InsiderInsight(
                        content=item.get('content', ''),
                        insight_type=item.get('type', ''),
                        source=item.get('source', '')
                    ))
                
                # 解析来源（并匹配文章 URL）
                sources = []
                for source_data in topic_data.get('sources', []):
                    source_title = source_data.get('title', '')
                    # 尝试匹配文章获取 URL
                    matched_url = ""
                    matched_feed = ""
                    matched_article = None
                    
                    # 提取《》中的标题（如果有）
                    title_match = re.search(r'《(.+?)》', source_title)
                    search_title = title_match.group(1) if title_match else source_title
                    
                    for article in articles:
                        # 多种匹配方式
                        if (search_title in article.title or 
                            article.title in search_title or
                            source_title in article.title or
                            article.title in source_title):
                            matched_url = article.url
                            matched_feed = article.feed_name
                            matched_article = article
                            break
                    
                    # 如果还没匹配上，尝试模糊匹配（关键词）
                    if not matched_url and len(search_title) > 4:
                        keywords = search_title[:min(10, len(search_title))]
                        for article in articles:
                            if keywords in article.title:
                                matched_url = article.url
                                matched_feed = article.feed_name
                                matched_article = article
                                break
                    
                    sources.append(TopicSource(
                        title=matched_article.title if matched_article else source_title,
                        key_contribution=source_data.get('key_contribution', source_data.get('key_point', '')),
                        url=matched_url,
                        feed_name=matched_feed
                    ))
                
                topic = Topic(
                    name=topic_data.get('name', '未命名话题'),
                    highlight=topic_data.get('highlight', ''),
                    articles=related_articles,
                    data_numbers=data_numbers,
                    events_news=events_news,
                    insider_insights=insider_insights,
                    sources=sources,
                    # 兼容旧字段
                    description=topic_data.get('description', ''),
                    ai_analysis=topic_data.get('analysis', ''),
                    key_dates=topic_data.get('key_dates', [])
                )
                topics.append(topic)
                
        except json.JSONDecodeError as e:
            logger.warning(f"解析话题 JSON 失败: {e}")
            # 使用按公众号分组的默认话题
            return self._create_default_topics(articles)
        
        return topics if topics else self._create_default_topics(articles)
