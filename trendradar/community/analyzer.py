# coding=utf-8
"""
社区内容 AI 分析器

包含两个阶段：
1. AI 评分：对每条内容评估相关性和重要性
2. AI 分析：对筛选后的内容进行深度分析
"""

import json
import os
import threading
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

from .collector import CollectedData, SourceData


@dataclass
class ScoredItem:
    """评分后的条目"""
    item: Dict[str, Any]
    score: float  # 1-10
    tags: List[str] = field(default_factory=list)
    reason: str = ""


@dataclass
class ItemAnalysis:
    """单个案例的 AI 分析结果"""
    item_id: str
    title: str
    source_id: str
    source_name: str
    analysis: str  # 详细分析文本
    url: str = ""
    meta: Dict[str, Any] = field(default_factory=dict)  # 原始元数据（得分、评论数等）


@dataclass
class SourceAnalysis:
    """单个来源的分析结果"""
    source_id: str
    source_name: str
    summary: str = ""
    highlights: List[str] = field(default_factory=list)
    trends: List[str] = field(default_factory=list)
    item_analyses: List[ItemAnalysis] = field(default_factory=list)  # 每个案例的详细分析


@dataclass
class AnalysisResult:
    """分析结果"""
    success: bool
    scored_items: List[ScoredItem] = field(default_factory=list)
    source_analyses: Dict[str, SourceAnalysis] = field(default_factory=dict)
    overall_summary: str = ""
    error: Optional[str] = None
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "scored_items_count": len(self.scored_items),
            "source_analyses": {
                k: {
                    "source_id": v.source_id,
                    "source_name": v.source_name,
                    "summary": v.summary,
                    "highlights": v.highlights,
                    "trends": v.trends,
                    "item_analyses": [
                        {
                            "item_id": ia.item_id,
                            "title": ia.title,
                            "analysis": ia.analysis,
                            "url": ia.url,
                            "meta": ia.meta,
                        }
                        for ia in v.item_analyses
                    ],
                }
                for k, v in self.source_analyses.items()
            },
            "overall_summary": self.overall_summary,
            "error": self.error,
        }


