#!/bin/bash
# ============================================
# TrendRadar 提交前强制验证脚本
#
# 在 git commit 前必须执行此脚本
# 只有验证通过才能提交代码和部署
# 验证失败则必须修复问题后重试
#
# 使用方式：
#   1. 手动执行：bash deploy/pre-commit-verify.sh
#   2. Git hook（自动）：.git/hooks/pre-commit
# ============================================

set -e

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m'

# 项目根目录
PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$PROJECT_ROOT"

echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  TrendRadar 提交前强制验证${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

# 验证阶段计数
PHASE=0
TOTAL_PHASES=7

# 错误计数
ERRORS=0
WARNINGS=0

# 检查函数
check_pass() {
    echo -e "  ${GREEN}✓${NC} $1"
}

check_fail() {
    echo -e "  ${RED}✗${NC} $1"
    ERRORS=$((ERRORS + 1))
}

check_warn() {
    echo -e "  ${YELLOW}!${NC} $1"
    WARNINGS=$((WARNINGS + 1))
}

# ============================================
# Phase 1: Git 状态检查
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] Git 状态检查${NC}"

# 检查是否有未提交的修改
if git diff --quiet && git diff --cached --quiet; then
    check_fail "没有检测到任何修改，无需提交"
    echo -e "${YELLOW}提示: 如果只是配置测试，不需要执行提交流程${NC}"
    exit 1
else
    check_pass "检测到代码修改"
fi

# 检查分支
CURRENT_BRANCH=$(git branch --show-current)
if [ "$CURRENT_BRANCH" = "master" ] || [ "$CURRENT_BRANCH" = "main" ]; then
    check_pass "当前分支: $CURRENT_BRANCH"
else
    check_warn "当前不在主分支: $CURRENT_BRANCH（建议在 master/main 分支提交）"
fi

echo ""

# ============================================
# Phase 2: 配置文件语法检查
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] 配置文件语法检查${NC}"

# 检查 config.yaml 语法
if [ -f "config/config.yaml" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('config/config.yaml'))" 2>/dev/null; then
        check_pass "config/config.yaml 语法正确"
    else
        check_fail "config/config.yaml 语法错误"
    fi
else
    check_fail "config/config.yaml 文件不存在"
fi

# 检查 system.yaml 语法
if [ -f "config/system.yaml" ]; then
    if python3 -c "import yaml; yaml.safe_load(open('config/system.yaml'))" 2>/dev/null; then
        check_pass "config/system.yaml 语法正确"
    else
        check_fail "config/system.yaml 语法错误"
    fi
else
    check_fail "config/system.yaml 文件不存在"
fi

echo ""

# ============================================
# Phase 3: 关键配置一致性检查
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] 关键配置一致性检查${NC}"

# 检查 prompts 挂载配置
if grep -q "prompt_file:" config/config.yaml 2>/dev/null || \
   grep -q "prompts:" config/config.yaml 2>/dev/null; then
    check_pass "prompts 配置存在"
else
    check_warn "prompts 配置未找到（如果模块不使用 prompts 可忽略）"
fi

# 检查 backfill 配置（播客模块）
if grep -q "backfill:" config/config.yaml 2>/dev/null; then
    check_pass "backfill 配置存在"

    # 检查 idle_hours 是否为合理值
    IDLE_HOURS=$(grep -A 2 "backfill:" config/config.yaml | grep "idle_hours:" | awk '{print $2}')
    if [ -n "$IDLE_HOURS" ] && [ "$IDLE_HOURS" -ge 1 ] && [ "$IDLE_HOURS" -le 24 ]; then
        check_pass "backfill.idle_hours = $IDLE_HOURS（合理范围）"
    else
        check_warn "backfill.idle_hours = $IDLE_HOURS（建议范围: 1-24）"
    fi
else
    check_warn "backfill 配置不存在（播客模块可能不需要）"
fi

echo ""

# ============================================
# Phase 4: Python 代码语法检查
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] Python 代码语法检查${NC}"

# 获取所有修改的 .py 文件
PY_FILES=$(git diff --name-only --cached | grep '\.py$' || true)
PY_FILES="$PY_FILES$(git diff --name-only | grep '\.py$' || true)"

