#!/bin/bash
# ============================================================
# WhisperX 服务测试脚本
# 
# 用法: bash test_whisperx.sh
# ============================================================

set -e

WHISPERX_URL="http://localhost:5000"
TEST_DIR="/home/zxy/Documents/code/TrendRadar/agents/whisperx_test"
mkdir -p "$TEST_DIR"

echo "=========================================="
echo "  WhisperX 服务测试"
echo "=========================================="

# 1. 检查服务状态
echo ""
echo "[1/5] 检查服务健康状态..."
HEALTH=$(curl -s "$WHISPERX_URL/health" 2>/dev/null || echo "FAILED")
if [[ "$HEALTH" == *"healthy"* ]]; then
    echo "✅ 服务正常运行"
    echo "   $HEALTH"
else
    echo "❌ 服务未运行，请先启动 WhisperX 服务："
    echo "   cd docker/whisperx && docker compose up -d"
    exit 1
fi

# 2. 获取服务信息
echo ""
echo "[2/5] 获取服务信息..."
INFO=$(curl -s "$WHISPERX_URL/info")
echo "   $INFO"

# 3. 下载测试音频（中文 - 硅谷101）
echo ""
echo "[3/5] 准备测试音频..."

# 中文测试音频（从硅谷101 RSS 获取最新一集的前 5 分钟）
ZH_AUDIO="$TEST_DIR/test_zh.mp3"
if [ ! -f "$ZH_AUDIO" ]; then
    echo "   下载中文测试音频..."
    # 使用 FFmpeg 从 RSS 中的音频 URL 下载前 5 分钟
    RSS_URL="https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc"
    AUDIO_URL=$(curl -s "$RSS_URL" | grep -o '<enclosure[^>]*url="[^"]*"' | head -1 | sed 's/.*url="\([^"]*\)".*/\1/')
    
    if [ -n "$AUDIO_URL" ]; then
        echo "   音频 URL: $AUDIO_URL"
        # 下载前 5 分钟
        ffmpeg -i "$AUDIO_URL" -t 300 -acodec copy "$ZH_AUDIO" -y 2>/dev/null || \
        curl -L -o "$ZH_AUDIO" "$AUDIO_URL" 2>/dev/null
    else
        echo "   ⚠️ 无法获取中文测试音频，跳过中文测试"
    fi
fi

# 英文测试音频（从 a16z RSS 获取）
EN_AUDIO="$TEST_DIR/test_en.mp3"
if [ ! -f "$EN_AUDIO" ]; then
    echo "   下载英文测试音频..."
    RSS_URL="https://feeds.simplecast.com/JGE3yC0V"
    AUDIO_URL=$(curl -s "$RSS_URL" | grep -o '<enclosure[^>]*url="[^"]*"' | head -1 | sed 's/.*url="\([^"]*\)".*/\1/')
    
    if [ -n "$AUDIO_URL" ]; then
        echo "   音频 URL: $AUDIO_URL"
        # 下载前 5 分钟
        ffmpeg -i "$AUDIO_URL" -t 300 -acodec copy "$EN_AUDIO" -y 2>/dev/null || \
        curl -L -o "$EN_AUDIO" "$AUDIO_URL" 2>/dev/null
    else
        echo "   ⚠️ 无法获取英文测试音频，跳过英文测试"
    fi
fi

# 4. 测试中文转写
echo ""
echo "[4/5] 测试中文转写（带说话人分离）..."
if [ -f "$ZH_AUDIO" ]; then
    echo "   开始转写..."
    START_TIME=$(date +%s)
    
    RESULT=$(curl -s -X POST "$WHISPERX_URL/transcribe" \
        -F "file=@$ZH_AUDIO" \
        -F "diarize=true" \
        -F "output_format=both")
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    # 保存结果
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('text',''))" > "$TEST_DIR/transcript_zh.txt"
    echo "$RESULT" > "$TEST_DIR/result_zh.json"
    
    echo "   ✅ 中文转写完成 (耗时: ${ELAPSED}秒)"
    echo "   语言: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('language',''))")"
    echo "   时长: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('duration',0))")秒"
    echo "   分段数: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('segment_count',0))")"
    echo ""
    echo "   转写结果预览（前500字符）:"
    echo "   ----------------------------------------"
    head -c 500 "$TEST_DIR/transcript_zh.txt"
    echo ""
    echo "   ----------------------------------------"
    echo "   完整结果保存至: $TEST_DIR/transcript_zh.txt"
else
    echo "   ⚠️ 中文测试音频不存在，跳过"
fi

# 5. 测试英文转写
echo ""
echo "[5/5] 测试英文转写（带说话人分离）..."
if [ -f "$EN_AUDIO" ]; then
    echo "   开始转写..."
    START_TIME=$(date +%s)
    
    RESULT=$(curl -s -X POST "$WHISPERX_URL/transcribe" \
        -F "file=@$EN_AUDIO" \
        -F "diarize=true" \
        -F "output_format=both")
    
    END_TIME=$(date +%s)
    ELAPSED=$((END_TIME - START_TIME))
    
    # 保存结果
    echo "$RESULT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('text',''))" > "$TEST_DIR/transcript_en.txt"
    echo "$RESULT" > "$TEST_DIR/result_en.json"
    
    echo "   ✅ 英文转写完成 (耗时: ${ELAPSED}秒)"
    echo "   语言: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('language',''))")"
    echo "   时长: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('duration',0))")秒"
    echo "   分段数: $(echo "$RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('segment_count',0))")"
    echo ""
    echo "   转写结果预览（前500字符）:"
    echo "   ----------------------------------------"
    head -c 500 "$TEST_DIR/transcript_en.txt"
    echo ""
    echo "   ----------------------------------------"
    echo "   完整结果保存至: $TEST_DIR/transcript_en.txt"
else
    echo "   ⚠️ 英文测试音频不存在，跳过"
fi

echo ""
echo "=========================================="
echo "  测试完成！"
echo "=========================================="
echo ""
echo "测试结果目录: $TEST_DIR"
echo ""
ls -la "$TEST_DIR"
