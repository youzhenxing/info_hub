# TrendRadar 统一测试框架使用指南

## 设计理念

**核心原则**: 测试脚本是纯触发器，不包含业务逻辑

```
测试脚本（触发器）→ CLI参数 → 生产代码 → 真实组件
```

### 为什么这样设计？

1. **避免代码重复**: 测试不重新实现业务逻辑
2. **保证一致性**: 测试运行的代码 = 生产部署的代码
3. **简化维护**: 生产代码更新时，测试自动同步
4. **真实环境**: 测试使用生产配置和数据库

---

## 快速开始

### 一键运行所有测试

```bash
python agents/test_e2e.py
```

### 单独运行播客测试

```bash
# 方式1: 使用测试脚本
python agents/test_e2e.py podcast

# 方式2: 直接调用CLI（生产代码）
python -m trendradar \
  --podcast-only \
  --test-mode \
  --test-feed lex-fridman \
  --test-guid 49264e2036d4
```

### 单独运行投资测试

```bash
# 方式1: 使用测试脚本
python agents/test_e2e.py investment

# 方式2: 直接调用CLI（生产代码）
python -m trendradar --investment-only --test-mode --market cn
```

### 单独运行社区测试

```bash
# 方式1: 使用测试脚本
python agents/test_e2e.py community

# 方式2: 直接调用CLI（生产代码）
python -m trendradar --community-only --test-mode
```

### 单独运行微信测试

```bash
# 1. 修改 wechat/config.yaml
test:
  enabled: true
  feed_limit: 3

# 2. 运行测试
python agents/test_e2e.py wechat

# 或直接调用
cd wechat && python main.py run
```

---

## 播客测试详解

### 固定测试数据

**测试feed**: `lex-fridman`（Lex Fridman Podcast）
**测试episode**: 使用固定的guid，确保每次测试相同

### 测试模式的作用

1. **过滤范围**: 只处理指定的feed和episode
2. **跳过重复检查**: 允许反复测试同一episode
3. **标记日志**: 日志中显示 🧪 测试模式标记

### 验证方法

```bash
# 查看日志，确认调用了生产代码
python -m trendradar --podcast-only --test-mode \
  --test-feed lex-fridman --test-guid xxx 2>&1 | grep "PodcastProcessor"

# 应该看到：
# [Podcast] 开始播客处理流程
# [Podcast] 🧪 测试模式：仅处理 feed=lex-fridman
# [Podcast] 🧪 测试模式：仅处理 guid=xxx
```

---

## 投资测试详解

### 测试数据

**市场类型**: A股/港股（cn）或美股（us）
**配置方式**: CLI参数 `--market cn`

### 测试模式的作用

- 强制运行（跳过时间检查）
- 复用现有的 `force=True` 参数

### 验证方法

```bash
# 查看日志
python -m trendradar --investment-only --test-mode --market cn

# 应该看到：
# 投资简报处理 (A股/港股)
# [Investment] 处理完成
```

---

## 社区测试详解

### 测试数据源

- HackerNews
- Reddit
- GitHub Trending
- ProductHunt

### 测试模式的作用

- 强制运行（跳过时间检查）
- 处理所有配置的数据源

### 验证方法

```bash
# 查看日志
python -m trendradar --community-only --test-mode

# 应该看到：
# 社区监控处理
# [CommunityProcessor] 开始处理
# [CommunityProcessor] ✅ 处理完成
```

---

## 微信测试详解

### 固定测试数据

**测试数量**: 3个公众号
**配置方式**: 在 `wechat/config.yaml` 中指定

### 配置示例

```yaml
test:
  enabled: true
  feed_limit: 3
  # 可选：指定测试哪3个
  test_feeds:
    - "新智元"
    - "量子位"
    - "机器之心"
```

### 验证方法

```bash
# 查看日志，确认只处理3个账号
cd wechat && python main.py run 2>&1 | grep "采集公众号"

# 应该看到：
# 开始采集 3 个公众号
# 🧪 测试模式：仅处理前 3 个公众号
```

---

## 验证测试代码=生产代码

### 方法1: 代码审查

```bash
# 查看测试脚本
cat agents/test_e2e.py | grep "def "

# 应该只看到：
# - test_podcast()
# - test_investment()
# - test_community()
# - test_wechat()
# - main()

# 没有 process_episode, send_email 等业务逻辑函数
```

