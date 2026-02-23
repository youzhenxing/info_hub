#!/bin/bash
# ============================================
# TrendRadar 部署前检查脚本
# 
# 在每次部署前自动执行，确保：
# 1. 必要文件存在
# 2. 配置正确
# 3. 脚本可执行
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SHARED_DIR="/home/zxy/Documents/install/trendradar/shared"

echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo -e "${BLUE}  TrendRadar 部署前检查${NC}"
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"
echo ""

ERRORS=0
WARNINGS=0

# 检查函数
check_file() {
    local file="$1"
    local desc="$2"
    if [ -f "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $desc"
    else
        echo -e "  ${RED}✗${NC} $desc: $file ${RED}不存在${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

check_executable() {
    local file="$1"
    local desc="$2"
    if [ -x "$file" ]; then
        echo -e "  ${GREEN}✓${NC} $desc (可执行)"
    elif [ -f "$file" ]; then
        echo -e "  ${YELLOW}!${NC} $desc: 文件存在但不可执行"
        chmod +x "$file"
        echo -e "    ${GREEN}→${NC} 已自动添加执行权限"
    else
        echo -e "  ${RED}✗${NC} $desc: $file ${RED}不存在${NC}"
        ERRORS=$((ERRORS + 1))
    fi
}

check_config_key() {
    local file="$1"
    local key="$2"
    local desc="$3"
    if grep -q "$key" "$file" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $desc"
    else
        echo -e "  ${RED}✗${NC} $desc: 配置项 '$key' 缺失"
        ERRORS=$((ERRORS + 1))
    fi
}

check_script_path() {
    local file="$1"
    local pattern="$2"
    local desc="$3"
    if grep -q "$pattern" "$file" 2>/dev/null; then
        echo -e "  ${GREEN}✓${NC} $desc"
    else
        echo -e "  ${RED}✗${NC} $desc: 路径 '$pattern' 未找到"
        ERRORS=$((ERRORS + 1))
    fi
}

# ============================================
# 1. 检查必要源文件
# ============================================
echo -e "${BLUE}[1/6] 检查源文件...${NC}"

check_file "$PROJECT_ROOT/docker/entrypoint.sh" "entrypoint.sh"
check_file "$PROJECT_ROOT/docker/run_investment.py" "run_investment.py (投资模块)"
check_file "$PROJECT_ROOT/docker/daily_report.py" "daily_report.py (每日日志)"
check_file "$PROJECT_ROOT/docker/run_community.py" "run_community.py (社区模块)"
check_file "$PROJECT_ROOT/config/config.yaml" "config.yaml"
check_file "$PROJECT_ROOT/prompts/investment_module_prompt.txt" "investment_module_prompt.txt"

# ============================================
# 2. 检查 entrypoint.sh 中的路径
# ============================================
echo ""
echo -e "${BLUE}[2/6] 检查脚本路径配置...${NC}"

ENTRYPOINT="$PROJECT_ROOT/docker/entrypoint.sh"
check_script_path "$ENTRYPOINT" "/app/run_investment.py" "投资脚本路径 (/app/run_investment.py)"
check_script_path "$ENTRYPOINT" "/app/run_community.py" "社区脚本路径 (/app/run_community.py)"
check_script_path "$ENTRYPOINT" "python -m trendradar" "主程序入口 (python -m trendradar)"

# 检查是否有错误的旧路径
if grep -q "/app/docker/run_investment.py" "$ENTRYPOINT" 2>/dev/null; then
    echo -e "  ${RED}✗${NC} 发现错误路径: /app/docker/run_investment.py"
    echo -e "    ${YELLOW}→${NC} 应该使用 /app/run_investment.py"
    ERRORS=$((ERRORS + 1))
fi

# ============================================
# 3. 检查 Docker Compose 配置
# ============================================
echo ""
echo -e "${BLUE}[3/6] 检查 Docker Compose 配置...${NC}"

# 注意：生产 docker-compose.yml 由 deploy.sh 动态生成，此处校验 .env 开关
ENV_FILE="$PROJECT_ROOT/agents/.env"
if [ -f "$ENV_FILE" ]; then
    check_config_key "$ENV_FILE" "INVESTMENT_ENABLED" "INVESTMENT_ENABLED (agents/.env)"
    check_config_key "$ENV_FILE" "COMMUNITY_ENABLED" "COMMUNITY_ENABLED (agents/.env)"
else
    echo -e "  ${YELLOW}!${NC} agents/.env 不存在，将在部署时从此文件同步到生产"
fi

# ============================================
# 4. 检查可执行权限
# ============================================
echo ""
echo -e "${BLUE}[4/6] 检查执行权限...${NC}"

check_executable "$PROJECT_ROOT/docker/entrypoint.sh" "entrypoint.sh"
check_executable "$PROJECT_ROOT/deploy/deploy.sh" "deploy.sh"
check_executable "$PROJECT_ROOT/deploy/update.sh" "update.sh"

# ============================================
# 5. 检查模块状态（强制所有模块启用）
# ============================================
echo ""
echo -e "${BLUE}[5/6] 检查模块状态...${NC}"

CONFIG_FILE="$PROJECT_ROOT/config/config.yaml"

# 检查 4 个核心模块是否启用
check_module_enabled() {
    local module_name="$1"
    local config_key="$2"
    
    # 使用 Python 读取 YAML 配置
    local enabled=$(python3 -c "
import yaml
try:
    with open('$CONFIG_FILE', 'r') as f:
        config = yaml.safe_load(f)
    module_config = config.get('$config_key', {})
    enabled = module_config.get('enabled', False)
    print('true' if enabled else 'false')
except Exception as e:
    print('error')
    " 2>/dev/null)
    
    if [ "$enabled" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} $module_name 已启用"
        return 0
    elif [ "$enabled" = "false" ]; then
        echo -e "  ${RED}✗${NC} $module_name ${RED}未启用${NC} (必须启用才能部署)"
        ERRORS=$((ERRORS + 1))
        return 1
    else
        echo -e "  ${RED}✗${NC} $module_name 配置读取失败"
        ERRORS=$((ERRORS + 1))
        return 1
    fi
}

# 检查 4 个核心模块
check_module_enabled "播客模块 (Podcast)" "podcast"
check_module_enabled "投资模块 (Investment)" "investment"
check_module_enabled "社区模块 (Community)" "community"

# 公众号模块特殊检查（配置在独立文件）
WECHAT_CONFIG="$PROJECT_ROOT/wechat/config.yaml"
if [ -f "$WECHAT_CONFIG" ]; then
    wechat_enabled=$(python3 -c "
import yaml
try:
    with open('$WECHAT_CONFIG', 'r') as f:
        config = yaml.safe_load(f)
    enabled = config.get('enabled', True)  # 默认启用
    print('true' if enabled else 'false')
except:
    print('true')
    " 2>/dev/null)
    
    if [ "$wechat_enabled" = "true" ]; then
        echo -e "  ${GREEN}✓${NC} 公众号模块 (WeChat) 已启用"
    else
        echo -e "  ${RED}✗${NC} 公众号模块 (WeChat) ${RED}未启用${NC} (必须启用才能部署)"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  ${RED}✗${NC} 公众号模块配置文件不存在: $WECHAT_CONFIG"
    ERRORS=$((ERRORS + 1))
fi

# ============================================
# 6. 检查生产环境共享目录（如果存在）
# ============================================
echo ""
echo -e "${BLUE}[6/6] 检查生产环境配置...${NC}"

if [ -d "$SHARED_DIR" ]; then
    # 检查共享目录中的文件
    if [ ! -f "$SHARED_DIR/run_investment.py" ]; then
        echo -e "  ${YELLOW}!${NC} 共享目录缺少 run_investment.py，将在部署时复制"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "  ${GREEN}✓${NC} 共享目录 run_investment.py 存在"
    fi
    
    if [ ! -f "$SHARED_DIR/entrypoint.sh" ]; then
        echo -e "  ${YELLOW}!${NC} 共享目录缺少 entrypoint.sh，将在部署时复制"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "  ${GREEN}✓${NC} 共享目录 entrypoint.sh 存在"
    fi

    if [ ! -f "$SHARED_DIR/run_community.py" ]; then
        echo -e "  ${YELLOW}!${NC} 共享目录缺少 run_community.py，将在部署时复制"
        WARNINGS=$((WARNINGS + 1))
    else
        echo -e "  ${GREEN}✓${NC} 共享目录 run_community.py 存在"
    fi

    # 检查 .env 配置
    if [ -f "$SHARED_DIR/.env" ]; then
        check_config_key "$SHARED_DIR/.env" "INVESTMENT_ENABLED" "生产环境 INVESTMENT_ENABLED"
        check_config_key "$SHARED_DIR/.env" "EMAIL_FROM" "生产环境邮件配置"
    else
        echo -e "  ${RED}✗${NC} 生产环境 .env 文件不存在"
        ERRORS=$((ERRORS + 1))
    fi
else
    echo -e "  ${YELLOW}!${NC} 生产环境目录不存在（首次部署会自动创建）"
fi

# ============================================
# 结果汇总
# ============================================
echo ""
echo -e "${BLUE}═══════════════════════════════════════════════${NC}"

if [ $ERRORS -gt 0 ]; then
    echo -e "${RED}✗ 检查失败！发现 $ERRORS 个错误${NC}"
    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}  另有 $WARNINGS 个警告${NC}"
    fi
    echo ""
    echo -e "${RED}请修复以上错误后再执行部署！${NC}"
    exit 1
elif [ $WARNINGS -gt 0 ]; then
    echo -e "${YELLOW}⚠ 检查通过，但有 $WARNINGS 个警告${NC}"
    echo -e "${GREEN}  可以继续部署${NC}"
    exit 0
else
    echo -e "${GREEN}✓ 所有检查通过！${NC}"
    exit 0
fi
