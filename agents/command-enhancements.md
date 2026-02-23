# TrendRadar 命令增强：部署信息与固定报告

**时间**: 2026-01-28 15:45 - 16:00
**任务**: 增强 trend 命令，提升用户体验
**状态**: ✅ 已完成

---

## 📋 需求背景

用户希望：
1. 在 `trend info` 中查看生产环境部署信息
2. 获得一个固定的本地 HTML 地址，可以收藏到浏览器随时查看最新报告

---

## 🔧 实现内容

### 1. 增强 `trend info` 命令

**新增功能**：
- 在服务状态监控面板前，显示生产环境部署信息
- 对比显示生产版本和开发版本
- 显示容器运行状态
- 提供快速管理命令提示

**显示内容**：
```
═══════════════════════════════════════════════
  生产环境部署信息
═══════════════════════════════════════════════

📦 部署目录: /home/zxy/Documents/install/trendradar
🚀 生产版本: v5.4.0
🔧 开发版本: v5.5.0
⏮️  上一版本: 无
📚 版本总数: 1
🐳 生产容器: 运行中 ✅

NAMES                 STATUS
trendradar-prod       Up 10 minutes
trendradar-mcp-prod   Up 10 minutes

💡 管理命令:
   查看所有版本: trend versions
   发布新版本: trend deploy
   更新版本: trend update <version>
```

**实现要点**：
- 加载 `version-manager.sh` 工具库函数
- 读取生产环境的 `manifest.yaml`
- 对比开发环境的 `version` 文件
- 颜色区分：生产版本（绿色）、开发版本（蓝色）

---

### 2. 增强 `trend report` 命令

**新增功能**：
- 优先显示生产环境的固定报告地址
- 提供 `file://` 协议的完整 URL，可直接收藏
- 检测 Web 服务器状态，显示 HTTP 访问地址
- 提供详细的使用说明

**显示效果**：
```
📄 查找最新报告...

🌐 生产环境最新报告

📄 文件路径: /home/zxy/Documents/install/trendradar/shared/output/html/latest/current.html
📏 文件大小: 100K
🕒 更新时间: 2026-01-28 15:38:40

═══════════════════════════════════════════════
🔖 固定访问地址（推荐收藏到浏览器）:
file:///home/zxy/Documents/install/trendradar/shared/output/html/latest/current.html
═══════════════════════════════════════════════

💡 使用提示:
   1. 复制上面的地址到浏览器打开
   2. 按 Ctrl+D 收藏此页面
   3. 以后打开收藏即可查看最新报告（自动更新）

🚀 正在浏览器中打开...
```

**实现亮点**：
- 使用 `latest/current.html` 作为固定文件名
- 系统每次生成报告时自动更新此文件
- 浏览器收藏的是地址而非内容，每次打开都是最新的
- 支持自动打开浏览器（`xdg-open` / `open`）

---

### 3. 创建书签文件

**文件位置**：`/home/zxy/Documents/bookmark-trendradar.txt`

**内容**：
```
file:///home/zxy/Documents/install/trendradar/shared/output/html/latest/current.html
```

**用途**：
- 快速复制固定地址
- 备份书签链接

---

## 📊 代码改动

### 修改文件

**`trend` 文件改动**：

1. **添加全局配置**（第 17-25 行）：
```bash
# 生产环境配置
PROD_BASE="/home/zxy/Documents/install/trendradar"
MANIFEST_FILE="$PROD_BASE/versions/manifest.yaml"

# 加载版本管理工具函数（如果存在）
if [ -f "$DEPLOY_DIR/version-manager.sh" ]; then
    source "$DEPLOY_DIR/version-manager.sh"
fi
```

2. **增强 `cmd_info()` 函数**（第 95-151 行）：
```bash
# 显示生产环境部署信息
if [ -f "$MANIFEST_FILE" ]; then
    # 读取版本信息
    CURRENT_VERSION=$(get_current_version 2>/dev/null || echo "未部署")
    PREVIOUS_VERSION=$(get_previous_version 2>/dev/null || echo "null")
    VERSION_COUNT=$(list_versions 2>/dev/null | wc -l)
    DEV_VERSION=$(cat "$SCRIPT_DIR/version" 2>/dev/null | tr -d '[:space:]' || echo "未知")

    # 显示部署信息面板
    # ...

    # 显示容器状态
    # ...
fi

# 显示开发环境状态
cd "$DOCKER_DIR" && ./status.sh
```

3. **重构 `cmd_report()` 函数**（第 292-360 行）：
```bash
local latest_report=""
local file_url=""

# 优先查找生产环境的报告
if [ -f "$PROD_BASE/shared/output/html/latest/current.html" ]; then
    latest_report="$PROD_BASE/shared/output/html/latest/current.html"
    echo -e "${GREEN}🌐 生产环境最新报告${NC}"
# 查找开发环境的报告
elif [ -f "$SCRIPT_DIR/output/html/latest/current.html" ]; then
    latest_report="$SCRIPT_DIR/output/html/latest/current.html"
    echo -e "${CYAN}🔧 开发环境最新报告${NC}"
else
    echo -e "${RED}❌ 未找到报告文件${NC}"
    exit 1
fi

file_url="file://$latest_report"

# 显示完整信息和固定地址
# ...

# 自动打开浏览器
xdg-open "$latest_report" 2>/dev/null &
```

---

## 🎯 使用场景

