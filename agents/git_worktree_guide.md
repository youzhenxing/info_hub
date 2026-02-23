# Git Worktree 协作开发指南

## 📋 场景说明

当多个会话同时修改同一仓库时，使用 **git worktree** 可以实现：
- ✅ 每个会话在独立分支工作，避免冲突
- ✅ 无需频繁 `git stash` 和 `git checkout`
- ✅ 可以同时运行和测试不同功能
- ✅ 合并时更清晰，减少冲突

---

## 🎯 推荐工作流程

### 方案 A：功能分支隔离（推荐）

#### Step 1: 为新功能创建 worktree

```bash
# 基础语法
git worktree add <路径> -b <分支名> [起点分支]

# 实例：为投资板块优化创建独立 worktree
git worktree add ../TrendRadar-investment -b feature/investment-optimization

# 为另一个会话的功能创建 worktree
git worktree add ../TrendRadar-community -b feature/community-enhancement
```

#### Step 2: 查看所有 worktree

```bash
git worktree list
# 输出示例：
# /home/zxy/Documents/code/TrendRadar              77cf1218 [master]
# /home/zxy/Documents/code/TrendRadar-investment   77cf1218 [feature/investment-optimization]
# /home/zxy/Documents/code/TrendRadar-community    77cf1218 [feature/community-enhancement]
```

#### Step 3: 在不同 worktree 中独立工作

```bash
# 终端 1：投资板块优化
cd ../TrendRadar-investment
# 进行开发、测试、提交...

# 终端 2：社区功能增强
cd ../TrendRadar-community
# 进行开发、测试、提交...

# 终端 3：主仓库（保持稳定）
cd /home/zxy/Documents/code/TrendRadar
# 运行生产版本，或合并其他分支...
```

#### Step 4: 合并功能到主分支

```bash
# 在主仓库中合并
cd /home/zxy/Documents/code/TrendRadar

# 合并投资板块优化
git merge feature/investment-optimization --no-ff -m "feat: 投资板块优化"

# 合并社区功能增强
git merge feature/community-enhancement --no-ff -m "feat: 社区功能增强"
```

#### Step 5: 清理已合并的 worktree

```bash
# 删除功能分支后，移除对应的 worktree
git worktree remove ../TrendRadar-investment
git branch -d feature/investment-optimization

# 或者在 worktree 目录内执行
cd ../TrendRadar-investment
git worktree remove .
```

---

## 🛠️ 实用命令清单

### 创建 worktree

```bash
# 从当前 HEAD 创建新分支
git worktree add ../my-feature -b feature/my-feature

# 从指定提交创建新分支
git worktree add ../my-feature -b feature/my-feature abc1234

# 从现有分支创建 worktree（检出已存在的分支）
git worktree add ../my-hotfix fix/critical-bug

# 创建临时 worktree（分离 HEAD 状态）
git worktree add ../test-build HEAD~1
```

### 管理 worktree

```bash
# 列出所有 worktree
git worktree list

# 显示 worktree 详细信息
git worktree list --porcelain

# 移除 worktree（先 cd 到其他目录）
git worktree remove ../my-feature

# 或者在 worktree 内部
cd ../my-feature
git worktree remove .

# 移动 worktree 到新位置
git worktree move ../old-path ../new-path

# 修复 worktree（如果 .git 文件损坏）
git worktree repair ../my-feature
```

### worktree 状态检查

```bash
# 检查 worktree 是否干净
git worktree list

# 查看 worktree 的分支状态
cd ../my-feature
git status

# 查看所有分支的提交
git log --all --graph --oneline --decorate
```

---

## 📝 最佳实践

### 1. 命名规范

```bash
# 功能分支
feature/investment-optimization
feature/community-enhancement
feature/podcast-language

# 修复分支
fix/critical-bug
fix/database-connection

# 实验性分支
experiment/new-ai-model
experiment/ui-redesign
```

### 2. worktree 路径规范

```bash
# 推荐放在父目录，便于管理
git worktree add ../TrendRadar-investment -b feature/investment-optimization
git worktree add ../TrendRadar-community -b feature/community-enhancement
git worktree add ../TrendRadar-testing -b test/integration-tests

# 或使用统一的 worktree 目录
git worktree add ./worktrees/investment -b feature/investment-optimization
git worktree add ./worktrees/community -b feature/community-enhancement
```

### 3. 分支策略

```bash
# 主分支（稳定）
master ─────┬──── 合并 feature/investment-optimization
            │
            └──── 合并 feature/community-enhancement

# 功能分支（开发中）
feature/investment-optimization ──── 独立开发
feature/community-enhancement ─────── 独立开发

# 实验分支（临时）
experiment/new-ai-model ───────────── 随时删除
```

### 4. 合并时机

```bash
# ✅ 好的时机
- 功能开发完成并测试通过
- 修复了关键 bug
- 到达一个稳定的里程碑

# ❌ 不好的时机
- 功能未完成（半成品）
- 代码无法运行
- 有未解决的冲突
```

---

## 🔄 多会话协作示例

### 场景：同时开发投资板块和社区功能

#### 会话 A：投资板块优化

```bash
# 1. 创建投资板块专用 worktree
git worktree add ../TrendRadar-investment -b feature/investment-optimization
cd ../TrendRadar-investment

# 2. 开始开发
vim trendradar/investment/collector.py
vim config/config.yaml

# 3. 提交更改
git add .
git commit -m "feat(investment): 启用RSS源并增强时间过滤

- 启用金十数据、东方财富等RSS源
- 实现市场感知时间过滤（A股/港股当天，美股昨21:00后）
- 金融分析源放宽到3天窗口

Refs: #123"

# 4. 推送到远程（可选）
git push -u origin feature/investment-optimization
```

