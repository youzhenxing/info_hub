# Docker 部署问题修复日志

**修复时间**: 2026-01-28 11:16 - 11:38
**问题类型**: Docker 镜像拉取失败
**修复状态**: ✅ 已解决

---

## 📋 问题描述

用户在部署 TrendRadar Docker 服务时遇到镜像拉取失败的问题，即使配置了多个国内镜像源仍然无法成功。

### 初始症状

1. 使用 `docker pull wantcat/trendradar:latest` 拉取镜像失败
2. 已配置的镜像源：
   - 阿里云镜像源
   - DaoCloud 镜像源
   - 多个备用镜像源（共 22 个）
3. 使用 `docker-compose-build.yml` 本地构建时也遇到问题

### 具体错误

```
ERROR: failed to build: failed to solve: python:3.10-slim:
failed to resolve source metadata for docker.io/library/python:3.10-slim:
unexpected status from HEAD request to
https://xseme2nr.mirror.aliyuncs.com/v2/library/python/manifests/3.10-slim?ns=docker.io:
403 Forbidden
```

---

## 🔍 问题分析

### 根本原因

1. **Docker Hub 镜像源访问受限**
   - 阿里云镜像源返回 403 Forbidden
   - 多个镜像源不稳定或失效

2. **网络下载速度慢**
   - PyPI 默认源下载大型包（如 botocore 14.6MB）速度慢
   - GitHub 文件下载（supercronic）可能超时

3. **构建配置未优化**
   - Dockerfile 未配置国内镜像源
   - 缺少重试和备用下载策略

---

## 🛠️ 修复方案

### 方案一：优化 Dockerfile（主 Dockerfile）

#### 1. 配置 APT 国内镜像源

**位置**: `docker/Dockerfile` 第 9-10 行

```dockerfile
# 配置 APT 使用国内镜像源
RUN sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list.d/debian.sources 2>/dev/null || \
    sed -i 's/deb.debian.org/mirrors.tuna.tsinghua.edu.cn/g' /etc/apt/sources.list
```

**效果**: 加速系统包下载

#### 2. 优化 supercronic 下载

**位置**: `docker/Dockerfile` 第 12-52 行

**关键优化**:
- 添加 ghproxy.com 国内代理
- 优先使用国内代理，失败后尝试直连
- 优化超时设置（15秒连接超时，60秒总超时）

```dockerfile
export SUPERCRONIC_URL_CN=https://ghproxy.com/${SUPERCRONIC_URL};
# 第一次尝试使用国内代理
if [ $i -eq 1 ] && curl -fsSL --connect-timeout 15 --max-time 60 -o "$SUPERCRONIC" "$SUPERCRONIC_URL_CN"; then
    echo "Download successful from CN proxy";
    break;
# 失败后尝试直连
elif curl -fsSL --connect-timeout 15 --max-time 60 -o "$SUPERCRONIC" "$SUPERCRONIC_URL"; then
    echo "Download successful from origin";
    break;
```

#### 3. 配置 PyPI 国内镜像源

**位置**: `docker/Dockerfile` 第 56-57 行

```dockerfile
# 使用国内 PyPI 镜像源加速安装
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

**效果**: 显著提升 Python 包下载速度

### 方案二：优化 Dockerfile.mcp

**位置**: `docker/Dockerfile.mcp` 第 7-8 行

```dockerfile
# 使用国内 PyPI 镜像源加速安装
RUN pip install --no-cache-dir -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
```

### 方案三：创建便捷构建脚本

**文件**: `docker/build-local.sh`

**功能**:
- 自动检查必要文件
- 一键构建本地镜像
- 提供清晰的构建提示

```bash
#!/bin/bash
set -e
echo "开始构建 TrendRadar Docker 镜像"
cd "$(dirname "$0")/.."

# 检查必要文件
if [ ! -f "requirements.txt" ]; then
    echo "错误: requirements.txt 文件不存在"
    exit 1
fi

# 构建主镜像
docker build -f docker/Dockerfile -t trendradar:local .
```

### 方案四：更新 docker-compose-build.yml

**修改**: 添加 `image: trendradar:local` 标签

```yaml
trendradar:
  build:
    context: ..
    dockerfile: docker/Dockerfile
  image: trendradar:local  # 新增：指定镜像标签
  container_name: trendradar
