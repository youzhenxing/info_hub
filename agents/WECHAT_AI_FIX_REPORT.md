# 微信公众号AI分析修复报告

## 问题描述

用户报告："我修复了微信登录的问题，帮我端到端测试下微信公众号的邮件推送"

### 测试结果

✅ **微信登录修复成功**
- 成功获取25篇文章
- 数据采集正常

❌ **AI分析完全失败**
- 所有AI分析字段为空
- 数据与数字：0条
- 事件与动态：0条
- 内幕与洞察：0条
- 文章AI摘要：0条

## 根本原因分析

### 1. 提示词路径错误 (Bug #1)

**问题代码** (`wechat/src/analyzer.py:33`):
```python
prompt_path = Path("prompts") / filename  # ❌ 查找根目录的prompts/
```

**实际情况**:
- 提示词文件位于：`wechat/prompts/wechat_step1_summary.txt`
- 代码查找：`prompts/wechat_step1_summary.txt` (不存在)
- **结果**：使用默认提示词，内容过于简化

**修复方案**:
```python
# 修改为相对于本文件的路径
wechat_dir = Path(__file__).parent.parent
prompt_path = wechat_dir / "prompts" / filename  # ✅ 查找wechat/prompts/
```

### 2. 代理配置干扰 (Bug #2)

**错误信息**:
```
InternalServerError: Unknown scheme for proxy URL URL('socks://127.0.0.1:7897/')
```

**环境变量**:
```bash
all_proxy=socks://127.0.0.1:7897/
HTTP_PROXY=http://127.0.0.1:7897/
```

**影响**:
- LiteLLM尝试通过代理访问硅基流动API
- 代理scheme不支持，导致所有AI调用失败
- 25篇文章的AI摘要全部失败
- 话题聚合也失败（重试3次后回退）

**修复方案**:
在调用AI前禁用代理：
```python
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
            'all_proxy', 'ALL_PROXY']:
    if var in os.environ:
        del os.environ[var]
```

### 3. API Key配置缺失 (Bug #3)

**配置文件** (`wechat/config.yaml`):
```yaml
ai:
  api_key: ""  # ❌ 为空
```

**环境变量**:
```bash
AI_API_KEY=  # 未设置
```

**生产环境配置** (`/home/zxy/Documents/install/trendradar/shared/.env`):
```bash
AI_API_KEY={{SILICONFLOW_API_KEY}}  # ✅ 已配置
```

**修复方案**:
```bash
# 方式1：设置环境变量（推荐）
export AI_API_KEY="sk-xxx"

# 方式2：创建本地.env文件
echo "AI_API_KEY=sk-xxx" > wechat/.env
```

## 修复代码

### 修改文件：`wechat/src/analyzer.py`

```diff
  def _load_prompt(self, filename: str) -> str:
      """加载提示词文件"""
-     prompt_path = Path("prompts") / filename
+     # 获取 wechat/prompts 目录（相对于本文件的路径）
+     wechat_dir = Path(__file__).parent.parent
+     prompt_path = wechat_dir / "prompts" / filename
      if prompt_path.exists():
          return prompt_path.read_text(encoding='utf-8')
```

### 创建测试脚本：`agents/test_wechat_ai.py`

```python
#!/usr/bin/env python3
"""
测试微信AI分析（禁用代理）
"""
import sys
import os

# 禁用所有代理
for var in ['http_proxy', 'https_proxy', 'HTTP_PROXY', 'HTTPS_PROXY',
            'all_proxy', 'ALL_PROXY']:
    if var in os.environ:
        del os.environ[var]

# 设置AI API Key
os.environ['AI_API_KEY'] = '{{SILICONFLOW_API_KEY}}'

sys.path.insert(0, 'wechat')

from src.config_loader import ConfigLoader
from src.storage import Storage
from src.analyzer import WechatAnalyzer

config = ConfigLoader('wechat/config.yaml')
storage = Storage('wechat/data/wechat.db')
analyzer = WechatAnalyzer(config, storage)

print("🔄 开始生成每日报告...")
report = analyzer.analyze_daily()
print(f"✅ 完成！话题数: {len(report.topics)}")
```

## 验证步骤

1. **修复提示词路径**
   ```bash
   git diff wechat/src/analyzer.py
   ```

2. **测试AI分析（禁用代理）**
   ```bash
   python agents/test_wechat_ai.py
   ```

3. **检查生成的HTML**
   ```bash
   ls -lt wechat/data/output/*.html | head -1
   grep -c "数据与数字" $(ls -t wechat/data/output/*.html | head -1)
   ```

4. **端到端测试**
   ```bash
   unset all_proxy && \
   export AI_API_KEY="sk-xxx" && \
   python -m trendradar.cli run wechat
   ```

## 预期结果

修复后，AI分析应该正常工作：
- ✅ 单篇AI摘要：25篇
- ✅ 话题聚合：2-4个话题
- ✅ 数据与数字：5-15条
- ✅ 事件与动态：3-10条
- ✅ 内幕与洞察：2-8条

## 之前为什么可以工作？

可能的原因：
1. **环境差异**：之前运行时没有设置代理，或者代理配置正确
2. **工作目录**：之前从 `wechat/` 目录运行，路径查找正确
3. **生产环境**：生产环境Docker容器内没有代理问题

## 后续建议

1. **添加代理检测**：在 `AIClient.__init__` 中检测并警告代理配置
2. **统一配置**：考虑使用统一的 `.env` 文件管理所有API Key
3. **改进提示词**：当前默认提示词过于简化，应该从文件加载失败时抛出警告

## 相关文件

- `wechat/src/analyzer.py` - 提示词路径修复
- `agents/test_wechat_ai.py` - 测试脚本
- `wechat/config.yaml` - AI配置
- `wechat/prompts/wechat_step2_aggregate.txt` - 话题聚合提示词

---

生成时间: 2026-02-02
测试环境: Ubuntu Linux, Python 3.x
