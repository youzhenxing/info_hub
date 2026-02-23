# Thinking 模式部署计划

## 📋 部署前检查清单

### 代码修改
- [x] `trendradar/podcast/analyzer.py`
  - [x] MAX_TOKENS 设置为 64000
  - [x] 启用 extra_body={"enable_thinking": True}
  - [x] 添加 Thinking 模式日志输出

### 配置验证
- [x] `TIMEOUT: 900` (config/config.yaml)
- [x] API Key 配置正确
- [x] 模型名称正确: `deepseek/deepseek-ai/DeepSeek-V3.2`

### 本地测试
- [ ] `test_podcast_thinking.py` - 播客分析场景测试
- [ ] 验证输出 >10K tokens
- [ ] 确认无硬性截断

---

## 🚀 部署步骤

### 步骤 1：本地测试验证

**运行测试**：
```bash
cd /home/zxy/Documents/code/TrendRadar
python3 agents/test_podcast_thinking.py
```

**预期结果**：
- ✅ 输出字符数 >15,000
- ✅ 估算 Token 数 >10,000
- ✅ 包含完整结构（摘要、要点、讨论等）
- ✅ 话题数量 ≥4 个
- ❌ 无硬性截断（如"他的"后中断）

**如果测试失败**：
1. 检查 API 是否返回错误
2. 查看 `agents/podcast_thinking_test_result.txt` 内容
3. 确认 max_tokens 是否正确传递

---

### 步骤 2：版本号更新

**修改版本号**：
```bash
# 更新 __version__
vim trendradar/__init__.py

# 修改为:
__version__ = "5.26.0"
```

**提交修改**：
```bash
git add trendradar/podcast/analyzer.py
git add trendradar/__init__.py
git commit -m "feat(podcast): 启用 Thinking 模式以支持完整的长内容输出

- 设置 MAX_TOKENS 为 64000（思考模式的最大输出限制）
- 启用 extra_body={'enable_thinking': True}
- 解决非思考模式 8K token 限制导致的截断问题
- 预期支持完整的中英双语播客分析（约 12-15K tokens）

参考: https://api-docs.deepseek.com/
- 非思考模式: 最大 8K 输出 tokens
- 思考模式: 最大 64K 输出 tokens

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"
```

---

### 步骤 3：完整部署

**选项 A：使用部署脚本（推荐）**
```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
./deploy.sh
```

**选项 B：手动部署**
```bash
# 1. 停止容器
docker stop trendradar-prod

# 2. 构建新镜像
docker build -t trendradar:latest .

# 3. 启动容器
docker-compose up -d
```

---

### 步骤 4：生产环境验证

#### A. 检查 Thinking 模式是否启用

```bash
# 查看日志
docker logs trendradar-prod | grep "Thinking"

# 预期输出:
# [PodcastAnalyzer] Thinking 模式: 已启用 (最大输出: 64K tokens)
```

#### B. 等待新播客处理

```bash
# 监控日志
docker logs -f trendradar-prod | grep -E "PodcastAnalyzer|分析完成"
```

#### C. 检查输出内容

```bash
# 查看最新的播客邮件
ls -lth /home/zxy/Documents/code/TrendRadar/output/podcast/email/ | head -5

# 检查文件大小和内容完整性
# 预期:
# - 文件大小 >50KB
# - 无硬性截断
# - 包含完整的话题讨论
```

---

## ⚠️ 潜在问题与解决方案

### 问题 1：超时

**症状**：
```
Timeout error: API request took longer than 900 seconds
```

**解决方案**：
```yaml
# config/config.yaml
TIMEOUT: 1800  # 增加到 30 分钟
```

### 问题 2：输出仍然截断

**症状**：输出仍在句子中间截断

**诊断**：
```bash
# 检查 API 返回的实际 token 数
docker logs trendradar-prod | grep "completion_tokens"
```

**可能原因**：
1. max_tokens 未正确传递 → 检查代码
2. API 限制 → 联系 SiliconFlow 支持
3. Prompt 太长 → 简化 Prompt

### 问题 3：成本增加

**症状**：API 费用显著增加

**分析**：
- Thinking 模式会增加计算时间
- 但输出质量更高，用户价值更大
- 建议先部署测试，监控成本

---

## 📊 性能基准

### 响应时间对比

| 模式 | 输入 tokens | 输出 tokens | 预计时间 |
|------|-----------|-----------|---------|
| 非思考模式 | ~8K | ~8K (截断) | 30-60 秒 |
| 思考模式 | ~8K | ~12K (完整) | 2-5 分钟 |

### 成本对比

| 模式 | 计算时间 | 相对成本 |
|------|---------|---------|
| 非思考模式 | 1x | 基准 |
| 思考模式 | 2-3x | 2-3x |

*注：Thinking 模式虽然成本增加，但输出完整性和质量大幅提升*

---

## 🎯 成功标准

### 部署成功的标志

1. **日志正确**：
   ```
   [PodcastAnalyzer] Thinking 模式: 已启用 (最大输出: 64K tokens)
   ```

2. **输出完整**：
   - 邮件无硬性截断
   - 包含所有话题讨论
   - 发言摘要完整

3. **Token 使用**：
   - 输出 tokens >10K
   - <64K 限制

4. **用户反馈**：
   - 邮件内容完整
   - 中英双语正常
   - 阅读体验良好

---

## 📝 部署后检查

### 自动化检查脚本

```bash
#!/bin/bash
# deploy_check.sh

echo "=== Thinking 模式部署检查 ==="

# 1. 检查 Thinking 模式日志
echo -n "1. Thinking 模式状态: "
if docker logs trendradar-prod 2>&1 | grep -q "Thinking 模式: 已启用"; then
    echo "✅"
else
    echo "❌ 未启用"
fi

# 2. 检查最新邮件
echo -n "2. 最新邮件大小: "
latest_email=$(ls -t /home/zxy/Documents/code/TrendRadar/output/podcast/email/*.html | head -1)
size=$(stat -f%z "$latest_email" 2>/dev/null || stat -c%s "$latest_email" 2>/dev/null)
if [ "$size" -gt 50000 ]; then
    echo "✅ $size 字节"
else
    echo "⚠️  $size 字节 (可能过小)"
fi

# 3. 检查是否截断
echo -n "3. 内容完整性: "
if grep -q "他的$" "$latest_email"; then
    echo "❌ 可能截断"
else
    echo "✅ 完整"
fi

echo "=== 检查完成 ==="
```

---

## 🔄 回滚方案

如果部署后发现问题，可以快速回滚：

```bash
# 回滚到上一个版本
git revert HEAD
./deploy/deploy.sh

# 或者直接回滚 commit
git log --oneline -5  # 查看最近 5 个 commit
git revert <commit-hash>
./deploy/deploy.sh
```

---

## 📚 相关文档

- [DeepSeek API 文档 - Thinking 模式](https://api-docs.deepseek.com/)
- [SiliconFlow 文档](https://docs.siliconflow.cn/)
- [LiteLLM 文档 - extra_body 参数](https://docs.litellm.ai/)
- [Token 分析报告](/home/zxy/Documents/code/TrendRadar/agents/token_analysis_report.md)
- [修复总结](/home/zxy/Documents/code/TrendRadar/agents/thinking_mode_fix_summary.md)

---

**部署时间**: 待定
**部署版本**: v5.26.0
**部署人员**: 待执行