class CommunityAnalyzer:
    """
    社区内容 AI 分析器
    
    两阶段分析：
    1. 评分阶段：对所有内容进行相关性评分
    2. 分析阶段：对各来源内容进行深度分析
    """
    
    def __init__(
        self,
        topics: List[str],
        prompt_file: str = "community_prompts.txt",
        model: str = None,
        api_base: str = None,
        api_key: str = None,
        language: str = "Chinese",
        top_n: int = 30,  # 每个来源保留的 Top N
        proxy_url: str = None,  # 代理 URL（用于内容抓取）
    ):
        """
        初始化分析器
        
        Args:
            topics: 关注的话题列表
            prompt_file: 提示词文件
            model: AI 模型
            api_base: API 端点
            api_key: API Key
            language: 输出语言
            top_n: 每个来源保留的条目数
            proxy_url: 代理 URL
        """
        self.topics = topics
        self.prompt_file = prompt_file
        self.model = model
        self.api_base = api_base
        self.api_key = api_key
        self.language = language
        self.top_n = top_n
        self.proxy_url = proxy_url
        
        # 加载提示词
        self.scoring_prompt = self._load_scoring_prompt()
        self.analysis_prompt = self._load_analysis_prompt()
        
        # 初始化 AI 客户端
        self.ai_client = None
        self._init_ai_client()
        
        # 初始化内容抓取器
        self.content_fetcher = None
        self._init_content_fetcher()
    
    def _init_ai_client(self):
        """初始化 AI 客户端"""
        try:
            from trendradar.ai.client import AIClient
            
            # AIClient 接受配置字典
            ai_config = {
                "model": self.model,
                "api_base": self.api_base,
                "api_key": self.api_key,
                "temperature": 0.7,
                "max_tokens": 4000,
                "timeout": 600,
            }
            
            self.ai_client = AIClient(ai_config)
            print(f"[CommunityAnalyzer] AI 客户端初始化成功: {self.model}")
            
        except Exception as e:
            print(f"[CommunityAnalyzer] AI 客户端初始化失败: {e}")
    
    def _init_content_fetcher(self):
        """初始化内容抓取器"""
        try:
            from .content_fetcher import ContentFetcher
            
            self.content_fetcher = ContentFetcher(
                cache_dir="output/community/content_cache",
                proxy_url=self.proxy_url,
                timeout=30,
                max_content_length=50000,
            )
            print(f"[CommunityAnalyzer] 内容抓取器初始化成功")
            
        except Exception as e:
            print(f"[CommunityAnalyzer] 内容抓取器初始化失败: {e}")
    
    def _load_scoring_prompt(self) -> str:
        """加载评分提示词"""
        return f"""你是一位内容筛选专家。请对以下内容进行相关性评分（1-10分）。

重点关注的话题：{', '.join(self.topics)}

评分标准：
- 9-10分：直接相关的重大新闻、突破性进展、重要产品发布
- 7-8分：相关且有价值的讨论、观点、趋势
- 5-6分：间接相关或一般性内容
- 1-4分：不相关或低价值内容

请以 JSON 格式返回评分结果：
```json
{{
  "items": [
    {{"id": "item_id", "score": 8, "tags": ["AI", "突破"], "reason": "简短说明"}}
  ]
}}
```

只返回 JSON，不要其他内容。"""
    
    def _load_analysis_prompt(self) -> str:
        """加载分析提示词"""
        # 尝试从文件加载
        prompt_paths = [
            Path("prompts") / self.prompt_file,
            Path("config/prompts") / self.prompt_file,
            Path(__file__).parent.parent.parent / "prompts" / self.prompt_file,
        ]
        
        for prompt_path in prompt_paths:
            if prompt_path.exists():
                try:
                    content = prompt_path.read_text(encoding="utf-8")
                    print(f"[CommunityAnalyzer] 加载提示词: {prompt_path}")
                    return content
                except Exception as e:
                    print(f"[CommunityAnalyzer] 读取提示词失败: {e}")
        
        # 使用默认提示词
        print("[CommunityAnalyzer] 使用默认提示词")
        return self._get_default_analysis_prompt()
    
    def _get_default_analysis_prompt(self) -> str:
        """获取默认分析提示词"""
        return f"""你是一位资深的科技内容分析师，擅长从海量信息中提炼关键洞察。

请对以下来源的内容进行深度分析，输出结构化的中文摘要。

重点关注话题：{', '.join(self.topics)}

请按以下格式输出（使用 Markdown）：

## 核心摘要
（3-5 句话概括今日最重要的动态和趋势）

## 热点亮点
（列出 3-5 个最值得关注的内容，每条包含标题和简要说明）

## 趋势洞察
（基于今日内容，分析 2-3 个值得关注的趋势或信号）

## 关键词
（列出今日内容涉及的关键技术、公司、人物、概念）

注意：
1. 使用中文输出
2. 保持客观，基于原文内容分析
3. 突出重要性和时效性
4. 信息要有具体的来源"""
    
    def analyze(self, data: CollectedData, quick_mode: bool = True, items_per_source: int = 10) -> AnalysisResult:
        """
        分析收集的数据
        
        新流程：
        1. 每个案例单独调用 AI 进行详细分析
        2. 将所有案例分析结果聚合，再调用一次 AI 生成总体摘要
        
        Args:
            data: 收集的数据
            quick_mode: 快速模式（跳过逐案例分析，只生成总结）
            items_per_source: 每个来源分析的案例数量
            
        Returns:
            AnalysisResult 对象
        """
        if not self.ai_client:
            return AnalysisResult(
                success=False,
                error="AI 客户端未初始化"
            )
        
        try:
            source_analyses = {}
            
            if quick_mode:
                # 快速模式：跳过逐案例分析，直接生成总结
                print("[CommunityAnalyzer] 快速模式：生成总体摘要...")
                overall_summary = self._generate_quick_summary_from_raw(data)
            else:
                # 详细模式：逐案例 AI 分析 + 聚合总结
                print(f"[CommunityAnalyzer] 详细模式：每个来源分析 {items_per_source} 个案例...")
                
                # 阶段 1：逐案例分析
                for source_id, source_data in data.sources.items():
                    if source_data.items:
                        print(f"[CommunityAnalyzer] 分析 {source_data.source_name}...")
                        source_analysis = self._analyze_source_items(
                            source_id, 
                            source_data, 
                            max_items=items_per_source
                        )
                        source_analyses[source_id] = source_analysis
                
                # 阶段 2：聚合所有分析结果，生成总体摘要
                print("[CommunityAnalyzer] 聚合分析结果，生成总体摘要...")
                overall_summary = self._aggregate_and_summarize(source_analyses)
            
            return AnalysisResult(
                success=True,
                scored_items=[],
                source_analyses=source_analyses,
                overall_summary=overall_summary,
            )
            
        except Exception as e:
            print(f"[CommunityAnalyzer] 分析失败: {e}")
            import traceback
            traceback.print_exc()
            return AnalysisResult(
                success=False,
                error=str(e)
            )
    
    def _analyze_source_items(self, source_id: str, source_data: SourceData, max_items: int = 10) -> SourceAnalysis:
        """
        分析单个来源的所有案例（使用线程池并发）

        Args:
            source_id: 来源 ID
            source_data: 来源数据
            max_items: 最多分析的案例数量

        Returns:
            SourceAnalysis 对象，包含每个案例的详细分析
        """
        source_names = {
            "hackernews": "HackerNews",
            "reddit": "Reddit",
            "github": "GitHub",
            "producthunt": "ProductHunt",
            "kickstarter": "Kickstarter",
            "twitter": "Twitter",
        }
        source_name = source_names.get(source_id, source_id)

        items_to_analyze = source_data.items[:max_items]
        item_analyses = []
        progress_lock = threading.Lock()
        completed_count = [0]  # 使用列表以便在闭包中修改

        def analyze_item(idx, item):
            """单个条目的分析函数（在线程池中运行）"""
            try:
                analysis = self._analyze_single_item(item, source_id, source_name)
                with progress_lock:
                    completed_count[0] += 1
                    print(f"  [{completed_count[0]}/{len(items_to_analyze)}] 分析: {item.get('title', '')[:50]}...")
                return (idx, analysis, None)
            except Exception as e:
                with progress_lock:
                    completed_count[0] += 1
                    print(f"    ⚠️ 分析失败: {e}")
                return (idx, None, e)

        # 使用线程池并发分析（5个线程平衡并发和API限流）
        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(analyze_item, idx, item): idx
                for idx, item in enumerate(items_to_analyze, 1)
            }

            results = []
            for future in as_completed(futures):
                idx, analysis, error = future.result()
                results.append((idx, analysis, error))

        # 按原始顺序排序结果，确保输出一致性
        results.sort(key=lambda x: x[0])

        # 构建最终的 item_analyses
        for idx, analysis, error in results:
            if analysis:
                item_analyses.append(analysis)
            else:
                # 创建失败的分析结果
                item = items_to_analyze[idx - 1]
                item_analyses.append(ItemAnalysis(
                    item_id=item.get("id", str(idx)),
                    title=item.get("title") or item.get("name") or "",
                    source_id=source_id,
                    source_name=source_name,
                    analysis=f"分析失败: {error}",
                    url=item.get("url", ""),
                    meta=self._extract_item_meta(item),
                ))

        print(f"  ✅ {source_name} 完成: {len(item_analyses)} 个案例")

        return SourceAnalysis(
            source_id=source_id,
            source_name=source_name,
            item_analyses=item_analyses,
        )
    
    def _analyze_single_item(self, item: Dict[str, Any], source_id: str, source_name: str) -> ItemAnalysis:
        """
        使用 AI 分析单个案例
        
        流程：
        1. 先抓取链接的完整内容
        2. 将完整内容作为上下文发给 AI 分析
        3. 如果无法获取内容则报错
        
        Args:
            item: 案例数据
            source_id: 来源 ID
            source_name: 来源名称
            
        Returns:
            ItemAnalysis 对象
        """
        title = item.get("title") or item.get("name") or ""
        description = item.get("description") or item.get("tagline") or ""
        url = item.get("url", "")
        
        # 提取元信息
        meta = self._extract_item_meta(item)
        meta_text = ", ".join([f"{k}: {v}" for k, v in meta.items() if v])
        
        # ===== 关键步骤：抓取链接内容 =====
        fetched_content = ""
        fetch_error = ""
        
        if url and self.content_fetcher:
            print(f"    📥 抓取内容: {url[:60]}...")
            fetched = self.content_fetcher.fetch(url)
            
            if fetched.success and fetched.content:
                fetched_content = fetched.content
                print(f"    ✅ 内容抓取成功 ({len(fetched_content)} 字符)")
            else:
                fetch_error = fetched.error or "内容为空"
                print(f"    ⚠️ 内容抓取失败: {fetch_error}")
        
        # 如果没有完整内容，尝试备选方案
        if not fetched_content:
            # 方案 1：对于 GitHub 项目，尝试获取 README
            if source_id == "github":
                readme_content = self._fetch_github_readme(item)
                if readme_content:
                    fetched_content = readme_content
                    print(f"    ✅ GitHub README 获取成功 ({len(readme_content)} 字符)")
            
            # 方案 2：对于 HackerNews，尝试获取讨论页面内容
            elif source_id == "hackernews" and item.get("id"):
                hn_content = self._fetch_hackernews_discussion(item)
                if hn_content:
                    fetched_content = hn_content
                    print(f"    ✅ HN 讨论内容获取成功 ({len(hn_content)} 字符)")

            # 方案 2.5：对于 Reddit，使用 RSS Feed 中的 selftext
            elif source_id == "reddit":
                reddit_content = item.get("selftext", "")
                if reddit_content and len(reddit_content) > 100:
                    fetched_content = reddit_content
                    print(f"    ✅ 使用 RSS 内容 ({len(reddit_content)} 字符)")

            # 方案 3：使用描述信息
            if not fetched_content and description and len(description) > 100:
                fetched_content = f"[项目/文章描述]\n{description}"
                print(f"    📝 使用描述作为内容 ({len(description)} 字符)")
        
        # 如果仍然没有内容，尝试最后的备选方案
        if not fetched_content or len(fetched_content) < 50:
            # 对于 HackerNews，即使原文获取失败，也可以基于标题+元信息进行分析
            if source_id == "hackernews":
                # 构建一个基于元数据的内容
                meta_content = f"""[HackerNews 热门内容]

标题: {title}
得分: {item.get('score', '未知')}
评论数: {item.get('comments', '未知')}
作者: {item.get('author', '未知')}
链接: {url}

注意: 原文内容无法直接获取（可能是付费墙或访问限制）。
以下分析基于标题和 HackerNews 社区的关注度进行推断。
"""
                fetched_content = meta_content
                print(f"    📊 使用 HN 元数据作为内容")
            else:
                error_msg = f"无法获取详细内容: {fetch_error or '内容过短'}"
                print(f"    ❌ {error_msg}")
                return ItemAnalysis(
                    item_id=item.get("id", ""),
                    title=title,
                    source_id=source_id,
                    source_name=source_name,
                    analysis=f"**分析失败**：{error_msg}\n\n仅有标题信息：{title}",
                    url=url,
                    meta=meta,
                )
        
        # ===== 使用完整内容进行 AI 分析 =====
        # 限制内容长度，避免超出 token 限制
        content_for_analysis = fetched_content[:15000] if len(fetched_content) > 15000 else fetched_content
        
        prompt = f"""请对以下来自 {source_name} 的内容进行详细分析：

**标题**：{title}
**元信息**：{meta_text if meta_text else "无"}
**链接**：{url if url else "无"}

---

**完整内容**：

{content_for_analysis}

---

请基于以上**完整内容**进行深入分析（使用中文）：

### 内容概述
（详细描述这是什么内容、涉及什么事件/项目/产品、背景是什么）

### 关键信息提取
- **涉及方**：公司、产品、人物、组织
- **关键数据**：具体的金额、数量、比例、时间节点、性能指标等
- **技术细节**：技术栈、架构、实现方式、算法等

### 核心观点/亮点
（从内容中提取的核心观点、重要结论、独特见解）

### 重要性分析
（为什么这个内容值得关注，对行业/技术/投资的潜在影响）

### 延伸思考
（基于这个内容，有什么值得进一步关注的问题或趋势）

---

要求：
1. 必须基于提供的完整内容进行分析，不要猜测
2. 提取具体的数字、公司名、产品名、技术名称
3. 内容要详实具体，让读者不看原文也能了解核心信息"""

        messages = [
            {"role": "system", "content": "你是一位资深科技内容分析师，擅长从文章中提取关键信息并进行深度分析。请务必基于提供的完整内容进行分析，不要凭空猜测。"},
            {"role": "user", "content": prompt},
        ]
        
        try:
            analysis_text = self.ai_client.chat(messages)
            return ItemAnalysis(
                item_id=item.get("id", ""),
                title=title,
                source_id=source_id,
                source_name=source_name,
                analysis=analysis_text,
                url=url,
                meta=meta,
            )
        except Exception as e:
            raise e
    
    def _fetch_github_readme(self, item: Dict[str, Any]) -> str:
        """
        获取 GitHub 项目的 README
        
        Args:
            item: GitHub 项目数据
            
        Returns:
            README 内容
        """
        try:
            full_name = item.get("full_name", "")
            if not full_name:
                return ""
            
            # 尝试获取 README
            readme_url = f"https://raw.githubusercontent.com/{full_name}/main/README.md"
            
            import requests
            response = requests.get(readme_url, timeout=15)
            
            if response.status_code == 404:
                # 尝试 master 分支
                readme_url = f"https://raw.githubusercontent.com/{full_name}/master/README.md"
                response = requests.get(readme_url, timeout=15)
            
            if response.status_code == 200:
                content = response.text
                # 限制长度
                if len(content) > 10000:
                    content = content[:10000] + "\n\n[README 已截断...]"
                return content
            
            return ""
            
        except Exception as e:
            print(f"    ⚠️ GitHub README 获取失败: {e}")
            return ""
    
    def _fetch_hackernews_discussion(self, item: Dict[str, Any]) -> str:
        """
        获取 HackerNews 讨论内容（评论摘要）
        
        Args:
            item: HackerNews 条目数据
            
        Returns:
            讨论内容
        """
        try:
            item_id = item.get("id", "")
            if not item_id:
                return ""
            
            # 使用 HN API 获取评论
            api_url = f"https://hn.algolia.com/api/v1/items/{item_id}"
            
            import requests
            response = requests.get(api_url, timeout=15)
            
            if response.status_code != 200:
                return ""
            
            data = response.json()
            
            # 构建讨论内容
            content_parts = []
            content_parts.append(f"# {data.get('title', '')}")
            content_parts.append(f"\n**作者**: {data.get('author', '')}")
            content_parts.append(f"**得分**: {data.get('points', 0)}")
            content_parts.append(f"**评论数**: {len(data.get('children', []))}")
            
            # 提取文章内容（如果有）
            story_text = data.get('text', '')
            if story_text:
                content_parts.append(f"\n## 文章内容\n{story_text}")
            
            # 提取热门评论
            children = data.get('children', [])
            if children:
                content_parts.append("\n## 热门评论")
                
                # 按点赞数排序，取前 10 条
                top_comments = sorted(
                    [c for c in children if c.get('text')],
                    key=lambda x: x.get('points', 0) or 0,
                    reverse=True
                )[:10]
                
                for i, comment in enumerate(top_comments, 1):
                    author = comment.get('author', '匿名')
                    points = comment.get('points', 0) or 0
                    text = comment.get('text', '')
                    
                    # 清理 HTML 标签
                    import re
                    text = re.sub(r'<[^>]+>', '', text)
                    
                    # 限制评论长度
                    if len(text) > 500:
                        text = text[:500] + "..."
                    
                    content_parts.append(f"\n### 评论 {i} ({author}, {points}赞)\n{text}")
            
            content = "\n".join(content_parts)
            
            # 限制总长度
            if len(content) > 8000:
                content = content[:8000] + "\n\n[讨论内容已截断...]"
            
            return content
            
        except Exception as e:
            print(f"    ⚠️ HN 讨论获取失败: {e}")
            return ""
    
    def _extract_item_meta(self, item: Dict[str, Any]) -> Dict[str, Any]:
        """提取案例的元信息"""
        meta = {}
        if "score" in item:
            meta["得分"] = item["score"]
        if "comments" in item:
            meta["评论数"] = item["comments"]
        if "stars" in item:
            meta["Stars"] = item["stars"]
        if "forks" in item:
            meta["Forks"] = item["forks"]
        if "votes" in item:
            meta["投票"] = item["votes"]
        if "language" in item and item["language"]:
            meta["语言"] = item["language"]
        if "author" in item and item["author"]:
            meta["作者"] = item["author"]
        if "subreddit" in item and item["subreddit"]:
            meta["板块"] = f"r/{item['subreddit']}"
        if "topics" in item and item["topics"]:
            meta["标签"] = ", ".join(item["topics"][:5])
        return meta
    
    def _aggregate_and_summarize(self, source_analyses: Dict[str, SourceAnalysis]) -> str:
        """
        聚合所有案例分析结果，生成总体摘要
        
        Args:
            source_analyses: 各来源的分析结果
            
        Returns:
            总体摘要文本
        """
        # 收集所有案例的分析摘要
        all_analyses = []
        for source_id, source_analysis in source_analyses.items():
            source_name = source_analysis.source_name
            for item_analysis in source_analysis.item_analyses:
                # 提取每个案例的关键信息
                all_analyses.append(f"""
【{source_name}】{item_analysis.title}
{item_analysis.analysis[:500]}...
""")
        
        # 构建聚合提示词
        analyses_text = "\n---\n".join(all_analyses[:30])  # 最多 30 个案例
        
        prompt = f"""以下是今日社区热点内容的逐案例分析结果，请基于这些分析生成一份全面的总体摘要报告。

{analyses_text}

---

请按以下结构生成总体摘要（使用中文）：

## 今日要点综述

（按主题分类详细展开今日所有重要内容，每个主题要包含：涉及的事件/项目、关键数据、潜在影响等。不要简化，要详尽。）

### AI 大模型与基础设施
（汇总今日与 AI 模型、训练、推理、芯片等相关的所有内容，每个内容详细展开）

### 开源项目与开发工具
（汇总今日热门的开源项目、开发工具，每个项目详细介绍）

### 创业与投资
（汇总今日与创业公司、融资相关的内容）

### 产品与创新
（汇总今日新发布的产品、创新应用）

### 行业动态
（汇总今日重要的行业新闻、趋势信号）

（根据实际内容调整主题分类）

---

## 关键数据汇总

| 数据 | 说明 | 来源 |
|------|------|------|
| ... | ... | ... |

---

## 趋势与洞察

（基于今日所有内容，归纳 3-5 个趋势或洞察，每个趋势要有具体的事件/数据支撑）

### 趋势 1: [名称]
**现象**：...
**支撑证据**：...
**潜在影响**：...

---

要求：
1. 内容要全面、详尽，覆盖所有重要信息
2. 必须包含具体的数字、公司名、产品名
3. 让读者不看原文也能获得完整信息"""

        messages = [
            {"role": "system", "content": "你是一位资深科技内容分析师，擅长从多个分析报告中提炼关键信息并生成结构化的总体摘要。"},
            {"role": "user", "content": prompt},
        ]
        
        try:
            return self.ai_client.chat(messages)
        except Exception as e:
            print(f"[CommunityAnalyzer] 聚合摘要生成失败: {e}")
            return ""
    
    def _generate_quick_summary_from_raw(self, data: CollectedData) -> str:
        """快速生成总体摘要（直接从原始数据，不经过 AI 评分）"""
        # 收集各来源的热门条目，包含完整详细信息
        items_by_source = {}
        source_names = {
            "hackernews": "HackerNews",
            "reddit": "Reddit",
            "github": "GitHub",
            "producthunt": "ProductHunt",
            "kickstarter": "Kickstarter",
            "twitter": "Twitter",
        }
        
        for source_id, source_data in data.sources.items():
            source_name = source_names.get(source_id, source_id)
            items_list = []
            
            # 每个来源取所有条目（最多 30 条，确保信息全面）
            for idx, item in enumerate(source_data.items[:30], 1):
                title = item.get("title") or item.get("name") or ""
                description = item.get("description") or item.get("tagline") or ""
                url = item.get("url", "")
                
                # 构建详细信息
                meta_parts = []
                if "score" in item:
                    meta_parts.append(f"得分:{item['score']}")
                if "comments" in item:
                    meta_parts.append(f"评论:{item['comments']}")
                if "stars" in item:
                    meta_parts.append(f"⭐{item['stars']}")
                if "forks" in item:
                    meta_parts.append(f"forks:{item['forks']}")
                if "votes" in item:
                    meta_parts.append(f"投票:{item['votes']}")
                if "language" in item and item["language"]:
                    meta_parts.append(f"语言:{item['language']}")
                if "author" in item and item["author"]:
                    meta_parts.append(f"作者:{item['author']}")
                if "subreddit" in item and item["subreddit"]:
                    meta_parts.append(f"板块:r/{item['subreddit']}")
                if "topics" in item and item["topics"]:
                    topics_str = ", ".join(item["topics"][:5])
                    meta_parts.append(f"标签:{topics_str}")
                
                meta_str = f" | {', '.join(meta_parts)}" if meta_parts else ""
                
                # 构建条目文本
                item_text = f"  {idx}. **{title}**{meta_str}"
                if description and description != title:
                    item_text += f"\n     描述: {description[:200]}"
                if url:
                    item_text += f"\n     链接: {url}"
                
                items_list.append(item_text)
            
            if items_list:
                items_by_source[source_name] = items_list
        
        if not items_by_source:
            return "今日暂无热点内容。"
        
        # 构建结构化的内容文本
        content_parts = []
        for source_name, items in items_by_source.items():
            content_parts.append(f"\n\n### 【{source_name}】 ({len(items)} 条)")
            content_parts.append("\n".join(items))
        
        items_text = "\n".join(content_parts)
        
        prompt = f"""你是一位资深科技内容分析师。请对以下今日社区热点内容进行**全面、深入、详尽**的分析。

**核心原则**：
- 不要凝练，不要省略，内容要尽可能丰富详尽
- 每个信息源至少分析 10 个条目，有多少分析多少
- 每个条目都要详细展开，包含背景、核心内容、关键数字、影响分析等
- 相同话题在不同来源出现时，聚合分析并综合各方观点
- 所有信息必须注明来源

{items_text}

---

请按以下格式输出（使用中文）：

## 今日要点综述

（对今日所有热点内容进行全面梳理，按主题/领域分类详细展开。每个主题要包含：相关的所有内容标题、涉及的公司/人物、关键数字、社区讨论焦点、潜在影响等。不要简化，要详尽。）

### AI 大模型与基础设施

（详细分析今日与 AI 模型、训练、推理、芯片等相关的所有内容）

**[内容1标题]**（来源：xxx）
- 事件背景：什么情况下发生的
- 核心内容：具体发生了什么，涉及哪些公司/人物
- 关键数据：金额、用户数、性能指标等
- 社区观点：社区讨论的主要观点
- 潜在影响：对行业的意义

**[内容2标题]**（来源：xxx）
...（同样详细展开）

**[内容3标题]**（来源：xxx）
...（继续列出所有相关内容）

### 开源项目与开发工具

（详细分析今日热门的开源项目、开发工具、框架等）

**[项目1名称]**（来源：GitHub，Stars: xxx）
- 项目定位：解决什么问题
- 技术特点：核心功能、技术栈、架构设计
- 使用场景：适合什么应用
- 为何值得关注：创新点、发展潜力

**[项目2名称]**（来源：xxx）
...（继续列出所有相关项目）

### 创业与投资

（详细分析今日与创业公司、融资、商业模式相关的内容）

**[事件1]**（来源：xxx）
- 交易详情：金额、估值、参与方
- 公司背景：公司业务、发展阶段
- 市场意义：对行业格局的影响

### 产品与创新

（详细分析今日新发布的产品、创新应用等）

**[产品1名称]**（来源：xxx）
- 产品定位：目标用户、解决的问题
- 核心功能：主要功能特点
- 差异化：与竞品的区别
- 商业模式：定价、变现方式

### 行业动态与趋势

（详细分析今日重要的行业新闻、趋势信号等）

**[新闻1]**（来源：xxx）
- 事件概述：发生了什么
- 背景分析：为什么发生
- 行业影响：对行业的潜在影响

（根据实际内容调整主题分类，确保覆盖所有重要信息）

---

## 分来源详细分析

（对每个来源的内容进行逐条详细分析。每个来源至少分析 10 个条目。）

### HackerNews 详细分析（至少10条）

#### 1. [标题]
**来源**：HackerNews（得分: xxx，评论: xxx）

**事件/项目概述**：
（详细描述这是什么、发生了什么、涉及哪些公司/人物/技术。不要一句话带过，要详细说明背景和来龙去脉。）

**关键信息提取**：
- 具体数字：金额、用户数、性能指标、时间节点等
- 技术细节：架构、实现方式、技术栈等
- 涉及方：公司、产品、人物、组织等

**社区讨论焦点**：
（社区对此的主要观点、争议、补充信息、不同声音等）

**重要性与影响**：
（为什么这个内容值得关注，对行业/技术/投资的潜在影响是什么）

#### 2. [标题]
...（同样详细展开，不要简化）

#### 3. [标题]
...

#### 4. [标题]
...

#### 5. [标题]
...

#### 6. [标题]
...

#### 7. [标题]
...

#### 8. [标题]
...

#### 9. [标题]
...

#### 10. [标题]
...

（如有更多值得分析的内容，继续列出）

---

### Reddit 详细分析（至少10条）

#### 1. [标题]
**来源**：Reddit r/xxx（点赞: xxx，评论: xxx）

**内容概述**：
（详细描述帖子内容、讨论背景等）

**关键信息提取**：
- 具体数字、技术细节、涉及方等

**社区讨论焦点**：
（主要观点、争议、补充信息等）

**重要性与影响**：
（为什么值得关注）

#### 2. [标题]
...

（至少分析10条，如有更多则继续）

---

### GitHub 热门项目详细分析（至少10个）

#### 1. [项目名]
**来源**：GitHub（Stars: xxx，Forks: xxx，语言: xxx）

**项目定位**：
（这个项目是做什么的，解决什么问题，目标用户是谁）

**技术特点**：
- 核心功能与架构
- 技术栈与实现方式
- 与同类项目的对比

**代码亮点**：
（如果能从信息中推断，说明代码质量、设计模式等）

**为何值得关注**：
（项目的创新点、应用场景、发展潜力、社区活跃度）

#### 2. [项目名]
...

（至少分析10个项目）

---

### ProductHunt 新产品详细分析（如有数据）

#### 1. [产品名]
**来源**：ProductHunt（投票: xxx）

**产品定位**：
（目标用户、解决的问题、使用场景）

**核心功能**：
（主要功能特点、技术实现）

**商业模式**：
（定价、变现方式、目标市场）

**竞品分析**：
（市场上的竞争对手、差异化优势）

**市场前景**：
（市场机会、潜在风险）

#### 2. [产品名]
...

---

## 关键数据汇总

（提取所有内容中出现的具体数据，完整列出）

| 数据 | 说明 | 背景/意义 | 来源 |
|------|------|----------|------|
| ... | ... | ... | ... |

---

## 技术与产品速览

（列出所有值得关注的技术/项目/产品）

| 名称 | 类型 | 简介 | 亮点 | 来源 |
|------|------|------|------|------|
| ... | ... | ... | ... | ... |

---

## 洞察与趋势

（基于以上所有内容，归纳观察到的趋势、洞察、值得关注的信号）

### 趋势 1: [趋势名称]
**观察到的现象**：具体描述观察到什么
**支撑证据**：列出支撑这个趋势的具体事件、数据、项目（至少3个）
**潜在影响**：对行业、技术、投资的意义

### 趋势 2: [趋势名称]
...

（继续列出所有观察到的趋势）

---

**关键要求**：
1. 每个信息源至少分析 10 个条目
2. 每个条目都要详细展开，包含背景、核心内容、数据、影响等
3. 不要简化、不要省略，内容要丰富详尽
4. 必须包含具体的数字、公司名、产品名、技术名称
5. 所有信息必须注明来源
6. 让读者不看原文也能获得完整、详细的信息"""
        
        try:
            messages = [
                {"role": "system", "content": "你是一位资深科技内容分析师，擅长从海量信息中提取关键数据、事件和洞察。总结的目的不是抽象化，而是找到并记录最重要的具体信息。"},
                {"role": "user", "content": prompt},
            ]
            return self.ai_client.chat(messages)
        except Exception as e:
            print(f"[CommunityAnalyzer] 快速摘要生成失败: {e}")
            return ""
    
    def _generate_quick_summary(self, scored_data: Dict[str, SourceData]) -> str:
        """快速生成总体摘要（基于评分数据）"""
        # 收集所有高分条目
        top_items = []
        for source_id, source_data in scored_data.items():
            source_name = {
                "hackernews": "HackerNews",
                "reddit": "Reddit",
                "github": "GitHub",
                "producthunt": "ProductHunt",
                "kickstarter": "Kickstarter",
                "twitter": "Twitter",
            }.get(source_id, source_id)
            
            for item in source_data.items[:5]:
                title = item.get("title") or item.get("name") or item.get("description", "")[:80]
                score = item.get("ai_score", 0)
                if score >= 6:  # 只包含高分条目
                    top_items.append(f"- [{source_name}] {title} (评分:{score})")
        
        if not top_items:
            return "今日未发现高度相关的热点内容。"
        
        # 构建提示词
        items_text = "\n".join(top_items[:15])
        prompt = f"""基于以下今日热点内容，生成一个简短的总体摘要（3-5 句话），突出最重要的趋势和亮点：

{items_text}

只输出摘要，不需要标题或格式。使用中文，简洁有力。"""
        
        try:
            messages = [
                {"role": "system", "content": "你是一位资深科技内容分析师。"},
                {"role": "user", "content": prompt},
            ]
            return self.ai_client.chat(messages)
        except Exception as e:
            print(f"[CommunityAnalyzer] 快速摘要生成失败: {e}")
            return ""
    
    def _score_items(self, data: CollectedData) -> Dict[str, SourceData]:
        """
        对所有条目进行 AI 评分
        
        Args:
            data: 收集的数据
            
        Returns:
            评分后的数据（按分数筛选 Top N）
        """
        scored_data = {}
        
        for source_id, source_data in data.sources.items():
            if not source_data.items:
                scored_data[source_id] = source_data
                continue
            
            try:
                # 准备评分请求
                items_for_scoring = []
                for item in source_data.items[:50]:  # 最多评估 50 条
                    items_for_scoring.append({
                        "id": item.get("id"),
                        "title": item.get("title") or item.get("name") or item.get("content", "")[:100],
                        "url": item.get("url"),
                    })
                
                # 调用 AI 评分
                scores = self._call_ai_scoring(items_for_scoring)
                
                # 合并分数并排序
                scored_items = []
                score_map = {s["id"]: s for s in scores}
                
                for item in source_data.items:
                    item_id = item.get("id")
                    if item_id in score_map:
                        item["ai_score"] = score_map[item_id].get("score", 5)
                        item["ai_tags"] = score_map[item_id].get("tags", [])
                        item["ai_reason"] = score_map[item_id].get("reason", "")
                    else:
                        item["ai_score"] = 5  # 默认分数
                    scored_items.append(item)
                
                # 按分数排序并取 Top N
                scored_items.sort(key=lambda x: x.get("ai_score", 0), reverse=True)
                top_items = scored_items[:self.top_n]
                
                scored_data[source_id] = SourceData(
                    source_id=source_id,
                    source_name=source_data.source_name,
                    items=top_items,
                    fetch_time=source_data.fetch_time,
                )
                
                print(f"[CommunityAnalyzer] {source_data.source_name} 评分完成，保留 {len(top_items)} 条")
                
            except Exception as e:
                print(f"[CommunityAnalyzer] {source_id} 评分失败: {e}")
                # 使用原始数据
                scored_data[source_id] = source_data
        
        return scored_data
    
    def _call_ai_scoring(self, items: List[Dict]) -> List[Dict]:
        """调用 AI 进行评分"""
        items_text = json.dumps(items, ensure_ascii=False, indent=2)
        
        messages = [
            {"role": "system", "content": self.scoring_prompt},
            {"role": "user", "content": f"请对以下内容评分：\n\n```json\n{items_text}\n```"},
        ]
        
        response = self.ai_client.chat(messages)
        
        # 解析 JSON 响应
        try:
            # 提取 JSON 部分
            json_str = response
            if "```json" in response:
                json_str = response.split("```json")[1].split("```")[0]
            elif "```" in response:
                json_str = response.split("```")[1].split("```")[0]
            
            result = json.loads(json_str.strip())
            return result.get("items", [])
            
        except json.JSONDecodeError as e:
            print(f"[CommunityAnalyzer] JSON 解析失败: {e}")
            return []
    
    def _analyze_source(self, source_id: str, source_data: SourceData) -> SourceAnalysis:
        """分析单个来源的内容"""
        source_names = {
            "hackernews": "HackerNews 技术社区",
            "reddit": "Reddit 社区讨论",
            "kickstarter": "Kickstarter 众筹项目",
            "twitter": "Twitter/X 动态",
        }
        
        # 准备分析内容
        items_text = self._format_items_for_analysis(source_data.items)
        
        prompt = f"""请分析以下 {source_names.get(source_id, source_id)} 的热门内容：

{items_text}

---

请输出：
1. **摘要**：3-5 句话概括这个来源今日的主要内容
2. **亮点**：列出 3-5 个最值得关注的条目
3. **趋势**：基于内容分析 1-2 个趋势或信号

使用 Markdown 格式，中文输出。"""
        
        messages = [
            {"role": "system", "content": "你是一位资深科技内容分析师。"},
            {"role": "user", "content": prompt},
        ]
        
        try:
            response = self.ai_client.chat(messages)
            
            return SourceAnalysis(
                source_id=source_id,
                source_name=source_names.get(source_id, source_id),
                summary=response,
            )
            
        except Exception as e:
            print(f"[CommunityAnalyzer] {source_id} 分析失败: {e}")
            return SourceAnalysis(
                source_id=source_id,
                source_name=source_names.get(source_id, source_id),
                summary=f"分析失败: {e}",
            )
    
    def _format_items_for_analysis(self, items: List[Dict]) -> str:
        """格式化条目用于分析"""
        lines = []
        for i, item in enumerate(items[:20], 1):  # 最多 20 条
            title = item.get("title") or item.get("name") or item.get("content", "")[:100]
            score = item.get("ai_score", "-")
            url = item.get("url", "")
            
            # 添加额外信息
            extra = []
            if "score" in item:
                extra.append(f"得分:{item['score']}")
            if "comments" in item:
                extra.append(f"评论:{item['comments']}")
            if "backers" in item:
                extra.append(f"支持者:{item['backers']}")
            
            extra_str = f" ({', '.join(extra)})" if extra else ""
            lines.append(f"{i}. [{score}分] {title}{extra_str}")
            if url:
                lines.append(f"   {url}")
        
        return "\n".join(lines)
    
    def _generate_overall_summary(self, source_analyses: Dict[str, SourceAnalysis]) -> str:
        """生成总体摘要"""
        if not source_analyses:
            return ""
        
        # 合并各来源的分析
        summaries = []
        for source_id, analysis in source_analyses.items():
            if analysis.summary:
                summaries.append(f"**{analysis.source_name}**:\n{analysis.summary}")
        
        if not summaries:
            return ""
        
        combined = "\n\n---\n\n".join(summaries)
        
        prompt = f"""基于以下各平台的分析，生成一个简短的总体摘要（3-5 句话），突出今日最重要的跨平台趋势和亮点：

{combined}

只输出摘要，不需要标题。使用中文。"""
        
        try:
            messages = [
                {"role": "system", "content": "你是一位资深科技内容分析师。"},
                {"role": "user", "content": prompt},
            ]
            
            return self.ai_client.chat(messages)
            
        except Exception as e:
            print(f"[CommunityAnalyzer] 总体摘要生成失败: {e}")
            return ""
    
    @classmethod
    def from_config(cls, config: dict) -> "CommunityAnalyzer":
        """
        从配置创建分析器
        
        Args:
            config: 完整配置字典
            
        Returns:
            CommunityAnalyzer 实例
        """
        community_config = config.get("COMMUNITY", config.get("community", {}))
        analysis_config = community_config.get("ANALYSIS", community_config.get("analysis", {}))
        
        # 获取 AI 配置（优先使用模块配置，其次使用全局配置）
        ai_config = config.get("AI", config.get("ai", {}))
        
        # 支持大小写 key
        model = (analysis_config.get("MODEL") or analysis_config.get("model") or 
                 ai_config.get("MODEL") or ai_config.get("model"))
        api_base = (analysis_config.get("API_BASE") or analysis_config.get("api_base") or 
                    ai_config.get("API_BASE") or ai_config.get("api_base"))
        api_key = (analysis_config.get("API_KEY") or analysis_config.get("api_key") or 
                   ai_config.get("API_KEY") or ai_config.get("api_key"))
        
        # 获取 topics
        topics = community_config.get("TOPICS", community_config.get("topics", []))
        
        # 获取代理配置
        proxy_config = community_config.get("PROXY", community_config.get("proxy", {}))
        proxy_url = None
        if proxy_config.get("ENABLED", proxy_config.get("enabled", False)):
            proxy_url = proxy_config.get("URL", proxy_config.get("url", ""))
        
        return cls(
            topics=topics,
            prompt_file=analysis_config.get("PROMPT_FILE", analysis_config.get("prompt_file", "community_prompts.txt")),
            model=model,
            api_base=api_base,
            api_key=api_key,
            language=analysis_config.get("LANGUAGE", analysis_config.get("language", "Chinese")),
            top_n=analysis_config.get("TOP_N", analysis_config.get("top_n", 30)),
            proxy_url=proxy_url,
        )
