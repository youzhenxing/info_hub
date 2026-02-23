# Docker 安装和启动指南

## 1. Docker 安装（需要管理员权限）

### 方法一：使用官方脚本（推荐）
```bash
# 下载安装脚本
curl -fsSL https://get.docker.com -o get-docker.sh

# 运行安装脚本（需要sudo权限）
sudo sh get-docker.sh

# 将当前用户添加到docker组（避免每次都使用sudo）
sudo usermod -aG docker $USER

# 重新登录或执行以下命令使组权限生效
newgrp docker
```

### 方法二：使用包管理器（Ubuntu/Debian）
```bash
# 更新包索引
sudo apt update

# 安装必要的包
sudo apt install -y apt-transport-https ca-certificates curl gnupg lsb-release

# 添加Docker官方GPG密钥
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | sudo gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg

# 添加Docker仓库
echo "deb [arch=amd64 signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/ubuntu $(lsb_release -cs) stable" | sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# 安装Docker Engine
sudo apt update
sudo apt install -y docker-ce docker-ce-cli containerd.io

# 将当前用户添加到docker组
sudo usermod -aG docker $USER

# 启动Docker服务
sudo systemctl start docker
sudo systemctl enable docker
```

## 2. 验证Docker安装
```bash
# 检查Docker版本
docker --version

# 运行测试容器
docker run hello-world
```

## 3. 启动TrendRadar服务

安装完Docker后，执行以下步骤：

```bash
# 进入项目目录
cd /home/zxy/Documents/code/TrendRadar

# 使用启动脚本
./agents/start-trendradar.sh
```

## 4. 触发一次推送（立即执行）

启动服务后，执行以下命令立即运行一次爬虫和推送：

```bash
# 方法一：使用manage.py命令
docker exec -it trendradar python manage.py run

# 方法二：重启容器（会立即执行一次）
docker restart trendradar
```

## 5. 查看推送结果

- 邮件推送：检查{{EMAIL_ADDRESS}}邮箱
- Web报告：访问 http://localhost:8080
- 日志查看：`docker logs -f trendradar`

## 常见问题

### Q: 提示权限不足
A: 确保当前用户在docker组中，或使用sudo运行docker命令

### Q: Docker服务未运行
A: 执行 `sudo systemctl start docker` 启动服务

### Q: 端口8080被占用
A: 修改agents/.env中的WEBSERVER_PORT为其他端口