if [ -z "$PY_FILES" ]; then
    echo -e "  ${YELLOW}○${NC} 没有 Python 文件修改"
else
    PYTHON_SYNTAX_ERRORS=0
    for py_file in $PY_FILES; do
        if [ -f "$py_file" ]; then
            if python3 -m py_compile "$py_file" 2>/dev/null; then
                check_pass "$py_file 语法正确"
            else
                check_fail "$py_file 语法错误"
                PYTHON_SYNTAX_ERRORS=$((PYTHON_SYNTAX_ERRORS + 1))
            fi
        fi
    done

    if [ $PYTHON_SYNTAX_ERRORS -gt 0 ]; then
        echo ""
        echo -e "${RED}发现 $PYTHON_SYNTAX_ERRORS 个 Python 语法错误${NC}"
        echo -e "${YELLOW}提示: 运行 'python3 -m py_compile <file>' 查看详细错误${NC}"
    fi
fi

echo ""

# ============================================
# Phase 5: 版本号检查
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] 版本号检查${NC}"

# 检查 deploy/version 文件
if [ -f "deploy/version" ]; then
    CURRENT_VERSION=$(cat deploy/version)
    check_pass "当前版本: $CURRENT_VERSION"

    # 检查版本格式
    if echo "$CURRENT_VERSION" | grep -qE '^v[0-9]+\.[0-9]+\.[0-9]+$'; then
        check_pass "版本格式正确"
    else
        check_fail "版本格式错误（应为 vMajor.Minor.Patch）"
    fi
else
    check_fail "deploy/version 文件不存在"
fi

echo ""

# ============================================
# Phase 6: 部署状态一致性检查（强制）
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] 部署状态一致性检查${NC}"

DEPLOYMENT_MARKER="$PROJECT_ROOT/.deployed_version"

if [ ! -f "$DEPLOYMENT_MARKER" ]; then
    check_warn "未找到部署标记文件（首次部署或从未部署过）"
else
    # 读取部署标记中的版本
    DEPLOYED_VERSION=$(grep "^version:" "$DEPLOYMENT_MARKER" | awk '{print $2}' | tr -d '"' | tr -d "'")
    CODE_VERSION=$(cat version | tr -d '[:space:]')

    check_pass "当前代码版本: $CODE_VERSION"
    check_pass "已部署版本: $DEPLOYED_VERSION"

    # 版本比较（去掉v前缀）
    DEPLOYED_VER_NUM=$(echo "$DEPLOYED_VERSION" | sed 's/^v//')
    CODE_VER_NUM=$(echo "$CODE_VERSION" | sed 's/^v//')

    if [ "$DEPLOYED_VER_NUM" != "$CODE_VER_NUM" ]; then
        echo ""
        echo -e "${YELLOW}⚠️  代码版本与部署版本不一致${NC}"
        echo -e "${YELLOW}   代码版本: ${CYAN}$CODE_VER_NUM${NC}"
        echo -e "${YELLOW}   部署版本: ${CYAN}$DEPLOYED_VER_NUM${NC}"
        echo ""
        echo -e "${RED}❌ 检测到代码修改但未部署！${NC}"
        echo -e "${RED}   必须先执行部署才能提交代码${NC}"
        echo ""
        echo -e "${CYAN}📋 正确流程:${NC}"
        echo -e "   1. ${GREEN}cd deploy && yes \"y\" | bash deploy.sh${NC}  # 部署新版本"
        echo -e "   2. ${GREEN}trend update v${CODE_VERSION}${NC}            # 切换到新版本"
        echo -e "   3. ${GREEN}git add .deployed_version${NC}                # 添加部署标记"
        echo -e "   4. ${GREEN}git commit${NC}                               # 提交代码"

        ERRORS=$((ERRORS + 1))
    else
        check_pass "代码版本与部署版本一致"

        # 检查暂存区的修改（即将提交的文件）
        if git diff --cached --quiet; then
            check_pass "暂存区无修改"
        else
            # 只检查暂存区的修改，排除部署标记和文档
            MODIFIED_FILES=$(git diff --cached --name-only | grep -v "\.deployed_version\|CHANGELOG\.md\|CLAUDE\.md\|AGENTS\.md" || true)

            # 进一步排除数据库、日志等不应该提交的文件
            MODIFIED_FILES=$(echo "$MODIFIED_FILES" | grep -v -E "\\.db$|\\.log$|\.sqlite|__pycache__|node_modules|\\.pyc" || true)

            if [ -n "$MODIFIED_FILES" ]; then
                echo ""
                echo -e "${YELLOW}⚠️  检测到暂存的文件修改${NC}"

                # 检查修改是否影响运行时代码
                AFFECTS_RUNTIME=$(echo "$MODIFIED_FILES" | grep -E "^(trendradar|docker|config|wechat)/" || true)

                if [ -n "$AFFECTS_RUNTIME" ]; then
                    # 版本已一致说明部署已完成，运行时文件只需警告（.deployed_version 在 .gitignore 中无法 stage）
                    check_warn "检测到运行时文件修改（版本已一致，部署已完成）"
                    echo -e "${CYAN}修改的文件:${NC}"
                    echo "$AFFECTS_RUNTIME" | sed 's/^/   - /'
                    WARNINGS=$((WARNINGS + 1))
                else
                    check_warn "仅文档/配置修改，不影响运行时"
                fi
            else
                check_pass "暂存的文件无需部署即可提交"
            fi
        fi
    fi
