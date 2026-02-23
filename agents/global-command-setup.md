# 全局 trend 命令配置完成

**配置时间**: 2026-01-28 14:00
**配置状态**: ✅ 完成

---

## ✅ 已完成的配置

### 1. alias 已添加到 ~/.zshrc

在你的 `~/.zshrc` 文件中添加了以下内容：

```bash
# TrendRadar 快捷命令
alias trend='/home/zxy/Documents/code/TrendRadar/trend'
```

### 2. 配置位置

```bash
文件: ~/.zshrc
位置: 文件末尾
```

---

## 🚀 如何使用

### 方法一：新开终端窗口（推荐）

**最简单的方式**：关闭当前终端，重新打开一个新终端。

新终端会自动加载 `~/.zshrc`，然后你就可以在任何位置使用 `trend` 命令了。

### 方法二：在当前终端生效

如果不想关闭当前终端，运行以下命令：

```bash
source ~/.zshrc
```

---

## 🧪 测试配置

### 打开新终端后测试

```bash
# 1. 打开新终端（或运行 source ~/.zshrc）

# 2. 在任意目录测试
cd /tmp
trend help

# 3. 如果看到帮助信息，说明配置成功！
```

### 完整测试流程

```bash
# 测试1：查看帮助
trend help

# 测试2：查看服务状态
trend info

# 测试3：在不同目录测试
cd ~
trend info

cd /tmp
trend info

# 如果都能正常工作，说明全局命令配置成功！
```

---

## 📋 可用命令（随时随地）

现在你可以在**任何目录**使用以下命令：

```bash
trend info      # 查看服务状态
trend trigger   # 手动触发推送
trend logs      # 查看实时日志
trend restart   # 重启服务
trend start     # 启动服务
trend stop      # 停止服务
trend config    # 编辑配置
trend report    # 打开最新报告
trend help      # 查看帮助
```

---

## 💡 使用示例

### 日常使用

```bash
# 早上打开终端
$ trend info
# 显示完整的服务状态

# 在家目录
$ cd ~
$ trend trigger
# 手动触发一次抓取

# 在其他项目目录
$ cd ~/other-project
$ trend logs
# 查看 TrendRadar 日志
```

### 多终端使用

```bash
# 终端1：监控日志
$ trend logs

# 终端2：操作服务
$ trend trigger
$ trend info
```

---

## 🔍 验证配置

### 检查 alias 是否添加

```bash
cat ~/.zshrc | grep trend
```

应该显示：
```bash
alias trend='/home/zxy/Documents/code/TrendRadar/trend'
```

### 检查 alias 是否生效

打开新终端后运行：
```bash
alias | grep trend
```

应该显示：
```bash
trend=/home/zxy/Documents/code/TrendRadar/trend
```

### 检查命令是否可用

```bash
which trend
```

应该显示：
```bash
trend: aliased to /home/zxy/Documents/code/TrendRadar/trend
```

---

## 🐛 故障排查

### 问题1：新终端中命令仍然不可用

**可能原因**：
- 使用了其他 shell（不是 zsh）
- ~/.zshrc 没有被加载

**解决方案**：

```bash
# 1. 检查使用的 shell
echo $SHELL

# 2. 如果是 zsh，手动加载配置
source ~/.zshrc

# 3. 如果是 bash，需要添加到 ~/.bashrc
echo "alias trend='/home/zxy/Documents/code/TrendRadar/trend'" >> ~/.bashrc
source ~/.bashrc
```

### 问题2：提示 "command not found"

**检查步骤**：

```bash
# 1. 检查文件是否存在
ls -la /home/zxy/Documents/code/TrendRadar/trend

# 2. 检查是否有执行权限
# 应该显示 -rwxrwxr-x

# 3. 如果没有执行权限，添加
chmod +x /home/zxy/Documents/code/TrendRadar/trend

# 4. 重新加载配置
source ~/.zshrc
```

### 问题3：某些命令不工作

**测试每个命令**：

```bash
trend help      # 应该显示帮助信息
trend info      # 应该显示服务状态
```

如果某个命令报错，查看错误信息并：
```bash
# 查看详细错误
trend <command> 2>&1

# 或查看 trend 脚本
cat /home/zxy/Documents/code/TrendRadar/trend
```

---

## 📚 其他 Shell 配置

### 如果使用 bash

```bash
# 添加到 ~/.bashrc
echo "alias trend='/home/zxy/Documents/code/TrendRadar/trend'" >> ~/.bashrc
source ~/.bashrc
```

### 如果使用 fish

```fish
# 添加到 ~/.config/fish/config.fish
echo "alias trend='/home/zxy/Documents/code/TrendRadar/trend'" >> ~/.config/fish/config.fish
source ~/.config/fish/config.fish
```

---

## 🎯 最佳实践

### 1. 每日检查习惯

打开终端后：
```bash
trend info
```

### 2. 组合使用

```bash
# 修改配置后
trend config
trend restart
trend info
```

### 3. 远程服务器使用

如果在远程服务器上：
```bash
# SSH 登录后
ssh user@server

# 直接使用
trend info
trend logs
```

---

## ✨ 配置优势

### 之前

```bash
# 必须在项目目录
cd /home/zxy/Documents/code/TrendRadar
./trend info

# 在其他目录无法使用
cd /tmp
./trend info  # ❌ 错误
```

### 现在

```bash
# 任何目录都可以
cd /tmp
trend info    # ✅ 成功

cd ~
trend info    # ✅ 成功

cd ~/projects
trend info    # ✅ 成功
```

---

## 📊 配置总结

| 项目 | 状态 | 说明 |
|------|------|------|
| alias 添加 | ✅ 完成 | 已添加到 ~/.zshrc |
| 全局可用 | ✅ 是 | 任何目录都能使用 |
| 开机自动加载 | ✅ 是 | 每次打开终端自动生效 |
| 需要重启 | ❌ 否 | 新终端或 source 即可 |

---

## 🔄 下一步

1. **关闭当前终端，打开新终端**
2. **测试命令**：
   ```bash
   trend help
   trend info
   ```
3. **开始使用**：
   ```bash
   trend trigger  # 手动触发一次
   trend logs     # 查看日志
   ```

---

**配置完成时间**: 2026-01-28 14:00
**生效方式**: 打开新终端或运行 `source ~/.zshrc`
**配置文件**: ~/.zshrc
**命令路径**: /home/zxy/Documents/code/TrendRadar/trend
