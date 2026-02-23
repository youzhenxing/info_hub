#!/bin/bash
# 播客功能测试脚本（临时禁用代理）

# 保存原始代理设置
OLD_HTTP_PROXY=$HTTP_PROXY
OLD_HTTPS_PROXY=$HTTPS_PROXY
OLD_ALL_PROXY=$ALL_PROXY

# 临时取消代理（避免 litellm socks 代理问题）
unset HTTP_PROXY
unset HTTPS_PROXY
unset ALL_PROXY
unset http_proxy
unset https_proxy
unset all_proxy

echo "========================================="
echo "播客功能测试（已临时禁用代理）"
echo "========================================="

# 运行播客测试
python -m trendradar --podcast-only

# 恢复代理设置
export HTTP_PROXY=$OLD_HTTP_PROXY
export HTTPS_PROXY=$OLD_HTTPS_PROXY
export ALL_PROXY=$OLD_ALL_PROXY
