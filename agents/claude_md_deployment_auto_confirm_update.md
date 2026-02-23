# CLAUDE.md 生产部署规范更新说明

## 📅 更新时间
**2026-02-09 18:50**

---

## 🎯 更新目的

强化生产部署规范，明确要求必须使用 `yes "y" | bash deploy.sh` 方式执行部署，禁止使用任何临时变通方式。

---

## 📝 主要变更

### 1️⃣ 强制要求更新

**之前**：
```bash
# 只说"禁止手动部署"
生产环境部署必须使用标准部署流程
```

**现在**：
```bash
# 明确要求必须使用自动确认模式
⚠️ 重要：部署脚本必须使用自动确认模式
- ✅ 强制要求：必须使用 `yes "y" | bash deploy.sh` 方式执行
- ❌ 严禁使用：直接 `./deploy.sh`（会因等待输入而超时失败）
- ❌ 严禁使用：后台运行 `nohup ./deploy.sh &`（无法处理交互提示）
- ❌ 严禁使用：其他临时变通方式（如手动 docker build）
```

### 2️⃣ 标准部署流程更新

**步骤2：执行标准部署脚本**

**之前**：
```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
./deploy.sh
```

**现在**：
```bash
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
```

**新增说明**：
> **为什么必须使用 `yes "y" |`？**
> - 脚本会检查版本是否已存在，并提示"是否覆盖现有版本？(y/N)"
> - 使用 `yes "y" |` 自动回答所有确认提示，避免超时失败
> - 确保部署流程完整执行，不会因等待输入而中断

### 3️⃣ 手动部署场景明确禁止

**之前**：
```bash
仅限以下场景可以使用手动部署：
- ✅ 开发测试阶段的快速迭代
- ✅ 实验性功能的临时部署
- ✅ 本地环境调试
```

**现在**：
```bash
仅限以下场景可以使用手动部署：
- ✅ 开发测试阶段的快速迭代（仅限本地环境）
- ✅ 本地环境调试

⚠️ 严禁场景：
- ❌ 生产环境部署
- ❌ 正式版本发布
- ❌ 团队共享环境部署
- ❌ 使用 `docker build + docker run` 的临时部署
- ❌ 使用后台运行 `nohup ./deploy.sh &` 的部署
- ❌ 任何跳过标准流程的变通方式

生产环境必须且只能使用：`yes "y" | bash deploy.sh`
```

### 4️⃣ 错误示例扩展

**新增5种常见错误**：

```bash
# 错误3: 不使用自动确认（会超时失败）
cd deploy
./deploy.sh  # ❌ 会卡在"是否覆盖现有版本？(y/N)"提示

# 错误4: 后台运行（无法处理交互）
cd deploy
nohup ./deploy.sh &  # ❌ 超时失败（exit code 144）

# 错误5: 手动 docker-compose up
cd releases/v5.25.3
docker-compose up -d  # ❌ 文件可能未同步，volumes不完整
```

### 5️⃣ 新增规则11：部署脚本自动确认模式

在"踩坑经验"章节新增**规则11**：

```markdown
#### ⚡ 规则 11：部署脚本必须使用自动确认模式（强制）

生产部署必须使用 `yes "y" | bash deploy.sh` 方式执行。

问题根源：
- deploy.sh 会检查版本是否已存在，并提示用户确认
- 直接运行 ./deploy.sh 会卡在等待输入，最终超时失败（exit code 144）
- 后台运行 nohup ./deploy.sh & 同样会因无法处理交互而失败

正确做法：
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh
```

包含：
- ✅ 正确做法和错误做法对比
- ✅ 为什么必须这样做的详细解释
- ✅ 验证部署是否成功的检查方法

### 6️⃣ 部署检查清单增强

**新增检查项**：
- [ ] **使用 `yes "y" | bash deploy.sh` 方式部署**（⚠️ 强制要求）
- [ ] **关键文件已挂载**：bootstrap.py, prompts/, shared/lib/
- [ ] **Bootstrap机制正常执行**（查看日志）

---

## 🔍 问题背景

### 实际案例

在 v5.25.3 部署过程中遇到的问题：

**第一次尝试**：
```bash
bash deploy.sh  # 后台运行
```

**结果**：
- ❌ 脚本卡在"是否覆盖现有版本？(y/N)"提示
- ❌ 无法接收输入，超时被终止（exit code 144）
- ❌ 部署失败

**解决方案**：
```bash
yes "y" | bash deploy.sh  # 自动确认所有提示
```

**结果**：
- ✅ 自动回答所有确认提示
- ✅ 部署流程完整执行
- ✅ 所有文件正确同步（bootstrap.py, prompts/, shared/lib/）

---

## 📊 影响范围

### 直接影响

1. **所有生产部署**
   - 必须使用 `yes "y" | bash deploy.sh`
   - 任何其他方式都被视为违规

2. **部署脚本执行**
   - 禁止直接运行 `./deploy.sh`
   - 禁止后台运行 `nohup ./deploy.sh &`

3. **紧急情况处理**
   - 即使是紧急修复，也必须使用标准方式
   - 不得因时间紧迫而使用变通方式

### 长期影响

1. **部署成功率提升**
   - 避免因等待输入导致的超时失败
   - 确保部署流程完整执行

2. **文件完整性保障**
   - 确保所有关键文件正确同步
   - 避免手动部署导致的文件缺失

3. **团队协作规范**
   - 统一部署方式，降低沟通成本
   - 便于问题追溯和排查

---

## ✅ 验证方法

### 部署后必须验证

```bash
# 1. 检查容器版本
docker logs trendradar-prod | grep "APP_VERSION"
# 应该看到：APP_VERSION = 5.25.3

# 2. 验证关键文件存在
docker exec trendradar-prod ls -la /app/bootstrap.py
docker exec trendradar-prod ls -la /app/prompts/
docker exec trendradar-prod ls -la /app/shared/lib/

# 3. 验证Bootstrap执行
docker logs trendradar-prod | grep -A 5 "Bootstrap"
# 应该看到：
# [Bootstrap] APP_VERSION = 5.25.3
# [Bootstrap] 各模块状态查询:
# [Bootstrap] 所有模块已是当前版本，跳过引导
```

---

## 🎯 关键要点

1. **强制要求**：生产部署必须使用 `yes "y" | bash deploy.sh`
2. **严禁行为**：禁止所有临时变通方式
3. **原因明确**：避免超时失败，确保文件完整同步
4. **验证完备**：提供完整的验证步骤

---

## 📚 相关文档

- 完整CLAUDE.md：`/home/zxy/Documents/code/TrendRadar/CLAUDE.md`
- 部署修复报告：`agents/deployment_fix_complete_report.md`
- 第一次部署失败分析：`/tmp/claude-1000/-home-zxy-Documents-code-TrendRadar/tasks/b736679.output`

---

*更新人：Claude Sonnet 4.5*
*更新时间：2026-02-09 18:50*
