# AI 配置统一架构说明

## 概述

TrendRadar 项目已从单一全局 AI 配置迁移到**模块专用配置统一架构**，各模块拥有独立的 AI 配置，提供更高的灵活性和可维护性。

## 架构设计

### 配置优先级（从高到低）

```
1. 模块专用配置（推荐）
   └─ config.yaml → investment.analysis.model
   └─ config.yaml → podcast.analysis.model
   └─ config.yaml → community.analysis.model
   └─ config.yaml → wechat.analysis.model

2. 全局 AI 配置（fallback）
   └─ config.yaml → ai.model
   └─ config.yaml → ai.api_key
   └─ config.yaml → ai.api_base

3. 环境变量（仅 Docker 部署）
   └─ AI_MODEL, AI_API_KEY, AI_API_BASE
   └─ 仅在 docker-compose.yml 中使用
```

### 模块配置映射

| 模块 | 配置路径 | 当前模型 |
|------|----------|----------|
| 投资模块 | `investment.analysis.model` | `openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` |
| 播客模块 | `podcast.analysis.model` | `openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` |
| 社区模块 | `community.analysis.model` | `openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` |
| 公众号模块 | 环境变量 `AI_MODEL` | `openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B` |

**统一架构**：所有模块都使用 DeepSeek-R1 推理模型，确保输出质量一致。

**注意**：公众号模块通过环境变量 `AI_MODEL` 覆盖 config.yaml 的 `ai.model` 配置（与其他模块不同）。

## 本地开发

### 配置加载顺序

`trendradar/core/loader.py` 按以下顺序加载环境变量：

```python
1. agents/.env      # 最高优先级（已废弃 AI 配置）
2. docker/.env      # Docker 配置文件
3. .env             # 项目根目录（如存在）
```

### 推荐做法

✅ **正确**：在 `config.yaml` 中修改模块专用配置

```yaml
investment:
  analysis:
    model: openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B
    api_key: sk-xxxxx
    api_base: https://api.siliconflow.cn/v1
```

❌ **错误**：修改 `agents/.env` 中的 AI 配置（不会生效）

## Docker 部署

### 环境变量覆盖

Docker Compose 使用 `.env` 文件中的环境变量覆盖 `config.yaml` 的默认配置：

```yaml
# docker-compose.yml
environment:
  - AI_MODEL=${AI_MODEL}
  - AI_API_KEY=${AI_API_KEY}
  - AI_API_BASE=${AI_API_BASE}
```

### 修改 Docker AI 配置

编辑 `docker/.env` 或 `agents/.env`：

```bash
AI_MODEL=openai/deepseek-ai/DeepSeek-V3
AI_API_KEY=sk-xxxxx
AI_API_BASE=https://api.siliconflow.cn/v1
```

## 历史变更

### 2026-02-02：统一架构迁移

**问题**：
- 混合使用 GLM 和 DeepSeek
- `.env` 文件优先级不明确
- 配置分散，难以维护

**解决方案**：
1. 各模块使用专用配置（优先级高于全局）
2. 清理 `.env` 文件中的 AI 配置，标记为已废弃
3. 统一使用 SiliconFlow DeepSeek 模型
4. 添加清晰的配置文档说明

**变更文件**：
- `config/config.yaml`：各模块专用配置
- `agents/.env`：添加废弃警告
- `docker/.env`：添加废弃警告
- `agents/.env.trendradar`：删除过时备份

## 故障排查

### 问题：模块使用了错误的 AI 模型

**检查步骤**：

1. 确认模块专用配置：
   ```bash
   grep -A 5 "investment:" config/config.yaml | grep model
   ```

2. 检查全局配置：
   ```bash
   grep -A 3 "^ai:" config/config.yaml
   ```

3. 验证环境变量（仅 Docker）：
   ```bash
   docker exec trendradar env | grep AI_MODEL
   ```

### 问题：本地开发和 Docker 行为不一致

**原因**：`agents/.env` 的 AI 配置已被废弃，本地开发不受影响

**解决**：
- 本地开发：修改 `config.yaml`
- Docker 部署：修改 `docker/.env`

## 最佳实践

1. **新模块开发**：使用模块专用配置，不依赖全局配置
2. **切换 AI 模型**：优先修改模块配置，而非全局配置
3. **敏感信息**：API Key 使用环境变量，不提交到代码仓库
4. **文档同步**：修改配置后更新相关文档

## 相关文件

- `trendradar/core/loader.py`：环境变量加载逻辑
- `config/config.yaml`：主配置文件
- `agents/.env`：本地开发配置（AI 配置已废弃）
- `docker/.env`：Docker 部署配置（AI 配置已废弃）
- `docker-compose.yml`：容器编排配置

## 技术细节

### LiteLLM 模型格式

使用 `openai/` 前缀强制 LiteLLM 使用 OpenAI 协议：

```python
# SiliconFlow DeepSeek（推荐）
model = "openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
api_base = "https://api.siliconflow.cn/v1"

# DeepSeek 官方 API
model = "openai/deepseek-chat"
api_base = "https://api.deepseek.com/v1"

# GLM（已废弃）
model = "zhipuai/glm-4.6"
api_base = "https://open.bigmodel.cn/api/paas/v4"
```

### 配置读取代码示例

```python
from trendradar.core.config import config

# 1. 读取模块专用配置（投资模块）
investment_config = config.get("investment", {})
analysis_config = investment_config.get("analysis", {})
model = analysis_config.get("model", "openai/gpt-4o-mini")  # fallback

# 2. 读取全局配置
ai_config = config.get("ai", {})
global_model = ai_config.get("model")

# 3. 读取环境变量（仅 Docker）
import os
env_model = os.getenv("AI_MODEL")
```
