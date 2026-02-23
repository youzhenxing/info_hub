# 提交前强制验证流程 - 快速参考

## 📋 规则 0：强制验证流程

所有代码修改和配置变更必须遵循以下严格流程：

```
修改 → 验证 → 提交 → 部署
```

## 🚀 快速开始

### 正确的提交流程

```bash
# 步骤 1: 修改代码/配置
vim config/config.yaml

# 步骤 2: 执行验证（必选）
bash deploy/pre-commit-verify.sh

# 步骤 3: 添加到暂存区
git add config/config.yaml CHANGELOG.md AGENTS.md

# 步骤 4: 提交（Git hook 自动再次验证）
git commit -m "chore(podcast): 优化配置"

# 步骤 5: 部署到生产环境
./deploy/deploy.sh
```

### 验证失败处理

```bash
# 查看验证结果
bash deploy/pre-commit-verify.sh

# 如果显示错误：
# ❌ 验证失败（发现 N 个错误）
# 请修复上述错误后再提交代码

# 常见错误修复：
# 1. YAML 语法错误 → 检查缩进和引号
# 2. Python 语法错误 → python3 -m py_compile <file>
# 3. 版本号格式错误 → 确保为 vMajor.Minor.Patch
# 4. 配置缺失 → 检查 AGENTS.md 规则 1-10

# 修复后重新验证
bash deploy/pre-commit-verify.sh

# 验证通过后提交
git add <files>
git commit -m "..."
```

## 🔍 验证内容（6 个阶段）

### Phase 1: Git 状态检查
- ✅ 检测是否有实际修改
- ✅ 检查当前分支

### Phase 2: 配置文件语法检查
- ✅ `config/config.yaml` YAML 语法
- ✅ `config/system.yaml` YAML 语法

### Phase 3: 关键配置一致性检查
- ✅ prompts 配置存在（prompt_file 或 prompts:）
- ✅ backfill 配置存在（播客模块）
- ✅ backfill.idle_hours 合理范围（1-24）

### Phase 4: Python 代码语法检查
- ✅ 所有修改的 `.py` 文件语法正确
- ✅ 使用 `python3 -m py_compile` 验证

### Phase 5: 版本号检查
- ✅ `deploy/version` 文件存在
- ✅ 版本格式正确（vMajor.Minor.Patch）

### Phase 6: 文档更新检查（警告级别）
- ⚠️ CHANGELOG.md 建议更新
- ⚠️ AGENTS.md 建议更新（如果是新增踩坑经验）

## 🛡️ 强制措施

### Git Hook 自动拦截

已安装 `.git/hooks/pre-commit`，每次 `git commit` 时自动执行验证：

```bash
git commit -m "test"
# 自动执行: bash deploy/pre-commit-verify.sh

# 如果验证失败：
# ❌ 验证失败（发现 N 个错误）
# 请修复上述错误后再提交代码
# (commit 被阻止)
```

### 跳过验证（不推荐）

如果确实需要跳过验证（不推荐）：

```bash
git commit --no-verify -m "..."
```

⚠️ **警告**：跳过验证可能导致：
- 配置语法错误
- 代码无法运行
- 部署失败
- 生产环境故障

## 📝 验证结果示例

### 验证通过

```
══════════════════════════════════════════════
  验证结果汇总
══════════════════════════════════════════════

✅ 所有检查通过，可以提交代码

待提交的文件:
  ? config/config.yaml
  ? CHANGELOG.md
  ? AGENTS.md

下一步操作:
  1. git add <files>     # 添加文件到暂存区
  2. git commit          # 提交变更
  3. ./deploy/deploy.sh   # 部署到生产环境
```

### 验证失败

```
══════════════════════════════════════════════
  验证结果汇总
══════════════════════════════════════════════

❌ 验证失败（发现 2 个错误）

⚠️  另有 1 个警告

请修复上述错误后再提交代码

常见修复方法:
  1. 配置语法错误: 检查 YAML 缩进和语法
  2. Python 语法错误: 运行 python3 -m py_compile <file> 查看详情
  3. 文件不存在: 检查文件路径是否正确
  4. 版本号格式: 确保版本号符合 vMajor.Minor.Patch 格式
```

## 🔧 故障排查

### 问题：验证脚本不存在

```bash
# 错误信息
⚠️  警告: 验证脚本不存在: deploy/pre-commit-verify.sh

# 解决方案
chmod +x deploy/pre-commit-verify.sh
```

### 问题：Git hook 未生效

```bash
# 检查 hook 是否存在
ls -la .git/hooks/pre-commit

# 如果不存在，重新安装
cat > .git/hooks/pre-commit << 'EOF'
#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
bash "$SCRIPT_DIR/deploy/pre-commit-verify.sh"
EOF
chmod +x .git/hooks/pre-commit
```

### 问题：Python 语法检查失败

```bash
# 查看详细错误
python3 -m py_compile trendradai/module.py

# 常见错误
# SyntaxError: invalid syntax
# IndentationError: unexpected indent

# 修复后重新验证
bash deploy/pre-commit-verify.sh
```

## 📚 相关文档

- [完整验证脚本源码](../deploy/pre-commit-verify.sh)
- [AGENTS.md 规则 0](../AGENTS.md#规则-0)（强制验证流程）
- [Git Hook 配置](../.git/hooks/pre-commit)
- [部署前检查](../deploy/pre-deploy-check.sh)（部署阶段验证）

## 🎯 最佳实践

1. **频繁验证**：每修改一个文件后立即执行验证
2. **小步提交**：将大的修改拆分成多个小提交
3. **写好提交信息**：使用规范的 commit message 格式
4. **更新文档**：及时更新 CHANGELOG.md 和 AGENTS.md
5. **不要跳过验证**：除非非常确定影响范围

## ⚠️ 历史教训

### v5.26.0 事故

**错误流程**：
```
修改配置 → 直接复制到生产环境 → 忘记提交代码
```

**后果**：
- 下次部署时配置丢失
- 代码和配置不同步
- 无法回溯配置变更历史

**正确流程**（现在）：
```
修改配置 → 验证 → 提交 → 部署
```

**效果**：
- ✅ 配置变更可追溯
- ✅ 代码和配置同步
- ✅ 避免配置丢失