#### 会话 B：社区功能增强

```bash
# 1. 创建社区功能专用 worktree
git worktree add ../TrendRadar-community -b feature/community-enhancement
cd ../TrendRadar-community

# 2. 开始开发（与会话 A 完全独立）
vim trendradar/community/sync.py
vim config/config.yaml

# 3. 提交更改
git add .
git commit -m "feat(community): 增强社区内容同步

- 新增 Reddit 同步源
- 优化内容去重逻辑
- 增加质量评分机制

Refs: #124"

# 4. 推送到远程
git push -u origin feature/community-enhancement
```

#### 会话 C：主仓库（生产环境）

```bash
# 1. 在主仓库中保持稳定
cd /home/zxy/Documents/code/TrendRadar

# 2. 查看其他分支的进度
git log --graph --oneline --decorate feature/investment-optimization
git log --graph --oneline --decorate feature/community-enhancement

# 3. 合并功能（按优先级）
# 先合并投资板块优化
git merge feature/investment-optimization --no-ff -m "feat: 投资板块优化"
python3 -m pytest tests/investment/  # 运行测试

# 再合并社区功能
git merge feature/community-enhancement --no-ff -m "feat: 社区功能增强"
python3 -m pytest tests/community/   # 运行测试

# 4. 推送到主分支
git push origin master
```

---

## ⚠️ 注意事项

### 1. 避免的问题

```bash
# ❌ 不要在多个 worktree 中修改同一文件的同一部分
# 会造成合并冲突

# ❌ 不要删除主 worktree 的 .git 目录
# 会导致所有 worktree 失效

# ❌ 不要在 worktree 中执行 git init
# 会创建独立的 git 仓库
```

### 2. 冲突解决

```bash
# 如果两个分支修改了同一文件，合并时会有冲突
git merge feature/investment-optimization

# 解决冲突
vim config/config.yaml  # 手动解决冲突
git add config/config.yaml
git commit -m "merge: 解决配置文件冲突"

# 或使用合并工具
git mergetool
```

### 3. worktree 清理

```bash
# 定期清理已合并的 worktree
git worktree list
# 查看哪些分支已经合并到 master

# 删除已合并的 worktree
git worktree remove ../TrendRadar-investment
git branch -d feature/investment-optimization

# 清理所有已合并的分支
git branch --merged | grep -v '\*' | xargs -r git branch -d
```

---

## 🚀 快速开始模板

### 为当前会话创建独立 worktree

```bash
# 1. 确定功能名称
FEATURE_NAME="investment-optimization"

# 2. 创建 worktree
git worktree add ../TrendRadar-${FEATURE_NAME} -b feature/${FEATURE_NAME}

# 3. 进入 worktree
cd ../TrendRadar-${FEATURE_NAME}

# 4. 查看状态
git status
git branch

# 5. 开始开发
# ... 进行开发 ...

# 6. 提交更改
git add .
git commit -m "feat: 功能描述"

# 7. 推送到远程（可选）
git push -u origin feature/${FEATURE_NAME}

# 8. 完成后清理（回到主仓库）
cd /home/zxy/Documents/code/TrendRadar
git worktree remove ../TrendRadar-${FEATURE_NAME}
git branch -d feature/${FEATURE_NAME}
```

---

## 📚 相关资源

- **Git 官方文档**：https://git-scm.com/docs/git-worktree
- **Pro Git 书籍**：https://git-scm.com/book/zh/v2/Git-%E5%B7%A5%E5%85%B7-%E9%AB%98%E7%BA%A7%E5%90%88%E5%B9%B6
- **Atlassian Git 教程**：https://www.atlassian.com/git/tutorials/advanced-overview

---

## 💡 常见问题

### Q1: worktree 和 submodule 有什么区别？

**A:** worktree 是同一仓库的不同分支，submodule 是完全独立的仓库。worktree 共享 `.git` 目录，submodule 有自己的 `.git`。

### Q2: 可以在 worktree 中推送代码吗？

**A:** 可以！worktree 就是普通的分支，可以正常推送、拉取、合并。

### Q3: 如何在 IDE 中使用 worktree？

**A:** 在 IDE 中打开不同的 worktree 目录作为独立项目，如 VSCode 的 `Multi-root Workspace`。

### Q4: worktree 会占用双倍空间吗？

**A:** 不会。worktree 只包含工作文件，`.git` 目录是共享的。空间占用约等于工作文件大小。

### Q5: 如何在 worktree 之间切换？

**A:** 不需要切换！每个 worktree 是独立目录，可以同时打开多个终端或 IDE 窗口。

---

## ✅ 总结

**使用 git worktree 的优势：**
- ✅ 无需频繁切换分支
- ✅ 多功能并行开发
- ✅ 隔离开发环境
- ✅ 减少合并冲突
- ✅ 更清晰的代码审查

**适用场景：**
- 🔧 同时开发多个功能
- 🐛 紧急修复线上 bug
- 🧪 并行测试多个方案
- 👥 多人协作同一仓库

**不适用场景：**
- ❌ 简单的单功能开发（直接用分支即可）
- ❌ 磁盘空间极度受限
- ❌ 需要频繁删除重建 worktree
