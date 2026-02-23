#!/bin/bash
# Bootstrap 验证脚本
# 用于测试 Bootstrap 机制增强功能

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
WECHAT_DIR="$PROJECT_ROOT/wechat"

echo "=========================================="
echo "Bootstrap 验证脚本"
echo "=========================================="
echo ""

# Step 1: 删除标记文件
echo "[Step 1/4] 删除 Bootstrap 标记文件..."
cd "$WECHAT_DIR"
docker exec wechat-service rm -f /app/data/.wechat_bootstrap_done 2>/dev/null || echo "  (标记文件不存在，继续)"
echo "  ✅ 标记文件已删除"
echo ""

# Step 2: 重启容器
echo "[Step 2/4] 重启 wechat-service 容器..."
docker compose restart wechat-service
echo "  ⏳ 等待容器启动（5秒）..."
sleep 5
echo "  ✅ 容器已重启"
echo ""

# Step 3: 查看日志
echo "[Step 3/4] 查看 Bootstrap 执行日志..."
echo "  ========================================"
docker logs wechat-service 2>&1 | grep -A 30 "Bootstrap" || echo "  ⚠️  未找到 Bootstrap 日志"
echo "  ========================================"
echo ""

# Step 4: 验证数据库未被污染
echo "[Step 4/4] 验证数据库状态..."
ARTICLE_COUNT=$(docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cursor = conn.cursor()
cursor.execute('SELECT COUNT(*) FROM articles')
count = cursor.fetchone()[0]
print(count)
" 2>/dev/null || echo "0")

echo "  当前数据库文章数: $ARTICLE_COUNT"
if [ "$ARTICLE_COUNT" -eq 0 ]; then
    echo "  ✅ 数据库未被污染"
else
    echo "  ⚠️  数据库中有 $ARTICLE_COUNT 篇文章（可能是之前的数据）"
fi
echo ""

# Step 5: 检查推送记录
echo "[Bonus] 检查推送记录..."
docker exec wechat-service python -c "
import sqlite3
conn = sqlite3.connect('/app/data/wechat.db')
cursor = conn.cursor()
cursor.execute('SELECT push_type, push_time, article_count FROM push_history ORDER BY push_time DESC LIMIT 5')
records = cursor.fetchall()
if records:
    print('  最近5次推送记录:')
    for r in records:
        print(f'    - 类型: {r[0]}, 时间: {r[1]}, 文章数: {r[2]}')
else:
    print('  未找到推送记录')
" 2>/dev/null || echo "  无法查询推送记录"
echo ""

echo "=========================================="
echo "验证完成！"
echo "=========================================="
echo ""
echo "📋 预期结果："
echo "  1. Bootstrap 日志显示采集了 3 个公众号"
echo "  2. Bootstrap 日志显示推送成功 ✅"
echo "  3. 数据库文章数为 0（或只有之前的数据）"
echo "  4. 推送记录中包含 'bootstrap' 类型"
echo ""
echo "📬 请检查邮箱确认是否收到 Bootstrap 验证邮件"
echo ""
