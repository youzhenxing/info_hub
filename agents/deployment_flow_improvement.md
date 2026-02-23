# 部署流程改进 - 避免 prompts 挂载失效

## 日期

2026-02-13

---

## 问题描述

**问题现象**：prompts 目录挂载失效导致渲染效果退化，已反复出现多次。

**问题根源**：
1. `deploy.sh` 只负责准备文件（复制 prompts、生成 docker-compose.yml），但**不会重启容器**
2. 用户容易遗漏执行 `trend update vX.X.X`，只执行了第一步
3. 使用 `docker restart` 而非 `trend update`，导致 volume 配置不生效

---

## 流程分析

| 步骤 | 命令 | 容器行为 | volume 配置 |
|--------|--------|----------|-------------|
| 1 | `./deploy/deploy.sh` | 不重启 | ⚠️ 已写入未生效 |
| 2 | `docker restart` | 只重启进程 | ❌ 不读取新配置 |
| 3 | `trend update` | 完整重启 | ✅ 重新读取配置 |

**漏洞**：步骤 1 和步骤 3 之间没有强制关联，用户容易遗漏步骤 3。

---

## 改进方案

### deploy.sh 自动执行 update

在 `deploy.sh` 最后**自动执行** `trend update`，完成完整的部署流程。

**优点**：
- ✅ 一步到位，避免用户遗漏
- ✅ 立即生效，容器使用新配置
- ✅ `.deployed_version` 自动更新，提交时版本一致

---

## 修改内容

### 文件：`deploy/deploy.sh`

**位置**：文件末尾，"下一步"提示部分

**修改前**：
```bash
echo -e "${CYAN}💡 下一步:${NC}"
echo -e "   查看所有版本: ${YELLOW}trend versions${NC}"
echo -e "   切换到此版本: ${YELLOW}trend update v${VERSION}${NC}"
echo ""
```

**修改后**：
```bash
# 自动切换到新版本
echo -e "${CYAN}🚀 正在切换到版本 v${VERSION}...${NC}"
"$SCRIPT_DIR/update.sh" "v${VERSION}"

# 检查切换结果
if [ $? -eq 0 ]; then
    echo ""
    echo -e "${GREEN}✅ 部署 + 切换完成！${NC}"
    echo -e "${CYAN}💡 查看日志: ${YELLOW}docker logs trendradar-prod -f${NC}"
else
    echo ""
    echo -e "${RED}❌ 切换失败${NC}"
    echo -e "${CYAN}💡 请手动执行: ${YELLOW}trend update v${VERSION}${NC}"
fi
```

---

## 验证方法

### 1. 完整部署测试

```bash
# 1. 修改版本号
echo "5.29.0" > version

# 2. 执行部署
cd /home/zxy/Documents/code/TrendRadar/deploy
yes "y" | bash deploy.sh

# 验证：应该自动切换到新版本，无需手动执行 trend update
```

**预期输出**：
```
✅ 版本发布完成！

🚀 正在切换到版本 v5.29.0...
[update.sh 输出...]

✅ 部署 + 切换完成！
💡 查看日志: docker logs trendradar-prod -f
```

### 2. 验证容器配置

```bash
# 检查容器内 prompts 目录
docker exec trendradar-prod ls -la /app/prompts/

# 验证版本一致性
cat /home/zxy/Documents/code/TrendRadar/.deployed_version
docker exec trendradar-prod printenv APP_VERSION
```

**预期结果**：
- 容器内 `/app/prompts/` 有 6 个文件
- `.deployed_version` 版本与 `APP_VERSION` 一致

### 3. 验证 pre-commit hook

```bash
# 部署完成后，尝试提交代码
cd /home/zxy/Documents/code/TrendRadar
git add .
git commit -m "test: 验证自动 update 流程"
```

**预期结果**：pre-commit hook 通过，因为 `.deployed_version` 已更新

---

## 经验总结

`★ Insight ─────────────────────────────────────`
1. **一步到位的重要性**：将部署的两个步骤合并为一个自动流程，避免用户遗漏
2. **docker restart 的陷阱**：只重启容器进程，不重新读取 docker-compose.yml
3. **版本一致性追踪**：update.sh 会更新 .deployed_version，确保提交时版本同步
`─────────────────────────────────────────────────`

---

## 回滚方案

如果修改导致问题：

1. 恢复原始 `deploy.sh`（从 Git）
2. 重新部署

---

## 相关文件

- `deploy/deploy.sh` - 添加自动 update 步骤
- `agents/deployment_flow_improvement.md` - 本文档
- `CLAUDE.md` - 规则 12 可能需要补充
