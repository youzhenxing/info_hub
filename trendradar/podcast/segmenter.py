# coding=utf-8
"""
播客音频分段器

使用 ffmpeg 将超长音频分段，便于 ASR API 处理

分段策略：
- 自适应均分：2等分 → 3等分 → ... 直到每段 < 2小时
- 前后重叠：每段前后各增加 2 分钟
- 文件命名：按 index 命名（001, 002, 003）
"""

import subprocess
from pathlib import Path
from typing import List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class SegmentResult:
    """分段结果"""
    success: bool
    original_file: Optional[str] = None
    segment_files: List[str] = None  # 分段文件列表
    segment_count: int = 0
    duration_seconds: float = 0.0
    error: Optional[str] = None


class AudioSegmenter:
    """
    音频分段器

    功能：
    1. 检测音频时长（使用 ffprobe）
    2. 超过阈值时自动分段（自适应均分）
    3. 使用 ffmpeg 进行无损分段（-c copy）
    """

    # 默认配置
    DEFAULT_DURATION_THRESHOLD = 7200   # 2小时
    DEFAULT_OVERLAP_SECONDS = 120      # 2分钟
    DEFAULT_TEMP_DIR = "output/podcast/audio/segments"

    def __init__(
        self,
        duration_threshold: int = DEFAULT_DURATION_THRESHOLD,
        overlap_seconds: int = DEFAULT_OVERLAP_SECONDS,
        temp_dir: str = DEFAULT_TEMP_DIR,
    ):
        """
        初始化分段器

        Args:
            duration_threshold: 时长阈值（秒），超过此时长才分段
            overlap_seconds: 重叠时间（秒），前后各增加这么多
            temp_dir: 分段文件临时目录
        """
        self.duration_threshold = duration_threshold
        self.overlap_seconds = overlap_seconds
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)

        # 检查 ffmpeg 是否可用
        self.ffmpeg_available = self._check_ffmpeg()

        if not self.ffmpeg_available:
            print("[Segmenter] ⚠️  警告: ffmpeg 不可用，分段功能将被禁用")
        else:
            print(f"[Segmenter] 音频分段器初始化完成")
            print(f"[Segmenter] - 时长阈值: {duration_threshold/3600:.2f} 小时")
            print(f"[Segmenter] - 重叠时间: {overlap_seconds} 秒")
            print(f"[Segmenter] - 临时目录: {temp_dir}")

    def _check_ffmpeg(self) -> bool:
        """检查 ffmpeg 是否可用"""
        try:
            result = subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            if result.returncode == 0:
                return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            pass
        return False

    def segment_audio(self, file_path: str) -> SegmentResult:
        """
        分段音频文件

        Args:
            file_path: 音频文件路径

        Returns:
            SegmentResult 对象
        """
        path = Path(file_path)
        if not path.exists():
            return SegmentResult(
                success=False,
                error=f"文件不存在: {file_path}"
            )

        # 检查 ffmpeg 是否可用
        if not self.ffmpeg_available:
            print("[Segmenter] ⚠️  ffmpeg 不可用，跳过分段")
            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=[file_path],
                segment_count=0,
                duration_seconds=0.0,
            )

        # 1. 检测音频时长
        duration = self._get_duration(file_path)
        if duration < 0:
            # 无法检测时长，返回原始文件（不分段）
            print("[Segmenter] ⚠️  无法检测音频时长，跳过分段")
            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=[file_path],
                segment_count=0,
                duration_seconds=0.0,
            )

        print(f"[Segmenter] 音频时长: {duration/3600:.2f} 小时")

        # 2. 判断是否需要分段
        if duration <= self.duration_threshold:
            print(f"[Segmenter] 时长未超过阈值 ({self.duration_threshold/3600:.2f}h)，不分段")
            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=[file_path],
                segment_count=0,
                duration_seconds=duration,
            )

        # 3. 计算分段数量（自适应均分）
        segment_count = self._calculate_segment_count(duration)
        print(f"[Segmenter] 需要分段: {segment_count} 段 (每段约 {duration/segment_count/3600:.2f} 小时)")

        # 4. 执行分段
        try:
            segment_files = self._split_with_ffmpeg(
                file_path=file_path,
                segment_count=segment_count,
                duration=duration,
            )

            print(f"[Segmenter] ✅ 分段完成: {len(segment_files)} 个文件")

            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=segment_files,
                segment_count=len(segment_files),
                duration_seconds=duration,
            )

        except Exception as e:
            print(f"[Segmenter] ❌ 分段失败: {e}")
            # 分段失败，返回原始文件
            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=[file_path],
                segment_count=0,
                duration_seconds=duration,
                error=str(e),
            )

    def _get_duration(self, file_path: str) -> float:
        """
        获取音频时长（秒）- 使用 ffprobe

        Args:
            file_path: 音频文件路径

        Returns:
            时长（秒），失败返回 -1.0
        """
        try:
            result = subprocess.run(
                ['ffprobe', '-v', 'error',
                 '-show_entries', 'format=duration',
                 '-of', 'default=noprint_wrappers=1:nokey=1',
                 file_path],
                capture_output=True,
                text=True,
                timeout=30,
            )
            if result.returncode == 0:
                return float(result.stdout.strip())
            return -1.0
        except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
            return -1.0

    def _calculate_segment_count(self, duration: float) -> int:
        """
        计算分段数量（自适应均分）

        Args:
            duration: 音频总时长（秒）

        Returns:
            分段数量
        """
        if duration <= self.duration_threshold:
            return 1

        # 从2等分开始，逐步增加，直到每段 < duration_threshold
        for n in range(2, 100):  # 最多100段
            segment_duration = duration / n
            if segment_duration < self.duration_threshold:
                return n

        return 100  # 安全上限

    def _split_with_ffmpeg(
        self,
        file_path: str,
        segment_count: int,
        duration: float,
    ) -> List[str]:
        """
        使用 ffmpeg 分段音频

        Args:
            file_path: 原始文件路径
            segment_count: 分段数量
            duration: 总时长（秒）

        Returns:
            分段文件路径列表
        """
        path = Path(file_path)
        base_name = path.stem
        extension = path.suffix

        segment_duration = duration / segment_count
        segment_files = []

        for i in range(segment_count):
            # 计算分段时间点（带前后重叠）
            base_start = i * segment_duration
            base_end = min((i + 1) * segment_duration, duration)

            # 添加重叠（第一段不往前，最后一段不往后）
            start = max(0, base_start - self.overlap_seconds)
            end = min(duration, base_end + self.overlap_seconds)

            # 生成分段文件名（按 index 命名）
            segment_name = f"{base_name}_{i+1:03d}{extension}"
            segment_path = self.temp_dir / segment_name

            # 使用 ffmpeg 分段（-c copy 无损复制，不重新编码）
            print(f"[Segmenter] 分段 {i+1}/{segment_count}: {segment_name} ({start/60:.1f}m - {end/60:.1f}m)")

            subprocess.run(
                [
                    'ffmpeg',
                    '-i', file_path,
                    '-ss', str(start),
                    '-to', str(end),
                    '-c', 'copy',  # 无损复制，不重新编码
                    str(segment_path),
                    '-y',  # 覆盖已存在文件
                ],
                capture_output=True,
                timeout=300,  # 5分钟超时
                check=True,
            )

            segment_files.append(str(segment_path))

        return segment_files

    def cleanup_segments(self, segment_files: List[str]) -> int:
        """
        清理分段文件

        Args:
            segment_files: 分段文件路径列表

        Returns:
            删除的文件数量
        """
        count = 0
        for file_path in segment_files:
            try:
                path = Path(file_path)
                if path.exists() and path.is_file():
                    path.unlink()
                    count += 1
                    print(f"[Segmenter] 已清理: {path.name}")
            except Exception as e:
                print(f"[Segmenter] 清理失败: {e}")

        if count > 0:
            print(f"[Segmenter] ✅ 已清理 {count} 个分段文件")

        return count

    @classmethod
    def from_config(cls, config: dict) -> "AudioSegmenter":
        """
        从配置字典创建分段器

        Args:
            config: 配置字典（来自 config.yaml 的 podcast.segment 段）

        Returns:
            AudioSegmenter 实例
        """
        # 多级查找，兼容大小写
        segment_config = config.get("SEGMENT", config.get("segment", {}))

        return cls(
            duration_threshold=segment_config.get("DURATION_THRESHOLD", segment_config.get("duration_threshold", cls.DEFAULT_DURATION_THRESHOLD)),
            overlap_seconds=segment_config.get("OVERLAP_SECONDS", segment_config.get("overlap_seconds", cls.DEFAULT_OVERLAP_SECONDS)),
            temp_dir=segment_config.get("TEMP_DIR", segment_config.get("temp_dir", cls.DEFAULT_TEMP_DIR)),
        )
