# coding=utf-8
"""
内容抓取器

负责获取每个案例链接的完整文本内容
支持缓存到本地，避免重复请求
"""

import os
import re
import time
import hashlib
import requests
from pathlib import Path
from typing import Optional, Dict, Any
from dataclasses import dataclass
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse


@dataclass
class FetchedContent:
    """抓取的内容"""
    url: str
    title: str
    content: str  # 提取的正文文本
    raw_html: str = ""  # 原始 HTML（可选保存）
    fetch_time: str = ""
    success: bool = True
    error: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "title": self.title,
            "content": self.content,
            "fetch_time": self.fetch_time,
            "success": self.success,
            "error": self.error,
        }


class ContentFetcher:
    """
    内容抓取器
    
    功能：
    1. 从 URL 抓取网页内容
    2. 提取正文文本（移除 HTML 标签、脚本、样式等）
    3. 缓存到本地文件
    """
    
    USER_AGENT = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    
    def __init__(
        self,
        cache_dir: str = "output/community/content_cache",
        proxy_url: str = None,
        timeout: int = 60,
        max_content_length: int = 50000,  # 最大内容长度（字符）
        request_delay: float = 2.0,  # 请求间隔（秒），避免频率限制
    ):
        """
        初始化抓取器

        Args:
            cache_dir: 缓存目录
            proxy_url: 代理 URL（可选）
            timeout: 请求超时时间（秒）
            max_content_length: 最大内容长度
            request_delay: 请求间隔（秒），避免频率限制
        """
        self.cache_dir = Path(cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        self.proxy_url = proxy_url
        self.timeout = timeout
        self.max_content_length = max_content_length
        self.request_delay = request_delay
        self.last_request_time = 0
        
        # 配置 session - 使用完整的浏览器请求头
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept-Encoding": "gzip, deflate, br",
            "DNT": "1",
            "Connection": "keep-alive",
            "Upgrade-Insecure-Requests": "1",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none",
            "Sec-Fetch-User": "?1",
            "Cache-Control": "max-age=0",
        })
        
        if proxy_url:
            self.session.proxies = {
                "http": proxy_url,
                "https": proxy_url,
            }
    
    def fetch(self, url: str, use_cache: bool = True) -> FetchedContent:
        """
        抓取 URL 内容
        
        Args:
            url: 要抓取的 URL
            use_cache: 是否使用缓存
            
        Returns:
            FetchedContent 对象
        """
        if not url or url == "#":
            return FetchedContent(
                url=url,
                title="",
                content="",
                success=False,
                error="无效的 URL",
            )
        
        # 检查缓存
        if use_cache:
            cached = self._load_from_cache(url)
            if cached:
                return cached
        
        # 特殊处理：GitHub 项目页面
        if "github.com" in url and "/blob/" not in url and "/tree/" not in url:
            result = self._fetch_github_repo(url)
            if result.success:
                self._save_to_cache(url, result)
                return result
        
        # 特殊处理：GitHub README 或代码文件
        if "github.com" in url and ("/blob/" in url or "/tree/" in url):
            result = self._fetch_github_raw(url)
            if result.success:
                self._save_to_cache(url, result)
                return result
        
        # 抓取内容（带重试机制）
        max_retries = 3
        last_error = None

        for attempt in range(max_retries):
            result = self._fetch_url(url)

            # 成功则返回
            if result.success:
                self._save_to_cache(url, result)
                return result

            # 403 错误不重试（被封锁）
            if "403" in result.error:
                return result

            # 其他错误重试
            last_error = result.error
            if attempt < max_retries - 1:
                retry_delay = 2 ** attempt  # 指数退避：1s, 2s, 4s
                print(f"    ⏳ 请求失败，{retry_delay} 秒后重试 ({attempt+1}/{max_retries})...")
                time.sleep(retry_delay)

        # 所有重试都失败
        return FetchedContent(
            url=url,
            title="",
            content="",
            success=False,
            error=last_error or "Max retries exceeded",
        )
    
    def _fetch_github_repo(self, url: str) -> FetchedContent:
        """
        获取 GitHub 仓库信息（包括 README）
        
        Args:
            url: GitHub 仓库 URL
            
        Returns:
            FetchedContent 对象
        """
        try:
            # 解析仓库路径
            parsed = urlparse(url)
            path_parts = parsed.path.strip('/').split('/')
            
            if len(path_parts) < 2:
                return FetchedContent(url=url, title="", content="", success=False, error="无效的 GitHub URL")
            
            owner, repo = path_parts[0], path_parts[1]
            
            # 获取仓库信息
            api_url = f"https://api.github.com/repos/{owner}/{repo}"
            response = self.session.get(api_url, timeout=self.timeout)
            
            content_parts = []
            
            if response.status_code == 200:
                repo_data = response.json()
                content_parts.append(f"# {repo_data.get('full_name', '')}")
                content_parts.append(f"\n**描述**: {repo_data.get('description', '无')}")
                content_parts.append(f"**Stars**: {repo_data.get('stargazers_count', 0)}")
                content_parts.append(f"**Forks**: {repo_data.get('forks_count', 0)}")
                content_parts.append(f"**语言**: {repo_data.get('language', '未知')}")
                content_parts.append(f"**创建时间**: {repo_data.get('created_at', '')}")
                content_parts.append(f"**最后更新**: {repo_data.get('updated_at', '')}")
                
                topics = repo_data.get('topics', [])
                if topics:
                    content_parts.append(f"**标签**: {', '.join(topics)}")
            
            # 获取 README
            readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/main/README.md"
            readme_response = self.session.get(readme_url, timeout=self.timeout)
            
            if readme_response.status_code == 404:
                readme_url = f"https://raw.githubusercontent.com/{owner}/{repo}/master/README.md"
                readme_response = self.session.get(readme_url, timeout=self.timeout)
            
            if readme_response.status_code == 200:
                readme_content = readme_response.text
                # 限制 README 长度
                if len(readme_content) > 8000:
                    readme_content = readme_content[:8000] + "\n\n[README 已截断...]"
                content_parts.append(f"\n\n---\n\n## README\n\n{readme_content}")
            
            if content_parts:
                return FetchedContent(
                    url=url,
                    title=f"{owner}/{repo}",
                    content="\n".join(content_parts),
                    fetch_time=datetime.now().isoformat(),
                    success=True,
                )
            
            return FetchedContent(url=url, title="", content="", success=False, error="无法获取 GitHub 仓库信息")
            
        except Exception as e:
            return FetchedContent(url=url, title="", content="", success=False, error=str(e))
    
    def _fetch_github_raw(self, url: str) -> FetchedContent:
        """
        获取 GitHub 文件的原始内容
        
        Args:
            url: GitHub 文件 URL
            
        Returns:
            FetchedContent 对象
        """
        try:
            # 转换为 raw URL
            if "github.com" in url and "/blob/" in url:
                raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
            elif "github.com" in url and "/tree/" in url:
                # tree 是目录，尝试获取 README
                raw_url = url.replace("github.com", "raw.githubusercontent.com").replace("/tree/", "/") + "/README.md"
            else:
                raw_url = url
            
            # 如果是 PDF，无法直接获取内容
            if raw_url.endswith('.pdf'):
                return FetchedContent(
                    url=url,
                    title="",
                    content="",
                    success=False,
                    error="PDF 文件无法直接抓取内容，请手动查看",
                )
            
            response = self.session.get(raw_url, timeout=self.timeout)
            
            if response.status_code == 200:
                content = response.text
                if len(content) > self.max_content_length:
                    content = content[:self.max_content_length] + "\n\n[内容已截断...]"
                
                return FetchedContent(
                    url=url,
                    title=url.split('/')[-1],
                    content=content,
                    fetch_time=datetime.now().isoformat(),
                    success=True,
                )
            
            return FetchedContent(url=url, title="", content="", success=False, error=f"HTTP {response.status_code}")
            
        except Exception as e:
            return FetchedContent(url=url, title="", content="", success=False, error=str(e))
    
    def _fetch_url(self, url: str) -> FetchedContent:
        """实际抓取 URL"""
        try:
            # 添加请求延迟（避免频率限制）
            if self.request_delay > 0:
                elapsed = time.time() - self.last_request_time
                if elapsed < self.request_delay:
                    time.sleep(self.request_delay - elapsed)
                self.last_request_time = time.time()

            # 针对 Reddit，添加 Referer（模拟从 Google 搜索过来）
            headers = {}
            if "reddit.com" in url:
                headers["Referer"] = "https://www.google.com/"

            response = self.session.get(url, timeout=self.timeout, headers=headers)
            response.raise_for_status()

            # 检查 Content-Type 是否为 HTML
            content_type = response.headers.get('Content-Type', '').lower()
            if 'text/html' not in content_type and 'application/xhtml' not in content_type:
                # 非 HTML 内容（可能是 PDF、图片、JSON 等）
                return FetchedContent(
                    url=url,
                    title="",
                    content="",
                    success=False,
                    error=f"非 HTML 内容: {content_type}",
                )

            # 检测响应内容是否为有效文本（非二进制/乱码）
            text = response.text
            if not self._is_valid_text(text):
                return FetchedContent(
                    url=url,
                    title="",
                    content="",
                    success=False,
                    error="内容包含无效字符或编码错误",
                )

            # 解析 HTML
            soup = BeautifulSoup(text, 'html.parser')
            
            # 提取标题
            title = ""
            if soup.title:
                title = soup.title.get_text(strip=True)
            
            # 移除不需要的元素
            for element in soup(['script', 'style', 'nav', 'footer', 'header', 
                                'aside', 'noscript', 'iframe', 'form']):
                element.decompose()
            
            # 尝试找到主要内容区域
            content = self._extract_main_content(soup)
            
            # 清理文本
            content = self._clean_text(content)
            
            # 限制长度
            if len(content) > self.max_content_length:
                content = content[:self.max_content_length] + "\n\n[内容已截断...]"
            
            if not content or len(content) < 100:
                return FetchedContent(
                    url=url,
                    title=title,
                    content="",
                    success=False,
                    error=f"提取的内容过短或为空（长度: {len(content)}）",
                )
            
            return FetchedContent(
                url=url,
                title=title,
                content=content,
                fetch_time=datetime.now().isoformat(),
                success=True,
            )
            
        except requests.exceptions.Timeout:
            return FetchedContent(
                url=url,
                title="",
                content="",
                success=False,
                error="请求超时",
            )
        except requests.exceptions.HTTPError as e:
            return FetchedContent(
                url=url,
                title="",
                content="",
                success=False,
                error=f"HTTP 错误: {e.response.status_code}",
            )
        except Exception as e:
            return FetchedContent(
                url=url,
                title="",
                content="",
                success=False,
                error=str(e),
            )
    
    def _extract_main_content(self, soup: BeautifulSoup) -> str:
        """
        提取主要内容
        
        优先级：
        1. article 标签
        2. main 标签
        3. 带有 content/article/post 类名的 div
        4. body 全文
        """
        # 尝试 article
        article = soup.find('article')
        if article:
            return article.get_text(separator='\n', strip=True)
        
        # 尝试 main
        main = soup.find('main')
        if main:
            return main.get_text(separator='\n', strip=True)
        
        # 尝试常见的内容容器
        content_selectors = [
            {'class_': re.compile(r'(content|article|post|entry|story)', re.I)},
            {'id': re.compile(r'(content|article|post|entry|story)', re.I)},
            {'class_': 'body'},
            {'class_': 'text'},
        ]
        
        for selector in content_selectors:
            element = soup.find('div', selector)
            if element:
                text = element.get_text(separator='\n', strip=True)
                if len(text) > 500:  # 确保找到的是主要内容
                    return text
        
        # 最后使用 body
        body = soup.find('body')
        if body:
            return body.get_text(separator='\n', strip=True)

        return soup.get_text(separator='\n', strip=True)

    def _is_valid_text(self, text: str) -> bool:
        """
        检测文本是否有效（非二进制/乱码）

        Args:
            text: 待检测的文本

        Returns:
            True 如果是有效的文本，False 如果包含乱码
        """
        if not text or len(text) < 50:
            return False

        # 检查控制字符比例
        # 正常文本的控制字符（除了换行、制表符等）应该很少
        control_chars = sum(1 for c in text if ord(c) < 32 and c not in '\n\r\t')
        control_ratio = control_chars / len(text)

        # 如果控制字符超过 1%，可能是二进制内容
        if control_ratio > 0.01:
            return False

        # 检查无效 UTF-8 字符（替换字符）
        replacement_chars = text.count('\ufffd')
        replacement_ratio = replacement_chars / len(text)

        # 如果替换字符超过 0.5%，说明有编码问题
        if replacement_ratio > 0.005:
            return False

        # 检查可打印字符比例
        printable = sum(1 for c in text if c.isprintable() or c in '\n\r\t')
        printable_ratio = printable / len(text)

        # 可打印字符应该超过 95%
        if printable_ratio < 0.95:
            return False

        # 检查是否有连续的高频乱码模式（如连续的非 BMP 字符）
        # 正常文本很少有连续的非 BMP 字符
        non_bmp_count = sum(1 for c in text if ord(c) > 65535)
        non_bmp_ratio = non_bmp_count / len(text)

        # 非 BMP 字符超过 1% 可能有问题（但 emoji 除外）
        if non_bmp_ratio > 0.01:
            return False

        return True

    def _clean_text(self, text: str) -> str:
        """清理文本"""
        # 移除多余空白
        text = re.sub(r'\n\s*\n', '\n\n', text)
        text = re.sub(r'[ \t]+', ' ', text)
        
        # 移除常见的无用内容
        patterns_to_remove = [
            r'Cookie\s*(Policy|Settings|Consent).*?\n',
            r'Subscribe\s*(to|for).*?\n',
            r'Sign\s*(up|in).*?\n',
            r'Share\s*(on|this).*?\n',
            r'Follow\s*us.*?\n',
            r'Advertisement.*?\n',
            r'Related\s*(Articles?|Posts?).*?\n',
        ]
        
        for pattern in patterns_to_remove:
            text = re.sub(pattern, '', text, flags=re.IGNORECASE)
        
        return text.strip()
    
    def _get_cache_path(self, url: str) -> Path:
        """获取缓存文件路径"""
        url_hash = hashlib.md5(url.encode()).hexdigest()[:16]
        # 使用日期作为子目录
        date_dir = datetime.now().strftime("%Y%m%d")
        cache_path = self.cache_dir / date_dir / f"{url_hash}.txt"
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        return cache_path
    
    def _load_from_cache(self, url: str) -> Optional[FetchedContent]:
        """从缓存加载"""
        cache_path = self._get_cache_path(url)
        
        if not cache_path.exists():
            return None
        
        try:
            content = cache_path.read_text(encoding='utf-8')
            
            # 解析缓存格式
            lines = content.split('\n', 3)
            if len(lines) < 4:
                return None
            
            return FetchedContent(
                url=lines[0].replace("URL: ", ""),
                title=lines[1].replace("Title: ", ""),
                fetch_time=lines[2].replace("Time: ", ""),
                content=lines[3],
                success=True,
            )
        except Exception:
            return None
    
    def _save_to_cache(self, url: str, result: FetchedContent):
        """保存到缓存"""
        cache_path = self._get_cache_path(url)
        
        try:
            cache_content = f"URL: {result.url}\nTitle: {result.title}\nTime: {result.fetch_time}\n{result.content}"
            cache_path.write_text(cache_content, encoding='utf-8')
        except Exception as e:
            print(f"[ContentFetcher] 缓存保存失败: {e}")
    
    def fetch_batch(self, urls: list, delay: float = 1.0) -> Dict[str, FetchedContent]:
        """
        批量抓取 URL
        
        Args:
            urls: URL 列表
            delay: 请求间隔（秒）
            
        Returns:
            {url: FetchedContent} 字典
        """
        results = {}
        
        for i, url in enumerate(urls):
            if i > 0:
                time.sleep(delay)
            
            results[url] = self.fetch(url)
        
        return results
