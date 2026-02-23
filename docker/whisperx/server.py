# coding=utf-8
"""
WhisperX API Server

提供 RESTful API 接口进行音频转写和说话人分离
支持中英文自动识别，输出带说话人标签的转写文本

API 端点:
- POST /transcribe - 上传音频文件进行转写
- GET /health - 健康检查
- GET /info - 服务信息
"""

import os
import tempfile
import time
from pathlib import Path
from typing import Optional, List, Dict, Any
import logging

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.responses import JSONResponse
import uvicorn

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("whisperx-server")

# 环境变量配置
HF_TOKEN = os.environ.get("HF_TOKEN", "")
WHISPER_MODEL = os.environ.get("WHISPER_MODEL", "large-v3")
COMPUTE_TYPE = os.environ.get("COMPUTE_TYPE", "float16")
DEVICE = os.environ.get("DEVICE", "cuda")
BATCH_SIZE = int(os.environ.get("BATCH_SIZE", "16"))

# 全局模型实例（延迟加载）
_whisper_model = None
_align_models = {}
_diarize_model = None

app = FastAPI(
    title="WhisperX API Server",
    description="音频转写服务，支持说话人分离",
    version="1.0.0"
)


def get_whisper_model():
    """延迟加载 Whisper 模型"""
    global _whisper_model
    if _whisper_model is None:
        import whisperx
        logger.info(f"加载 Whisper 模型: {WHISPER_MODEL} (device={DEVICE}, compute_type={COMPUTE_TYPE})")
        _whisper_model = whisperx.load_model(
            WHISPER_MODEL,
            device=DEVICE,
            compute_type=COMPUTE_TYPE
        )
        logger.info("Whisper 模型加载完成")
    return _whisper_model


def get_align_model(language_code: str):
    """延迟加载对齐模型"""
    global _align_models
    if language_code not in _align_models:
        import whisperx
        logger.info(f"加载对齐模型: {language_code}")
        model, metadata = whisperx.load_align_model(
            language_code=language_code,
            device=DEVICE
        )
        _align_models[language_code] = (model, metadata)
        logger.info(f"对齐模型加载完成: {language_code}")
    return _align_models[language_code]


def get_diarize_model():
    """延迟加载说话人分离模型"""
    global _diarize_model
    if _diarize_model is None:
        if not HF_TOKEN:
            raise HTTPException(
                status_code=500,
                detail="未配置 HF_TOKEN，无法使用说话人分离功能"
            )
        from pyannote.audio import Pipeline
        logger.info("加载说话人分离模型...")
        _diarize_model = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-3.1",
            use_auth_token=HF_TOKEN
        )
        import torch
        if DEVICE == "cuda" and torch.cuda.is_available():
            _diarize_model.to(torch.device("cuda"))
        logger.info("说话人分离模型加载完成")
    return _diarize_model


def format_transcript_with_speakers(segments: List[Dict]) -> str:
    """
    将带说话人的 segments 格式化为可读文本
    
    输出格式:
    [SPEAKER_00] 这是第一个人说的话...
    [SPEAKER_01] 这是第二个人说的话...
    """
    lines = []
    current_speaker = None
    current_text = []
    
    for seg in segments:
        speaker = seg.get("speaker", "UNKNOWN")
        text = seg.get("text", "").strip()
        
        if not text:
            continue
            
        if speaker != current_speaker:
            # 输出之前的说话人内容
            if current_speaker is not None and current_text:
                lines.append(f"[{current_speaker}] {''.join(current_text)}")
            current_speaker = speaker
            current_text = [text]
        else:
            current_text.append(text)
    
    # 输出最后一个说话人的内容
    if current_speaker is not None and current_text:
        lines.append(f"[{current_speaker}] {''.join(current_text)}")
    
    return "\n\n".join(lines)


@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "model": WHISPER_MODEL}


@app.get("/info")
async def server_info():
    """服务信息"""
    import torch
    return {
        "whisper_model": WHISPER_MODEL,
        "compute_type": COMPUTE_TYPE,
        "device": DEVICE,
        "cuda_available": torch.cuda.is_available(),
        "gpu_name": torch.cuda.get_device_name(0) if torch.cuda.is_available() else None,
        "hf_token_configured": bool(HF_TOKEN),
    }


