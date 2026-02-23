# WhisperX GPU 服务
# 基于 Python slim 镜像 + pip 安装 PyTorch CUDA
# 支持说话人分离 (Speaker Diarization)
#
# 构建: docker compose build
# 运行: docker compose up -d

FROM python:3.10-slim

# 构建参数
ARG HF_TOKEN
ARG WHISPER_MODEL=large-v3
ARG COMPUTE_TYPE=float16

# 环境变量
ENV DEBIAN_FRONTEND=noninteractive
ENV HF_TOKEN=${HF_TOKEN}
ENV WHISPER_MODEL=${WHISPER_MODEL}
ENV COMPUTE_TYPE=${COMPUTE_TYPE}
ENV PYTHONUNBUFFERED=1
ENV PIP_NO_CACHE_DIR=1

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# 设置工作目录
WORKDIR /app

# 安装 PyTorch with CUDA (使用清华镜像加速)
RUN pip install --upgrade pip && \
    pip install torch==2.0.1 torchaudio==2.0.2 --index-url https://download.pytorch.org/whl/cu118 || \
    pip install torch==2.0.1 torchaudio==2.0.2 --index-url https://mirror.sjtu.edu.cn/pytorch-wheels/cu118

# 复制并安装其他依赖
COPY requirements.txt .
RUN pip install -r requirements.txt

# 安装 WhisperX
RUN pip install git+https://github.com/m-bain/whisperx.git

# 复制应用代码
COPY server.py .

# 暴露端口
EXPOSE 5000

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=3 \
    CMD curl -f http://localhost:5000/health || exit 1

# 启动服务
CMD ["python", "server.py"]