### 场景 1：查看环境状态
```bash
trend info

# 输出：
# - 生产环境：v5.4.0（运行中）
# - 开发环境：v5.5.0（开发中）
# - 容器状态、定时任务等详细信息
```

### 场景 2：收藏报告页面
```bash
trend report

# 操作：
# 1. 复制显示的 file:// 地址
# 2. 在浏览器打开
# 3. Ctrl+D 收藏
# 4. 以后一键打开查看最新热点
```

### 场景 3：快速对比版本
```bash
trend info

# 看到：
# 🚀 生产版本: v5.4.0
# 🔧 开发版本: v5.5.0
# → 开发版本比生产版本新，可以考虑发布
```

---

## 💡 设计思路

### 1. 环境信息展示原则
- **颜色区分**：生产（绿色）、开发（蓝色）、警告（黄色）、错误（红色）
- **信息层次**：重要信息前置，详细信息后置
- **操作提示**：显示相关命令，降低使用门槛

### 2. 固定地址实现原理
- **固定文件名**：`latest/current.html` 永远存在且自动更新
- **file:// 协议**：浏览器直接访问本地文件系统，无需服务器
- **收藏机制**：浏览器收藏地址而非内容，每次打开读取最新文件

### 3. 用户体验优化
- **一键操作**：`trend report` 自动打开浏览器
- **地址可见**：明确显示可收藏的固定地址
- **使用提示**：step-by-step 引导用户操作

---

## 🔍 技术细节

### 版本信息读取
```bash
# 读取生产版本
CURRENT_VERSION=$(get_current_version 2>/dev/null || echo "未部署")

# 读取开发版本
DEV_VERSION=$(cat "$SCRIPT_DIR/version" 2>/dev/null | tr -d '[:space:]' || echo "未知")

# 对比显示
if [ "$CURRENT_VERSION" = "未部署" ] || [ "$CURRENT_VERSION" = "null" ]; then
    echo -e "${CYAN}🚀 生产版本:${NC} ${RED}未部署${NC}"
else
    echo -e "${CYAN}🚀 生产版本:${NC} ${GREEN}v${CURRENT_VERSION}${NC}"
fi
```

### 文件路径处理
```bash
# 优先级：生产环境 > 开发环境
if [ -f "$PROD_BASE/shared/output/html/latest/current.html" ]; then
    latest_report="$PROD_BASE/shared/output/html/latest/current.html"
elif [ -f "$SCRIPT_DIR/output/html/latest/current.html" ]; then
    latest_report="$SCRIPT_DIR/output/html/latest/current.html"
fi

# 生成 file:// URL
file_url="file://$latest_report"
```

### Web 服务器检测
```bash
# 检查是否启用了 Web 服务器
if [ -f "$PROD_BASE/shared/.env" ] && \
   grep -q "ENABLE_WEBSERVER=true" "$PROD_BASE/shared/.env" 2>/dev/null; then
    if docker ps --format "{{.Names}}" | grep -q "trendradar-prod"; then
        echo -e "${CYAN}🌐 Web 服务器地址:${NC} ${YELLOW}http://localhost:8080/html/latest/current.html${NC}"
    fi
fi
```

---

## ✅ 测试验证

### 测试 `trend info`
```bash
trend info

# 验证：
# ✓ 显示生产环境部署信息
# ✓ 显示生产版本 v5.4.0
# ✓ 显示开发版本 v5.5.0
# ✓ 显示容器运行状态
# ✓ 显示管理命令提示
# ✓ 显示完整的服务状态面板
```

### 测试 `trend report`
```bash
trend report

# 验证：
# ✓ 找到生产环境报告
# ✓ 显示固定的 file:// 地址
# ✓ 显示文件大小和更新时间
# ✓ 显示使用提示
# ✓ 自动打开浏览器
# ✓ 地址可以在浏览器中正常访问
```

### 书签功能测试
```bash
# 1. 复制固定地址
cat ~/Documents/bookmark-trendradar.txt

# 2. 在浏览器打开
# 3. 按 Ctrl+D 收藏
# 4. 关闭浏览器，重新打开收藏
# 5. 验证显示最新报告内容
```

---

## 📝 相关文档

- [trend 命令行工具指南](./trend-command-guide.md) - 基础命令说明
- [版本管理系统](./version-management-system.md) - 版本管理实现
- [deploy/README.md](../deploy/README.md) - 生产环境部署指南

---

## 🎓 学习要点

### Shell 函数库复用
通过 `source` 加载工具库，实现函数复用：
```bash
if [ -f "$DEPLOY_DIR/version-manager.sh" ]; then
    source "$DEPLOY_DIR/version-manager.sh"
fi

# 之后可以直接调用工具库中的函数
CURRENT_VERSION=$(get_current_version)
```

### 条件信息展示
根据环境状态动态调整显示内容：
```bash
# 有生产环境：显示完整部署信息
if [ -f "$MANIFEST_FILE" ]; then
    # 显示生产环境信息面板
fi

# 无生产环境：跳过
```

### 文件协议 URL
`file://` 协议让浏览器直接访问本地文件：
```bash
file:///home/zxy/Documents/install/trendradar/shared/output/html/latest/current.html
```
- 三个斜杠：`file://` + `/绝对路径`
- 可以直接在浏览器地址栏输入
- 可以收藏，每次打开都是最新内容

---

**实现者**: Claude Code (AI Assistant)
**审核者**: zxy
**文档版本**: 1.0
