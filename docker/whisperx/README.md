# WhisperX 本地转写服务

基于 [WhisperX](https://github.com/m-bain/whisperX) 的本地 GPU 转写服务，支持：
- 多语言自动识别（中文、英文等）
- **说话人分离 (Speaker Diarization)**
- 词级时间戳

## 系统要求

- NVIDIA GPU（推荐 8GB+ 显存）
- NVIDIA 驱动 >= 525
- Docker + NVIDIA Container Toolkit

### 安装 NVIDIA Container Toolkit

```bash
# Ubuntu/Debian
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | sudo gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
  sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
  sudo tee /etc/apt/sources.list.d/nvidia-container-toolkit.list
sudo apt-get update
sudo apt-get install -y nvidia-container-toolkit
sudo nvidia-ctk runtime configure --runtime=docker
sudo systemctl restart docker
```

## 快速开始

### 1. 配置 Hugging Face Token

编辑 `.env` 文件：

```bash
HF_TOKEN=your_huggingface_token
```

获取 Token: https://huggingface.co/settings/tokens

**重要**: 需要在 Hugging Face 接受以下模型的用户协议：
- https://huggingface.co/pyannote/segmentation
- https://huggingface.co/pyannote/speaker-diarization-3.1

### 2. 构建并启动服务

```bash
cd docker/whisperx

# 构建镜像（首次需要较长时间）
docker-compose build

# 启动服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 测试服务

```bash
# 健康检查
curl http://localhost:5000/health

# 服务信息
curl http://localhost:5000/info

# 转写音频（带说话人分离）
curl -X POST http://localhost:5000/transcribe \
  -F "file=@test.mp3" \
  -F "diarize=true"
```

## API 说明

### POST /transcribe

转写音频文件。

**参数:**
| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| file | File | (必填) | 音频文件 |
| language | string | auto | 语言代码 (zh/en/auto) |
| diarize | bool | true | 是否启用说话人分离 |
| min_speakers | int | null | 最少说话人数 |
| max_speakers | int | null | 最多说话人数 |
| output_format | string | both | 输出格式 (segments/text/both) |

**响应示例:**
```json
{
  "success": true,
  "language": "zh",
  "duration": 3600.5,
  "elapsed_seconds": 45.2,
  "segment_count": 156,
  "text": "[SPEAKER_00] 大家好，欢迎收听本期播客...\n\n[SPEAKER_01] 今天我们来聊聊...",
  "segments": [
    {
      "start": 0.0,
      "end": 5.2,
      "text": "大家好，欢迎收听本期播客",
      "speaker": "SPEAKER_00"
    }
  ]
}
```

### GET /health

健康检查。

### GET /info

服务信息（模型、GPU 等）。

## 配置选项

编辑 `.env` 文件：

| 变量 | 默认值 | 说明 |
|------|--------|------|
| HF_TOKEN | (必填) | Hugging Face Token |
| WHISPER_MODEL | large-v3 | Whisper 模型 (tiny/base/small/medium/large-v2/large-v3) |
| COMPUTE_TYPE | float16 | 计算精度 (float16/int8) |
| BATCH_SIZE | 16 | 批处理大小 |

### 模型选择建议

| 模型 | 显存需求 | 速度 | 准确率 |
|------|----------|------|--------|
| tiny | ~1GB | 最快 | 较低 |
| base | ~1GB | 很快 | 一般 |
| small | ~2GB | 快 | 较好 |
| medium | ~5GB | 中等 | 好 |
| large-v3 | ~10GB | 较慢 | 最佳 |

RTX 4060 (8GB) 推荐使用 `large-v3` + `float16`。

## 与 TrendRadar 集成

在 `config/config.yaml` 中配置：

```yaml
podcast:
  asr:
    backend: "local"  # 使用本地 WhisperX
    local:
      api_url: "http://localhost:5000"
      diarize: true
```

## 故障排除

### GPU 未检测到

```bash
# 检查 NVIDIA 驱动
nvidia-smi

# 检查 Docker GPU 支持
docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi
```

### 模型加载失败

```bash
# 查看详细日志
docker-compose logs whisperx

# 检查显存
nvidia-smi
```

### pyannote 模型下载失败

确保已在 Hugging Face 接受模型协议，并检查 Token 是否正确。
