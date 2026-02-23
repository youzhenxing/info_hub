# 硅基流动 API 使用说明

> **生成时间**: 2026-02-09
> **文档用途**: 整理硅基流动 API 的配置和使用方式

---

## 📋 基本信息

| 项目 | 值 |
|------|-----|
| **服务提供商** | 硅基流动 (SiliconFlow) |
| **API 端点** | `https://api.siliconflow.cn/v1` |
| **API Key** | `{{SILICONFLOW_API_KEY}}` |
| **使用的模型** | DeepSeek-R1-0528-Qwen3-8B |
| **协议** | OpenAI 兼容协议 |

---

## 🔧 配置方式

### 方式1: 配置文件 (推荐用于本地开发)

在 `config/system.yaml` 中配置：

```yaml
ai:
  # LiteLLM 模型格式: provider/model_name
  # 使用 openai/ 前缀 + api_base 可连接任意兼容 OpenAI 协议的服务
  model: "openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"

  # 硅基流动 API 端点
  api_base: "https://api.siliconflow.cn/v1"

  # API Key
  api_key: "{{SILICONFLOW_API_KEY}}"

  # 请求参数
  timeout: 120                        # 请求超时（秒）
  max_tokens: 8000                    # 最大生成 token 数
  temperature: 1.0                    # 采样温度
```

### 方式2: 环境变量 (推荐用于生产环境)

在 `.env` 文件或 Docker Compose 中设置：

```bash
# AI API Key
AI_API_KEY={{SILICONFLOW_API_KEY}}

# 模型名称（LiteLLM 格式）
AI_MODEL=openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B

# 硅基流动 API 端点
AI_API_BASE=https://api.siliconflow.cn/v1

# AI 功能开关
AI_ANALYSIS_ENABLED=true
```

---

## 💻 代码调用方式

### 通过 AIClient 类调用

```python
from trendradar.ai.client import AIClient

# 配置
config = {
    "MODEL": "openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    "API_KEY": "{{SILICONFLOW_API_KEY}}",
    "API_BASE": "https://api.siliconflow.cn/v1",
    "TEMPERATURE": 1.0,
    "MAX_TOKENS": 8000,
    "TIMEOUT": 120
}

# 创建客户端
client = AIClient(config)

# 调用 AI
messages = [
    {"role": "system", "content": "你是一个专业的分析助手"},
    {"role": "user", "content": "请分析以下内容..."}
]

response = client.chat(messages)
print(response)
```

### 配置加载优先级

```
1. 模块专用配置 (最高优先级)
   └─ 例如: investment.analysis.model

2. 全局 AI 配置
   └─ config/system.yaml → ai.model

3. 环境变量
   └─ AI_MODEL, AI_API_KEY, AI_API_BASE
```

---

## 🎯 使用模块

硅基流动 API 在以下模块中被使用：

| 模块 | 配置位置 | 说明 |
|------|----------|------|
| **播客模块** | `config.yaml → podcast.analysis.model` | 分析播客内容 |
| **投资模块** | `config.yaml → investment.analysis.model` | 分析投资资讯 |
| **社区模块** | `config.yaml → community.analysis.model` | 分析社区热点 |
| **微信模块** | `wechat/config.yaml → ai.model` | 分析公众号文章 |

---

## 🔑 技术细节

### LiteLLM 集成

项目使用 [LiteLLM](https://github.com/BerriAI/litellm) 作为统一接口：

- ✅ 支持 100+ AI 提供商
- ✅ 统一的 API 调用方式
- ✅ 自动重试机制
- ✅ Fallback 模型支持

### OpenAI 协议适配

使用 `openai/` 前缀强制 LiteLLM 使用 OpenAI 协议：

```python
# 模型名称格式
"openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
  ↓        ↓
前缀     实际模型名

# 传递给 LiteLLM 时会去掉 openai/ 前缀
# 并强制使用 OpenAI 协议调用硅基流动 API
```

### 代理禁用

在 `trendradar/ai/client.py` 中，AI API 调用时会自动禁用代理：

```python
# 禁用代理：AI API（api.siliconflow.cn）不需要代理，直连访问
proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]

for var in proxy_vars:
    if var in os.environ:
        old_env[var] = os.environ[var]
        del os.environ[var]
```

---

## 📊 当前配置汇总

### 模型信息

- **模型名称**: DeepSeek-R1-0528-Qwen3-8B
- **模型类型**: DeepSeek R1 系列推理模型
- **参数规模**: 8B (80亿参数)
- **特点**: 推理能力强，适合复杂分析任务

### 请求参数

| 参数 | 值 | 说明 |
|------|-----|------|
| `temperature` | 1.0 | 较高的创造性，适合分析任务 |
| `max_tokens` | 8000 | 全局配置；微信模块使用 4000 |
| `timeout` | 120秒 | 请求超时时间 |

---

## ⚠️ 安全注意事项

1. **API Key 保护**
   - ✅ 已将 API Key 存储在配置文件中
   - ✅ 确保配置文件不提交到公开仓库
   - ⚠️ `.env` 文件已添加到 `.gitignore`

2. **生产环境**
   - 推荐使用环境变量配置 API Key
   - 不要在代码中硬编码密钥

3. **费用监控**
   - 定期检查硅基流动控制台的用量
   - 关注 API 调用次数和 Token 消耗

---

## 🔗 相关链接

- **硅基流动官网**: https://siliconflow.cn
- **API 文档**: https://docs.siliconflow.cn
- **控制台**: https://cloud.siliconflow.cn
- **LiteLLM 文档**: https://docs.litellm.ai

---

## 📝 快速测试

### 测试 API 连接

```bash
# 使用 curl 测试
curl -X POST https://api.siliconflow.cn/v1/chat/completions \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer {{SILICONFLOW_API_KEY}}" \
  -d '{
    "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
    "messages": [
      {"role": "user", "content": "你好"}
    ]
  }'
```

### 在项目中测试

```bash
# 进入项目目录
cd /home/zxy/Documents/code/TrendRadar

# 使用 Python 测试 AI 客户端
python -c "
from trendradar.core.loader import load_config
from trendradar.ai.client import AIClient

config = load_config()
ai_config = config.get('ai', {})
client = AIClient(ai_config)

# 验证配置
is_valid, error = client.validate_config()
print(f'配置验证: {\"通过\" if is_valid else \"失败: \" + error}')

# 简单测试
if is_valid:
    response = client.chat([{'role': 'user', 'content': '你好，请简单介绍一下自己'}])
    print(f'AI 回复: {response[:100]}...')
"
```

---

## 📌 更新日志

| 日期 | 更新内容 |
|------|----------|
| 2026-02-09 | 初始版本，整理硅基流动 API 配置和使用方式 |

---

**文档维护**: 如有变更请及时更新本文档