### 方法2: 日志对比

```bash
# 运行生产代码
python -m trendradar --podcast-only > prod.log 2>&1

# 运行测试
python agents/test_e2e.py podcast > test.log 2>&1

# 对比代码路径（应该完全相同）
grep "PodcastProcessor" prod.log
grep "PodcastProcessor" test.log
```

### 方法3: 检查subprocess调用

测试脚本应该只包含：
```python
subprocess.run([sys.executable, "-m", "trendradar", ...])
```

不应该包含：
- ❌ `import requests` 直接调用API
- ❌ `smtplib.SMTP()` 发送邮件
- ❌ 重新实现配置加载逻辑

---

## 常见问题

### Q: 测试会消耗API配额吗？
A: 是的。测试使用真实的API（ASR、AI等）。建议：
- 固定测试1个episode
- 控制测试频率

### Q: 测试会污染生产数据库吗？
A: 会写入相同的数据库。建议：
- 测试episode在数据库中有`test_mode`标记（可选）
- 或使用 `--test-db-path` 参数（需要实现）

### Q: 如何确认测试使用了生产代码？
A: 三个方法：
1. 查看日志，确认调用了生产类（PodcastProcessor等）
2. 在生产代码中添加 `print("[生产代码] ...")` 验证
3. 对比subprocess.run的参数，应该是 `python -m trendradar`

### Q: 测试失败怎么办？
A: 检查：
1. 配置文件是否正确（config.yaml）
2. 测试数据是否存在（feed_id, guid）
3. API密钥是否有效
4. 网络连接是否正常

### Q: 如何修改测试数据？
A: 编辑 `agents/test_e2e.py`：
```python
# 修改播客测试数据
TEST_FEED_ID = "your-feed-id"
TEST_EPISODE_GUID = "your-episode-guid"
```

---

## 设计决策记录

### 为什么不用unittest/pytest？

**理由**:
- 用户需求是"触发器"而非"断言测试"
- 生产代码已有完整的错误处理和日志
- subprocess更接近真实部署（cron/systemd）

### 为什么测试模式跳过重复检查？

**理由**:
- 测试需要反复运行同一episode
- `_is_new_episode()` 会阻止重复处理
- 跳过检查不影响其他逻辑（下载、转录、AI分析仍正常）

### 为什么不统一用配置文件？

**理由**:
- 播客测试需要频繁切换episode → CLI更灵活
- 微信测试固定3个账号 → 配置文件更清晰
- 混合方案兼顾灵活性和可维护性

### 为什么用subprocess而不是import？

**理由**:
1. subprocess模拟真实的命令行调用
2. 隔离测试环境（独立进程）
3. 更接近cron/systemd的部署方式
4. 可以验证CLI参数解析逻辑

---

## 测试最佳实践

### 1. 定期运行测试

```bash
# 每次发布前运行
python agents/test_e2e.py

# 或在CI/CD中集成
```

### 2. 保持测试数据有效

```bash
# 定期检查测试episode是否仍可访问
python -m trendradar --podcast-only --test-mode \
  --test-feed lex-fridman --test-guid xxx
```

### 3. 监控测试输出

```bash
# 保存测试日志
python agents/test_e2e.py > test_$(date +%Y%m%d).log 2>&1
```

### 4. 隔离测试环境

```bash
# 使用独立的测试配置（可选）
cp config/config.yaml config/config.test.yaml
# 编辑 config.test.yaml，修改邮件接收者等
```

---

## 下一步

1. ✅ 阅读本文档
2. ✅ 运行 `python agents/test_e2e.py` 尝试测试
3. ✅ 查看日志，确认测试代码=生产代码
4. ✅ 根据需要调整测试数据（feed_id, guid）

**Happy Testing! 🎉**

---

## 附录：旧测试脚本迁移

旧测试脚本已归档至 `agents/archive/old_tests/`。

如需参考旧逻辑：
```bash
cat agents/archive/old_tests/test_full_pipeline.py
```

**注意**: 不要运行旧测试脚本，请使用新的 `agents/test_e2e.py`。

详见：`agents/archive/old_tests/README.md`
