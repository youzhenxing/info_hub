# 播客邮件推送问题诊断报告

## 问题现象

播客处理成功，但没有收到邮件推送。

## 错误日志

```
[PodcastNotifier] 发件人:
[PodcastNotifier] 收件人:
[PodcastNotifier] ❌ 邮件配置不完整
```

---

## 🔍 根本原因分析

### 配置结构不匹配

**实际配置位置** (`config/config.yaml:250-255`):
```yaml
notification:
  channels:
    email:
      from: "{{EMAIL_ADDRESS}}"
      password: "your_email_auth_code"
      to: "{{EMAIL_ADDRESS}}"
      smtp_server: "smtp.163.com"
      smtp_port: "465"
```

**代码读取位置** (`trendradar/podcast/processor.py:184-190`):
```python
email_config = {
    "FROM": self.config.get("EMAIL_FROM", ""),      # ❌ 错误位置
    "PASSWORD": self.config.get("EMAIL_PASSWORD", ""),
    "TO": self.config.get("EMAIL_TO", ""),
    "SMTP_SERVER": self.config.get("EMAIL_SMTP_SERVER", ""),
    "SMTP_PORT": self.config.get("EMAIL_SMTP_PORT", ""),
}
```

### 问题原因

代码尝试从配置根级别读取 `EMAIL_FROM`、`EMAIL_TO` 等键，但这些键实际存在于：
```yaml
notification.channels.email.from
notification.channels.email.to
```

---

## 🛠️ 解决方案

### 方案 A: 修复代码读取路径（推荐）

修改 `trendradar/podcast/processor.py` 第 184-190 行：

**修改前**:
```python
email_config = {
    "FROM": self.config.get("EMAIL_FROM", ""),
    "PASSWORD": self.config.get("EMAIL_PASSWORD", ""),
    "TO": self.config.get("EMAIL_TO", ""),
    "SMTP_SERVER": self.config.get("EMAIL_SMTP_SERVER", ""),
    "SMTP_PORT": self.config.get("EMAIL_SMTP_PORT", ""),
}
```

**修改后**:
```python
# 从 notification.channels.email 读取配置
notification_config = self.config.get("NOTIFICATION", self.config.get("notification", {}))
channels = notification_config.get("channels", notification_config.get("CHANNELS", {}))
email_channel = channels.get("email", {})

email_config = {
    "FROM": email_channel.get("from", ""),
    "PASSWORD": email_channel.get("password", ""),
    "TO": email_channel.get("to", ""),
    "SMTP_SERVER": email_channel.get("smtp_server", ""),
    "SMTP_PORT": email_channel.get("smtp_port", ""),
}
```

### 方案 B: 添加环境变量配置（快速临时方案）

在 `config.yaml` 根级别添加邮件配置：

```yaml
# 在文件顶部附近添加
EMAIL_FROM: "{{EMAIL_ADDRESS}}"
EMAIL_PASSWORD: "your_email_auth_code"
EMAIL_TO: "{{EMAIL_ADDRESS}}"
EMAIL_SMTP_SERVER: "smtp.163.com"
EMAIL_SMTP_PORT: "465"
```

---

## ✅ 推荐实施步骤

1. **立即修复**: 采用方案 B（5分钟）
   - 在 config.yaml 根级别添加邮件配置
   - 重新运行测试验证

2. **长期优化**: 采用方案 A（15分钟）
   - 修复 processor.py 的配置读取逻辑
   - 统一配置结构
   - 提交代码

---

## 🧪 快速验证

添加配置后，运行以下命令验证：

```bash
python3 << 'EOF'
import yaml
with open('config/config.yaml', 'r') as f:
    config = yaml.safe_load(f)

email_from = config.get("EMAIL_FROM", "未设置")
email_to = config.get("EMAIL_TO", "未设置")

print(f"EMAIL_FROM: {email_from}")
print(f"EMAIL_TO: {email_to}")

if email_from and email_to:
    print("✅ 邮件配置已设置")
else:
    print("❌ 邮件配置不完整")
EOF
```

---

## 📝 注意事项

### 安全警告 ⚠️
1. **不要提交密码到 Git**: `config.yaml` 包含敏感信息，已在 `.gitignore` 中
2. **使用环境变量**: 生产环境建议使用环境变量
3. **使用授权码**: 163邮箱等需要使用授权码而非登录密码

### 163邮箱特殊说明
- SMTP服务器: `smtp.163.com`
- SMTP端口: `465` (SSL) 或 `994` (SSL)
- 需要授权码: 需要在163邮箱设置中开启SMTP服务并获取授权码

---

**报告生成时间**: 2026-02-07
**问题类型**: 配置路径不匹配
**优先级**: 中（不影响核心功能，仅影响通知）