```

---

## 📊 修复执行过程

### 阶段 1: 诊断问题（11:16-11:18）

1. ✅ 检查 Docker 镜像源配置
   ```bash
   docker info | grep -A 5 "Registry Mirrors"
   cat /etc/docker/daemon.json
   ```

2. ✅ 尝试拉取基础镜像
   ```bash
   docker pull python:3.10-slim
   ```
   - 结果：成功拉取（说明部分镜像源可用）

3. ✅ 读取现有 Dockerfile 配置
   - 发现未配置国内镜像源
   - 发现下载策略可以优化

### 阶段 2: 实施修复（11:18-11:25）

1. ✅ 优化 `docker/Dockerfile`
   - 添加 APT 镜像源配置
   - 添加 GitHub 代理
   - 优化 PyPI 镜像源

2. ✅ 优化 `docker/Dockerfile.mcp`
   - 添加 PyPI 镜像源配置

3. ✅ 创建构建脚本 `docker/build-local.sh`

4. ✅ 更新 `docker-compose-build.yml`

### 阶段 3: 验证修复（11:25-11:38）

1. ✅ 执行构建脚本
   ```bash
   cd docker
   ./build-local.sh
   ```
   - 结果：主镜像构建成功

2. ✅ 启动服务
   ```bash
   docker compose -f docker-compose-build.yml up -d --build
   ```
   - 构建 trendradar 镜像：成功
   - 构建 trendradar-mcp 镜像：成功
   - 启动两个容器：成功

3. ✅ 验证服务运行
   ```bash
   docker ps | grep trendradar
   ```
   - trendradar: ✅ 运行中
   - trendradar-mcp: ✅ 运行中

4. ✅ 检查日志
   - 成功抓取 11 个平台数据（255 条）
   - 成功抓取 2 个 RSS 源（23 条）
   - 生成 HTML 报告

---

## 📈 性能对比

### 优化前
- PyPI 包下载速度：30-40 KB/s（botocore 14.6MB 需要 6+ 分钟）
- 构建时间：预计 15-20 分钟（如果不超时）
- 成功率：低（经常因超时失败）

### 优化后
- PyPI 包下载速度：10-13 MB/s（提升 300+ 倍）
- 构建时间：约 2-3 分钟
- 成功率：高（使用清华镜像源稳定）

---

## 📂 修改文件清单

| 文件路径 | 修改类型 | 说明 |
|---------|---------|------|
| `docker/Dockerfile` | 修改 | 添加 APT、PyPI 镜像源，优化下载策略 |
| `docker/Dockerfile.mcp` | 修改 | 添加 PyPI 镜像源 |
| `docker/build-local.sh` | 新建 | 便捷构建脚本 |
| `docker/docker-compose-build.yml` | 修改 | 添加镜像标签 |
| `docker/部署说明.md` | 新建 | 部署指南文档 |
| `docker/部署成功.md` | 新建 | 部署成功确认文档 |

---

## 🎯 验证结果

### 容器状态

```
CONTAINER ID   IMAGE                   STATUS              PORTS
961d959bc7b9   trendradar:local        Up 11 seconds       127.0.0.1:8080->8080/tcp
4b85ed6e890e   docker-trendradar-mcp   Up 11 seconds       127.0.0.1:3333->3333/tcp
```

### 首次运行结果

**数据抓取**:
- ✅ 今日头条、百度热搜、华尔街见闻
- ✅ 澎湃新闻、哔哩哔哩热搜、财联社
- ✅ 凤凰网、贴吧、微博、抖音、知乎
- ✅ Hacker News (20 条)
- ✅ 阮一峰的网络日志 (3 条)

**报告生成**:
- ✅ `output/html/2026-01-28/11-37.html` (94KB)
- ✅ `output/html/latest/current.html` (最新报告链接)

**定时任务**:
- ✅ Supercronic 已启动，定时规则：`*/30 * * * *`

---

## 💡 关键技术洞察

### 1. Docker 镜像源策略

**问题**: 单一镜像源容易失效
**解决**:
- 在构建阶段使用国内镜像源
- 优先级：清华 > 中科大 > 阿里云
- 不依赖 Docker daemon 配置

### 2. 多层次优化

**系统层**: APT 使用清华镜像源
**应用层**: PyPI 使用清华镜像源
**文件下载**: GitHub 使用 ghproxy.com 代理

### 3. 构建缓存利用

Docker 构建时充分利用层缓存：
- 依赖安装步骤放在代码复制之前
- 不频繁变化的步骤放在前面
- 主镜像构建完成后，MCP 镜像构建更快

---

## 🔄 后续维护建议

### 1. 定期更新镜像源列表

清华镜像源列表：
- PyPI: https://mirrors.tuna.tsinghua.edu.cn/help/pypi/
- Debian: https://mirrors.tuna.tsinghua.edu.cn/help/debian/

### 2. 监控构建性能

记录每次构建时间，如果发现变慢：
- 检查镜像源是否可用
- 考虑切换备用源

### 3. 镜像标签管理

当前使用 `trendradar:local` 标签，建议：
- 重要更新时打上版本标签（如 `trendradar:v1.0.0`）
- 保留最近 2-3 个版本的镜像以便回滚

### 4. 依赖版本管理

`requirements.txt` 已使用版本范围约束，如：
```
requests>=2.32.5,<3.0.0
litellm>=1.57.0,<2.0.0
```

这确保了稳定性和安全性的平衡。

---

## 📚 相关文档

- [部署说明](./部署说明.md)
- [部署成功确认](./部署成功.md)
- [构建脚本](./build-local.sh)

---

## ✨ 经验总结

### 对于 Docker 部署问题

1. **优先使用本地构建**而非依赖远程镜像
2. **配置多层次的国内镜像源**（系统包、Python 包、文件下载）
3. **添加重试机制和备用方案**
4. **创建便捷脚本**降低使用门槛

### 对于网络依赖的构建

1. **识别所有网络下载点**（apt、pip、curl 等）
2. **为每个下载点配置国内加速**
3. **设置合理的超时时间**
4. **添加下载失败的友好提示**

### 对于生产环境部署

1. **验证首次运行**确保服务正常
2. **检查日志输出**确认无错误
3. **测试定时任务**确认调度正常
4. **记录详细文档**便于后续维护

---

**修复完成**: 2026-01-28 11:38
**修复者**: Claude (Sonnet 4.5)
**验证状态**: ✅ 完全成功
