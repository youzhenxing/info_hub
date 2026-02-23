# 每个渠道最大账号数配置修改记录

**修改日期**: 2026-02-06
**修改人**: Claude Code (Sonnet 4.5)

---

## 📋 修改内容

### 配置项
- **配置文件**: `config/config.yaml`
- **配置位置**: 第497行
- **配置键**: `advanced.max_accounts_per_channel` (加载后扁平化为 `MAX_ACCOUNTS_PER_CHANNEL`)
- **原值**: 3
- **新值**: 20

### 修改差异

```diff
  # 多账号限制
- max_accounts_per_channel: 3         # 每个渠道最大账号数量
+ max_accounts_per_channel: 20        # 每个渠道最大账号数量
```

---

## 📊 影响分析

### 数量变化

| 指标 | 修改前 | 修改后 | 变化 |
|------|--------|--------|------|
| 每渠道最大账号数 | 3 | 20 | +17 |
| 提升比例 | 基准 | 567% | +467% |

### 实际影响

**支持的渠道**:
- 邮件 (Email)
- 钉钉 (DingTalk)
- 飞书 (Feishu)
- 企业微信 (WeWork)
- Bark
- Slack
- Telegram
- ntfy

**单个渠道可支持账号数**:
- 修改前: 最多3个账号
- 修改后: 最多20个账号

---

## 🔍 技术细节

### 配置加载

配置文件中使用嵌套结构:
```yaml
advanced:
  max_accounts_per_channel: 20
```

`load_config()` 加载后扁平化为根级别键:
```python
config = {
    "MAX_ACCOUNTS_PER_CHANNEL": 20,
    ...
}
```

### 配置读取

**正确方式**:
```python
from trendradar.core.loader import load_config

config = load_config()
max_accounts = config.get('MAX_ACCOUNTS_PER_CHANNEL', 3)
```

**错误方式**:
```python
# ❌ 不工作,因为配置被扁平化
max_accounts = config.get('advanced', {}).get('max_accounts_per_channel', 3)
```

### 环境变量覆盖

可以通过环境变量覆盖配置文件值:

```bash
export MAX_ACCOUNTS_PER_CHANNEL=20
```

优先级: 环境变量 > 配置文件 > 默认值(3)

---

## ✅ 验证结果

### 配置文件验证
```bash
$ grep -n "max_accounts_per_channel" config/config.yaml
214:# • 每个渠道最多支持 max_accounts_per_channel 个账号
497:  max_accounts_per_channel: 20        # 每个渠道最大账号数量
```

### 运行时验证
```python
from trendradar.core.loader import load_config

config = load_config()
max_accounts = config.get('MAX_ACCOUNTS_PER_CHANNEL', 3)

print(f"每个渠道最大账号数: {max_accounts}")
# 输出: 每个渠道最大账号数: 20
```

**结果**: ✅ 配置正确加载为20

---

## 📝 使用场景

### 适用场景

1. **多账号通知**: 需要向同一平台的多个账号发送通知
2. **团队协作**: 不同团队成员需要接收不同类别的通知
3. **业务分群**: 按业务线或项目分群发送通知

### 示例配置

假设需要向5个不同的邮箱发送投资简报:

```yaml
email:
  enabled: true
  # 最多可以配置20个邮箱
  accounts:
    - account_id: "user1"
      email_to: "user1@example.com"
    - account_id: "user2"
      email_to: "user2@example.com"
    - account_id: "user3"
      email_to: "user3@example.com"
    - account_id: "user4"
      email_to: "user4@example.com"
    - account_id: "user5"
      email_to: "user5@example.com"
```

---

## ⚠️ 注意事项

### 1. 性能影响

增加账号数会增加:
- 邮件发送时间 (每封邮件约1-3秒)
- API请求次数
- 内存占用

**建议**:
- 仅配置需要的账号数
- 使用批量发送减少请求次数
- 考虑使用邮件列表(邮件群发)而非多个独立账号

### 2. 频率限制

某些平台有API频率限制:
- **Gmail**: 每天发送上限(免费账户500封)
- **钉钉/飞书**: 每分钟请求次数限制
- **企业微信**: 每分钟请求次数限制

**建议**:
- 增加请求间隔(`BATCH_SEND_INTERVAL`)
- 监控API响应状态
- 遇到限流时自动重试

### 3. 配置建议

**小规模使用** (<5账号):
- 使用默认配置即可
- 间隔: 3秒

**中等规模** (5-10账号):
- 建议间隔: 5秒
- 启用批量发送

**大规模使用** (10-20账号):
- 建议间隔: 10秒
- 必须启用批量发送
- 考虑使用消息队列

---

## 🎯 总结

### 修改内容
- ✅ 将 `max_accounts_per_channel` 从 3 增加到 20
- ✅ 提升567%,支持更多账号

### 验证状态
- ✅ 配置文件修改成功
- ✅ 运行时加载正确
- ✅ 无语法错误

### 后续建议
1. 监控系统性能和API调用频率
2. 根据实际使用情况调整 `BATCH_SEND_INTERVAL`
3. 如遇到API限流,考虑增加重试机制或使用消息队列

---

**修改完成时间**: 2026-02-06 21:55
**文档版本**: v1.0
