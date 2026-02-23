# 已废弃的旧测试脚本

## 废弃原因

这些测试脚本存在以下问题：
1. **代码重复**：重新实现了业务逻辑
2. **硬编码秘密**：API密钥和密码直接写在代码中
3. **配置不统一**：与生产代码使用不同的配置加载机制
4. **调用方式不一致**：直接调用API，绕过生产代码接口

导致"反复返工"问题：测试通过但生产失败。

## 新测试框架

统一测试框架位于：`agents/test_e2e.py`

核心原则：测试脚本只是触发器，实际运行的是生产代码。

详见：`agents/README_TEST_FRAMEWORK.md`

## 这些文件还有用吗？

保留原因：
- 可以参考旧的测试数据（API密钥已失效需重新配置）
- 了解历史问题和演变过程

不应该再运行：
- ❌ 不要直接运行这些脚本
- ❌ 不要基于这些脚本开发新测试
- ✅ 使用新的 `agents/test_e2e.py`

## 文件清单

### 根目录测试文件（4个）
- `test_full_pipeline.py` - 播客完整流程测试
- `test_investment.py` - 投资模块测试
- `test_community.py` - 社区监控测试
- `test_assemblyai.py` - ASR测试

### agents 目录测试文件（12个）
- `test_podcast_ai.py` - 播客AI分析测试
- `test_podcast_fetch.py` - 播客抓取测试
- `test_podcast_mobile_fix.py` - 播客移动端修复测试
- `test_wechat_ai.py` - 微信AI分析测试
- `test_wechat_unified_config.py` - 微信统一配置测试
- `test_163_email.py` - 163邮箱测试
- `test_deploy_retry.py` - 部署重试测试
- `test_h2_conversion.py` - H2转换测试
- `test_markdown_filter.py` - Markdown过滤测试
- `test_new_rss.py` - 新RSS测试
- `config_priority_test.py` - 配置优先级测试
- `config_priority_test2.py` - 配置优先级测试2

共计：**16个旧测试文件**

## 如何恢复

如果需要参考旧逻辑：

```bash
# 查看文件
cat agents/archive/old_tests/test_full_pipeline.py

# 临时恢复（不推荐）
cp agents/archive/old_tests/test_full_pipeline.py ./
```

## 归档日期

2026-02-02

## 相关提交

查看统一测试框架的实施提交：
```bash
git log --grep="统一测试框架"
```
