# 微信公众号日报邮件发送配置指南

## 问题诊断

**错误**: `(535, b'Error: authentication failed')`

**原因**: 163邮箱授权码已过期或不正确

---

## 🔧 解决步骤

### 步骤1: 获取163邮箱授权码

1. **登录163邮箱**
   - 访问: https://mail.163.com
   - 使用你的账号登录: {{EMAIL_ADDRESS}}

2. **进入设置**
   - 点击右上角 "设置"
   - 选择 "POP3/SMTP/IMAP"

3. **开启SMTP服务**
   - 找到 "SMTP服务"
   - 点击开启（如果未开启）
   - 可能需要手机验证码验证

4. **生成授权码**
   - 点击 "客户端授权密码"
   - 可能需要再次验证手机
   - **重要**: 生成新的授权码（16位字符）
   - 复制授权码并保存

### 步骤2: 更新配置

#### 方式1: 更新环境变量（推荐）

```bash
# 编辑 ~/.bashrc 或 ~/.zshrc
export EMAIL_PASSWORD="你新生成的16位授权码"

# 重新加载配置
source ~/.bashrc  # 或 source ~/.zshrc
```

#### 方式2: 更新配置文件

编辑 `wechat/config.yaml`:

```yaml
email:
  from: "{{EMAIL_ADDRESS}}"
  password: "你新生成的16位授权码"  # 粘贴新授权码
  to: "{{EMAIL_ADDRESS}}"
  smtp_server: "smtp.163.com"
  smtp_port: "465"
```

### 步骤3: 测试发送

```bash
# 方式1: 使用测试脚本
cd /home/zxy/Documents/code/TrendRadar
python agents/test_wechat_ai.py

# 方式2: 直接发送邮件
python3 << 'EOF'
import sys, os, smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.utils import formataddr
from pathlib import Path

sys.path.insert(0, 'wechat')
from src.config_loader import ConfigLoader

config = ConfigLoader('wechat/config.yaml')
html_file = Path('wechat/data/output/wechat_daily_20260202_194113.html')

with open(html_file, 'r', encoding='utf-8') as f:
    html_content = f.read()

msg = MIMEMultipart('alternative')
msg['Subject'] = "📱 测试邮件"
msg['From'] = formataddr(('微信公众号订阅', config.email.from_addr))
msg['To'] = config.email.to_addr
msg.attach(MIMEText(html_content, 'html', 'utf-8'))

with smtplib.SMTP_SSL(config.email.smtp_server, 465, timeout=30) as server:
    server.login(config.email.from_addr, config.email.password)
    server.sendmail(config.email.from_addr, config.email.to_addr.split(','), msg.as_string())

print("✅ 测试邮件发送成功！")
EOF
```

---

## ⚠️ 常见问题

### Q1: 什么是授权码？
**A**: 授权码是163邮箱用于第三方客户端（如Outlook、手机邮件App等）登录的专用密码，**不是邮箱登录密码**。

### Q2: 为什么需要授权码？
**A**: 为了增强安全性，163邮箱禁止在第三方客户端中使用登录密码，必须使用授权码。

### Q3: 授权码会过期吗？
**A**: 会！授权码通常有效期为几个月到一年。过期后需要重新生成。

### Q4: 如何查看授权码是否有效？
**A**: 无法直接查看，只能通过测试发送邮件来验证。

---

## 📋 验证清单

完成配置后，请验证：

- [ ] 163邮箱SMTP服务已开启
- [ ] 已生成新的16位授权码
- [ ] 授权码已更新到配置文件或环境变量
- [ ] 测试邮件发送成功
- [ ] 收件箱能收到测试邮件

---

## 🚀 正常使用

配置完成后，发送日报只需：

```bash
# 禁用代理（重要！）
unset all_proxy

# 设置API Key
export AI_API_KEY="{{SILICONFLOW_API_KEY}}"

# 发送日报
cd wechat && python main.py run
```

或从项目根目录：

```bash
python -m trendradar.cli run wechat
```

---

## 📞 163邮箱帮助

如果遇到问题，可以参考163官方文档：
- POP3/SMTP/IMAP设置: https://help.mail.163.com/

---

生成时间: 2026-02-02
配置文件: wechat/config.yaml
