# 服务状态监控脚本使用指南

**创建时间**: 2026-01-28 12:04
**脚本版本**: 1.0

---

## 📋 概述

为了方便实时监控 TrendRadar 服务状态，创建了一个美观的状态监控脚本，可以一键查看所有关键信息。

---

## 🚀 快速使用

### 方法一：在项目根目录运行（推荐）

```bash
cd /home/zxy/Documents/code/TrendRadar
./status
```

### 方法二：在 docker 目录运行

```bash
cd /home/zxy/Documents/code/TrendRadar/docker
./status.sh
```

### 方法三：从任意位置运行

```bash
/home/zxy/Documents/code/TrendRadar/status
```

---

## 📊 显示内容

### 1. 📦 容器运行状态
- 容器名称
- 运行时长
- 端口映射
- 整体运行状态

### 2. 🔄 自动化配置
- 容器重启策略（unless-stopped）
- Docker 服务开机自启状态

### 3. ⏰ 定时任务状态
- 任务调度器状态（supercronic）
- 执行频率（cron 表达式）
- **下次执行时间**（动态计算）
- 距离下次执行的倒计时

### 4. 📝 最近执行记录
- 最后一次抓取时间
- 生成的报告文件路径
- 抓取的新闻条数

### 5. 📧 邮件推送状态
- 邮件配置状态
- 发件邮箱地址
- 最近一次推送状态
- 推送时间和内容
- 推送时间窗口设置

### 6. 💾 数据存储信息
- 今日生成的报告数量
- 最新报告文件名和大小
- 新闻数据库状态和大小

### 7. 🌐 监控平台
- 当前监控的所有平台列表
- 共 11 个热榜平台

### 8. 🛠️ 快速操作
- 常用命令快捷方式
- 包括查看日志、手动执行、重启等

---

## 🎨 界面特点

### 彩色输出
- ✅ 绿色：正常运行
- ❌ 红色：异常状态
- ⚠️ 黄色：警告或未配置
- 🔵 蓝色：标题
- 🔷 青色：重要信息

### 图标标识
- 📦 容器
- 🔄 自动化
- ⏰ 定时任务
- 📝 执行记录
- 📧 邮件
- 💾 数据存储
- 🌐 平台
- 🛠️ 操作

---

## 📸 输出示例

```
════════════════════════════════════════════════════════════════
        TrendRadar 服务状态监控面板
════════════════════════════════════════════════════════════════

📦 容器运行状态

NAMES                STATUS                  PORTS
trendradar           Up 8 minutes            127.0.0.1:8080->8080/tcp
trendradar-mcp       Up 26 minutes           127.0.0.1:3333->3333/tcp

  状态: ✅ 服务正常运行

🔄 自动化配置

  容器重启策略: ✅ unless-stopped
  Docker 开机自启: ✅ enabled

⏰ 定时任务状态

  任务调度器: ✅ supercronic (PID 1)
  执行频率: */30 * * * * (每 30 分钟)
  下次执行: 12:30:00 (26 分钟后)

📝 最近执行记录

  HTML报告已生成: output/html/2026-01-28/11-55.html

📧 邮件推送状态

  邮件配置: ✅ 已配置
  发件邮箱: {{EMAIL_ADDRESS}}
  最近推送: 成功

💾 数据存储信息

  今日报告: 2 个
  最新报告: 11-55.html (72K)
  新闻数据库: 存在 (252K)

🌐 监控平台

  • 今日头条
  • 百度热搜
  • 华尔街见闻
  ... (共 11 个)

🛠️ 快速操作

  查看实时日志:    docker logs trendradar -f
  手动执行一次:    docker exec -it trendradar python manage.py run
  重启服务:        docker restart trendradar
  停止服务:        docker compose -f docker-compose-build.yml down
  编辑配置:        nano ../config/config.yaml

════════════════════════════════════════════════════════════════
```

---

## 💡 使用场景

### 1. 每日检查
早上打开终端，运行 `./status` 快速了解服务状态。

### 2. 问题排查
当邮件没收到时，运行脚本查看：
- 定时任务是否正常
- 上次推送是否成功
- 下次执行时间

### 3. 维护前确认
修改配置或重启服务前，先查看当前状态。

### 4. 远程监控
SSH 连接服务器后，快速检查服务是否正常。

---

## 🔧 脚本技术细节

### 文件位置
- 主脚本: `docker/status.sh`
- 快捷方式: `status` (项目根目录)

### 依赖工具
- `docker` - 容器管理
- `systemctl` - 服务管理
- `date` - 时间计算
- 标准 Linux 工具：`grep`, `awk`, `sed`, `wc`, `du`

### 权限要求
- 脚本需要执行权限（`chmod +x`）
- 需要能够执行 `docker` 命令
- 需要读取配置文件权限

---

## 🐛 故障排查

### 问题1：权限错误

```bash
bash: ./status: Permission denied
```

**解决**：
```bash
chmod +x status
```

### 问题2：Docker 命令失败

```bash
Got permission denied while trying to connect to the Docker daemon socket
```

**解决**：
```bash
# 添加用户到 docker 组
sudo usermod -aG docker $USER
# 重新登录使权限生效
```

### 问题3：找不到容器

```
状态: ❌ 服务未运行
```

**解决**：
```bash
cd docker
docker compose -f docker-compose-build.yml up -d
```

---

## 🔄 自动化监控

### 定时检查（可选）

可以设置定时任务，每天自动检查并保存状态：

```bash
# 编辑 crontab
crontab -e

# 添加以下行（每天 9:00 检查）
0 9 * * * /home/zxy/Documents/code/TrendRadar/status >> /tmp/trendradar-status.log 2>&1
```

### 健康检查脚本

基于 status.sh 可以扩展为健康检查脚本：

```bash
#!/bin/bash
# health-check.sh
output=$(./status)
if echo "$output" | grep -q "服务正常运行"; then
    echo "健康状态: 正常"
    exit 0
else
    echo "健康状态: 异常"
    exit 1
fi
```

---

## 📈 后续改进计划

### 已实现功能 ✅
- ✅ 容器状态检查
- ✅ 定时任务监控
- ✅ 邮件推送状态
- ✅ 数据存储信息
- ✅ 彩色输出
- ✅ 下次执行时间计算

### 计划增强功能
- 🔲 添加性能监控（CPU、内存使用率）
- 🔲 添加网络连接检查
- 🔲 添加磁盘空间告警
- 🔲 支持 JSON 输出格式
- 🔲 添加历史趋势图表
- 🔲 支持 Webhook 通知

---

## 🎯 最佳实践

### 1. 每日使用习惯
- 早上运行一次，确认服务正常
- 修改配置后立即检查
- 发现异常及时排查

### 2. 配合日志查看
```bash
# 先查看状态
./status

# 如有异常，查看详细日志
docker logs trendradar -f
```

### 3. 定期检查数据
```bash
# 查看状态
./status

# 查看数据目录
ls -lh output/html/$(date +%Y-%m-%d)/
```

---

## 📚 相关文档

- [Docker 部署修复日志](./docker-deployment-fix.md)
- [邮件推送配置](./email-config-success.md)
- [项目主 README](../README.md)

---

## 🔐 安全提示

- 脚本会显示邮箱地址（但不会显示密码）
- 输出可能包含敏感信息，不要随意分享
- 日志文件需要妥善保管

---

**脚本创建时间**: 2026-01-28 12:04
**最后更新**: 2026-01-28 12:04
**维护者**: Claude (Sonnet 4.5)
