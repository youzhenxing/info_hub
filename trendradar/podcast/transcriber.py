# coding=utf-8
"""
播客 ASR 转写服务

支持多种转写后端:
1. siliconflow (默认): 硅基流动 SenseVoice API（快速，无说话人分离）
2. assemblyai: AssemblyAI API（支持说话人分离，推荐）
3. local: 本地 WhisperX 服务（需要 GPU）

说话人分离输出格式:
[SPEAKER_00] 这是第一个人说的话...
[SPEAKER_01] 这是第二个人说的话...
"""

import os
import time
from pathlib import Path
from typing import Tuple, Optional, List
from dataclasses import dataclass

import requests


@dataclass
class TranscribeResult:
    """转写结果"""
    success: bool
    transcript: str = ""
    duration_seconds: float = 0.0
    language: str = ""
    speaker_count: int = 0  # 说话人数量
    error: Optional[str] = None


class ASRTranscriber:
    """
    ASR 转写服务

    支持多种后端:
    - siliconflow: 硅基流动 SenseVoice API（快速，无说话人分离）
    - assemblyai: AssemblyAI API（支持说话人分离）
    - local: 本地 WhisperX 服务（需要 GPU）
    """

    # 默认配置 - 硅基流动
    DEFAULT_API_BASE = "https://api.siliconflow.cn/v1/audio/transcriptions"
    DEFAULT_MODEL = "FunAudioLLM/SenseVoiceSmall"
    DEFAULT_LANGUAGE = "auto"

    # AssemblyAI 配置
    ASSEMBLYAI_API_BASE = "https://api.assemblyai.com/v2"

    # 本地 WhisperX 配置
    DEFAULT_LOCAL_API_URL = "http://localhost:5000"

    # 支持的语言
    SUPPORTED_LANGUAGES = ["zh", "en", "auto"]

    def __init__(
        self,
        # 通用配置
        backend: str = "siliconflow",  # siliconflow | assemblyai | local
        language: str = DEFAULT_LANGUAGE,
        timeout: int = 3600,  # 超时时间（秒），支持超长播客（5小时约需30分钟转写）
        # 硅基流动配置
        api_base: str = DEFAULT_API_BASE,
        api_key: str = "",
        model: str = DEFAULT_MODEL,
        # AssemblyAI 配置
        assemblyai_api_key: str = "",
        speaker_labels: bool = True,  # 是否启用说话人分离
        # 本地 WhisperX 配置
        local_api_url: str = DEFAULT_LOCAL_API_URL,
        diarize: bool = True,
        min_speakers: Optional[int] = None,
        max_speakers: Optional[int] = None,
    ):
        """
        初始化转写服务

        Args:
            backend: 转写后端 (siliconflow/assemblyai/local)
            language: 语言（zh/en/auto）
            timeout: 请求超时时间（秒）
            api_base: 硅基流动 API 端点
            api_key: 硅基流动 API Key
            model: 硅基流动模型名称
            assemblyai_api_key: AssemblyAI API Key
            speaker_labels: 是否启用说话人分离（AssemblyAI）
            local_api_url: 本地 WhisperX API 地址
            diarize: 是否启用说话人分离（本地模式）
            min_speakers: 最少说话人数
            max_speakers: 最多说话人数
        """
        self.backend = backend.lower()
        self.language = language if language in self.SUPPORTED_LANGUAGES else self.DEFAULT_LANGUAGE
        self.timeout = timeout

        # 硅基流动配置
        self.api_base = api_base or self.DEFAULT_API_BASE
        self.api_key = api_key or os.environ.get("SILICONFLOW_API_KEY", "")
        self.model = model or self.DEFAULT_MODEL

        # AssemblyAI 配置
        self.assemblyai_api_key = assemblyai_api_key or os.environ.get("ASSEMBLYAI_API_KEY", "")
        self.speaker_labels = speaker_labels

        # 本地 WhisperX 配置
        self.local_api_url = local_api_url or self.DEFAULT_LOCAL_API_URL
        self.diarize = diarize
        self.min_speakers = min_speakers
        self.max_speakers = max_speakers

        # 验证配置
        if self.backend == "siliconflow" and not self.api_key:
            print("[ASR] 警告: 硅基流动模式未设置 API Key")
        elif self.backend == "assemblyai":
            if not self.assemblyai_api_key:
                print("[ASR] 警告: AssemblyAI 模式未设置 API Key")
            else:
                print(f"[ASR] 使用 AssemblyAI，说话人分离: {'启用' if self.speaker_labels else '禁用'}")
        elif self.backend == "local":
            print(f"[ASR] 使用本地 WhisperX: {self.local_api_url}")

    def transcribe(self, audio_path: str) -> TranscribeResult:
        """
        转写音频文件

        Args:
            audio_path: 音频文件路径

        Returns:
            TranscribeResult 对象
        """
        if self.backend == "assemblyai":
            return self._transcribe_assemblyai(audio_path)
        elif self.backend == "local":
            return self._transcribe_local(audio_path)
        else:
            return self._transcribe_siliconflow(audio_path)

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
        failed_count = 0

        for i, segment_file in enumerate(segment_files):
            print(f"\n[ASR] ─────────────────────────────────────────")
            print(f"[ASR] 转写分段 {i+1}/{len(segment_files)}: {Path(segment_file).name}")
            print(f"[ASR] ─────────────────────────────────────────")

            # 转写单个分段
            result = self.transcribe(segment_file)

            if not result.success:
                # 部分分段失败，继续处理其他分段
                print(f"[ASR] ⚠️  分段 {i+1} 转写失败: {result.error}")
                failed_count += 1
                continue

            # 收集转写结果
            all_transcripts.append(result.transcript)
            total_duration += result.duration_seconds
            if result.language:
                all_languages.add(result.language)
            if result.speaker_count > 0:
                all_speakers.add(result.speaker_count)

            print(f"[ASR] 分段 {i+1} 完成: {len(result.transcript)} 字符")

        # 检查是否至少有一个分段成功
        if not all_transcripts:
            return TranscribeResult(
                success=False,
                error=f"所有分段转写均失败 ({failed_count}/{len(segment_files)})"
            )

        # 简单拼接，保留所有内容（包括重叠部分）
        # 让 AI 处理拼接和去重
        merged_transcript = self._merge_transcripts(all_transcripts)

        print(f"\n[ASR] ✅ 批量转写完成:")
        print(f"[ASR] - 成功转写: {len(all_transcripts)}/{len(segment_files)} 个分段")
        print(f"[ASR] - 失败分段: {failed_count} 个")
        print(f"[ASR] - 总时长: {total_duration/3600:.2f} 小时")
        print(f"[ASR] - 总字符数: {len(merged_transcript)}")
        if all_languages:
            print(f"[ASR] - 检测语言: {', '.join(all_languages)}")
        if all_speakers:
            print(f"[ASR] - 说话人数: {len(all_speakers)}")

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

    def _transcribe_assemblyai(self, audio_path: str) -> TranscribeResult:
        """使用 AssemblyAI API 转写（支持说话人分离）"""
        if not self.assemblyai_api_key:
            return TranscribeResult(
                success=False,
                error="未设置 AssemblyAI API Key"
            )

        path = Path(audio_path)
        if not path.exists():
            return TranscribeResult(
                success=False,
                error=f"音频文件不存在: {audio_path}"
            )

        file_size_mb = path.stat().st_size / (1024 * 1024)
        print(f"[ASR-AssemblyAI] 开始转写: {path.name} ({file_size_mb:.1f}MB)")
        print(f"[ASR-AssemblyAI] 说话人分离: {'启用' if self.speaker_labels else '禁用'}")

        headers = {
            "Authorization": self.assemblyai_api_key,
            "Content-Type": "application/json"
        }

        try:
            # Step 1: 上传音频文件
            print("[ASR-AssemblyAI] 上传音频文件...")
            upload_url = f"{self.ASSEMBLYAI_API_BASE}/upload"
            
            with open(audio_path, "rb") as f:
                upload_response = requests.post(
                    upload_url,
                    headers={"Authorization": self.assemblyai_api_key},
                    data=f,
                    timeout=self.timeout
                )
            
            if upload_response.status_code != 200:
                return TranscribeResult(
                    success=False,
                    error=f"上传失败 ({upload_response.status_code}): {upload_response.text}"
                )
            
            audio_url = upload_response.json().get("upload_url")
            print(f"[ASR-AssemblyAI] 上传完成")

            # Step 2: 创建转写任务
            print("[ASR-AssemblyAI] 创建转写任务...")
            transcript_request = {
                "audio_url": audio_url,
                "speaker_labels": self.speaker_labels,
            }
            
            # 语言设置
            if self.language == "zh":
                transcript_request["language_code"] = "zh"
            elif self.language == "en":
                transcript_request["language_code"] = "en"
            else:
                transcript_request["language_detection"] = True

            transcript_response = requests.post(
                f"{self.ASSEMBLYAI_API_BASE}/transcript",
                headers=headers,
                json=transcript_request,
                timeout=60
            )

            if transcript_response.status_code != 200:
                return TranscribeResult(
                    success=False,
                    error=f"创建任务失败 ({transcript_response.status_code}): {transcript_response.text}"
                )

            transcript_id = transcript_response.json()["id"]
            print(f"[ASR-AssemblyAI] 任务已创建: {transcript_id}")

            # Step 3: 轮询等待完成
            print("[ASR-AssemblyAI] 等待转写完成...")
            polling_url = f"{self.ASSEMBLYAI_API_BASE}/transcript/{transcript_id}"
            
            start_time = time.time()
            while True:
                poll_response = requests.get(polling_url, headers=headers, timeout=30)
                result = poll_response.json()
                status = result.get("status")

                if status == "completed":
                    break
                elif status == "error":
                    return TranscribeResult(
                        success=False,
                        error=f"转写失败: {result.get('error', '未知错误')}"
                    )
                
                # 检查超时
                elapsed = time.time() - start_time
                if elapsed > self.timeout:
                    return TranscribeResult(
                        success=False,
                        error=f"转写超时 ({self.timeout}s)"
                    )
                
                # 等待后重试
                time.sleep(5)
                print(f"[ASR-AssemblyAI] 状态: {status}, 已等待 {int(elapsed)}s...")

            # Step 4: 处理结果
            duration = result.get("audio_duration", 0)
            language = result.get("language_code", "")
            
            # 格式化带说话人标签的文本
            if self.speaker_labels and "utterances" in result:
                transcript = self._format_utterances(result["utterances"])
                speakers = set(u.get("speaker") for u in result["utterances"])
                speaker_count = len(speakers)
            else:
                transcript = result.get("text", "")
                speaker_count = 0

            print(f"[ASR-AssemblyAI] 转写完成: {len(transcript)} 字符")
            print(f"[ASR-AssemblyAI] 检测语言: {language}")
            if speaker_count > 0:
                print(f"[ASR-AssemblyAI] 识别说话人: {speaker_count} 人")

            return TranscribeResult(
                success=True,
                transcript=transcript,
                duration_seconds=duration,
                language=language,
                speaker_count=speaker_count,
            )

        except requests.Timeout:
            return TranscribeResult(
                success=False,
                error=f"请求超时 ({self.timeout}s)"
            )
        except requests.RequestException as e:
            return TranscribeResult(
                success=False,
                error=f"网络请求失败: {e}"
            )
        except Exception as e:
            return TranscribeResult(
                success=False,
                error=f"转写失败: {e}"
            )

    def _format_utterances(self, utterances: list) -> str:
        """
        将 AssemblyAI utterances 格式化为带说话人标签的文本
        
        输出格式:
        [SPEAKER_A] 这是第一个人说的话...
        [SPEAKER_B] 这是第二个人说的话...
        """
        lines = []
        for utterance in utterances:
            speaker = utterance.get("speaker", "UNKNOWN")
            text = utterance.get("text", "").strip()
            if text:
                # 将 AssemblyAI 的 speaker (A, B, C...) 转换为标准格式
                speaker_label = f"SPEAKER_{speaker}" if len(speaker) == 1 else speaker
                lines.append(f"[{speaker_label}] {text}")
        
        return "\n\n".join(lines)

    def _transcribe_local(self, audio_path: str) -> TranscribeResult:
        """使用本地 WhisperX 服务转写"""
        path = Path(audio_path)
        if not path.exists():
            return TranscribeResult(
                success=False,
                error=f"音频文件不存在: {audio_path}"
            )

        file_size_mb = path.stat().st_size / (1024 * 1024)
        print(f"[ASR-Local] 开始转写: {path.name} ({file_size_mb:.1f}MB)")
        print(f"[ASR-Local] 说话人分离: {'启用' if self.diarize else '禁用'}")

        try:
            url = f"{self.local_api_url.rstrip('/')}/transcribe"
            
            with open(audio_path, "rb") as audio_file:
                files = {
                    "file": (path.name, audio_file, self._get_mime_type(path.suffix))
                }
                data = {
                    "diarize": str(self.diarize).lower(),
                    "output_format": "both",
                }
                
                if self.language != "auto":
                    data["language"] = self.language
                
                if self.min_speakers is not None:
                    data["min_speakers"] = str(self.min_speakers)
                if self.max_speakers is not None:
                    data["max_speakers"] = str(self.max_speakers)

                response = requests.post(
                    url,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )

            if response.status_code != 200:
                error_msg = self._parse_error(response)
                return TranscribeResult(
                    success=False,
                    error=f"本地 API 错误 ({response.status_code}): {error_msg}"
                )

            result = response.json()
            
            if not result.get("success", False):
                return TranscribeResult(
                    success=False,
                    error=result.get("detail", "转写失败")
                )

            transcript = result.get("text", "")
            duration = result.get("duration", 0.0)
            language = result.get("language", "")
            
            speaker_count = 0
            if self.diarize and "segments" in result:
                speakers = set(seg.get("speaker", "") for seg in result["segments"])
                speaker_count = len([s for s in speakers if s and s != "UNKNOWN"])

            if not transcript:
                return TranscribeResult(
                    success=False,
                    error="转写结果为空"
                )

            print(f"[ASR-Local] 转写完成: {len(transcript)} 字符")
            if speaker_count > 0:
                print(f"[ASR-Local] 识别说话人: {speaker_count} 人")

            return TranscribeResult(
                success=True,
                transcript=transcript,
                duration_seconds=duration,
                language=language,
                speaker_count=speaker_count,
            )

        except requests.ConnectionError:
            return TranscribeResult(
                success=False,
                error=f"无法连接到本地 WhisperX 服务: {self.local_api_url}"
            )
        except Exception as e:
            return TranscribeResult(
                success=False,
                error=f"转写失败: {e}"
            )

    def _transcribe_siliconflow(self, audio_path: str) -> TranscribeResult:
        """使用硅基流动 API 转写（无说话人分离）"""
        if not self.api_key:
            return TranscribeResult(
                success=False,
                error="未设置硅基流动 API Key，无法进行转写"
            )

        path = Path(audio_path)
        if not path.exists():
            return TranscribeResult(
                success=False,
                error=f"音频文件不存在: {audio_path}"
            )

        file_size_mb = path.stat().st_size / (1024 * 1024)
        print(f"[ASR-SiliconFlow] 开始转写: {path.name} ({file_size_mb:.1f}MB)")
        print(f"[ASR-SiliconFlow] 模型: {self.model}")

        try:
            with open(audio_path, "rb") as audio_file:
                files = {
                    "file": (path.name, audio_file, self._get_mime_type(path.suffix))
                }
                data = {
                    "model": self.model,
                }

                if self.language != "auto":
                    data["language"] = self.language

                headers = {
                    "Authorization": f"Bearer {self.api_key}"
                }

                response = requests.post(
                    self.api_base,
                    headers=headers,
                    files=files,
                    data=data,
                    timeout=self.timeout,
                )

                if response.status_code != 200:
                    error_msg = self._parse_error(response)
                    return TranscribeResult(
                        success=False,
                        error=f"API 错误 ({response.status_code}): {error_msg}"
                    )

                result = response.json()
                transcript = result.get("text", "")
                duration = result.get("duration", 0.0)
                language = result.get("language", self.language if self.language != "auto" else "")

                if not transcript:
                    return TranscribeResult(
                        success=False,
                        error="转写结果为空"
                    )

                transcript = self._clean_transcript(transcript)

                print(f"[ASR-SiliconFlow] 转写完成: {len(transcript)} 字符")
                if duration > 0:
                    print(f"[ASR-SiliconFlow] 音频时长: {duration:.1f} 秒")
                if language:
                    print(f"[ASR-SiliconFlow] 检测语言: {language}")

                return TranscribeResult(
                    success=True,
                    transcript=transcript,
                    duration_seconds=duration,
                    language=language,
                )

        except requests.Timeout:
            return TranscribeResult(
                success=False,
                error=f"请求超时 ({self.timeout}s)"
            )
        except Exception as e:
            return TranscribeResult(
                success=False,
                error=f"转写失败: {e}"
            )

    def _get_mime_type(self, suffix: str) -> str:
        """根据文件扩展名获取 MIME 类型"""
        mime_types = {
            ".mp3": "audio/mpeg",
            ".m4a": "audio/x-m4a",
            ".mp4": "audio/mp4",
            ".aac": "audio/aac",
            ".ogg": "audio/ogg",
            ".wav": "audio/wav",
            ".flac": "audio/flac",
        }
        return mime_types.get(suffix.lower(), "audio/mpeg")

    def _parse_error(self, response: requests.Response) -> str:
        """解析 API 错误响应"""
        try:
            error_data = response.json()
            if "error" in error_data:
                error = error_data["error"]
                if isinstance(error, dict):
                    return error.get("message", str(error))
                return str(error)
            if "message" in error_data:
                return error_data["message"]
            if "detail" in error_data:
                return error_data["detail"]
            return str(error_data)
        except Exception:
            return response.text[:200] if response.text else "未知错误"

    def _clean_transcript(self, text: str) -> str:
        """清理转写文本"""
        if not text:
            return ""
        import re
        text = re.sub(r'\s+', ' ', text)
        text = text.strip()
        return text

    @classmethod
    def from_config(cls, config: dict) -> "ASRTranscriber":
        """
        从配置字典创建转写器

        Args:
            config: 配置字典（来自 config.yaml 的 podcast.asr 段）

        Returns:
            ASRTranscriber 实例
        """
        backend = config.get("backend", "siliconflow")
        local_config = config.get("local", {})
        assemblyai_config = config.get("assemblyai", {})
        
        return cls(
            backend=backend,
            language=config.get("language", cls.DEFAULT_LANGUAGE),
            # 硅基流动配置
            api_base=config.get("api_base", cls.DEFAULT_API_BASE),
            api_key=config.get("api_key", ""),
            model=config.get("model", cls.DEFAULT_MODEL),
            # AssemblyAI 配置
            assemblyai_api_key=assemblyai_config.get("api_key", ""),
            speaker_labels=assemblyai_config.get("speaker_labels", True),
            # 本地配置
            local_api_url=local_config.get("api_url", cls.DEFAULT_LOCAL_API_URL),
            diarize=local_config.get("diarize", True),
            min_speakers=local_config.get("min_speakers"),
            max_speakers=local_config.get("max_speakers"),
        )


# 便捷函数
def transcribe_audio(
    audio_path: str,
    backend: str = "siliconflow",
    api_key: str = "",
    assemblyai_api_key: str = "",
    speaker_labels: bool = True,
    language: str = "auto",
) -> Tuple[str, Optional[str]]:
    """
    转写音频文件的便捷函数

    Args:
        audio_path: 音频文件路径
        backend: 转写后端 (siliconflow/assemblyai/local)
        api_key: 硅基流动 API Key
        assemblyai_api_key: AssemblyAI API Key
        speaker_labels: 是否启用说话人分离
        language: 语言

    Returns:
        (转写文本, 错误信息) 元组
    """
    transcriber = ASRTranscriber(
        backend=backend,
        api_key=api_key,
        assemblyai_api_key=assemblyai_api_key,
        speaker_labels=speaker_labels,
        language=language,
    )
    result = transcriber.transcribe(audio_path)

    if result.success:
        return result.transcript, None
    else:
        return "", result.error
