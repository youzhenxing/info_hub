#!/bin/bash
# ============================================================
# NVIDIA Container Toolkit 安装脚本
# 适用于 Ubuntu 22.04
# 
# 用法: sudo bash install-nvidia-toolkit.sh
# ============================================================

set -e

echo "=========================================="
echo "  安装 NVIDIA Container Toolkit"
echo "=========================================="

# 检查是否为 root
if [ "$EUID" -ne 0 ]; then
    echo "请使用 sudo 运行此脚本"
    echo "用法: sudo bash install-nvidia-toolkit.sh"
    exit 1
fi

# 1. 添加 GPG 密钥
echo "[1/4] 添加 NVIDIA GPG 密钥..."
curl -fsSL https://nvidia.github.io/libnvidia-container/gpgkey | \
    gpg --dearmor -o /usr/share/keyrings/nvidia-container-toolkit-keyring.gpg

# 2. 添加软件源
echo "[2/4] 添加 NVIDIA 软件源..."
curl -s -L https://nvidia.github.io/libnvidia-container/stable/deb/nvidia-container-toolkit.list | \
    sed 's#deb https://#deb [signed-by=/usr/share/keyrings/nvidia-container-toolkit-keyring.gpg] https://#g' | \
    tee /etc/apt/sources.list.d/nvidia-container-toolkit.list > /dev/null

# 3. 安装
echo "[3/4] 安装 nvidia-container-toolkit..."
apt-get update
apt-get install -y nvidia-container-toolkit

# 4. 配置 Docker
echo "[4/4] 配置 Docker 使用 NVIDIA runtime..."
nvidia-ctk runtime configure --runtime=docker

# 重启 Docker
echo "重启 Docker 服务..."
systemctl restart docker

echo ""
echo "=========================================="
echo "  安装完成！"
echo "=========================================="
echo ""
echo "验证安装："
echo "  docker run --rm --gpus all nvidia/cuda:11.8-base-ubuntu22.04 nvidia-smi"
echo ""
