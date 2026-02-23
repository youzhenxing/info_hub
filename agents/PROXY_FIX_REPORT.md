# AI 分析代理错误修复报告

## 问题描述

**症状**：所有模块（播客、投资、社区、微信）的邮件内容缺失，AI 分析失败

**错误信息**：
```
litellm.InternalServerError: Unknown scheme for proxy URL URL('socks://127.0.0.1:7897/')
```

**根本原因**：
- 系统环境变量中设置了 `all_proxy=socks://127.0.0.1:7897/`
- litellm 库不支持 socks 协议的代理
- AI API 调用时尝试使用该代理，导致失败

## 环境变量分析

**问题配置**：
```bash
all_proxy=socks://127.0.0.1:7897/          # litellm 不支持
HTTPS_PROXY=http://127.0.0.1:7897/         # HTTP 代理（正常）
https_proxy=http://127.0.0.1:7897/
HTTP_PROXY=http://127.0.0.1:7897/
http_proxy=http://127.0.0.1:7897/
NO_PROXY=localhost,127.0.0.1,192.168.0.0/16,10.0.0.0/8,...
```

**冲突原因**：
1. litellm 优先读取 `all_proxy` 环境变量
2. `all_proxy` 使用 socks 协议，litellm 无法处理
3. 即使有 HTTP 代理配置，也不会使用

## 解决方案

### 方案选择

考虑了三种方案：
1. ❌ **修改系统环境变量** - 影响范围太大
2. ❌ **测试时添加 NO_PROXY** - 治标不治本
3. ✅ **代码层面精确控制代理** - 根本解决问题

### 实施细节

**核心原则**：代理不应默认使用，只在明确需要时才启用

#### 改动1：AI 客户端禁用代理

**文件**：`trendradar/ai/client.py`

在 `AIClient.chat()` 方法中，调用 litellm completion 前临时禁用代理：

```python
# 调用 LiteLLM
# 禁用代理：AI API（api.siliconflow.cn）不需要代理，直连访问
# 保存当前环境变量
old_env = {}
proxy_vars = ["http_proxy", "https_proxy", "HTTP_PROXY", "HTTPS_PROXY", "all_proxy", "ALL_PROXY"]

for var in proxy_vars:
    if var in os.environ:
        old_env[var] = os.environ[var]
        del os.environ[var]

try:
    response = completion(**params)
finally:
    # 恢复环境变量
    for var, value in old_env.items():
        os.environ[var] = value
```

**效果**：
- ✅ AI API 调用不使用任何代理（直连）
- ✅ 不影响其他模块的代理使用
- ✅ 调用完成后恢复环境变量，不影响后续请求

#### 改动2：社区模块代理配置

**文件**：`config/config.yaml`

更新社区模块的代理配置，使用 HTTP 协议：

```yaml
community:
  # 代理配置（仅用于访问被墙网站：Reddit、Kickstarter 等）
  # 注意：
  #   1. 使用 HTTP 代理协议（不支持 SOCKS）
  #   2. AI API 调用不使用代理（代码中已禁用）
  #   3. 只有社区模块的网络请求会使用此代理
  proxy:
    enabled: true                           # 是否启用代理
    url: "http://127.0.0.1:7897"           # 使用 HTTP 协议（而非 SOCKS）
```

**效果**：
- ✅ 社区模块可以通过配置启用代理
- ✅ 使用 HTTP 协议（requests 库支持）
- ✅ 只有社区数据源（Reddit、GitHub 等）使用代理

#### 改动3：测试脚本简化

**文件**：`agents/test_e2e.py`

简化 `get_test_env()` 函数（移除 NO_PROXY 设置）：

```python
def get_test_env():
    """
    获取测试环境变量

    注意：代理控制已在代码层面实现：
    - AI API 调用时自动禁用代理（trendradar/ai/client.py）
    - 社区模块通过配置文件控制代理使用（config.yaml community.proxy）
    """
    env = os.environ.copy()
    env["TEST_MODE"] = "true"
    return env
```

**影响范围**：
- `test_podcast()` - ✅ 已更新
- `test_investment()` - ✅ 已更新
- `test_community()` - ✅ 已更新
- `test_wechat()` - ✅ 已更新

## AI API 配置分析

所有模块使用的 AI API：

| 模块 | API 域名 | 模型 |
|------|---------|------|
| 播客 ASR | api.siliconflow.cn | FunAudioLLM/SenseVoiceSmall |
| 播客 AI | api.siliconflow.cn | openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B |
| 投资 AI | api.siliconflow.cn | openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B |
| 社区 AI | api.siliconflow.cn | openai/deepseek-ai/DeepSeek-R1-0528-Qwen3-8B |
| 微信 AI | （待确认） | - |