fi

echo ""

# ============================================
# Phase 7: 文档更新检查（警告）
# ============================================
PHASE=$((PHASE + 1))
echo -e "${BLUE}[Phase $PHASE/$TOTAL_PHASES] 文档更新检查${NC}"

# 检查 CHANGELOG.md
if git diff --name-only --cached | grep -q "CHANGELOG.md" || \
   git diff --name-only | grep -q "CHANGELOG.md"; then
    check_pass "CHANGELOG.md 已更新"
else
    check_warn "CHANGELOG.md 未更新（建议记录本次变更）"
fi

# 检查 AGENTS.md（如果是重要功能修改）
if git diff --name-only --cached | grep -q "AGENTS.md" || \
   git diff --name-only | grep -q "AGENTS.md"; then
    check_pass "AGENTS.md 已更新"
else
    echo -e "  ${YELLOW}○${NC} AGENTS.md 未更新（如果是新增踩坑经验，建议更新）"
fi

echo ""

# ============================================
# 验证结果汇总
# ============================================
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo -e "${CYAN}  验证结果汇总${NC}"
echo -e "${CYAN}═══════════════════════════════════════════════${NC}"
echo ""

if [ $ERRORS -eq 0 ]; then
    echo -e "${GREEN}✅ 所有检查通过，可以提交代码${NC}"
    echo ""

    # 显示待提交文件
    echo -e "${BLUE}待提交的文件:${NC}"
    git diff --name-only --cached | sed 's/^/  /'
    git diff --name-only | sed 's/^/  ? /'

    echo ""
    echo -e "${CYAN}下一步操作:${NC}"
    echo -e "  1. ${GREEN}git add <files>${NC}     # 添加文件到暂存区"
    echo -e "  2. ${GREEN}git commit${NC}          # 提交变更"
    echo -e "  3. ${GREEN}./deploy/deploy.sh${NC}   # 部署到生产环境"

    exit 0
else
    echo -e "${RED}❌ 验证失败（发现 $ERRORS 个错误）${NC}"
    echo ""

    if [ $WARNINGS -gt 0 ]; then
        echo -e "${YELLOW}⚠️  另有 $WARNINGS 个警告${NC}"
    fi

    echo ""
    echo -e "${RED}请修复上述错误后再提交代码${NC}"
    echo ""
    echo -e "${CYAN}常见修复方法:${NC}"
    echo -e "  1. 配置语法错误: 检查 YAML 缩进和语法"
    echo -e "  2. Python 语法错误: 运行 ${YELLOW}python3 -m py_compile <file>${NC} 查看详情"
    echo -e "  3. 文件不存在: 检查文件路径是否正确"
    echo -e "  4. 版本号格式: 确保版本号符合 ${YELLOW}vMajor.Minor.Patch${NC} 格式"

    exit 1
fi
