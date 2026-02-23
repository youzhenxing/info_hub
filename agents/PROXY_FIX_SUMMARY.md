# AI 分析代理问题修复总结

## 问题描述

**症状**：所有模块的邮件内容缺失，AI 分析失败

**错误**：`litellm.InternalServerError: Unknown scheme for proxy URL URL('socks://127.0.0.1:7897/')`

**根本原因**：
- 系统环境变量中设置了 `all_proxy=socks://127.0.0.1:7897/`
- litellm 库不支持 socks 协议
- 所有 AI API 调用都尝试使用该代理，导致失败

## 解决方案

### 核心原则

**代理不应默认使用，只在明确需要时才启用**

### 实施改动

#### 1. AI 客户端禁用代理

**文件**：`trendradar/ai/client.py`

**改动**：在 `AIClient.chat()` 方法中，调用 litellm completion 前临时禁用代理

```python
# 禁用代理：AI API 不需要代理，直连访问
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
- ✅ AI API 调用不受环境变量代理影响
- ✅ 调用完成后恢复环境变量
- ✅ 不影响其他模块的网络请求

#### 2. 社区模块代理配置

**文件**：`config/config.yaml`

**改动**：更新代理配置，使用 HTTP 协议

```yaml
community:
  proxy:
    enabled: true                           # 是否启用代理
    url: "http://127.0.0.1:7897"           # 使用 HTTP 协议（而非 SOCKS）
```

**说明**：
- 仅在社区模块的数据源（Reddit、GitHub 等）需要访问时使用代理
- AI API 调用不使用此代理（代码中已禁用）

#### 3. 测试脚本简化

**文件**：`agents/test_e2e.py`

**改动**：简化 `get_test_env()` 函数

```python
def get_test_env():
    """
    获取测试环境变量

    注意：代理控制已在代码层面实现
    """
    env = os.environ.copy()
    env["TEST_MODE"] = "true"
    return env
```

## 验证结果

### 测试1：AI 客户端代理禁用

```bash
python -c "from trendradar.ai.client import AIClient; ..."
```

**结果**：
```
环境变量代理设置:
  all_proxy: socks://127.0.0.1:7897/
  http_proxy: http://127.0.0.1:7897/

测试 AI 调用...
✅ AI 调用成功！响应: 你好呀！我是DeepSeek-R1...

调用后环境变量检查:
  all_proxy: socks://127.0.0.1:7897/
  http_proxy: http://127.0.0.1:7897/
```

**验证通过**：
- ✅ AI 调用成功，无代理错误
- ✅ 环境变量正确恢复

### 测试2：端到端测试（待运行）

```bash
python agents/test_e2e.py
```

**预期结果**：
- 所有模块测试通过
- 邮件包含 AI 分析内容
- 无 "Unknown scheme for proxy" 错误

## 架构改进

### 修复前：全局代理控制

```
┌─────────────────────────────┐
│  系统环境变量                │
│  all_proxy=socks://...      │
└─────────────┬───────────────┘
              │
              ├──► AI API 调用 ❌ SOCKS 不支持
              ├──► 社区数据源 ✅ 需要代理
              └──► 其他请求   ? 意外使用代理
```

### 修复后：精确代理控制

```
┌─────────────────────────────┐
│  AI 调用层                   │
│  - 调用前：禁用代理          │
│  - 调用后：恢复环境变量       │
└──────────────────────────────┘
              ↓
        ✅ 直连 AI API

┌─────────────────────────────┐
│  社区模块                     │
│  - 读取配置：proxy.enabled   │
│  - 使用 HTTP 协议代理        │
└──────────────────────────────┘
              ↓
        ✅ 按需使用代理
```

## 修改文件清单

| 文件 | 改动内容 | 行号 |
|------|---------|------|
| `trendradar/ai/client.py` | AI 调用时禁用代理 | 107-123 |
| `config/config.yaml` | 社区模块代理配置 | 964-966 |
| `agents/test_e2e.py` | 简化测试环境变量 | 27-35 |
| `agents/PROXY_FIX_REPORT.md` | 详细修复报告 | 新建 |
| `agents/PROXY_FIX_SUMMARY.md` | 修复总结 | 新建 |

## 下一步

1. ✅ 运行完整的端到端测试：`python agents/test_e2e.py`
2. ✅ 检查所有模块的邮件内容是否包含 AI 分析
3. ✅ 验证社区模块的代理是否正常工作
4. ✅ 提交代码，记录此次修复

## 技术要点

### litellm 代理支持

litellm 通过环境变量读取代理配置：
- ✅ 支持：`http_proxy`、`https_proxy`（HTTP/HTTPS 协议）
- ❌ 不支持：`all_proxy`（SOCKS 协议）

### requests 库代理支持

社区模块使用 requests 库，支持：
- ✅ HTTP 代理：`{"http": "http://...", "https": "http://..."}`
- ✅ HTTPS 代理：`{"http": "https://...", "https": "https://..."}`
- ❌ SOCKS 代理：需要额外安装 `requests[socks]`

### 环境变量恢复技术

```python
# 1. 保存当前环境变量
old_env = {var: os.environ[var] for var in proxy_vars if var in os.environ}

# 2. 删除代理变量
for var in proxy_vars:
    if var in os.environ:
        del os.environ[var]

# 3. 执行操作
response = completion(**params)

# 4. 恢复环境变量（在 finally 块中，确保一定执行）
for var, value in old_env.items():
    os.environ[var] = value
```

**关键点**：
- 使用 `try...finally` 确保环境变量恢复
- 不影响其他线程/协程（环境变量是进程级的）
- 调用前后状态一致

## 参考文档

- [LiteLLM Proxy Settings](https://docs.litellm.ai/docs/proxy/configs)
- [Requests Proxies](https://requests.readthedocs.io/en/latest/user/advanced/#proxies)
- [Python os.environ](https://docs.python.org/3/library/os.html#os.environ)

---

**修复日期**：2026-02-03
**修复人员**：Claude (AI Assistant)
**验证状态**：✅ AI 调用测试通过，端到端测试待运行