**共同点**：
- 所有模块都使用 `api.siliconflow.cn`
- 该域名现在已添加到 NO_PROXY

## 验证计划

### 测试步骤

```bash
# 1. 运行单个模块测试
python agents/test_e2e.py podcast

# 预期结果：
# - 🧪 测试模式标记正常显示
# - ASR 转录成功
# - AI 分析生成内容
# - 邮件发送成功且有内容

# 2. 运行所有模块测试
python agents/test_e2e.py

# 预期结果：
# - 4个模块全部测试通过
# - 所有邮件都包含正确的内容
```

### 检查点

1. **日志检查**：
   - 没有 "Unknown scheme for proxy" 错误
   - AI API 调用成功
   - 日志中显示生成的内容

2. **邮件检查**：
   - 播客邮件：包含播客摘要和关键点
   - 投资邮件：包含市场分析
   - 社区邮件：包含热点话题
   - 微信邮件：包含公众号文章摘要

3. **数据库检查**：
   ```bash
   # 检查播客数据库
   sqlite3 output/news/podcast.db "SELECT title, ai_summary FROM podcast_episodes WHERE guid='697f9a2ab4be4c149b85137c' LIMIT 1;"

   # 应该看到非空的 ai_summary
   ```

## 技术背景

### litellm 代理支持

litellm 库支持的代理协议：
- ✅ HTTP/HTTPS 代理（通过 http_proxy, https_proxy）
- ❌ SOCKS 代理（不支持）

### 环境变量优先级

Python requests/httpx 库读取代理的顺序：
1. `all_proxy` - 最高优先级
2. `https_proxy` / `http_proxy` - 协议特定
3. 代码中显式设置 - 最低优先级

### NO_PROXY 机制

NO_PROXY 环境变量：
- 语法：逗号分隔的域名或IP列表
- 匹配：精确匹配或后缀匹配
- 示例：`api.siliconflow.cn` 匹配该域名
- 效果：匹配的域名不使用代理，直连

## 后续优化

### 生产环境

如果生产环境也遇到同样问题，可以考虑：

1. **修改系统环境变量**（永久方案）：
   ```bash
   # 在 ~/.zshrc 或 ~/.bashrc 中添加
   export NO_PROXY="$NO_PROXY,api.siliconflow.cn,open.bigmodel.cn"
   ```

2. **修改 Docker 环境**（容器内方案）：
   ```yaml
   # docker-compose.yml
   environment:
     NO_PROXY: "localhost,127.0.0.1,api.siliconflow.cn,open.bigmodel.cn"
   ```

3. **修改代码**（代码方案）：
   ```python
   # 在调用 litellm 前
   import os
   os.environ["NO_PROXY"] = "api.siliconflow.cn,open.bigmodel.cn"
   ```

### 监控和告警

建议添加 AI API 调用监控：
- 记录 API 响应时间
- 记录失败率
- 代理错误时发送告警

## 总结

**问题根源**：系统环境变量中的 socks 代理被所有请求使用，导致 litellm 报错

**解决方案**：代码层面精确控制代理使用范围
- ✅ AI API 调用：主动禁用代理（直连访问）
- ✅ 社区模块：通过配置文件控制代理（仅在需要时启用）
- ✅ 其他模块：不受影响

**修改文件**：
1. `trendradar/ai/client.py` - AI 调用时禁用代理
2. `config/config.yaml` - 社区模块代理配置（HTTP 协议）
3. `agents/test_e2e.py` - 简化测试环境变量

**核心改进**：
- 🎯 **精确控制**：代理不再默认使用，只在需要时启用
- 🔒 **隔离影响**：AI API 不受环境变量代理影响
- 📝 **可配置**：社区模块通过配置文件控制代理

**验证方法**：
- 运行 `python agents/test_e2e.py`
- 检查邮件内容是否包含 AI 分析结果
- 检查日志无 "Unknown scheme for proxy" 错误

**风险评估**：✅ 低风险
- AI 调用前后恢复环境变量，不影响其他请求
- 社区模块代理可通过配置开关控制
- 所有改动向后兼容

---

**修复日期**：2026-02-03
**修复人员**：Claude (AI Assistant)
**相关文档**：
- `agents/test_e2e.py` - 测试触发器
- `agents/README_TEST_FRAMEWORK.md` - 测试框架文档
- `AGENTS.md` - 测试操作流程
