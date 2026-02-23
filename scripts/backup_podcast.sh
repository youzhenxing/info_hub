#!/bin/bash
# 播客数据库备份脚本
# 功能：每天凌晨2点自动备份播客数据库，保留最近30天的备份

set -e

BACKUP_DIR="/app/output/news/backup"
DB_PATH="/app/output/news/podcast.db"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")
BACKUP_FILE="$BACKUP_DIR/podcast_$TIMESTAMP.db"
RETENTION_DAYS=30

echo "========================================="
echo "播客数据库备份"
echo "========================================="
echo "开始时间: $(date)"

# 创建备份目录
mkdir -p "$BACKUP_DIR"

# 检查数据库文件是否存在
if [ ! -f "$DB_PATH" ]; then
    echo "❌ 错误：数据库文件不存在: $DB_PATH"
    exit 1
fi

# 创建备份（使用 SQLite 的 .backup 命令，确保数据一致性）
echo "📦 开始备份播客数据库..."
sqlite3 "$DB_PATH" ".backup $BACKUP_FILE"

if [ $? -eq 0 ]; then
    echo "✅ 备份成功: $BACKUP_FILE"
    SIZE=$(du -h "$BACKUP_FILE" | cut -f1)
    echo "📊 备份大小: $SIZE"
else
    echo "❌ 备份失败！"
    exit 1
fi

# 清理超过保留期的旧备份
echo "🧹 清理超过 $RETENTION_DAYS 天的旧备份..."
DELETED=$(find "$BACKUP_DIR" -name "podcast_*.db" -mtime +$RETENTION_DAYS -delete -print | wc -l)
echo "🗑️  已删除 $DELETED 个旧备份文件"

# 显示当前备份列表
BACKUP_COUNT=$(ls -1 "$BACKUP_DIR"/podcast_*.db 2>/dev/null | wc -l)
echo "📋 当前备份数量: $BACKUP_COUNT"

# 显示最近的5个备份
if [ $BACKUP_COUNT -gt 0 ]; then
    echo ""
    echo "最近的备份文件："
    ls -lt "$BACKUP_DIR"/podcast_*.db | head -5 | awk '{print $9, $5, $6, $7, $8}'
fi

echo ""
echo "========================================="
echo "备份任务完成"
echo "完成时间: $(date)"
echo "========================================="

# 返回成功
exit 0