@app.post("/transcribe")
async def transcribe_audio(
    file: UploadFile = File(..., description="音频文件"),
    language: Optional[str] = Form(None, description="语言代码 (zh/en/auto)，留空自动检测"),
    diarize: bool = Form(True, description="是否启用说话人分离"),
    min_speakers: Optional[int] = Form(None, description="最少说话人数"),
    max_speakers: Optional[int] = Form(None, description="最多说话人数"),
    output_format: str = Form("both", description="输出格式: segments/text/both"),
):
    """
    转写音频文件
    
    支持格式: mp3, wav, m4a, mp4, ogg, flac 等
    
    返回:
    - segments: 带时间戳和说话人的分段列表
    - text: 格式化的纯文本（带说话人标签）
    - language: 检测到的语言
    - duration: 音频时长（秒）
    """
    import whisperx
    
    start_time = time.time()
    
    # 保存上传的文件到临时目录
    suffix = Path(file.filename).suffix if file.filename else ".mp3"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name
    
    try:
        logger.info(f"开始转写: {file.filename} ({len(content) / 1024 / 1024:.1f} MB)")
        
        # 1. 加载音频
        audio = whisperx.load_audio(tmp_path)
        duration = len(audio) / 16000  # 采样率 16kHz
        logger.info(f"音频时长: {duration:.1f} 秒")
        
        # 2. 转写
        model = get_whisper_model()
        result = model.transcribe(audio, batch_size=BATCH_SIZE, language=language)
        detected_language = result.get("language", "en")
        logger.info(f"检测语言: {detected_language}")
        
        # 3. 对齐（获取词级时间戳）
        try:
            align_model, metadata = get_align_model(detected_language)
            result = whisperx.align(
                result["segments"],
                align_model,
                metadata,
                audio,
                DEVICE,
                return_char_alignments=False
            )
        except Exception as e:
            logger.warning(f"对齐失败 (语言: {detected_language}): {e}")
        
        # 4. 说话人分离
        if diarize:
            try:
                diarize_model = get_diarize_model()
                diarize_segments = diarize_model(tmp_path)
                result = whisperx.assign_word_speakers(diarize_segments, result)
                logger.info("说话人分离完成")
            except Exception as e:
                logger.warning(f"说话人分离失败: {e}")
        
        # 5. 构建响应
        segments = result.get("segments", [])
        formatted_text = format_transcript_with_speakers(segments)
        
        elapsed = time.time() - start_time
        logger.info(f"转写完成: {len(segments)} 段, 耗时 {elapsed:.1f} 秒")
        
        response = {
            "success": True,
            "language": detected_language,
            "duration": round(duration, 2),
            "elapsed_seconds": round(elapsed, 2),
            "segment_count": len(segments),
        }
        
        if output_format in ("segments", "both"):
            # 简化 segments，移除不必要的字段
            simplified_segments = []
            for seg in segments:
                simplified_segments.append({
                    "start": round(seg.get("start", 0), 2),
                    "end": round(seg.get("end", 0), 2),
                    "text": seg.get("text", "").strip(),
                    "speaker": seg.get("speaker", "UNKNOWN"),
                })
            response["segments"] = simplified_segments
        
        if output_format in ("text", "both"):
            response["text"] = formatted_text
        
        return JSONResponse(content=response)
        
    except Exception as e:
        logger.error(f"转写失败: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
    
    finally:
        # 清理临时文件
        try:
            os.unlink(tmp_path)
        except:
            pass


@app.on_event("startup")
async def startup_event():
    """启动时预加载模型（可选）"""
    logger.info("=" * 50)
    logger.info("WhisperX API Server 启动中...")
    logger.info(f"模型: {WHISPER_MODEL}")
    logger.info(f"设备: {DEVICE}")
    logger.info(f"计算类型: {COMPUTE_TYPE}")
    logger.info(f"HF Token: {'已配置' if HF_TOKEN else '未配置'}")
    logger.info("=" * 50)
    
    # 预加载 Whisper 模型（启动时加载，避免首次请求延迟）
    try:
        get_whisper_model()
    except Exception as e:
        logger.error(f"预加载模型失败: {e}")


if __name__ == "__main__":
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=5000,
        workers=1,  # GPU 模型不支持多进程
        log_level="info"
    )
