# trend 命令行工具使用指南

**创建时间**: 2026-01-28 13:51
**工具版本**: 1.0

---

## 📋 概述

`trend` 是 TrendRadar 的统一命令行工具，提供简洁友好的命令来管理和监控服务。

---

## 🚀 快速开始

### 基本使用

```bash
cd /home/zxy/Documents/code/TrendRadar
./trend <command>
```

### 设置全局命令（推荐）

添加到 shell 配置文件（~/.bashrc 或 ~/.zshrc）：

```bash
# TrendRadar 快捷命令
alias trend='/home/zxy/Documents/code/TrendRadar/trend'
```

生效配置：
```bash
source ~/.bashrc  # 或 source ~/.zshrc
```

之后可以在任何目录直接使用：
```bash
trend info
```

---

## 📚 命令列表

### 1. info - 查看服务状态 ⭐

查看完整的服务状态面板。

```bash
trend info
# 或
trend --info
trend -i
```

**显示内容**：
- 容器运行状态
- 自动化配置
- 定时任务状态和下次执行时间
- 最近执行记录
- 邮件推送状态
- 数据存储信息
- 监控平台列表
- 快速操作指南

**使用场景**：
- 每日检查服务状态
- 问题排查前确认状态
- 修改配置后验证

---

### 2. trigger - 手动触发抓取 ⭐

立即执行一次数据抓取和推送（不等待定时任务）。

```bash
trend trigger
# 或
trend --trigger
trend -t
```

**执行流程**：
1. 抓取所有平台的热点数据
2. 生成 HTML 报告
3. 如果在推送窗口内，发送邮件

**使用场景**：
- 测试配置是否正常
- 需要立即获取最新数据
- 验证邮件推送功能

**注意事项**：
- 执行时间约 10-30 秒
- 会受到推送时间窗口限制
- 邮件推送每天只会发送一次

---

### 3. logs - 查看实时日志

实时查看容器日志输出。

```bash
trend logs
# 或
trend --logs
trend -l
```

**操作说明**：
- 显示最近 50 行日志
- 自动跟踪新日志
- 按 `Ctrl+C` 退出

**使用场景**：
- 监控定时任务执行
- 排查错误问题
- 查看推送记录

---

### 4. restart - 重启服务

重启 TrendRadar 容器。

```bash
trend restart
# 或
trend --restart
trend -r
```

**执行过程**：
1. 检查容器状态
2. 重启容器
3. 显示重启后状态

**使用场景**：
- 修改配置后生效
- 服务出现异常
- 更新代码后重启

**注意事项**：
- 会中断正在执行的抓取任务
- 重启时间约 5-10 秒
- 定时任务会自动恢复

---

### 5. start - 启动服务

启动已停止的服务。

```bash
trend start
# 或
trend --start
```

**执行过程**：
1. 检查容器是否已运行
2. 如果未运行，启动容器
3. 显示启动状态

**使用场景**：
- 首次部署启动
- stop 后重新启动
- 系统重启后手动启动（通常自动启动）

---

### 6. stop - 停止服务

停止运行中的服务。

```bash
trend stop
# 或
trend --stop
```

**执行过程**：
1. 确认操作（需要输入 y）
2. 停止并删除容器
3. 保留数据和配置

**使用场景**：
- 临时停止服务
- 维护前停止
- 节省系统资源

**注意事项**：
- 需要手动确认
- 数据不会丢失
- 重新启动需要用 `trend start`

---

### 7. config - 编辑配置

打开配置文件进行编辑。

```bash
trend config
# 或
trend --config
trend -c
```

**编辑器优先级**：
1. nano（如果可用）
2. vim
3. vi

**编辑后**：
- 保存并退出编辑器
- 运行 `trend restart` 使配置生效

**使用场景**：
- 修改监控平台
- 调整推送时间
- 更新邮箱配置
- 修改抓取频率

---

### 8. report - 打开最新报告

在浏览器中打开最新的 HTML 报告。

```bash
trend report
# 或
trend --report
```

**执行过程**：
1. 查找最新报告文件
2. 显示报告信息（大小、时间）
3. 自动在浏览器中打开

**支持的系统**：
- Linux: 使用 xdg-open
- macOS: 使用 open
- 其他: 显示文件路径手动打开

**使用场景**：
- 查看最新热点新闻
- 验证数据抓取结果
- 浏览历史报告

---

### 9. help - 帮助信息

显示命令帮助。

```bash
trend help
# 或
trend --help
trend -h
# 或不带参数
trend
```

---

## 🎯 使用示例

### 日常使用流程

```bash
# 早上检查服务状态
trend info

# 查看最新报告
trend report

# 需要时手动触发一次
trend trigger

# 查看执行日志
trend logs
```

### 配置修改流程

```bash
# 1. 编辑配置
trend config

# 2. 保存退出后重启
trend restart

# 3. 确认状态
trend info

# 4. 测试执行
trend trigger
```

### 问题排查流程

```bash
# 1. 检查服务状态
trend info

# 2. 查看实时日志
trend logs

# 3. 如有异常，重启服务
trend restart

# 4. 验证恢复
trend info
```

---

## 💡 最佳实践

