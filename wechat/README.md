# 微信公众号订阅模块

基于 Wewe-RSS 的微信公众号订阅、AI 分析和邮件推送服务。

## 功能特性

- 自动获取微信公众号文章（基于 Wewe-RSS + 微信读书）
- 两类公众号差异化处理：
  - **第一类（关键信息）**：保留完整原文 + AI 生成摘要
  - **第二类（普通信息）**：AI 按话题聚合分析
- 每日 23:00 自动推送邮件
- 账号失效自动提醒

## 快速开始

### 1. 环境准备

```bash
# 进入模块目录
cd wechat/

# 复制环境变量配置
cp .env.example .env

# 编辑 .env 填写必要配置
vim .env
```

### 2. 启动服务

```bash
# 启动 Docker 服务
docker-compose up -d

# 查看日志
docker-compose logs -f
```

### 3. 配置 Wewe-RSS

1. 浏览器访问 http://localhost:4000
2. 输入 AUTH_CODE 进入后台
3. 添加账号：微信扫码登录微信读书
4. 添加公众号：通过分享链接添加

### 4. 配置公众号列表

编辑 `config.yaml`，将 Wewe-RSS 中的 feed_id 填入配置：

```yaml
feeds:
  critical:  # 第一类：关键信息
    - id: "example"
      name: "示例公众号"
      wewe_feed_id: "MP_WXS_xxx"  # 从 Wewe-RSS 获取
      enabled: true
  
  normal:  # 第二类：普通信息
    - id: "example2"
      name: "示例公众号2"
      wewe_feed_id: "MP_WXS_xxx"
      enabled: true
```

### 5. 手动测试

```bash
# 执行完整流程
docker exec wechat-service python main.py run

# 仅检查账号状态
docker exec wechat-service python main.py monitor

# 测试邮件发送
docker exec wechat-service python main.py test-email
```

## 目录结构

```
wechat/
├── docker-compose.yml    # Docker 编排配置
├── Dockerfile            # 服务镜像构建
├── config.yaml           # 配置文件
├── .env.example          # 环境变量示例
├── main.py               # 主入口
├── requirements.txt      # Python 依赖
├── src/                  # 源代码
│   ├── collector.py      # 数据采集
│   ├── analyzer.py       # AI 分析
│   ├── notifier.py       # 邮件推送
│   ├── monitor.py        # 账号监控
│   └── ...
├── prompts/              # AI 提示词
├── templates/            # 邮件模板
└── data/                 # 数据目录（运行时生成）
```

## 配置说明

### 环境变量 (.env)

| 变量 | 说明 | 示例 |
|------|------|------|
| `WEWE_AUTH_CODE` | Wewe-RSS 后台授权码 | `123456` |
| `AI_API_KEY` | AI API 密钥 | `sk-xxx` |
| `EMAIL_FROM` | 发件人邮箱 | `user@163.com` |
| `EMAIL_PASSWORD` | 邮箱授权码 | `xxx` |
| `EMAIL_TO` | 收件人邮箱 | `user@example.com` |

### 配置文件 (config.yaml)

详见 `config.yaml` 中的注释说明。

## 维护说明

### 账号失效处理

Wewe-RSS 的微信读书登录状态通常在 2-3 天后失效，届时需要重新扫码：

1. 收到账号失效提醒邮件
2. 访问 Wewe-RSS 后台 http://localhost:4000
3. 进入「账号管理」→「添加账号」
4. 微信扫码重新登录

### 日志查看

```bash
# 查看 wechat-service 日志
docker logs -f wechat-service

# 查看 wewe-rss 日志
docker logs -f wewe-rss
```

## 常见问题

**Q: 为什么收不到邮件？**
- 检查邮箱配置是否正确
- 检查垃圾邮件箱
- 运行 `python main.py test-email` 测试

**Q: 账号状态显示"今日小黑屋"？**
- 请求频率过高被限制，等待 24 小时自动恢复

**Q: 如何添加新的公众号？**
1. 在 Wewe-RSS 后台添加公众号
2. 获取 feed_id（格式：MP_WXS_xxx）
3. 在 config.yaml 中配置
