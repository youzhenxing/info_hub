#!/bin/bash
# v5.26.0 发版验证脚本

echo "=========================================="
echo "v5.26.0 发版验证"
echo "=========================================="
echo ""

# 1. 检查 Git 状态
echo "📋 1. Git 状态检查"
git_status=$(git status --short | grep -E "^(M|M| M)" | wc -l)
if [ $git_status -eq 0 ]; then
    echo "  ✅ 工作区干净（除已忽略的文件）"
else
    echo "  ⚠️  工作区有未提交的修改（忽略数据库和日志文件）"
fi
echo ""

# 2. 检查版本标签
echo "🏷️  2. 版本标签检查"
if git rev-parse v5.26.0 >/dev/null 2>&1; then
    echo "  ✅ 标签 v5.26.0 已创建"
    tag_msg=$(git tag -l v5.26.0 --format='%(contents:subject)')
    echo "     标签说明: $tag_msg"
else
    echo "  ❌ 标签 v5.26.0 不存在"
    exit 1
fi
echo ""

# 3. 检查配置文件
echo "⚙️  3. 配置文件验证"
idle_hours=$(grep -A 2 "backfill:" config/config.yaml | grep "idle_hours:" | awk '{print $2}')
language=$(grep -A 4 "analysis:" config/config.yaml | grep "language:" | head -1 | awk '{print $2}')

if [ "$idle_hours" = "6" ]; then
    echo "  ✅ backfill.idle_hours = $idle_hours"
else
    echo "  ❌ backfill.idle_hours = $idle_hours (预期: 6)"
fi

if [ "$language" = '"中文"' ]; then
    echo "  ✅ podcast.analysis.language = $language"
else
    echo "  ❌ podcast.analysis.language = $language (预期: \"中文\")"
fi
echo ""

# 4. 检查生产环境
echo "🐳 4. 生产环境验证"
if docker ps --filter "name=trendradar-prod" --format "{{.Status}}" | grep -q "Up"; then
    echo "  ✅ 容器运行中"
    
    # 检查容器内配置
    prod_idle=$(docker exec trendradar-prod grep -A 2 "backfill:" /app/config/config.yaml | grep "idle_hours:" | awk '{print $2}')
    prod_lang=$(docker exec trendradar-prod grep -A 4 "analysis:" /app/config/config.yaml | grep "language:" | head -1 | awk '{print $2}')
    
    if [ "$prod_idle" = "6" ]; then
        echo "  ✅ 生产环境 idle_hours = $prod_idle"
    else
        echo "  ⚠️  生产环境 idle_hours = $prod_idle (可能需要重启容器)"
    fi
    
    if [ "$prod_lang" = '"中文"' ]; then
        echo "  ✅ 生产环境 language = $prod_lang"
    else
        echo "  ⚠️  生产环境 language = $prod_lang (可能需要重启容器)"
    fi
else
    echo "  ❌ 容器未运行"
fi
echo ""

# 5. 检查文档更新
echo "📚 5. 文档更新检查"
if grep -q "5.26.0" CHANGELOG.md; then
    echo "  ✅ CHANGELOG.md 已更新"
else
    echo "  ⚠️  CHANGELOG.md 未找到 v5.26.0 记录"
fi
echo ""

echo "=========================================="
echo "✅ v5.26.0 发版验证完成"
echo "=========================================="
