# coding=utf-8
"""
播客音频下载器

负责下载播客音频文件，支持大小限制、流式下载和临时文件管理
"""

import os
import hashlib
from pathlib import Path
from typing import Optional, Tuple
from dataclasses import dataclass

import requests


@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    file_path: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None
    # 分段相关字段
    is_segmented: bool = False           # 是否进行了分段
    segment_files: list = None           # 分段文件列表（如果分段）
    original_file: Optional[str] = None  # 原始文件路径（如果分段）


class AudioDownloader:
    """播客音频下载器"""

    # 默认配置
    DEFAULT_TEMP_DIR = "output/podcast/audio"
    DEFAULT_MAX_SIZE_MB = 500
    DEFAULT_CHUNK_SIZE = 8192  # 8KB

    def __init__(
        self,
        temp_dir: str = DEFAULT_TEMP_DIR,
        max_file_size_mb: int = DEFAULT_MAX_SIZE_MB,
        cleanup_after_use: bool = True,
        timeout: int = 300,
        proxy_url: str = "",
    ):
        """
        初始化下载器

        Args:
            temp_dir: 临时文件存放目录
            max_file_size_mb: 最大文件大小（MB），超过则跳过下载
            cleanup_after_use: 使用后是否清理文件（由外部调用 cleanup 方法）
            timeout: 下载超时时间（秒）
            proxy_url: 代理 URL
        """
        self.temp_dir = Path(temp_dir)
        self.max_file_size_bytes = max_file_size_mb * 1024 * 1024
        self.cleanup_after_use = cleanup_after_use
        self.timeout = timeout
        self.proxy_url = proxy_url

        # 初始化智能代理切换状态
        self._proxy_enabled = False  # 初始不启用代理
        self._proxy_fallback_triggered = False  # 是否已切换到代理

        # 确保临时目录存在
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 创建会话
        self.session = self._create_session()

    def _create_session(self) -> requests.Session:
        """创建请求会话"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "TrendRadar/2.0 Podcast Downloader",
            "Accept": "*/*",
        })

        # 智能代理切换：初始不设置代理（直连模式）
        # 代理 URL 存在时，在失败时才通过 enable_proxy_fallback() 启用
        return session

    def _create_session_with_proxy(self) -> requests.Session:
        """创建带代理的请求会话"""
        session = requests.Session()
        session.headers.update({
            "User-Agent": "TrendRadar/2.0 Podcast Downloader (Proxy)",
            "Accept": "*/*",
        })

        # 设置代理
        if self.proxy_url:
            session.proxies = {
                "http": self.proxy_url,
                "https": self.proxy_url,
            }
            print(f"[Download] 已启用代理: {self.proxy_url}")
        return session

    def enable_proxy_fallback(self) -> None:
        """启用代理降级模式"""
        self._proxy_enabled = True
        self._proxy_fallback_triggered = True
        print("[Download] ⚠️  直连失败，切换到代理模式")

    def _retry_with_proxy(
        self,
        audio_url: str,
        feed_id: str,
        segmenter: Optional["AudioSegmenter"] = None,
    ) -> DownloadResult:
        """启用代理后重试下载"""
        print(f"[Download] 使用代理重试: {audio_url[:80]}...")

        # 重新创建会话（启用代理）
        self.session = self._create_session_with_proxy()

        filename = self._generate_filename(audio_url, feed_id)
        file_path = self.temp_dir / filename

        try:
            response = self.session.get(
                audio_url,
                stream=True,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # 检查文件大小
            content_length = int(response.headers.get("content-length", 0))
            if content_length > 0 and content_length > self.max_file_size_bytes:
                return DownloadResult(
                    success=False,
                    error=f"文件大小 {content_length/(1024*1024):.1f}MB 超过限制"
                )

            # 写入文件
            downloaded_size = 0
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.DEFAULT_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

            size_mb = downloaded_size / (1024 * 1024)
            print(f"[Download] ✅ 代理下载成功: {filename} ({size_mb:.1f}MB)")

            result = DownloadResult(
                success=True,
                file_path=str(file_path),
                file_size=downloaded_size,
            )

            # 如果需要分段
            if segmenter:
                segment_result = segmenter.segment_audio(str(file_path))
                if segment_result.success and segment_result.segment_count > 0:
                    result.is_segmented = True
                    result.segment_files = segment_result.segment_files
                    result.original_file = segment_result.original_file
                    # file_path 指向第一个分段文件
                    result.file_path = segment_result.segment_files[0]

            return result

        except Exception as e:
            return DownloadResult(
                success=False,
                error=f"代理重试失败: {e}"
        )

    def _generate_filename(self, audio_url: str, feed_id: str) -> str:
        """
        根据 URL 生成唯一文件名

        Args:
            audio_url: 音频 URL
            feed_id: 播客源 ID

        Returns:
            文件名（包含扩展名）
        """
        # 使用 URL 的 MD5 哈希作为文件名，避免特殊字符
        url_hash = hashlib.md5(audio_url.encode()).hexdigest()[:12]

        # 从 URL 推断扩展名
        ext = ".mp3"  # 默认
        lower_url = audio_url.lower()
        if ".m4a" in lower_url:
            ext = ".m4a"
        elif ".mp4" in lower_url:
            ext = ".mp4"
        elif ".aac" in lower_url:
            ext = ".aac"
        elif ".ogg" in lower_url:
            ext = ".ogg"
        elif ".wav" in lower_url:
            ext = ".wav"

        return f"{feed_id}_{url_hash}{ext}"

    def download(
        self,
        audio_url: str,
        feed_id: str,
        expected_size: int = 0,
        segmenter: Optional["AudioSegmenter"] = None,
    ) -> DownloadResult:
        """
        下载音频文件

        Args:
            audio_url: 音频 URL
            feed_id: 播客源 ID
            expected_size: 预期文件大小（字节），用于预检查
            segmenter: 音频分段器（可选）

        Returns:
            DownloadResult 对象
        """
        # 预检查：如果已知大小超过限制，直接跳过
        if expected_size > 0 and expected_size > self.max_file_size_bytes:
            size_mb = expected_size / (1024 * 1024)
            max_mb = self.max_file_size_bytes / (1024 * 1024)
            return DownloadResult(
                success=False,
                error=f"文件大小 {size_mb:.1f}MB 超过限制 {max_mb:.0f}MB，跳过下载"
            )

        # 生成文件路径
        filename = self._generate_filename(audio_url, feed_id)
        file_path = self.temp_dir / filename

        # 如果文件已存在，检测是否需要分段
        if file_path.exists():
            file_size = file_path.stat().st_size
            print(f"[Download] 文件已存在: {filename} ({file_size / (1024*1024):.1f}MB)")

            # 即使文件已存在，也要检查是否需要分段
            result = DownloadResult(
                success=True,
                file_path=str(file_path),
                file_size=file_size,
            )

            # 集成分段器：如果启用且文件存在，检测是否需要分段
            if segmenter is None:
                print(f"[Download] ⚠️  segmenter 未启用，跳过分段检测")
                return result
            segment_result = segmenter.segment_audio(str(file_path))

            if segment_result.success and segment_result.segment_count > 1:
                # 需要分段：更新返回结果
                print(f"[Download] ✅ 音频已分段为 {segment_result.segment_count} 段")
                result.is_segmented = True
                result.segment_files = segment_result.segment_files
                result.original_file = segment_result.original_file
                # 分段后的第一个文件路径
                result.file_path = segment_result.segment_files[0] if segment_result.segment_files else str(file_path)
                result.file_size = segment_result.segment_duration * segment_result.segment_count if segment_result.segment_duration > 0 else file_size
            else:
                # 不需要分段或分段失败，使用原文件
                if segment_result.error:
                    print(f"[Download] ⚠️  分段检测失败: {segment_result.error}")
                return result

        try:
            print(f"[Download] 开始下载: {audio_url[:80]}...")

            # 流式下载
            response = self.session.get(
                audio_url,
                stream=True,
                timeout=self.timeout,
            )
            response.raise_for_status()

            # 检查 Content-Length
            content_length = int(response.headers.get("content-length", 0))
            if content_length > 0 and content_length > self.max_file_size_bytes:
                size_mb = content_length / (1024 * 1024)
                max_mb = self.max_file_size_bytes / (1024 * 1024)
                return DownloadResult(
                    success=False,
                    error=f"文件大小 {size_mb:.1f}MB 超过限制 {max_mb:.0f}MB，跳过下载"
                )

            # 写入文件
            downloaded_size = 0
            with open(file_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=self.DEFAULT_CHUNK_SIZE):
                    if chunk:
                        f.write(chunk)
                        downloaded_size += len(chunk)

                        # 实时检查大小限制
                        if downloaded_size > self.max_file_size_bytes:
                            f.close()
                            file_path.unlink(missing_ok=True)
                            size_mb = downloaded_size / (1024 * 1024)
                            max_mb = self.max_file_size_bytes / (1024 * 1024)
                            return DownloadResult(
                                success=False,
                                error=f"下载中断：已下载 {size_mb:.1f}MB 超过限制 {max_mb:.0f}MB"
                            )

            size_mb = downloaded_size / (1024 * 1024)
            print(f"[Download] 下载完成: {filename} ({size_mb:.1f}MB)")

            # 构建基础结果
            result = DownloadResult(
                success=True,
                file_path=str(file_path),
                file_size=downloaded_size,
            )

            # 如果提供了分段器，尝试分段
            if segmenter is None:
                print("[Download] ⚠️  segmenter 未启用，跳过分段检测")
                return result

            print("[Download] 检测是否需要分段...")
            segment_result = segmenter.segment_audio(str(file_path))

            if segment_result.success and segment_result.segment_count > 0:
                print(f"[Download] ✅ 音频已分段为 {segment_result.segment_count} 段")
                result.is_segmented = True
                result.segment_files = segment_result.segment_files
                result.original_file = segment_result.original_file
                # file_path 指向第一个分段文件
                result.file_path = segment_result.segment_files[0]
            elif not segment_result.success and segment_result.error:
                # 分段失败，但下载成功，记录错误但不影响流程
                print(f"[Download] ⚠️  分段失败，使用原始文件: {segment_result.error}")

            return result

        except requests.Timeout:
            if not self._proxy_fallback_triggered and self.proxy_url:
                self.enable_proxy_fallback()
                return self._retry_with_proxy(audio_url, feed_id, segmenter)
            return DownloadResult(
                success=False,
                error=f"下载超时 ({self.timeout}s)"
            )

        except requests.RequestException as e:
            if not self._proxy_fallback_triggered and self.proxy_url:
                self.enable_proxy_fallback()
                return self._retry_with_proxy(audio_url, feed_id, segmenter)
            return DownloadResult(
                success=False,
                error=f"下载失败: {e}"
            )

        except Exception as e:
            return DownloadResult(
                success=False,
                error=f"未知错误: {e}"
            )

    def cleanup(self, file_path: str) -> bool:
        """
        清理下载的文件

        Args:
            file_path: 文件路径

        Returns:
            是否成功删除
        """
        if not self.cleanup_after_use:
            return False

        try:
            path = Path(file_path)
            if path.exists():
                path.unlink()
                print(f"[Download] 已清理: {path.name}")
                return True
        except Exception as e:
            print(f"[Download] 清理失败: {e}")

        return False

    def cleanup_all(self) -> int:
        """
        清理所有临时文件

        Returns:
            删除的文件数量
        """
        count = 0
        try:
            for file_path in self.temp_dir.glob("*"):
                if file_path.is_file():
                    file_path.unlink()
                    count += 1
            if count > 0:
                print(f"[Download] 已清理 {count} 个临时文件")
        except Exception as e:
            print(f"[Download] 批量清理失败: {e}")

        return count

    @classmethod
    def from_config(cls, config: dict) -> "AudioDownloader":
        """
        从配置字典创建下载器

        Args:
            config: 配置字典（来自 config.yaml 的 podcast.download 段）

        Returns:
            AudioDownloader 实例
        """
        return cls(
            temp_dir=config.get("temp_dir", cls.DEFAULT_TEMP_DIR),
            max_file_size_mb=config.get("max_file_size_mb", cls.DEFAULT_MAX_SIZE_MB),
            cleanup_after_use=config.get("cleanup_after_transcribe", True),
            timeout=config.get("download_timeout", 1800),  # ✅ 修复：默认值从 300 改为 1800
            proxy_url=config.get("proxy_url", ""),  # ✅ 添加代理参数
        )
