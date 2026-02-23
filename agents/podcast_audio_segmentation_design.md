# 播客音频分段功能 - 详细实施方案

**创建时间**: 2026-02-11  
**设计者**: Claude  
**优先级**: P1 (中期改进)  
**预计工作量**: 4-5 小时

---

## 📋 目录

1. [技术方案](#1-技术方案)
2. [代码架构](#2-代码架构)
3. [依赖管理](#3-依赖管理)
4. [配置设计](#4-配置设计)
5. [错误处理](#5-错误处理)
6. [测试策略](#6-测试策略)
7. [实施步骤](#7-实施步骤)

---

## 1. 技术方案

### 1.1 核心思路

**问题根源**：
- 超长音频（>2小时，如391.7MB）可能导致 ASR API 超时或返回 500 错误
- SiliconFlow API 对文件大小有限制
- AssemblyAI 虽然支持更大文件，但仍需考虑稳定性

**解决方案**：
```
下载完成 → 检测音频时长 → 超过阈值？ → 是：自动分段 → 分别转写 → 智能合并
                                        ↓
                                     否：直接转写
```

### 1.2 音频时长检测

**工具**: `ffprobe`（FFmpeg 的探测工具）

**检测方法**：
```bash
ffprobe -v error -show_entries format=duration -of default=noprint_wrappers=1:nokey=1 audio.mp3
```

**Python 封装**：
```python
import subprocess
from pathlib import Path

def get_audio_duration(file_path: str) -> float:
    """
    获取音频时长（秒）
    
    Returns:
        时长（秒），失败返回 -1
    """
    try:
        result = subprocess.run(
            ['ffprobe', '-v', 'error', 
             '-show_entries', 'format=duration',
             '-of', 'default=noprint_wrappers=1:nokey=1',
             file_path],
            capture_output=True,
            text=True,
            timeout=10
        )
        if result.returncode == 0:
            return float(result.stdout.strip())
        return -1.0
    except (subprocess.TimeoutExpired, ValueError, FileNotFoundError):
        return -1.0
```

### 1.3 分段策略

**分段配置**：
```yaml
segment:
  enabled: true                  # 是否启用分段
  duration_threshold: 7200       # 时长阈值（秒）= 2小时
  segment_duration: 3600         # 每段时长（秒）= 1小时
  overlap: 5                     # 段间重叠（秒）= 5秒
```

**分段逻辑**：
```
原音频: 0 ──────────────────────── 3小时 (10800秒)
       │
       ├─ Segment 1: [0:00:00 - 1:00:05]  (3605秒)
       ├─ Segment 2: [0:59:55 - 2:00:05]  (3610秒) 
       ├─ Segment 3: [1:59:55 - 3:00:00]  (3605秒)
       │
       └─ 每段重叠5秒，确保连续性
```

### 1.4 分段后的文件管理

**文件命名规则**：
```
原始文件: feed_id_hash123.mp3
分段文件: feed_id_hash123_part001.mp3
         feed_id_hash123_part002.mp3
         ...
```

**临时目录结构**：
```
output/podcast/audio/
├── feed_id_hash123.mp3           # 原始文件
└── segments/
    ├── feed_id_hash123_part001.mp3
    ├── feed_id_hash123_part002.mp3
    └── feed_id_hash123_part003.mp3
```

**清理策略**：
- 所有分段文件在转写完成后统一删除
- 原始文件根据 `cleanup_after_transcribe` 配置决定是否删除

### 1.5 转写结果合并策略

**合并原则**：
```
Segment 1: "[SPEAKER_00] 第一段话...\n[SPEAKER_01] 回答..."
Segment 2: "[SPEAKER_00] ...重叠的话...\n[SPEAKER_01] 第二段..."
Segment 3: "[SPEAKER_00] 第三段..."

合并结果:
  [SPEAKER_00] 第一段话...
  [SPEAKER_01] 回答...
  [SPEAKER_01] 第二段...  (跳过重叠部分)
  [SPEAKER_00] 第三段...
```

**智能去重算法**：
1. 识别每段的说话人和最后一句
2. 检测相邻段的重叠部分（相似度匹配）
3. 只保留非重叠部分
4. 按时间顺序拼接

**简化版（推荐初期）**：
```python
def merge_transcripts(transcripts: list[str]) -> str:
    """
    合并分段转写结果（简化版：保留重叠，AI会处理）
    """
    return "\n\n".join(transcripts)
```

**理由**：
- 重叠部分只有 5 秒，AI 分析时会自动去重
- 简化实现，避免复杂的文本对齐算法
- 避免误删重要内容

---

## 2. 代码架构

### 2.1 类图

```
┌─────────────────────────────────────────────────────────────┐
│                    AudioSegmenter (新增)                      │
├─────────────────────────────────────────────────────────────┤
│ + segment_audio(file_path: str) → List[str]                  │
│ - _get_duration(file_path: str) → float                      │
│ - _split_ffmpeg(file_path: str) → List[str]                  │
│ - _generate_segment_names(base: str, count: int) → List[str] │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  AudioDownloader (修改)                       │
├─────────────────────────────────────────────────────────────┤
│ + download(...) → DownloadResult                             │
│   - 添加：下载后调用 segmenter.segment_audio()                │
│   - 返回：original_file + segment_files (如果分段)            │
└─────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  ASRTranscriber (修改)                        │
├─────────────────────────────────────────────────────────────┤
│ + transcribe_segments(...) → TranscribeResult                │
│   - 新增：批量转写分段文件                                    │
│   - 新增：合并转写结果                                        │
└─────────────────────────────────────────────────────────────┘
```

### 2.2 新增类/函数

#### 2.2.1 `AudioSegmenter` 类

**文件**: `trendradar/podcast/segmenter.py` (新建)

```python
# coding=utf-8
"""
播客音频分段器

使用 ffmpeg 将超长音频分段，便于 ASR API 处理
"""

import subprocess
from pathlib import Path
from typing import List, Optional
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
    1. 检测音频时长
    2. 超过阈值时自动分段
    3. 使用 ffmpeg 进行无损分段
    """
    
    DEFAULT_DURATION_THRESHOLD = 7200   # 2小时
    DEFAULT_SEGMENT_DURATION = 3600     # 1小时
    DEFAULT_OVERLAP = 5                 # 5秒重叠
    
    def __init__(
        self,
        duration_threshold: int = DEFAULT_DURATION_THRESHOLD,
        segment_duration: int = DEFAULT_SEGMENT_DURATION,
        overlap: int = DEFAULT_OVERLAP,
        temp_dir: str = "output/podcast/audio/segments",
    ):
        """
        初始化分段器
        
        Args:
            duration_threshold: 时长阈值（秒），超过此时长才分段
            segment_duration: 每段时长（秒）
            overlap: 段间重叠时间（秒）
            temp_dir: 分段文件临时目录
        """
        self.duration_threshold = duration_threshold
        self.segment_duration = segment_duration
        self.overlap = overlap
        self.temp_dir = Path(temp_dir)
        self.temp_dir.mkdir(parents=True, exist_ok=True)
        
        # 检查 ffmpeg 是否可用
        self._check_ffmpeg()
    
    def _check_ffmpeg(self):
        """检查 ffmpeg 是否可用"""
        try:
            subprocess.run(
                ['ffmpeg', '-version'],
                capture_output=True,
                timeout=5
            )
            print("[Segmenter] ffmpeg 检测成功")
        except (FileNotFoundError, subprocess.TimeoutExpired):
            print("[Segmenter] ⚠️  警告: ffmpeg 不可用，分段功能将被禁用")
    
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
        
        # 1. 检测音频时长
        duration = self._get_duration(file_path)
        if duration < 0:
            # 无法检测时长，返回原始文件（不分段）
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
        
        # 3. 计算分段数量
        segment_count = int(duration / self.segment_duration) + 1
        print(f"[Segmenter] 需要分段: {segment_count} 段")
        
        # 4. 执行分段
        try:
            segment_files = self._split_with_ffmpeg(
                file_path=file_path,
                segment_count=segment_count,
                duration=duration,
            )
            
            return SegmentResult(
                success=True,
                original_file=file_path,
                segment_files=segment_files,
                segment_count=len(segment_files),
                duration_seconds=duration,
            )
        
        except Exception as e:
            return SegmentResult(
                success=False,
                error=f"分段失败: {e}"
            )
    
    def _get_duration(self, file_path: str) -> float:
        """获取音频时长（秒）"""
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
        
        segment_files = []
        
        for i in range(segment_count):
            # 计算分段起止时间
            start_time = i * self.segment_duration - (self.overlap if i > 0 else 0)
            end_time = min((i + 1) * self.segment_duration + self.overlap, duration)
            
            # 确保时间不越界
            if start_time < 0:
                start_time = 0
            if start_time >= duration:
                break
            
            # 生成分段文件名
            segment_name = f"{base_name}_part{i+1:03d}{extension}"
            segment_path = self.temp_dir / segment_name
            
            # 使用 ffmpeg 分段
            # 格式：ffmpeg -i input.mp3 -ss 00:00:00 -to 01:00:05 -c copy output.mp3
            subprocess.run(
                [
                    'ffmpeg',
                    '-i', file_path,
                    '-ss', str(start_time),
                    '-to', str(end_time),
                    '-c', 'copy',  # 无损复制，不重新编码
                    str(segment_path),
                    '-y',  # 覆盖已存在文件
                ],
                capture_output=True,
                timeout=300,  # 5分钟超时
                check=True,
            )
            
            segment_files.append(str(segment_path))
            print(f"[Segmenter] 分段 {i+1}/{segment_count}: {segment_name} ({start_time/60:.1f}m - {end_time/60:.1f}m)")
        
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
                if path.exists():
                    path.unlink()
                    count += 1
                    print(f"[Segmenter] 已清理: {path.name}")
            except Exception as e:
                print(f"[Segmenter] 清理失败: {e}")
        
        if count > 0:
            print(f"[Segmenter] 已清理 {count} 个分段文件")
        
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
        segment_config = config.get("SEGMENT", config.get("segment", {}))
        
        return cls(
            duration_threshold=segment_config.get("DURATION_THRESHOLD", segment_config.get("duration_threshold", cls.DEFAULT_DURATION_THRESHOLD)),
            segment_duration=segment_config.get("SEGMENT_DURATION", segment_config.get("segment_duration", cls.DEFAULT_SEGMENT_DURATION)),
            overlap=segment_config.get("OVERLAP", segment_config.get("overlap", cls.DEFAULT_OVERLAP)),
            temp_dir=segment_config.get("TEMP_DIR", segment_config.get("temp_dir", "output/podcast/audio/segments")),
        )
```

### 2.3 修改现有文件

#### 2.3.1 修改 `DownloadResult`

**文件**: `trendradar/podcast/downloader.py`

```python
@dataclass
class DownloadResult:
    """下载结果"""
    success: bool
    file_path: Optional[str] = None
    file_size: int = 0
    error: Optional[str] = None
    
    # 新增字段
    is_segmented: bool = False           # 是否进行了分段
    segment_files: List[str] = None      # 分段文件列表（如果分段）
    original_file: Optional[str] = None  # 原始文件路径（如果分段）
```

#### 2.3.2 修改 `AudioDownloader.download()`

**文件**: `trendradar/podcast/downloader.py`

```python
def download(
    self,
    audio_url: str,
    feed_id: str,
    expected_size: int = 0,
    segmenter: Optional["AudioSegmenter"] = None,  # 新增参数
) -> DownloadResult:
    """
    下载音频文件
    
    Args:
        audio_url: 音频 URL
        feed_id: 播客源 ID
        expected_size: 预期文件大小（字节）
        segmenter: 音频分段器（可选）
    
    Returns:
        DownloadResult 对象
    """
    # ... 现有下载逻辑 ...
    
    # 下载完成后的新逻辑
    if download_result.success and segmenter:
        print("[Download] 检测是否需要分段...")
        segment_result = segmenter.segment_audio(download_result.file_path)
        
        if segment_result.success and segment_result.segment_count > 0:
            print(f"[Download] 音频已分段为 {segment_result.segment_count} 段")
            return DownloadResult(
                success=True,
                file_path=segment_result.segment_files[0],  # 主文件指向第一段
                file_size=Path(segment_result.segment_files[0]).stat().st_size,
                is_segmented=True,
                segment_files=segment_result.segment_files,
                original_file=segment_result.original_file,
            )
        elif not segment_result.success:
            # 分段失败，但下载成功，回退到原始文件
            print(f"[Download] 分段失败，使用原始文件: {segment_result.error}")
    
    return download_result
```

#### 2.3.3 修改 `ASRTranscriber`

**文件**: `trendradar/podcast/transcriber.py`

```python
def transcribe_segments(
    self,
    segment_files: List[str],
) -> TranscribeResult:
    """
    批量转写分段音频
    
    Args:
        segment_files: 分段文件路径列表
    
    Returns:
        TranscribeResult 对象（合并后的结果）
    """
    if not segment_files:
        return TranscribeResult(
            success=False,
            error="分段文件列表为空"
        )
    
    print(f"[ASR] 开始批量转写 {len(segment_files)} 个分段...")
    
    all_transcripts = []
    total_duration = 0.0
    all_languages = set()
    all_speakers = set()
    
    for i, segment_file in enumerate(segment_files):
        print(f"\n[ASR] ─────────────────────────────────────────")
        print(f"[ASR] 转写分段 {i+1}/{len(segment_files)}: {Path(segment_file).name}")
        print(f"[ASR] ─────────────────────────────────────────")
        
        # 转写单个分段
        result = self.transcribe(segment_file)
        
        if not result.success:
            # 部分分段失败，继续处理其他分段
            print(f"[ASR] ⚠️  分段 {i+1} 转写失败: {result.error}")
            continue
        
        # 收集转写结果
        all_transcripts.append(result.transcript)
        total_duration += result.duration_seconds
        if result.language:
            all_languages.add(result.language)
        if result.speaker_count > 0:
            all_speakers.add(result.speaker_count)
        
        print(f"[ASR] 分段 {i+1} 完成: {len(result.transcript)} 字符")
    
    # 合并转写结果
    if not all_transcripts:
        return TranscribeResult(
            success=False,
            error="所有分段转写均失败"
        )
    
    merged_transcript = self._merge_transcripts(all_transcripts)
    
    print(f"\n[ASR] ✅ 批量转写完成:")
    print(f"[ASR] - 成功转写: {len(all_transcripts)}/{len(segment_files)} 个分段")
    print(f"[ASR] - 总时长: {total_duration/3600:.2f} 小时")
    print(f"[ASR] - 总字符数: {len(merged_transcript)}")
    print(f"[ASR] - 检测语言: {', '.join(all_languages)}")
    
    return TranscribeResult(
        success=True,
        transcript=merged_transcript,
        duration_seconds=total_duration,
        language=all_languages.pop() if len(all_languages) == 1 else "mixed",
        speaker_count=len(all_speakers) if all_speakers else 0,
    )

def _merge_transcripts(self, transcripts: List[str]) -> str:
    """
    合并分段转写结果
    
    策略：简单拼接（AI会处理重叠部分）
    
    Args:
        transcripts: 分段转写文本列表
    
    Returns:
        合并后的转写文本
    """
    # 简单拼接，保留分段标记
    # AI 分析时会自动处理重叠部分
    return "\n\n".join(transcripts)
```

#### 2.3.4 修改 `PodcastProcessor.process_episode()`

**文件**: `trendradar/podcast/processor.py`

```python
def _init_components(self):
    """初始化各个处理组件"""
    # ... 现有组件初始化 ...
    
    # 新增：音频分段器
    segment_config = self.podcast_config.get("SEGMENT", self.podcast_config.get("segment", {}))
    segment_enabled = segment_config.get("ENABLED", segment_config.get("enabled", False))
    
    if segment_enabled:
        self.segmenter = AudioSegmenter.from_config(self.podcast_config)
    else:
        self.segmenter = None

def process_episode(self, episode: PodcastEpisode) -> ProcessResult:
    """处理单个播客节目"""
    # ... 现有代码 ...
    
    # 1. 下载音频（传入 segmenter）
    download_result = self.downloader.download(
        audio_url=episode.audio_url,
        feed_id=episode.feed_id,
        expected_size=episode.audio_length,
        segmenter=self.segmenter,  # 传入分段器
    )
    
    # 2. ASR 转写（处理分段）
    if download_result.is_segmented:
        # 批量转写分段文件
        transcribe_result = self.transcriber.transcribe_segments(
            segment_files=download_result.segment_files
        )
    else:
        # 直接转写单个文件
        transcribe_result = self.transcriber.transcribe(
            audio_path=download_result.file_path
        )
    
    # 3. 清理分段文件
    if download_result.is_segmented:
        if self.segmenter:
            self.segmenter.cleanup_segments(download_result.segment_files)
    
    # ... 其余代码 ...
```

---

## 3. 依赖管理

### 3.1 Dockerfile 修改

**文件**: `docker/Dockerfile`

**修改位置**: 第 13-15 行（安装系统依赖部分）

```dockerfile
# 安装系统依赖
RUN set -ex && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    curl ca-certificates \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*
```

**说明**：
- 只需添加 `ffmpeg` 包
- ffmpeg 包含 `ffmpeg` 和 `ffprobe` 两个工具
- 镜像大小增加约 10MB

### 3.2 requirements.txt 修改

**文件**: `requirements.txt`

**无需修改**：
- 使用 subprocess 调用 ffmpeg，不需要 Python 绑定
- 不需要 `pydub` 或 `ffmpeg-python` 等库

### 3.3 容器启动验证

**文件**: `docker/bootstrap.py`（新增验证）

```python
def _check_ffmpeg(self) -> bool:
    """检查 ffmpeg 是否可用"""
    try:
        result = subprocess.run(
            ['ffmpeg', '-version'],
            capture_output=True,
            timeout=5
        )
        if result.returncode == 0:
            print("[Bootstrap] ✅ ffmpeg 可用")
            return True
        else:
            print("[Bootstrap] ❌ ffmpeg 不可用")
            return False
    except FileNotFoundError:
        print("[Bootstrap] ❌ ffmpeg 未安装")
        return False
    except Exception as e:
        print(f"[Bootstrap] ❌ ffmpeg 检测失败: {e}")
        return False

def run_verifications(self):
    """运行所有验证"""
    # ... 现有验证 ...
    
    # 新增：ffmpeg 验证
    if not self._check_ffmpeg():
        print("[Bootstrap] ⚠️  警告: ffmpeg 不可用，音频分段功能将被禁用")
```

---

## 4. 配置设计

### 4.1 config.yaml 新增配置

**文件**: `config/config.yaml`

**位置**: `podcast` 段落内，`download` 之后

```yaml
podcast:
  enabled: true
  poll_interval_minutes: 360
  
  # ... 现有配置 ...
  
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  # 音频分段配置（新增）
  # 
  # 用途：自动将超长音频分段，避免 ASR API 超时或文件过大错误
  # 适用于：> 2小时的超长播客
  # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
  segment:
    enabled: true                     # 是否启用音频分段
    duration_threshold: 7200          # 时长阈值（秒）= 2小时
    segment_duration: 3600            # 每段时长（秒）= 1小时
    overlap: 5                        # 段间重叠（秒）= 5秒
    temp_dir: "output/podcast/audio/segments"  # 分段文件临时目录
```

### 4.2 配置项说明

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `enabled` | boolean | `false` | 是否启用分段功能 |
| `duration_threshold` | int | `7200` | 超过此时长（秒）才分段 |
| `segment_duration` | int | `3600` | 每段的目标时长（秒） |
| `overlap` | int | `5` | 相邻段之间的重叠时间（秒） |
| `temp_dir` | string | `"output/podcast/audio/segments"` | 分段文件临时存放目录 |

### 4.3 默认值设计思路

**为什么是 2 小时阈值？**
- AssemblyAI 支持最大 3 小时，但超过 2 小时稳定性下降
- 大部分播客在 1-2 小时之间
- 2 小时阈值可以过滤掉大部分正常播客

**为什么是 1 小时分段？**
- 1 小时音频约 50-100MB，上传和转写时间合理
- AssemblyAI 转写速度约 1/10 实时，1 小时约需 6 分钟
- 3 小时分 3 段，总耗时约 18 分钟，可接受

**为什么是 5 秒重叠？**
- 说话人切换通常在 2-3 秒内完成
- 5 秒重叠确保不会丢失说话人的半句话
- 重叠部分 AI 分析时会自动去重

---

## 5. 错误处理

### 5.1 ffmpeg 不可用时的降级方案

**场景**：容器内未安装 ffmpeg

**处理逻辑**：
```python
def segment_audio(self, file_path: str) -> SegmentResult:
    """分段音频文件"""
    # 检查 ffmpeg 是否可用
    if not self._check_ffmpeg():
        print("[Segmenter] ⚠️  ffmpeg 不可用，跳过分段")
        return SegmentResult(
            success=True,
            original_file=file_path,
            segment_files=[file_path],
            segment_count=0,
            duration_seconds=0.0,
        )
    
    # ... 继续分段逻辑 ...
```

**效果**：
- 功能自动降级，不影响主流程
- 日志提示用户安装 ffmpeg
- 超长文件直接传递给 ASR API

### 5.2 分段失败时的处理

**场景**：ffmpeg 命令执行失败

**处理逻辑**：
```python
def _split_with_ffmpeg(self, ...) -> List[str]:
    """使用 ffmpeg 分段"""
    try:
        subprocess.run(..., check=True)
    except subprocess.CalledProcessError as e:
        print(f"[Segmenter] ❌ ffmpeg 执行失败: {e}")
        raise  # 抛出异常，由上层处理
    except subprocess.TimeoutExpired:
        print(f"[Segmenter] ❌ ffmpeg 超时")
        raise
```

**效果**：
- 返回 `success=False` 的 `SegmentResult`
- 上层逻辑检测到失败，使用原始文件
- 不影响播客处理主流程

### 5.3 部分分段失败的处理

**场景**：3 个分段中有 1 个转写失败

**处理逻辑**：
```python
def transcribe_segments(self, segment_files: List[str]) -> TranscribeResult:
    """批量转写分段"""
    all_transcripts = []
    
    for i, segment_file in enumerate(segment_files):
        result = self.transcribe(segment_file)
        
        if not result.success:
            # 部分分段失败，继续处理其他分段
            print(f"[ASR] ⚠️  分段 {i+1} 转写失败: {result.error}")
            continue  # 跳过失败的分段
        
        all_transcripts.append(result.transcript)
    
    # 检查是否至少有一个分段成功
    if not all_transcripts:
        return TranscribeResult(
            success=False,
            error="所有分段转写均失败"
        )
    
    # 继续合并成功的分段
    return TranscribeResult(success=True, ...)
```

**效果**：
- 尽可能多地保留内容
- 失败的分段跳过，不阻塞整体流程
- 如果所有分段都失败，才返回失败

### 5.4 错误日志设计

```python
# 分段失败
[Segmenter] ❌ 分段失败: ffmpeg returned exit code 1
[Segmenter] ⚠️  使用原始文件继续处理

# 部分转写失败
[ASR] ⚠️  分段 2/3 转写失败: API timeout
[ASR] ✅ 成功转写 2/3 个分段，继续合并

# 全部失败
[ASR] ❌ 所有分段转写均失败
[Podcast] ❌ 转录最终失败: 所有分段转写均失败
```

---

## 6. 测试策略

### 6.1 单元测试

**文件**: `tests/test_segmenter.py`（新建）

```python
import pytest
from trendradar.podcast.segmenter import AudioSegmenter, SegmentResult

class TestAudioSegmenter:
    """音频分段器测试"""
    
    def test_get_duration(self):
        """测试音频时长检测"""
        segmenter = AudioSegmenter()
        
        # 使用真实音频文件
        duration = segmenter._get_duration("tests/fixtures/short_audio.mp3")
        assert duration > 0
        assert duration < 10  # 测试文件应该很短
    
    def test_no_segment_needed(self):
        """测试短音频不分段"""
        segmenter = AudioSegmenter(duration_threshold=7200)
        result = segmenter.segment_audio("tests/fixtures/short_audio.mp3")
        
        assert result.success
        assert result.segment_count == 0
        assert len(result.segment_files) == 1
    
    def test_segment_long_audio(self):
        """测试长音频分段"""
        segmenter = AudioSegmenter(
            duration_threshold=60,  # 1分钟阈值
            segment_duration=30,    # 30秒分段
        )
        result = segmenter.segment_audio("tests/fixtures/long_audio.mp3")
        
        assert result.success
        assert result.segment_count > 0
        assert len(result.segment_files) == result.segment_count
    
    def test_ffmpeg_not_available(self):
        """测试 ffmpeg 不可用时的降级"""
        segmenter = AudioSegmenter()
        segmenter._check_ffmpeg = lambda: False  # Mock
        
        result = segmenter.segment_audio("any_file.mp3")
        
        assert result.success
        assert result.segment_count == 0
```

### 6.2 集成测试

**文件**: `tests/test_podcast_segmentation_integration.py`（新建）

```python
import pytest
from trendradar.podcast.processor import PodcastProcessor

class TestPodcastSegmentationIntegration:
    """播客分段处理集成测试"""
    
    @pytest.fixture
    def config_with_segmentation(self):
        """启用分段的配置"""
        return {
            "PODCAST": {
                "enabled": True,
                "segment": {
                    "enabled": True,
                    "duration_threshold": 60,
                    "segment_duration": 30,
                },
                # ... 其他配置 ...
            }
        }
    
    def test_full_segmentation_workflow(self, config_with_segmentation):
        """测试完整的分段处理流程"""
        processor = PodcastProcessor(config=config_with_segmentation)
        
        # 创建测试播客节目
        episode = PodcastEpisode(
            feed_id="test",
            feed_name="Test Podcast",
            title="Long Episode",
            audio_url="http://example.com/long.mp3",
            # ... 其他字段 ...
        )
        
        # 处理节目
        result = processor.process_episode(episode)
        
        # 验证结果
        assert result.status == "completed"
        assert result.download_result.is_segmented
        assert len(result.download_result.segment_files) > 0
```

### 6.3 测试文件准备

**所需测试音频**：

```
tests/fixtures/audio/
├── short_10s.mp3           # 10秒音频（不分段）
├── medium_30m.mp3          # 30分钟音频（不分段）
├── long_3h.mp3             # 3小时音频（需要分段）
└── corrupted.mp3           # 损坏的音频（测试错误处理）
```

**获取方式**：
```bash
# 使用 ffmpeg 生成测试音频
ffmpeg -f lavfi -i testsrc=duration=10:size=320x240:rate=1 -f mp3 tests/fixtures/audio/short_10s.mp3

# 下载真实播客作为测试文件
wget -O tests/fixtures/audio/long_3h.mp3 "https://example.com/long-podcast.mp3"
```

### 6.4 手动测试步骤

**步骤 1：验证 ffmpeg 安装**
```bash
# 进入容器
docker exec -it trendradar-prod bash

# 检查 ffmpeg
ffmpeg -version
ffprobe -version
```

**步骤 2：测试分段功能**
```bash
# 下载测试音频
cd /app/output/podcast/audio
wget https://podcasts.example.com/long-episode.mp3

# 测试分段
python -c "
from trendradar.podcast.segmenter import AudioSegmenter
segmenter = AudioSegmenter(duration_threshold=3600)  # 1小时阈值
result = segmenter.segment_audio('long-episode.mp3')
print(f'分段结果: {result.segment_count} 段')
print(f'分段文件: {result.segment_files}')
"

# 验证分段文件
ls -lh segments/
```

**步骤 3：测试转写合并**
```bash
# 测试批量转写
python -c "
from trendradar.podcast.transcriber import ASRTranscriber
transcriber = ASRTranscriber(backend='assemblyai')
result = transcriber.transcribe_segments([
    'output/podcast/audio/segments/long-episode_part001.mp3',
    'output/podcast/audio/segments/long-episode_part002.mp3',
])
print(f'合并转写: {len(result.transcript)} 字符')
"
```

**步骤 4：测试完整流程**
```yaml
# 修改 config.yaml，降低分段阈值
podcast:
  segment:
    enabled: true
    duration_threshold: 60  # 1分钟阈值（测试用）
    segment_duration: 30
```

```bash
# 触发播客处理
docker exec trendradar-prod python -m trendradar --podcast-only

# 查看日志
docker logs trendradar-prod 2>&1 | grep -A 20 "Segmenter"
```

---

## 7. 实施步骤

### Phase 1: 准备工作（30分钟）

1. **创建分支**
   ```bash
   git checkout -b feature/podcast-audio-segmentation
   ```

2. **准备测试文件**
   - 下载不同时长的测试音频
   - 放置在 `tests/fixtures/audio/` 目录

3. **本地安装 ffmpeg**
   ```bash
   # Ubuntu/Debian
   sudo apt-get install ffmpeg
   
   # macOS
   brew install ffmpeg
   
   # 验证安装
   ffmpeg -version
   ```

### Phase 2: 核心功能开发（2小时）

1. **创建 `segmenter.py`**（45分钟）
   - [ ] 实现 `AudioSegmenter` 类
   - [ ] 实现 `_get_duration()` 方法
   - [ ] 实现 `_split_with_ffmpeg()` 方法
   - [ ] 实现 `cleanup_segments()` 方法
   - [ ] 添加单元测试

2. **修改 `downloader.py`**（30分钟）
   - [ ] 扩展 `DownloadResult` 类
   - [ ] 修改 `download()` 方法，集成分段器
   - [ ] 添加错误处理

3. **修改 `transcriber.py`**（30分钟）
   - [ ] 实现 `transcribe_segments()` 方法
   - [ ] 实现 `_merge_transcripts()` 方法
   - [ ] 添加批量转写逻辑

4. **修改 `processor.py`**（15分钟）
   - [ ] 在 `_init_components()` 中初始化分段器
   - [ ] 在 `process_episode()` 中调用分段逻辑
   - [ ] 添加分段文件清理

### Phase 3: 集成与配置（1小时）

1. **修改 Dockerfile**（15分钟）
   - [ ] 添加 `ffmpeg` 到系统依赖
   - [ ] 验证镜像构建

2. **修改 config.yaml**（15分钟）
   - [ ] 添加 `podcast.segment` 配置段落
   - [ ] 设置合理的默认值
   - [ ] 添加配置注释

3. **修改 bootstrap.py**（15分钟）
   - [ ] 添加 ffmpeg 可用性检查
   - [ ] 添加分段功能验证
   - [ ] 添加降级提示

4. **更新 deploy.sh**（15分钟）
   - [ ] 验证配置同步
   - [ ] 验证 volume 挂载

### Phase 4: 测试与验证（1小时）

1. **单元测试**（20分钟）
   - [ ] 运行 `pytest tests/test_segmenter.py`
   - [ ] 修复发现的问题

2. **集成测试**（20分钟）
   - [ ] 运行完整播客处理流程
   - [ ] 验证分段、转写、合并

3. **容器测试**（20分钟）
   - [ ] 重新构建 Docker 镜像
   - [ ] 验证 ffmpeg 可用
   - [ ] 测试分段功能

### Phase 5: 文档与部署（30分钟）

1. **更新文档**（15分钟）
   - [ ] 更新 `CLAUDE.md`（添加分段功能说明）
   - [ ] 更新 `CHANGELOG.md`（记录版本变更）
   - [ ] 更新 `agents/podcast_improvement_suggestions.md`（标记完成）

2. **提交代码**（15分钟）
   - [ ] 运行 `bash deploy/pre-commit-verify.sh`
   - [ ] 提交代码：`git commit`
   - [ ] 执行部署：`cd deploy && yes "y" | bash deploy.sh`

---

## 8. 关键文件清单

### 新增文件

1. **`trendradar/podcast/segmenter.py`**
   - 核心分段逻辑
   - ~300 行代码

2. **`tests/test_segmenter.py`**
   - 单元测试
   - ~150 行代码

3. **`tests/test_podcast_segmentation_integration.py`**
   - 集成测试
   - ~100 行代码

### 修改文件

1. **`trendradar/podcast/downloader.py`**
   - 扩展 `DownloadResult` 类
   - 修改 `download()` 方法
   - ~20 行代码

2. **`trendradar/podcast/transcriber.py`**
   - 新增 `transcribe_segments()` 方法
   - 新增 `_merge_transcripts()` 方法
   - ~80 行代码

3. **`trendradar/podcast/processor.py`**
   - 初始化分段器
   - 调用分段逻辑
   - ~30 行代码

4. **`docker/Dockerfile`**
   - 添加 ffmpeg 依赖
   - ~2 行代码

5. **`config/config.yaml`**
   - 添加 segment 配置
   - ~10 行配置

6. **`docker/bootstrap.py`**
   - 添加 ffmpeg 检查
   - ~20 行代码

---

## 9. 风险与限制

### 9.1 技术风险

| 风险 | 影响 | 概率 | 缓解措施 |
|------|------|------|----------|
| ffmpeg 分段失败 | 功能不可用 | 低 | 降级到原始文件 |
| 分段转写部分失败 | 内容缺失 | 中 | 尽可能多保留，记录失败 |
| 合并后的文本质量下降 | AI分析不准确 | 低 | 保留重叠，AI会处理 |
| 镜像体积增加 | 部署变慢 | 低 | ffmpeg 仅 10MB |

### 9.2 功能限制

1. **只支持音频文件**：不支持视频文件的音频提取
2. **固定重叠策略**：无法根据内容动态调整重叠时间
3. **简单合并算法**：初期版本不做智能去重
4. **无断点续传**：分段失败后需要重新处理

### 9.3 性能考虑

| 操作 | 时间成本 | 备注 |
|------|----------|------|
| 检测时长 | 1-5秒 | ffprobe 快速检测 |
| 分段处理 | 10-30秒 | 3小时约需 30秒 |
| 批量转写 | 15-30分钟 | 3段并行，每段~10分钟 |
| 合并结果 | <1秒 | 简单字符串拼接 |
| **总计** | **15-30分钟** | 比不分段稍慢，但更稳定 |

---

## 10. 后续优化方向

### 短期（1-2周后）

1. **智能分段**
   - 根据静音检测自动分段
   - 避免在说话中间切断

2. **并行转写**
   - 同时转写多个分段
   - 使用多线程或 asyncio

3. **进度显示**
   - 显示分段转写进度
   - 估算剩余时间

### 长期（1个月后）

1. **分布式处理**
   - 分段分发到多个容器
   - 使用消息队列协调

2. **缓存机制**
   - 缓存分段结果
   - 避免重复转写

3. **智能去重**
   - NLP 相似度匹配
   - 精确去除重叠部分

---

## 附录 A: 配置完整示例

```yaml
podcast:
  enabled: true
  
  # ... 现有配置 ...
  
  # 音频下载配置
  download:
    temp_dir: "output/podcast/audio"
    max_file_size_mb: 1000
    cleanup_after_transcribe: true
  
  # 音频分段配置（新增）
  segment:
    enabled: true                     # 是否启用音频分段
    duration_threshold: 7200          # 时长阈值（秒）= 2小时
    segment_duration: 3600            # 每段时长（秒）= 1小时
    overlap: 5                        # 段间重叠（秒）= 5秒
    temp_dir: "output/podcast/audio/segments"  # 分段文件临时目录
  
  # ASR 转写配置
  asr:
    backend: "assemblyai"
    language: "auto"
    # ... 其他配置 ...
```

---

## 附录 B: 日志输出示例

### 成功场景

```
[Download] 开始下载: https://podcasts.example.com/long-episode.mp3
[Download] 下载完成: feed_id_hash123.mp3 (391.7MB)
[Download] 检测是否需要分段...
[Segmenter] 音频时长: 3.25 小时
[Segmenter] 需要分段: 4 段
[Segmenter] 分段 1/4: feed_id_hash123_part001.mp3 (0.0m - 60.1m)
[Segmenter] 分段 2/4: feed_id_hash123_part002.mp3 (59.9m - 120.1m)
[Segmenter] 分段 3/4: feed_id_hash123_part003.mp3 (119.9m - 180.1m)
[Segmenter] 分段 4/4: feed_id_hash123_part004.mp3 (179.9m - 195.0m)
[Download] 音频已分段为 4 段

[⏱️] 步骤 2/4: 开始 ASR 转写...
[ASR] 开始批量转写 4 个分段...

[ASR] ─────────────────────────────────────────
[ASR] 转写分段 1/4: feed_id_hash123_part001.mp3
[ASR] ─────────────────────────────────────────
[ASR-AssemblyAI] 上传音频文件...
[ASR-AssemblyAI] 创建转写任务...
[ASR-AssemblyAI] 转写完成: 15234 字符
[ASR] 分段 1 完成: 15234 字符

[ASR] ─────────────────────────────────────────
[ASR] 转写分段 2/4: feed_id_hash123_part002.mp3
[ASR] ─────────────────────────────────────────
[ASR-AssemblyAI] 转写完成: 14890 字符
[ASR] 分段 2 完成: 14890 字符

... (分段 3, 4 省略) ...

[ASR] ✅ 批量转写完成:
[ASR] - 成功转写: 4/4 个分段
[ASR] - 总时长: 3.25 小时
[ASR] - 总字符数: 62145

[Segmenter] 已清理 4 个分段文件
[⏱️] 转写完成，耗时: 1245.3秒
```

### 降级场景

```
[Download] 下载完成: feed_id_hash123.mp3 (391.7MB)
[Download] 检测是否需要分段...
[Segmenter] ⚠️  警告: ffmpeg 不可用，跳过分段
[Download] 使用原始文件继续处理

[ASR-AssemblyAI] 开始转写: feed_id_hash123.mp3 (391.7MB)
[ASR-AssemblyAI] 上传音频文件...
[ASR-AssemblyAI] 创建转写任务...
[ASR-AssemblyAI] 转写失败: audio too large
[Podcast] ❌ 转录最终失败: audio too large
```

---

**文档版本**: v1.0  
**最后更新**: 2026-02-11  
**作者**: Claude  
**状态**: 待实施
