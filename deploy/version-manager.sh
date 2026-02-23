#!/bin/bash

# TrendRadar 版本管理工具库
# 提供版本信息的读取、更新、查询等功能

# 配置
PROD_BASE="/home/zxy/Documents/install/trendradar"
MANIFEST_FILE="$PROD_BASE/versions/manifest.yaml"
HISTORY_DIR="$PROD_BASE/versions/history"

# 检查生产环境是否初始化
check_production_initialized() {
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo "错误：生产环境未初始化"
        echo "请先运行: trend deploy/init-production.sh"
        return 1
    fi
    return 0
}

# 读取当前版本
get_current_version() {
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo "null"
        return
    fi

    grep "^current_version:" "$MANIFEST_FILE" | awk '{print $2}' | tr -d '"' | tr -d "'"
}

# 读取上一版本
get_previous_version() {
    if [ ! -f "$MANIFEST_FILE" ]; then
        echo "null"
        return
    fi

    grep "^previous_version:" "$MANIFEST_FILE" | awk '{print $2}' | tr -d '"' | tr -d "'"
}

# 检查版本是否存在
version_exists() {
    local version="$1"

    if [ ! -d "$PROD_BASE/releases/v${version}" ]; then
        return 1
    fi
    return 0
}

# 获取所有版本列表
list_versions() {
    if [ ! -d "$PROD_BASE/releases" ]; then
        return
    fi

    # 列出所有版本目录
    ls -1 "$PROD_BASE/releases" 2>/dev/null | grep "^v" | sed 's/^v//' | sort -V -r
}

# 添加新版本到清单
add_version_to_manifest() {
    local version="$1"
    local image="$2"
    local timestamp="$3"

    # 如果 manifest 中 versions 为空数组，需要初始化
    if ! grep -q "^  - version:" "$MANIFEST_FILE"; then
        # 删除空的 versions: [] 行
        sed -i '/^versions: \[\]$/d' "$MANIFEST_FILE"

        # 添加 versions: 开头
        if ! grep -q "^versions:$" "$MANIFEST_FILE"; then
            echo "versions:" >> "$MANIFEST_FILE"
        fi
    fi

    # 添加新版本
    cat >> "$MANIFEST_FILE" << EOF
  - version: "$version"
    released_at: "$timestamp"
    status: "inactive"
    image: "$image"
EOF
}

# 更新当前版本
update_current_version() {
    local new_version="$1"
    local old_version

    old_version=$(get_current_version)

    # 更新 current_version
    sed -i "s/^current_version:.*/current_version: \"$new_version\"/" "$MANIFEST_FILE"

    # 更新 previous_version
    if [ "$old_version" != "null" ] && [ -n "$old_version" ]; then
        sed -i "s/^previous_version:.*/previous_version: \"$old_version\"/" "$MANIFEST_FILE"

        # 将旧版本状态改为 inactive
        sed -i "/  - version: \"$old_version\"/,/status:/ s/status: \"active\"/status: \"inactive\"/" "$MANIFEST_FILE"
    fi

    # 将新版本状态改为 active
    sed -i "/  - version: \"$new_version\"/,/status:/ s/status: \"inactive\"/status: \"active\"/" "$MANIFEST_FILE"
}

# 创建版本详细记录
create_version_record() {
    local version="$1"
    local main_image="$2"
    local mcp_image="$3"
    local summary="$4"

    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
    local record_file="$HISTORY_DIR/v${version}.yaml"

    mkdir -p "$HISTORY_DIR"

    cat > "$record_file" << EOF
version: "$version"
released_at: "$timestamp"
deployed_at: null
deployed_by: "$(whoami)"
status: "inactive"

changes:
  summary: "$summary"
  details: []

images:
  main: "$main_image"
  mcp: "$mcp_image"

deployment_history: []
EOF

    echo "$record_file"
}

# 更新版本记录 - 添加部署历史
add_deployment_history() {
    local version="$1"
    local action="$2"  # deployed, updated, rollback
    local from_version="$3"
    local success="$4"  # true/false

    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%S+00:00")
    local record_file="$HISTORY_DIR/v${version}.yaml"

    if [ ! -f "$record_file" ]; then
        echo "警告：版本记录文件不存在: $record_file"
        return
    fi

    # 更新 deployed_at
    if [ "$action" = "deployed" ]; then
        sed -i "s/^deployed_at:.*/deployed_at: \"$timestamp\"/" "$record_file"
    fi

    # 添加部署历史
    cat >> "$record_file" << EOF
  - action: "$action"
    timestamp: "$timestamp"
    from_version: $([ -n "$from_version" ] && echo "\"$from_version\"" || echo "null")
    success: $success
EOF
}

# 获取版本信息
get_version_info() {
    local version="$1"
    local record_file="$HISTORY_DIR/v${version}.yaml"

    if [ ! -f "$record_file" ]; then
        echo "版本记录不存在: $version"
        return 1
    fi

    cat "$record_file"
}

# 自动递增版本号（patch 版本）
# 格式：major.minor.patch -> major.minor.(patch+1)
bump_version() {
    local current_version="$1"

    # 解析版本号
    local major=$(echo "$current_version" | cut -d. -f1)
    local minor=$(echo "$current_version" | cut -d. -f2)
    local patch=$(echo "$current_version" | cut -d. -f3)

    # 递增 patch 版本
    patch=$((patch + 1))

    echo "${major}.${minor}.${patch}"
}

# 更新版本文件
update_version_file() {
    local new_version="$1"
    local version_file="$2"

    if [ -z "$version_file" ]; then
        version_file="$DEV_BASE/version"
    fi

    echo "$new_version" > "$version_file"
}

# 导出函数供其他脚本使用
export -f check_production_initialized
export -f get_current_version
export -f get_previous_version
export -f version_exists
export -f list_versions
export -f add_version_to_manifest
export -f update_current_version
export -f create_version_record
export -f add_deployment_history
export -f get_version_info
export -f bump_version
export -f update_version_file
