#!/usr/bin/env python3
# coding=utf-8
"""
播客转写缓存管理器

用于缓存已转写的播客文本，避免重复转写
"""

import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional

class TranscriptCache:
    """播客转写缓存管理器"""

    def __init__(self, cache_dir: Optional[Path] = None):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录，默认为 agents/transcript_cache
        """
        if cache_dir is None:
            cache_dir = Path(__file__).parent / "transcript_cache"
        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.cache_file = self.cache_dir / "transcripts.json"

    def get(self, episode_id: str) -> Optional[str]:
        """
        获取缓存的转写文本

        Args:
            episode_id: 节目唯一标识（建议使用 feed_id_发布日期_title）

        Returns:
            转写文本，如果不存在则返回 None
        """
        if not self.cache_file.exists():
            return None

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                cache_data = json.load(f)
            return cache_data.get(episode_id)
        except Exception:
            return None

    def set(self, episode_id: str, transcript: str, metadata: Optional[Dict] = None):
        """
        保存转写文本到缓存

        Args:
            episode_id: 节目唯一标识
            transcript: 转写文本
            metadata: 元数据（如节目信息、转写时间等）
        """
        try:
            # 读取现有缓存
            if self.cache_file.exists():
                with open(self.cache_file, 'r', encoding='utf-8') as f:
                    cache_data = json.load(f)
            else:
                cache_data = {}

            # 更新缓存
            cache_data[episode_id] = {
                "transcript": transcript,
                "cached_at": datetime.now().isoformat(),
                "metadata": metadata or {}
            }

            # 保存到文件
            with open(self.cache_file, 'w', encoding='utf-8') as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)

            print(f"[TranscriptCache] 已缓存转写文本: {episode_id}")

        except Exception as e:
            print(f"[TranscriptCache] 缓存保存失败: {e}")

    def list_cached(self) -> Dict[str, Dict]:
        """
        列出所有已缓存的转写

        Returns:
            {episode_id: cache_entry} 字典
        """
        if not self.cache_file.exists():
            return {}

        try:
            with open(self.cache_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception:
            return {}
