# coding=utf-8
"""
播客处理器

协调 RSS 抓取、音频下载、ASR 转写、AI 分析和即时推送的完整流程
"""

import sqlite3
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .fetcher import PodcastFetcher, PodcastFeedConfig, PodcastEpisode
from .downloader import AudioDownloader, DownloadResult
from .transcriber import ASRTranscriber, TranscribeResult
from .analyzer import PodcastAnalyzer, AnalysisResult
from .notifier import PodcastNotifier, NotifyResult

from trendradar.utils.time import get_configured_time, DEFAULT_TIMEZONE


@dataclass
class ProcessResult:
    """单个节目的处理结果"""
    episode: PodcastEpisode
    download_result: Optional[DownloadResult] = None
    transcribe_result: Optional[TranscribeResult] = None
    analysis_result: Optional[AnalysisResult] = None
    notify_results: Optional[Dict[str, NotifyResult]] = None
    status: str = "pending"  # pending | downloading | transcribing | analyzing | notifying | completed | failed
    error: Optional[str] = None


class PodcastProcessor:
    """
    播客处理器

    完整处理流程：
    1. 抓取播客 RSS → 解析 enclosure
    2. 检测新节目（数据库去重）
    3. 对每个新节目：
       a. 下载音频
       b. ASR 转写
       c. AI 分析
       d. 即时邮件推送
       e. 清理音频文件
    """

    def __init__(
        self,
        config: dict,
        db_path: str = "output/news/podcast.db",
        # 新增测试模式参数
        test_mode: bool = False,
        test_feed_id: Optional[str] = None,
        test_episode_guid: Optional[str] = None,
        # 版本首次启动引导
        bootstrap_mode: bool = False,
    ):
        """
        初始化处理器

        Args:
            config: 完整配置字典
            db_path: 数据库文件路径
            test_mode: 测试模式开关
            test_feed_id: 测试模式：指定feed_id
            test_episode_guid: 测试模式：指定episode的guid
            bootstrap_mode: 版本首次启动引导模式（选取一期节目处理）
        """
        self.config = config
        self.db_path = Path(db_path)

        # 保存测试参数
        self.test_mode = test_mode
        self.test_feed_id = test_feed_id
        self.test_episode_guid = test_episode_guid
        self.bootstrap_mode = bootstrap_mode

        # 解析配置（支持大写和小写键名）
        self.podcast_config = config.get("PODCAST", config.get("podcast", {}))
        self.enabled = self.podcast_config.get("ENABLED", self.podcast_config.get("enabled", False))

        # 获取时区
        app_config = config.get("APP", config.get("app", {}))
        self.timezone = app_config.get("timezone", DEFAULT_TIMEZONE)

        # 简化后的处理参数
        self.max_episodes_per_run = self.podcast_config.get("MAX_EPISODES_PER_RUN", 3)
        self.new_episode_threshold_days = self.podcast_config.get("NEW_EPISODE_THRESHOLD_DAYS", 2)

        # 新增：Retry 参数
        self.retry_enabled = self.podcast_config.get("RETRY_ENABLED", self.podcast_config.get("retry_enabled", True))
        self.max_retries = self.podcast_config.get("MAX_RETRIES", self.podcast_config.get("max_retries", 3))
        self.retry_delay = self.podcast_config.get("RETRY_DELAY", self.podcast_config.get("retry_delay", 60))

        # 初始化各组件
        if self.enabled:
            self._init_components()
            self._init_database()
            # 简化版不需要部署时间保护，使用2天阈值代替

    def _init_components(self):
        """初始化各个处理组件"""
        # 播客 RSS 抓取器
        feeds = []
        for feed_config in self.podcast_config.get("FEEDS", self.podcast_config.get("feeds", [])):
            if feed_config.get("enabled", True):
                feed = PodcastFeedConfig(
                    id=feed_config.get("id", ""),
                    name=feed_config.get("name", ""),
                    url=feed_config.get("url", ""),
                    enabled=True,
                    max_items=feed_config.get("max_items", 10),  # 支持限制节目数量
                )
                if feed.id and feed.url:
                    feeds.append(feed)

        self.fetcher = PodcastFetcher(
            feeds=feeds,
            timezone=self.timezone,
        )

        # 音频下载器
        download_config = self.podcast_config.get("DOWNLOAD", self.podcast_config.get("download", {}))

        # 获取代理配置（支持配置和环境变量）
        proxy_config = download_config.get("PROXY", download_config.get("proxy", {}))
        proxy_url = ""
        if proxy_config.get("ENABLED", proxy_config.get("enabled", False)):
            proxy_url = proxy_config.get("URL", proxy_config.get("url", ""))
            if not proxy_url:
                import os
                proxy_url = os.environ.get("PODCAST_PROXY_URL", "")
                if proxy_url:
                    print(f"[Podcast] 使用环境变量代理: {proxy_url}")

        self.downloader = AudioDownloader(
            temp_dir=download_config.get("TEMP_DIR", download_config.get("temp_dir", "output/podcast/audio")),
            max_file_size_mb=download_config.get("MAX_FILE_SIZE_MB", download_config.get("max_file_size_mb", 500)),
            cleanup_after_use=download_config.get("CLEANUP_AFTER_TRANSCRIBE", download_config.get("cleanup_after_transcribe", True)),
            timeout=download_config.get("download_timeout", 1800),  # ✅ 直接使用配置值，默认 1800 秒
            proxy_url=proxy_url,  # ✅ 添加代理参数传递
        )

        # ASR 转写器
        # 注意：配置键可能被转换为大写，需要兼容两种格式
        asr_config = self.podcast_config.get("ASR", self.podcast_config.get("asr", {}))

        # 从 asr_config 中提取配置（兼容大小写）
        backend = asr_config.get("BACKEND", asr_config.get("backend", "assemblyai"))
        api_base = asr_config.get("API_BASE", asr_config.get("api_base", ""))
        api_key = asr_config.get("API_KEY", asr_config.get("api_key", ""))
        model = asr_config.get("MODEL", asr_config.get("model", ""))
        language = asr_config.get("LANGUAGE", asr_config.get("language", "zh"))

        # AssemblyAI 配置（可能内嵌在 asr_config 或作为独立键）
        assemblyai_config = asr_config.get("ASSEMBLYAI", asr_config.get("assemblyai", {}))
        assemblyai_api_key = assemblyai_config.get("API_KEY", assemblyai_config.get("api_key", ""))
        speaker_labels = assemblyai_config.get("SPEAKER_LABELS", assemblyai_config.get("speaker_labels", True))

        # 如果 assemblyai_api_key 为空，尝试从 podcast_config 顶层获取
        if not assemblyai_api_key:
            assemblyai_api_key = self.podcast_config.get("ASSEMBLYAI_API_KEY", self.podcast_config.get("assemblyai_api_key", ""))

        # 最后尝试环境变量
        if not assemblyai_api_key:
            import os
            assemblyai_api_key = os.environ.get("ASSEMBLYAI_API_KEY", "")

        self.transcriber = ASRTranscriber(
            backend=backend,
            api_base=api_base,
            api_key=api_key,
            model=model,
            language=language,
            # AssemblyAI 配置
            assemblyai_api_key=assemblyai_api_key,
            speaker_labels=speaker_labels,
        )

        # 音频分段器（优先读取大写键，兼容 load_config 规范化后的格式）
        segment_config = self.podcast_config.get("SEGMENT", self.podcast_config.get("segment", {}))
        segment_enabled = segment_config.get("ENABLED", segment_config.get("enabled", False))

        if segment_enabled:
            from trendradar.podcast.segmenter import AudioSegmenter
            self.segmenter = AudioSegmenter.from_config(self.podcast_config)
        else:
            self.segmenter = None

        # AI 分析器
        analysis_config = self.podcast_config.get("ANALYSIS", self.podcast_config.get("analysis", {}))
        global_ai_config = self.config.get("AI", self.config.get("ai", {}))
        
        # 构建 AI 配置：优先使用播客专用配置，其次使用全局配置
        ai_config = {}
        if isinstance(global_ai_config, dict):
            ai_config = global_ai_config.copy()
        
        # 播客专用 AI 配置覆盖全局配置（使用大写 key）
        podcast_model = analysis_config.get("MODEL") or analysis_config.get("model")
        podcast_api_base = analysis_config.get("API_BASE") or analysis_config.get("api_base")
        podcast_api_key = analysis_config.get("API_KEY") or analysis_config.get("api_key")
        
        if podcast_model:
            ai_config["MODEL"] = podcast_model
            ai_config["model"] = podcast_model
        if podcast_api_base:
            ai_config["API_BASE"] = podcast_api_base
            ai_config["api_base"] = podcast_api_base
        if podcast_api_key:
            ai_config["API_KEY"] = podcast_api_key
            ai_config["api_key"] = podcast_api_key
        
        actual_model = ai_config.get('MODEL') or ai_config.get('model', 'N/A')
        actual_base = ai_config.get('API_BASE') or ai_config.get('api_base', 'N/A')
        print(f"[Podcast] AI 分析配置: model={actual_model}, api_base={actual_base[:30] if actual_base and actual_base != 'N/A' else 'N/A'}")
        
        self.analyzer = PodcastAnalyzer(
            ai_config=ai_config,
            analysis_config=analysis_config,
            prompt_file=analysis_config.get("PROMPT_FILE", analysis_config.get("prompt_file", "podcast_prompts.txt")),
            language=analysis_config.get("LANGUAGE", analysis_config.get("language", "Chinese")),
        )
        self.analysis_enabled = analysis_config.get("ENABLED", analysis_config.get("enabled", True))

        # 通知器
        notification_config = self.podcast_config.get("NOTIFICATION", self.podcast_config.get("notification", {}))
        
        # 获取邮件配置（EMAIL_ 前缀的键在 config 根级别）
        email_config = {
            "FROM": self.config.get("EMAIL_FROM", ""),
            "PASSWORD": self.config.get("EMAIL_PASSWORD", ""),
            "TO": self.config.get("EMAIL_TO", ""),
            "SMTP_SERVER": self.config.get("EMAIL_SMTP_SERVER", ""),
            "SMTP_PORT": self.config.get("EMAIL_SMTP_PORT", ""),
        }

        self.notifier = PodcastNotifier(
            notification_config=notification_config,
            email_config=email_config,
            timezone=self.timezone,
        )

    def _init_deploy_time_protection(self):
        """
        初始化部署时间保护
        
        首次部署时记录时间，后续只处理该时间之后发布的播客
        防止重新部署时误触发大量历史内容处理
        """
        deploy_marker = self.db_path.parent / ".podcast_deploy_time"
        
        if not deploy_marker.exists():
            # 首次部署，记录当前时间
            now = get_configured_time(self.timezone)
            deploy_time = now.strftime("%Y-%m-%d %H:%M:%S")
            deploy_marker.write_text(deploy_time, encoding="utf-8")
            print(f"[Podcast] 📌 首次部署，记录基准时间: {deploy_time}")
            print(f"[Podcast] ⚠️  只会处理此时间之后发布的播客")
            self._deploy_time = now
        else:
            # 读取已有的部署时间
            deploy_time_str = deploy_marker.read_text(encoding="utf-8").strip()
            try:
                self._deploy_time = datetime.strptime(deploy_time_str, "%Y-%m-%d %H:%M:%S")
            except:
                self._deploy_time = None
        
        # 如果配置了 min_publish_time，使用配置值覆盖
        if self.min_publish_time:
            try:
                self._deploy_time = datetime.strptime(self.min_publish_time, "%Y-%m-%d %H:%M:%S")
                print(f"[Podcast] 📌 使用配置的最早发布时间: {self.min_publish_time}")
            except:
                print(f"[Podcast] ⚠️  min_publish_time 格式错误，使用部署时间")

    def _add_column_if_not_exists(self, table: str, column: str, column_def: str):
        """添加字段（如果不存在）- 用于数据库迁移"""
        conn = sqlite3.connect(str(self.db_path))
        try:
            # 检查字段是否已存在
            cursor = conn.execute(f"PRAGMA table_info({table})")
            columns = [row[1] for row in cursor.fetchall()]
            if column not in columns:
                conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {column_def}")
                conn.commit()
                print(f"[Podcast] ✅ 添加字段: {table}.{column}")
            else:
                print(f"[Podcast] ℹ️  字段已存在，跳过: {table}.{column}")
        finally:
            conn.close()

    def _init_database(self):
        """初始化数据库"""
        # 确保目录存在
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        # 读取 schema
        schema_path = Path(__file__).parent.parent / "storage" / "podcast_schema.sql"
        if schema_path.exists():
            schema_sql = schema_path.read_text(encoding="utf-8")
        else:
            # 内联 schema
            schema_sql = """
            CREATE TABLE IF NOT EXISTS podcast_episodes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                feed_id TEXT NOT NULL,
                feed_name TEXT,
                title TEXT NOT NULL,
                url TEXT,
                guid TEXT,
                audio_url TEXT NOT NULL,
                audio_type TEXT,
                audio_length INTEGER DEFAULT 0,
                duration TEXT,
                published_at TEXT,
                author TEXT,
                summary TEXT,
                status TEXT DEFAULT 'pending',
                error_message TEXT,
                transcript TEXT,
                analysis TEXT,
                first_crawl_time TEXT NOT NULL,
                download_time TEXT,
                transcribe_time TEXT,
                analyze_time TEXT,
                notify_time TEXT,
                UNIQUE(feed_id, audio_url)
            );
            """

        conn = sqlite3.connect(str(self.db_path))
        try:
            conn.executescript(schema_sql)
            conn.commit()
        finally:
            conn.close()

        # 新增：确保失败次数字段存在（兼容旧数据库）
        print("[Podcast] 🔍 检查数据库字段...")
        self._add_column_if_not_exists("podcast_episodes", "failure_count", "INTEGER DEFAULT 0")
        self._add_column_if_not_exists("podcast_episodes", "last_error_time", "TEXT")

    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(str(self.db_path))

    def _is_new_episode(self, episode: PodcastEpisode) -> bool:
        """检查是否为新节目（数据库中不存在）"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT id FROM podcast_episodes WHERE feed_id = ? AND audio_url = ?",
                (episode.feed_id, episode.audio_url)
            )
            return cursor.fetchone() is None
        finally:
            conn.close()

    def _get_last_completed_time(self) -> Optional[datetime]:
        """获取最后一次成功处理的时间"""
        import pytz
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                SELECT MAX(notify_time) FROM podcast_episodes 
                WHERE status = 'completed' AND notify_time IS NOT NULL
            """)
            row = cursor.fetchone()
            if row and row[0]:
                try:
                    # 解析时间并添加时区信息
                    dt = datetime.strptime(row[0], "%Y-%m-%d %H:%M:%S")
                    tz = pytz.timezone(self.timezone)
                    return tz.localize(dt)
                except:
                    return None
            return None
        finally:
            conn.close()

    def _get_unprocessed_history_episodes(self, limit: int = 1) -> List[Tuple]:
        """
        获取未处理的历史节目

        按照以下优先级选择：
        1. 状态为 pending、skipped_old 或 failed 的节目
        2. 失败次数 < 20（避免无限重试永久失败的项目）
        3. 按发布时间从新到旧排序
        4. 优先选择不同的播客源（避免集中处理同一个播客）

        Returns:
            列表，每项为 (feed_id, feed_name, title, audio_url, published_at, summary)
        """
        conn = self._get_connection()
        try:
            # 选择未处理的节目，按 feed 分组后交替选择
            # 新增：包含 failed 状态，并过滤失败次数 >= 20 的记录
            cursor = conn.execute("""
                SELECT feed_id, feed_name, title, audio_url, published_at, summary, author, url, duration
                FROM podcast_episodes
                WHERE status IN ('pending', 'skipped_old', 'failed')
                  AND (failure_count IS NULL OR failure_count < 20)
                ORDER BY
                    feed_id,  -- 先按 feed 分组
                    published_at DESC  -- 同一 feed 内按时间排序
                LIMIT ?
            """, (limit * 10,))  # 多取一些，后面做交替选择
            
            rows = cursor.fetchall()
            
            if not rows:
                return []
            
            # 按 feed 分组，然后交替选择
            feed_episodes = {}
            for row in rows:
                feed_id = row[0]
                if feed_id not in feed_episodes:
                    feed_episodes[feed_id] = []
                feed_episodes[feed_id].append(row)
            
            # 交替从各个 feed 取节目
            result = []
            feed_ids = list(feed_episodes.keys())
            idx = 0
            while len(result) < limit:
                feed_id = feed_ids[idx % len(feed_ids)]
                if feed_episodes[feed_id]:
                    result.append(feed_episodes[feed_id].pop(0))
                idx += 1
                # 如果所有 feed 都空了就退出
                if all(len(eps) == 0 for eps in feed_episodes.values()):
                    break

            return result[:limit]
        finally:
            conn.close()

    def _increment_failure_count(self, episode_id: int, error_message: str = ""):
        """
        递增失败次数并更新状态（防止重复计数）

        Args:
            episode_id: 节目的数据库 ID
            error_message: 错误信息
        """
        conn = self._get_connection()
        try:
            # ✅ 检查当前状态，避免重复计数
            cursor = conn.execute("SELECT status, failure_count FROM podcast_episodes WHERE id = ?", (episode_id,))
            row = cursor.fetchone()
            if not row:
                return  # 节目不存在，不处理

            current_status, current_failures = row

            if current_status != 'failed':
                # 只有不在失败状态时才计数
                conn.execute("""
                    UPDATE podcast_episodes
                    SET failure_count = COALESCE(failure_count, 0) + 1,
                        last_error_time = ?,
                        error_message = ?,
                        status = 'failed'
                    WHERE id = ?
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_message, episode_id))
                print(f"[Podcast] ⚠️  节目 ID {episode_id} 失败计数: {current_failures + 1}")
            else:
                # 只更新错误信息，不增加计数
                conn.execute("""
                    UPDATE podcast_episodes
                    SET last_error_time = ?,
                        error_message = ?
                    WHERE id = ?
                """, (datetime.now().strftime("%Y-%m-%d %H:%M:%S"), error_message, episode_id))
                print(f"[Podcast] ⚠️  节目 ID {episode_id} 已在失败状态，仅更新错误信息")

            # 检查失败次数
            cursor = conn.execute("SELECT failure_count FROM podcast_episodes WHERE id = ?", (episode_id,))
            row = cursor.fetchone()
            if row and row[0] >= 20:
                print(f"[Podcast] ⚠️  节目 ID {episode_id} 失败次数已达 {row[0]}，将永久忽略")

            conn.commit()
        finally:
            conn.close()
    def _save_episode(self, episode: PodcastEpisode, status: str):
        """
        保存节目到数据库（简化版）

        注意：只在处理完成后调用（status=completed/failed）
        不再保存 pending/skipped_old 等中间状态
        """
        now = get_configured_time(self.timezone)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        try:
            if status == "completed":
                # 完成状态：设置 notify_time
                conn.execute("""
                    INSERT OR REPLACE INTO podcast_episodes
                    (feed_id, feed_name, title, url, guid, audio_url, audio_type, audio_length,
                     duration, published_at, author, summary, status, first_crawl_time, notify_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.feed_id, episode.feed_name, episode.title, episode.url, episode.guid,
                    episode.audio_url, episode.audio_type, episode.audio_length, episode.duration,
                    episode.published_at, episode.author, episode.summary, status,
                    time_str, time_str
                ))
            elif status == "failed":
                # 失败状态：只保存基本信息和错误信息
                error_msg = episode.error_message if hasattr(episode, 'error_message') else None
                conn.execute("""
                    INSERT OR REPLACE INTO podcast_episodes
                    (feed_id, feed_name, title, url, guid, audio_url, audio_type, audio_length,
                     duration, published_at, author, summary, status, error_message, first_crawl_time)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    episode.feed_id, episode.feed_name, episode.title, episode.url, episode.guid,
                    episode.audio_url, episode.audio_type, episode.audio_length, episode.duration,
                    episode.published_at, episode.author, episode.summary, status,
                    error_msg, time_str
                ))
            else:
                # 简化版不应该调用其他状态
                print(f"[Podcast] ⚠️ _save_episode 被调用，使用了不支持的 status: {status}，跳过")
                return
            conn.commit()
        finally:
            conn.close()

    def _build_transcript_with_metadata(
        self,
        episode: PodcastEpisode,
        transcript: str,
        language: str = "",
        speaker_count: int = 0,
    ) -> str:
        """
        构建带元数据头的转写文本
        
        将播客元数据和完整的 Show Notes 添加到转写文本头部，
        让 AI 自行理解和提取有用信息（如嘉宾、大纲、术语等）。
        
        Args:
            episode: 播客节目信息
            transcript: 原始转写文本
            language: 检测到的语言
            speaker_count: 识别的说话人数量
            
        Returns:
            带元数据头的完整文本
        """
        import re
        import html as html_module
        
        # 构建元数据头部
        metadata_lines = [
            "=" * 60,
            "【播客元数据 / Podcast Metadata】",
            "=" * 60,
        ]
        
        # 基础信息
        if episode.feed_name:
            metadata_lines.append(f"播客名称: {episode.feed_name}")
        if episode.title:
            metadata_lines.append(f"节目标题: {episode.title}")
        if episode.author:
            metadata_lines.append(f"主播/嘉宾: {episode.author}")
        if episode.published_at:
            # 格式化发布时间
            try:
                from datetime import datetime
                dt = datetime.fromisoformat(episode.published_at.replace("Z", "+00:00"))
                pub_date = dt.strftime("%Y-%m-%d %H:%M")
            except:
                pub_date = episode.published_at
            metadata_lines.append(f"发布时间: {pub_date}")
        if episode.duration:
            metadata_lines.append(f"节目时长: {episode.duration}")
        if episode.url:
            metadata_lines.append(f"节目链接: {episode.url}")
        
        # ASR 识别信息
        if language:
            lang_name = "中文" if language == "zh" else ("英文" if language == "en" else language)
            metadata_lines.append(f"识别语言: {lang_name}")
        if speaker_count > 0:
            metadata_lines.append(f"说话人数: {speaker_count} 人")
        
        # 直接添加完整的 Show Notes（不做复杂解析，让 AI 自行理解）
        if episode.summary:
            # 清理 HTML 标签
            show_notes = html_module.unescape(episode.summary)
            show_notes = re.sub(r'<[^>]+>', '\n', show_notes)
            show_notes = re.sub(r'\n{3,}', '\n\n', show_notes)
            show_notes = show_notes.strip()
            
            # 限制长度（避免过长影响 AI 处理）
            max_length = 4000
            if len(show_notes) > max_length:
                show_notes = show_notes[:max_length] + "\n\n[...Show Notes 已截断...]"
            
            metadata_lines.append("")
            metadata_lines.append("【Show Notes / 节目说明】")
            metadata_lines.append("（可能包含：节目简介、嘉宾信息、时间轴大纲、延伸阅读等）")
            metadata_lines.append("-" * 40)
            metadata_lines.append(show_notes)
        
        # 分隔线和转写文本
        metadata_lines.append("")
        metadata_lines.append("=" * 60)
        metadata_lines.append("【转写文本 / Transcript】")
        metadata_lines.append("=" * 60)
        metadata_lines.append("")
        
        # 组合元数据头和转写文本
        metadata_header = "\n".join(metadata_lines)
        return metadata_header + transcript

    def _update_episode_status(
        self,
        episode: PodcastEpisode,
        status: str,
        error_message: str = None,
        transcript: str = None,
        analysis: str = None,
    ):
        """更新节目状态"""
        now = get_configured_time(self.timezone)
        time_str = now.strftime("%Y-%m-%d %H:%M:%S")

        conn = self._get_connection()
        try:
            # 根据状态更新对应的时间字段
            time_field = {
                "downloading": None,
                "transcribing": "download_time",
                "analyzing": "transcribe_time",
                "notifying": "analyze_time",
                "completed": "notify_time",
                "failed": None,
            }.get(status)

            if time_field:
                conn.execute(f"""
                    UPDATE podcast_episodes
                    SET status = ?, error_message = ?, transcript = COALESCE(?, transcript),
                        analysis = COALESCE(?, analysis), {time_field} = ?
                    WHERE feed_id = ? AND audio_url = ?
                """, (status, error_message, transcript, analysis, time_str,
                      episode.feed_id, episode.audio_url))
            else:
                conn.execute("""
                    UPDATE podcast_episodes
                    SET status = ?, error_message = ?, transcript = COALESCE(?, transcript),
                        analysis = COALESCE(?, analysis)
                    WHERE feed_id = ? AND audio_url = ?
                """, (status, error_message, transcript, analysis,
                      episode.feed_id, episode.audio_url))
            conn.commit()
        finally:
            conn.close()

    def process_episode(self, episode: PodcastEpisode) -> ProcessResult:
        """
        处理单个播客节目

        Args:
            episode: 播客节目

        Returns:
            ProcessResult 对象
        """
        import time
        result = ProcessResult(episode=episode)
        episode.error_message = None

        print(f"\n[Podcast] ═══════════════════════════════════════")
        print(f"[Podcast] 开始处理: {episode.title}")
        print(f"[Podcast] 播客: {episode.feed_name}")
        print(f"[Podcast] ═══════════════════════════════════════")

        start_time = time.time()
        step_times = {}

        try:
            # 1. 下载音频（添加 retry + 失败计数）
            print(f"[⏱️] 步骤 1/4: 开始下载音频...")
            step_start = time.time()

            max_retries = self.max_retries if self.retry_enabled else 0
            download_result = None
            for attempt in range(max_retries + 1):
                download_result = self.downloader.download(
                    audio_url=episode.audio_url,
                    feed_id=episode.feed_id,
                    expected_size=episode.audio_length,
                    segmenter=self.segmenter,  # 传入分段器
                )

                # 检查下载结果是否成功
                if download_result.success:
                    break  # 成功，退出重试循环
                else:
                    # 下载失败，触发重试
                    if attempt < max_retries:
                        # 指数退避：10s → 20s → 40s
                        delay = min(10 * (2 ** attempt), 300)
                        print(f"[Podcast] ⚠️  下载失败（尝试 {attempt + 1}/{max_retries + 1}）: {download_result.error}")
                        print(f"[Podcast] ⚠️  {delay}秒后重试...")
                        time.sleep(delay)  # 指数退避
                    else:
                        # 所有重试都失败，递增失败次数
                        print(f"[Podcast] ❌ 下载最终失败（已重试{max_retries}次）: {download_result.error}")
                        # 获取 episode 的数据库 ID
                        conn = self._get_connection()
                        try:
                            cursor = conn.execute(
                                "SELECT id FROM podcast_episodes WHERE feed_id = ? AND audio_url = ?",
                                (episode.feed_id, episode.audio_url)
                            )
                            row = cursor.fetchone()
                            if row:
                                self._increment_failure_count(row[0], f"下载失败: {download_result.error}")
                        finally:
                            conn.close()
                        # 抛出异常，终止处理
                        raise Exception(f"下载失败（已重试{max_retries}次）: {download_result.error}")

            result.download_result = download_result
            step_times['下载'] = time.time() - step_start
            print(f"[⏱️] 下载完成，耗时: {step_times['下载']:.1f}秒")

            if not download_result.success:
                result.status = "failed"
                result.error = download_result.error
                episode.error_message = download_result.error
                self._save_episode(episode, "failed")  # 只在结束时保存
                print(f"[Podcast] ❌ 下载失败: {download_result.error}")
                return result

            # 2. ASR 转写（添加 retry + 失败计数）
            print(f"[⏱️] 步骤 2/4: 开始 ASR 转写...")
            step_start = time.time()

            max_retries = self.max_retries if self.retry_enabled else 0
            transcribe_result = None

            # 判断是否为分段文件
            if download_result.is_segmented and download_result.segment_files:
                print(f"[Podcast] 检测到分段音频，使用批量转写模式")
                # 分段文件转写（不重试，因为已经批量处理）
                transcribe_result = self.transcriber.transcribe_segments(download_result.segment_files)
            else:
                # 单文件转写（带重试）
                for attempt in range(max_retries + 1):
                    transcribe_result = self.transcriber.transcribe(download_result.file_path)

                    # 检查转录结果是否成功
                    if transcribe_result.success:
                        break  # 成功，退出重试循环
                    else:
                        # 转录失败，触发重试
                        if attempt < max_retries:
                            print(f"[Podcast] ⚠️  转录失败（尝试 {attempt + 1}/{max_retries + 1}）: {transcribe_result.error}")
                            time.sleep(self.retry_delay)  # 等待后重试
                        else:
                            # 所有重试都失败，递增失败次数
                            print(f"[Podcast] ❌ 转录最终失败（已重试{max_retries}次）: {transcribe_result.error}")
                            # 清理下载的文件
                            self.downloader.cleanup(download_result.file_path)
                            # 获取 episode 的数据库 ID
                            conn = self._get_connection()
                        try:
                            cursor = conn.execute(
                                "SELECT id FROM podcast_episodes WHERE feed_id = ? AND audio_url = ?",
                                (episode.feed_id, episode.audio_url)
                            )
                            row = cursor.fetchone()
                            if row:
                                self._increment_failure_count(row[0], f"转录失败: {transcribe_result.error}")
                        finally:
                            conn.close()
                        # 抛出异常，终止处理
                        raise Exception(f"转录失败（已重试{max_retries}次）: {transcribe_result.error}")

            result.transcribe_result = transcribe_result
            step_times['转写'] = time.time() - step_start
            print(f"[⏱️] 转写完成，耗时: {step_times['转写']:.1f}秒")

            # 清理分段文件（如果有）
            if download_result.is_segmented and download_result.segment_files and self.segmenter:
                print(f"[Podcast] 清理 {len(download_result.segment_files)} 个分段文件...")
                self.segmenter.cleanup_segments(download_result.segment_files)

            if not transcribe_result.success:
                result.status = "failed"
                result.error = transcribe_result.error
                episode.error_message = transcribe_result.error
                self.downloader.cleanup(download_result.file_path)
                self._save_episode(episode, "failed")
                print(f"[Podcast] ❌ 转写失败: {transcribe_result.error}")
                return result

            # 3. AI 分析（如果启用，添加 retry + 失败计数）
            analysis_text = ""
            if self.analysis_enabled:
                print(f"[⏱️] 步骤 3/4: 开始 AI 分析...")
                step_start = time.time()

                # 构建带元数据头的转写文本，为 AI 提供更多上下文
                transcript_with_metadata = self._build_transcript_with_metadata(
                    episode=episode,
                    transcript=transcribe_result.transcript,
                    language=transcribe_result.language,
                    speaker_count=transcribe_result.speaker_count,
                )

                max_retries = self.max_retries if self.retry_enabled else 0
                analysis_result = None
                for attempt in range(max_retries + 1):
                    try:
                        analysis_result = self.analyzer.analyze(
                            transcript=transcript_with_metadata,
                            podcast_name=episode.feed_name,
                            podcast_title=episode.title,
                            detected_language=transcribe_result.language,
                        )

                        # 检查分析结果是否成功
                        if analysis_result.success:
                            break  # 成功，退出重试循环
                        else:
                            # 分析失败，触发重试
                            if attempt < max_retries:
                                print(f"[Podcast] ⚠️  AI分析失败（尝试 {attempt + 1}/{max_retries + 1}）: {analysis_result.error}")
                                time.sleep(self.retry_delay)  # 等待后重试
                            else:
                                # 所有重试都失败，递增失败次数
                                print(f"[Podcast] ❌ AI分析最终失败（已重试{max_retries}次）: {analysis_result.error}")
                                # 获取 episode 的数据库 ID
                                conn = self._get_connection()
                                try:
                                    cursor = conn.execute(
                                        "SELECT id FROM podcast_episodes WHERE feed_id = ? AND audio_url = ?",
                                        (episode.feed_id, episode.audio_url)
                                    )
                                    row = cursor.fetchone()
                                    if row:
                                        self._increment_failure_count(row[0], f"AI分析失败: {analysis_result.error}")
                                finally:
                                    conn.close()
                                # 不抛出异常，继续处理（允许无AI分析的播客发送邮件）
                                break
                    except Exception as e:
                        # 捕获未预期的异常
                        if attempt < max_retries:
                            print(f"[Podcast] ⚠️  AI分析异常（尝试 {attempt + 1}/{max_retries + 1}）: {e}")
                            time.sleep(self.retry_delay)  # 等待后重试
                        else:
                            # 所有重试都失败，递增失败次数
                            print(f"[Podcast] ❌ AI分析最终异常（已重试{max_retries}次）: {e}")
                            # 获取 episode 的数据库 ID
                            conn = self._get_connection()
                            try:
                                cursor = conn.execute(
                                    "SELECT id FROM podcast_episodes WHERE feed_id = ? AND audio_url = ?",
                                    (episode.feed_id, episode.audio_url)
                                )
                                row = cursor.fetchone()
                                if row:
                                    self._increment_failure_count(row[0], f"AI分析异常: {str(e)}")
                            finally:
                                conn.close()
                            # 不抛出异常，继续处理
                            break

                result.analysis_result = analysis_result
                step_times['分析'] = time.time() - step_start
                print(f"[⏱️] 分析完成，耗时: {step_times['分析']:.1f}秒")

                if analysis_result.success:
                    analysis_text = analysis_result.analysis
                else:
                    print(f"[Podcast] ⚠️ AI 分析失败: {analysis_result.error}")
            else:
                print(f"[⏱️] 步骤 3/4: AI 分析已禁用，跳过")

            # 4. 即时推送
            print(f"[⏱️] 步骤 4/4: 开始邮件推送...")
            step_start = time.time()

            notify_results = self.notifier.notify(
                episode=episode,
                transcript=transcribe_result.transcript,
                analysis=analysis_text,
            )
            result.notify_results = notify_results
            step_times['推送'] = time.time() - step_start
            print(f"[⏱️] 推送完成，耗时: {step_times['推送']:.1f}秒")

            # 5. 完成
            result.status = "completed"
            self._save_episode(episode, "completed")  # 只在结束时保存

            # 6. 清理音频文件
            self.downloader.cleanup(download_result.file_path)
            step_times['清理'] = time.time() - time.time()

            total_time = time.time() - start_time
            print(f"\n[⏱️] ═══════ 处理完成，总耗时: {total_time:.1f}秒 ═══════")
            print(f"[⏱️] 详细耗时:")
            for step, duration in step_times.items():
                percentage = (duration / total_time) * 100
                print(f"[⏱️]   {step}: {duration:.1f}秒 ({percentage:.1f}%)")
            print(f"[⏱️] ═══════════════════════════════════════════")
            
            print(f"[Podcast] ✅ 处理完成: {episode.title}")
            return result

        except Exception as e:
            result.status = "failed"
            result.error = str(e)
            episode.error_message = str(e)
            self._save_episode(episode, "failed")
            print(f"[Podcast] ❌ 处理异常: {e}")
            return result

    def _cleanup_stuck_episodes(self):
        """清理卡死的中间状态节目（简化版兼容）"""
        conn = self._get_connection()
        try:
            cursor = conn.execute("""
                UPDATE podcast_episodes SET status = 'failed', error_message = '清理旧中间状态'
                WHERE status IN ('downloading', 'transcribing', 'analyzing', 'notifying', 'pending')
            """)
            if cursor.rowcount > 0:
                conn.commit()
                print(f"[Podcast] 🧹 清理 {cursor.rowcount} 个旧中间状态节目")
        finally:
            conn.close()

    def _build_candidate_pool(self, all_episodes: Dict[str, List[PodcastEpisode]]) -> List[Tuple[PodcastEpisode, str]]:
        """
        构建候选池（RSS 新节目 + 历史未处理节目）

        Args:
            all_episodes: RSS 抓取的所有节目（按 feed_id 分组）

        Returns:
            候选列表，每个元素是 (episode, source) 元组
            - episode: PodcastEpisode 对象
            - source: 来源标识（'rss_new', 'rss_old', 'history'）
        """
        from datetime import timedelta
        import pytz

        candidates = []
        processed_audio_urls = set()

        now = get_configured_time(self.timezone)
        two_days_ago = (now - timedelta(days=self.new_episode_threshold_days))

        # 1. RSS 新节目（2天内）
        for feed_id, episodes in all_episodes.items():
            for episode in episodes:
                # 去重（跳过数据库已处理的）
                if not self._is_new_episode(episode):
                    continue

                # 去重（同一音频URL只保留一个候选）
                if episode.audio_url in processed_audio_urls:
                    continue
                processed_audio_urls.add(episode.audio_url)

                # 检查发布时间
                if episode.published_at:
                    try:
                        pub_time = self._parse_episode_time(episode.published_at)
                        if pub_time:
                            if pub_time >= two_days_ago:
                                candidates.append((episode, 'rss_new'))
                            else:
                                candidates.append((episode, 'rss_old'))
                    except Exception as e:
                        print(f"[Podcast] ⚠️ 时间解析失败: {e}")

        # 2. 历史未处理节目（数据库 pending/skipped_old/failed，失败次数<3）
        history_rows = self._get_unprocessed_history_episodes(limit=50)  # 获取更多候选

        for row in history_rows:
            feed_id, feed_name, title, audio_url, published_at, summary, author, url, duration = row

            # 去重（同一音频URL只保留一个候选）
            if audio_url in processed_audio_urls:
                continue
            processed_audio_urls.add(audio_url)

            episode = PodcastEpisode(
                feed_id=feed_id,
                feed_name=feed_name,
                title=title,
                audio_url=audio_url,
                published_at=published_at,
                summary=summary or "",
                author=author or "",
                url=url or "",
                duration=duration or "",
            )
            candidates.append((episode, 'history'))

        # 排序：新节目优先（rss_new > rss_old > history），同类型按发布时间降序
        priority_map = {'rss_new': 0, 'rss_old': 1, 'history': 2}

        def sort_key(item):
            episode, source = item
            pub_time = episode.published_at or ""
            return (priority_map.get(source, 99), pub_time, episode.title)

        candidates.sort(key=sort_key, reverse=True)

        print(f"[Podcast] 🎯 候选池构建完成: {len(candidates)} 个候选")
        print(f"[Podcast]   - RSS新节目: {sum(1 for _, s in candidates if s == 'rss_new')}")
        print(f"[Podcast]   - RSS老节目: {sum(1 for _, s in candidates if s == 'rss_old')}")
        print(f"[Podcast]   - 历史未处理: {sum(1 for _, s in candidates if s == 'history')}")

        return candidates

    def _select_episodes_to_process(self, all_episodes: Dict[str, List[PodcastEpisode]]) -> List[PodcastEpisode]:
        """
        选择要处理的节目（简化版）- 保留用于兼容性

        策略：
        1. 第一级：从 2 天以内的新播客中，循环遍历 feeds，每个 feed 取 1 个
        2. 第二级：如果第一级不够，从超过 2 天的老播客中，继续循环遍历 feeds 补齐

        筛选条件：不在 DB 中（_is_new_episode 返回 True）
        """
        from datetime import timedelta
        import pytz

        MAX_EPISODES = self.max_episodes_per_run  # 从配置读取
        now = get_configured_time(self.timezone)
        two_days_ago = (now - timedelta(days=self.new_episode_threshold_days))

        selected = []
        processed_feeds = set()  # 已从中选取的 feed_id

        # 第一级：2 天以内的新播客
        print(f"[Podcast] 🔍 第一级筛选：{self.new_episode_threshold_days} 天以内的新播客")
        for feed_id in list(all_episodes.keys()):  # 按配置顺序循环
            if len(selected) >= MAX_EPISODES:
                break
            if feed_id in processed_feeds:
                continue

            for episode in all_episodes[feed_id]:
                # 跳过 DB 中已处理的
                if not self._is_new_episode(episode):
                    continue

                # 检查发布时间（2 天以内）
                if episode.published_at:
                    try:
                        pub_time = self._parse_episode_time(episode.published_at)
                        if pub_time and pub_time >= two_days_ago:
                            selected.append(episode)
                            processed_feeds.add(feed_id)
                            print(f"[Podcast] ✓ 选中（新）: [{feed_id}] {episode.title[:50]}")
                            break  # 每个 feed 只取 1 个
                    except Exception as e:
                        print(f"[Podcast] ⚠️ 时间解析失败 ({episode.published_at}): {e}")

        # 第二级：超过 2 天的老播客（如果第一级不够 3 个）
        if len(selected) < MAX_EPISODES:
            print(f"[Podcast] 🔍 第二级筛选：超过 {self.new_episode_threshold_days} 天的老播客（还需 {MAX_EPISODES - len(selected)} 个）")
            for feed_id in list(all_episodes.keys()):  # 按配置顺序循环
                if len(selected) >= MAX_EPISODES:
                    break
                if feed_id in processed_feeds:
                    continue

                for episode in all_episodes[feed_id]:
                    # 跳过 DB 中已处理的
                    if not self._is_new_episode(episode):
                        continue

                    # 检查发布时间（超过 2 天）
                    if episode.published_at:
                        try:
                            pub_time = self._parse_episode_time(episode.published_at)
                            if pub_time and pub_time < two_days_ago:
                                selected.append(episode)
                                processed_feeds.add(feed_id)
                                print(f"[Podcast] ✓ 选中（老）: [{feed_id}] {episode.title[:50]}")
                                break  # 每个 feed 只取 1 个
                        except Exception as e:
                            print(f"[Podcast] ⚠️ 时间解析失败 ({episode.published_at}): {e}")

        return selected

    def _parse_episode_time(self, time_str: str) -> Optional[datetime]:
        """
        解析播客发布时间（统一处理时区）

        Args:
            time_str: ISO 格式时间字符串

        Returns:
            带时区的 datetime 对象（在配置的时区），解析失败返回 None
        """
        import pytz

        try:
            dt = None

            # 尝试解析带时区的格式
            if "+" in time_str or time_str.endswith("Z"):
                time_str_normalized = time_str.replace("Z", "+00:00")
                try:
                    dt = datetime.fromisoformat(time_str_normalized)
                except ValueError:
                    pass

            # 尝试解析不带时区的格式（假设为 UTC）
            if dt is None:
                try:
                    if "T" in time_str:
                        dt = datetime.fromisoformat(time_str.replace("T", " ").split(".")[0])
                    else:
                        dt = datetime.fromisoformat(time_str.split(".")[0])
                    # 假设为 UTC 时间
                    dt = pytz.UTC.localize(dt)
                except ValueError:
                    pass

            if dt is None:
                return None

            # 转换到配置的时区（与 two_days_ago 保持一致）
            config_tz = pytz.timezone(self.timezone)
            return dt.astimezone(config_tz)

        except Exception as e:
            print(f"[Podcast] ⚠️ 时间解析异常: {e}")
            return None

    def _check_and_backfill(self) -> List[PodcastEpisode]:
        """
        检查是否需要补充处理历史节目（简化版）

        策略：每次调用都从历史未处理节目中选择一个来处理
        不再检查空闲时间（因为触发间隔已改为6小时）

        Returns:
            需要补充处理的节目列表
        """
        print(f"[Podcast] 📋 尝试从历史未处理节目中选取...")

        # 获取未处理的历史节目（每次选取1个）
        history_rows = self._get_unprocessed_history_episodes(limit=1)

        if not history_rows:
            print("[Podcast] ✅ 所有历史节目都已处理完成")
            return []

        # 转换为 PodcastEpisode 对象
        episodes = []
        for row in history_rows:
            feed_id, feed_name, title, audio_url, published_at, summary, author, url, duration = row
            episode = PodcastEpisode(
                feed_id=feed_id,
                feed_name=feed_name,
                title=title,
                audio_url=audio_url,
                published_at=published_at,
                summary=summary or "",
                author=author or "",
                url=url or "",
                duration=duration or "",
            )
            episodes.append(episode)
            print(f"[Podcast] 🔄 补充处理: [{feed_name}] {title}")

        return episodes

    def _bootstrap_select_episode(self, all_episodes: Dict[str, List[PodcastEpisode]]) -> List[PodcastEpisode]:
        """
        Bootstrap 模式两级选取策略

        第一级：从 RSS 新节目中找最新未处理的一期
        第二级（回退）：从 DB 历史未处理节目中取最新一期
        """
        # 第一级：从 RSS 新节目中筛选
        new_episodes = []
        for feed_id, episodes in all_episodes.items():
            for ep in episodes:
                if self._is_new_episode(ep):
                    new_episodes.append(ep)

        print(f"[Podcast][Bootstrap] 第一级筛选: RSS 新节目数={len(new_episodes)}")

        if new_episodes:
            new_episodes.sort(
                key=lambda e: e.published_at or "",
                reverse=True
            )
            selected = new_episodes[0]
            print(f"[Podcast][Bootstrap] 选取(第一级): [{selected.feed_name}] {selected.title}")
            self._save_episode(selected, "pending")
            return [selected]

        # 第二级回退：从 DB 历史未处理节目中查找
        print("[Podcast][Bootstrap] 第一级无新节目, 进入第二级回退")
        history_rows = self._get_unprocessed_history_episodes(limit=1)

        if not history_rows:
            print("[Podcast][Bootstrap] 第二级查询: 无历史未处理节目")
            return []

        # 转换 tuple → PodcastEpisode（与 backfill 逻辑一致）
        feed_id, feed_name, title, audio_url, published_at, summary, author, url, duration = history_rows[0]
        episode = PodcastEpisode(
            feed_id=feed_id,
            feed_name=feed_name,
            title=title,
            audio_url=audio_url,
            published_at=published_at,
            summary=summary or "",
            author=author or "",
            url=url or "",
            duration=duration or "",
        )
        print(f"[Podcast][Bootstrap] 选取(第二级): [{feed_name}] {title} (status=历史未处理)")
        return [episode]

    def run(self) -> List[ProcessResult]:
        """
        运行播客处理流程（轮询模式）

        Returns:
            处理结果列表
        """
        if not self.enabled:
            print("[Podcast] 播客功能未启用")
            return []

        results = []

        # 1. 抓取所有播客源
        print("\n[Podcast] ═══════════════════════════════════════")
        print("[Podcast] 开始播客处理流程（轮询模式）")
        print("[Podcast] ═══════════════════════════════════════")

        all_episodes = self.fetcher.fetch_all()

        # 测试模式过滤
        if self.test_mode:
            if self.test_feed_id:
                # 只保留指定feed
                all_episodes = {
                    fid: eps for fid, eps in all_episodes.items()
                    if fid == self.test_feed_id
                }
                print(f"[Podcast] 🧪 测试模式：仅处理 feed={self.test_feed_id}")

            if self.test_episode_guid:
                # 进一步过滤到指定episode
                filtered = {}
                for feed_id, episodes in all_episodes.items():
                    matched = [ep for ep in episodes if ep.guid == self.test_episode_guid]
                    if matched:
                        filtered[feed_id] = matched
                all_episodes = filtered
                print(f"[Podcast] 🧪 测试模式：仅处理 guid={self.test_episode_guid}")

        if not all_episodes:
            print("[Podcast] 没有获取到任何节目")
            return []

        # 2. 清理卡死的中间状态节目
        self._cleanup_stuck_episodes()

        # 3. 构建候选池（Bootstrap 模式除外）
        if self.bootstrap_mode:
            # Bootstrap 模式：版本首次启动引导，选取一期节目
            selected_episodes = self._bootstrap_select_episode(all_episodes)
            if not selected_episodes:
                print("[Podcast][Bootstrap] 无可处理节目，引导结束")
                return []
            print(f"[Podcast][Bootstrap] 📦 引导触发处理 1 期节目")

            # 处理选中的节目
            for episode in selected_episodes:
                result = self.process_episode(episode)
                results.append(result)

            return results
        else:
            # 正常模式：构建候选池 + 轮询处理
            candidates = self._build_candidate_pool(all_episodes)

            if not candidates:
                print("[Podcast] 候选池为空，无需处理")
                return []

            # 轮询处理
            success_count = 0
            attempt_count = 0
            max_attempts = 20  # 最大尝试次数
            target_count = self.max_episodes_per_run

            print(f"[Podcast] 🎯 目标: 成功推送 {target_count} 个节目")
            print(f"[Podcast] 🎯 限制: 最多尝试 {max_attempts} 个候选")

            while success_count < target_count and attempt_count < max_attempts and candidates:
                attempt_count += 1
                episode, source = candidates.pop(0)  # 取出第一个候选

                print(f"\n[Podcast] 📦 尝试 {attempt_count}/{max_attempts}: [{episode.feed_name}] {episode.title[:60]}")
                print(f"[Podcast]    来源: {source}")

                # 处理节目
                result = self.process_episode(episode)
                results.append(result)

                if result.status == "completed":
                    success_count += 1
                    print(f"[Podcast] ✅ 成功推送 ({success_count}/{target_count})")
                else:
                    print(f"[Podcast] ❌ 处理失败: {result.error}")
                    # 失败计数已在 process_episode 中处理
                    # 继续尝试下一个候选

            print(f"\n[Podcast] ═══════════════════════════════════════")
            print(f"[Podcast] 轮询结果: 尝试 {attempt_count} 个候选，成功 {success_count} 个")
            print(f"[Podcast] ═══════════════════════════════════════")

            return results

    @classmethod
    def from_config(
        cls,
        config: dict,
        test_mode: bool = False,
        test_feed_id: Optional[str] = None,
        test_episode_guid: Optional[str] = None,
        bootstrap_mode: bool = False,
    ) -> "PodcastProcessor":
        """从配置创建处理器"""
        # 确定数据库路径
        storage_config = config.get("STORAGE", config.get("storage", {}))
        local_config = storage_config.get("local", {})
        data_dir = local_config.get("data_dir", "output")

        db_path = Path(data_dir) / "news" / "podcast.db"

        return cls(
            config=config,
            db_path=str(db_path),
            test_mode=test_mode,
            test_feed_id=test_feed_id,
            test_episode_guid=test_episode_guid,
            bootstrap_mode=bootstrap_mode,
        )