### 1. 设置全局命令

在 `~/.bashrc` 或 `~/.zshrc` 中添加：

```bash
alias trend='/home/zxy/Documents/code/TrendRadar/trend'

# 可选：添加命令补全
complete -W "info trigger logs restart start stop config report help" trend
```

### 2. 每日检查习惯

创建一个早晨检查脚本：

```bash
#!/bin/bash
# ~/morning-check.sh

echo "检查 TrendRadar 服务状态..."
trend info

echo ""
echo "按回车打开最新报告..."
read
trend report
```

### 3. 配合 cron 监控

虽然服务内置定时任务，但也可以添加外部监控：

```bash
# crontab -e
# 每小时检查服务状态并记录
0 * * * * /home/zxy/Documents/code/TrendRadar/trend info >> /tmp/trend-monitor.log 2>&1
```

### 4. 快捷键绑定（可选）

如果使用支持自定义快捷键的终端，可以绑定：

- `Ctrl+Alt+T` → `trend info`
- `Ctrl+Alt+L` → `trend logs`

---

## 📊 命令对比

### 与直接 Docker 命令对比

| 操作 | trend 命令 | Docker 命令 |
|------|-----------|------------|
| 查看状态 | `trend info` | 多个命令组合 |
| 手动执行 | `trend trigger` | `docker exec -it trendradar python manage.py run` |
| 查看日志 | `trend logs` | `docker logs trendradar -f` |
| 重启服务 | `trend restart` | `docker restart trendradar` |
| 停止服务 | `trend stop` | `cd docker && docker compose down` |

**优势**：
- ✅ 更简洁易记
- ✅ 统一的命令风格
- ✅ 友好的错误提示
- ✅ 自动确认和验证
- ✅ 彩色输出

---

## 🔧 高级技巧

### 1. 组合使用

```bash
# 修改配置并立即测试
trend config && trend restart && trend trigger
```

### 2. 后台监控

```bash
# 终端1：实时日志
trend logs

# 终端2：手动触发
trend trigger
```

### 3. 状态监控循环

```bash
# 每10秒刷新一次状态
watch -n 10 'trend info'
```

### 4. 集成到脚本

```bash
#!/bin/bash
# deploy.sh - 部署脚本

echo "拉取最新代码..."
git pull

echo "重启服务..."
trend restart

echo "等待5秒..."
sleep 5

echo "检查状态..."
trend info

echo "执行一次测试..."
trend trigger
```

---

## 🐛 故障排查

### 问题1：命令不存在

```bash
bash: trend: command not found
```

**解决方案**：

```bash
# 方案1：使用完整路径
/home/zxy/Documents/code/TrendRadar/trend info

# 方案2：添加到 PATH
export PATH="$PATH:/home/zxy/Documents/code/TrendRadar"

# 方案3：使用 alias（推荐）
alias trend='/home/zxy/Documents/code/TrendRadar/trend'
```

### 问题2：权限错误

```bash
Permission denied
```

**解决方案**：
```bash
chmod +x /home/zxy/Documents/code/TrendRadar/trend
```

### 问题3：容器未运行

```bash
❌ 错误: trendradar 容器未运行
```

**解决方案**：
```bash
trend start
```

---

## 📈 命令统计

### 使用频率（预估）

| 命令 | 使用频率 | 说明 |
|------|---------|------|
| info | ⭐⭐⭐⭐⭐ | 最常用，每日必用 |
| logs | ⭐⭐⭐⭐ | 问题排查常用 |
| trigger | ⭐⭐⭐ | 测试时常用 |
| restart | ⭐⭐ | 修改配置后使用 |
| config | ⭐⭐ | 需要调整配置时 |
| report | ⭐⭐ | 查看报告时 |
| start | ⭐ | 偶尔使用 |
| stop | ⭐ | 很少使用 |

---

## 🎨 输出示例

### info 命令输出

```
📊 正在获取服务状态...

════════════════════════════════════════
        TrendRadar 服务状态监控面板
════════════════════════════════════════

📦 容器运行状态
  状态: ✅ 服务正常运行

⏰ 定时任务状态
  任务调度器: ✅ supercronic (PID 1)
  执行频率: */30 * * * * (每 30 分钟)
  下次执行: 14:00:00 (5 分钟后)
...
```

### trigger 命令输出

```
🚀 手动触发数据抓取和推送...

⏳ 执行中，请稍候...

开始爬取数据...
获取 toutiao 成功（最新数据）
...
HTML报告已生成: output/html/2026-01-28/13-55.html

✅ 执行完成！
💡 查看最新报告: trend report
```

---

## 📚 相关文档

- [服务状态脚本指南](./status-script-guide.md)
- [快速开始指南](../快速开始.md)
- [Docker 部署文档](./docker-deployment-fix.md)

---

## 🔮 未来计划

### 计划添加的命令

- `trend version` - 检查版本更新
- `trend backup` - 备份配置和数据
- `trend test` - 测试通知渠道
- `trend stats` - 统计数据分析
- `trend export` - 导出报告数据

---

**工具创建时间**: 2026-01-28 13:51
**最后更新**: 2026-01-28 13:51
**维护者**: Claude (Sonnet 4.5)
