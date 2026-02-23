# coding=utf-8
"""
财经新闻内容提取器

从新闻链接提取正文内容，支持多种来源：
- 华尔街见闻
- 财联社
- 金十数据
- 通用网页
"""

import logging
import re
import time
from typing import Optional, Dict, Any
from dataclasses import dataclass
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


@dataclass
class FetchedContent:
    """提取的内容"""
    url: str
    title: str
    content: str
    author: str = ""
    publish_time: str = ""
    success: bool = True
    error: str = ""


class ContentFetcher:
    """
    财经新闻内容提取器
    
    根据不同来源使用不同的提取策略
    """
    
    def __init__(self, config: Dict[str, Any] = None):
        self.config = config or {}
        self.timeout = self.config.get("timeout", 15)
        self.max_content_length = self.config.get("max_content_length", 10000)
        
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'zh-CN,zh;q=0.9,en;q=0.8',
        })
        
        # 来源特定的提取器
        self._extractors = {
            "wallstreetcn.com": self._extract_wallstreetcn,
            "cls.cn": self._extract_cls,
            "jin10.com": self._extract_jin10,
            "yicai.com": self._extract_yicai,
            "caixin.com": self._extract_caixin,
        }
    
    def fetch(self, url: str, source: str = "") -> FetchedContent:
        """
        获取新闻正文内容
        
        Args:
            url: 新闻链接
            source: 来源标识（可选，用于选择提取策略）
        
        Returns:
            FetchedContent: 提取的内容
        """
        if not url:
            return FetchedContent(
                url=url, title="", content="",
                success=False, error="URL 为空"
            )
        
        try:
            # 解析域名
            parsed = urlparse(url)
            domain = parsed.netloc.lower()
            
            # 查找特定提取器
            extractor = None
            for key, func in self._extractors.items():
                if key in domain:
                    extractor = func
                    break
            
            # 获取页面
            response = self.session.get(url, timeout=self.timeout)
            response.raise_for_status()
            response.encoding = response.apparent_encoding or 'utf-8'
            
            html = response.text
            
            # 使用特定提取器或通用提取器
            if extractor:
                return extractor(url, html)
            else:
                return self._extract_generic(url, html)
            
        except requests.Timeout:
            return FetchedContent(
                url=url, title="", content="",
                success=False, error="请求超时"
            )
        except requests.RequestException as e:
            return FetchedContent(
                url=url, title="", content="",
                success=False, error=f"请求失败: {str(e)}"
            )
        except Exception as e:
            logger.warning(f"内容提取失败 {url}: {e}")
            return FetchedContent(
                url=url, title="", content="",
                success=False, error=str(e)
            )
    
    def fetch_batch(self, urls: list, delay: float = 1.0) -> Dict[str, FetchedContent]:
        """
        批量获取内容
        
        Args:
            urls: URL 列表
            delay: 请求间隔（秒）
        
        Returns:
            URL -> FetchedContent 映射
        """
        results = {}
        for url in urls:
            results[url] = self.fetch(url)
            if delay > 0:
                time.sleep(delay)
        return results
    
    def _extract_wallstreetcn(self, url: str, html: str) -> FetchedContent:
        """提取华尔街见闻文章"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 标题
        title = ""
        title_elem = soup.select_one('h1.article-title, h1.title, article h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        # 正文
        content = ""
        article_elem = soup.select_one('div.article-content, div.content, article .body')
        if article_elem:
            # 移除广告和相关推荐
            for elem in article_elem.select('.ad, .related, .recommend, script, style'):
                elem.decompose()
            content = article_elem.get_text(separator='\n', strip=True)
        
        # 作者和时间
        author = ""
        publish_time = ""
        meta = soup.select_one('.article-meta, .meta')
        if meta:
            author_elem = meta.select_one('.author')
            if author_elem:
                author = author_elem.get_text(strip=True)
            time_elem = meta.select_one('.time, time')
            if time_elem:
                publish_time = time_elem.get_text(strip=True)
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            author=author,
            publish_time=publish_time,
            success=bool(content)
        )
    
    def _extract_cls(self, url: str, html: str) -> FetchedContent:
        """提取财联社文章"""
        soup = BeautifulSoup(html, 'lxml')
        
        title = ""
        title_elem = soup.select_one('h1.f-title, h1, .article-title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        content = ""
        article_elem = soup.select_one('div.article-content, div.content, .f-article')
        if article_elem:
            for elem in article_elem.select('.ad, script, style'):
                elem.decompose()
            content = article_elem.get_text(separator='\n', strip=True)
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            success=bool(content)
        )
    
    def _extract_jin10(self, url: str, html: str) -> FetchedContent:
        """提取金十数据文章"""
        soup = BeautifulSoup(html, 'lxml')
        
        title = ""
        title_elem = soup.select_one('h1.detail-title, h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        content = ""
        article_elem = soup.select_one('div.detail-content, .article-content')
        if article_elem:
            for elem in article_elem.select('.ad, script, style'):
                elem.decompose()
            content = article_elem.get_text(separator='\n', strip=True)
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            success=bool(content)
        )
    
    def _extract_yicai(self, url: str, html: str) -> FetchedContent:
        """提取第一财经文章"""
        soup = BeautifulSoup(html, 'lxml')
        
        title = ""
        title_elem = soup.select_one('h1.m-title, h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        content = ""
        article_elem = soup.select_one('div.m-text, .article-content')
        if article_elem:
            for elem in article_elem.select('.ad, script, style'):
                elem.decompose()
            content = article_elem.get_text(separator='\n', strip=True)
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            success=bool(content)
        )
    
    def _extract_caixin(self, url: str, html: str) -> FetchedContent:
        """提取财新文章（可能需要付费）"""
        soup = BeautifulSoup(html, 'lxml')
        
        title = ""
        title_elem = soup.select_one('h1#Main_Content_articleTitle, h1')
        if title_elem:
            title = title_elem.get_text(strip=True)
        
        content = ""
        article_elem = soup.select_one('div#Main_Content_articleBody, .article-content')
        if article_elem:
            for elem in article_elem.select('.ad, script, style'):
                elem.decompose()
            content = article_elem.get_text(separator='\n', strip=True)
        
        # 检查是否是付费内容
        if "付费" in content or "会员" in content or len(content) < 100:
            return FetchedContent(
                url=url,
                title=title,
                content="[付费内容]",
                success=False,
                error="付费内容需要订阅"
            )
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            success=bool(content)
        )
    
    def _extract_generic(self, url: str, html: str) -> FetchedContent:
        """通用内容提取"""
        soup = BeautifulSoup(html, 'lxml')
        
        # 移除脚本和样式
        for elem in soup(['script', 'style', 'nav', 'header', 'footer', 'aside']):
            elem.decompose()
        
        # 标题
        title = ""
        title_elem = soup.select_one('h1, .title, .article-title')
        if title_elem:
            title = title_elem.get_text(strip=True)
        if not title:
            title_elem = soup.find('title')
            if title_elem:
                title = title_elem.get_text(strip=True)
        
        # 正文 - 尝试多种选择器
        content = ""
        content_selectors = [
            'article', '.article-content', '.article-body',
            '.content', '.post-content', '.entry-content',
            'main', '#content', '.main-content'
        ]
        
        for selector in content_selectors:
            elem = soup.select_one(selector)
            if elem:
                text = elem.get_text(separator='\n', strip=True)
                if len(text) > len(content):
                    content = text
        
        # 如果还是没有，取 body
        if not content or len(content) < 100:
            body = soup.find('body')
            if body:
                content = body.get_text(separator='\n', strip=True)
        
        return FetchedContent(
            url=url,
            title=title,
            content=self._clean_content(content),
            success=bool(content) and len(content) > 50
        )
    
    def _clean_content(self, content: str) -> str:
        """清理内容"""
        if not content:
            return ""
        
        # 移除多余空白
        content = re.sub(r'\n{3,}', '\n\n', content)
        content = re.sub(r' {2,}', ' ', content)
        
        # 移除常见广告文字
        ad_patterns = [
            r'关注.*公众号',
            r'扫码关注',
            r'点击下方',
            r'阅读原文',
            r'责任编辑[:：].*',
            r'来源[:：].*\n',
        ]
        for pattern in ad_patterns:
            content = re.sub(pattern, '', content)
        
        # 截断
        if len(content) > self.max_content_length:
            content = content[:self.max_content_length] + "...[内容已截断]"
        
        return content.strip()
