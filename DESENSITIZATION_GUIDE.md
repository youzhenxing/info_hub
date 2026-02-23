# 脱敏记录与部署配置指南

> 本文档记录了项目中所有敏感信息的脱敏位置，方便后续进行部署配置。

---

## 变量定义

在部署前，你需要准备以下变量，并将它们替换到配置文件中：

| 变量名 | 说明 | 获取方式 |
|--------|------|----------|
| `{{SILICONFLOW_API_KEY}}` | SiliconFlow API Key（AI 内容分析，使用 DeepSeek-V3/DeepSeek-R1 模型） | https://siliconflow.cn |
| `{{EMAIL_AUTH_CODE}}` | 163 邮箱授权码 | 邮箱设置 → POP3/SMTP/IMAP → 开启并获取授权码 |
| `{{EMAIL_ADDRESS}}` | 163 邮箱地址 | 你的邮箱地址 |
| `{{WEWE_RSS_AUTH_CODE}}` | WeWe RSS 自定义授权码 | 在 WeWe RSS 服务中自行设置 |
| `{{ASSEMBLYAI_API_KEY}}` | AssemblyAI API Key（语音转文字 + 说话人分离） | https://www.assemblyai.com |

---

## 配置项清单

### 1. SiliconFlow API Key

**变量**: `{{SILICONFLOW_API_KEY}}`
**涉及文件数**: 27个

| 文件 | 行号 | 占位符 | 说明 |
|------|------|--------|------|
| config/config.yaml | 550 | {{SILICONFLOW_API_KEY}} | SiliconFlow API (播客分析) |
| config/config.yaml | 579 | {{SILICONFLOW_API_KEY}} | SiliconFlow API (公众号分析) |
| config/config.yaml | 1057 | {{SILICONFLOW_API_KEY}} | SiliconFlow API (社区分析) |
| config/config.yaml | 1221 | {{SILICONFLOW_API_KEY}} | SiliconFlow API (投资分析) |
| config/system.yaml | 51 | {{SILICONFLOW_API_KEY}} | 系统默认 AI 配置 |
| agents/.env | 87 | {{SILICONFLOW_API_KEY}} | Docker 环境变量 |
| agents/.env.backup | 87 | {{SILICONFLOW_API_KEY}} | 环境变量备份 |
| agents/system.yaml.backup.20260209_183832 | 51 | {{SILICONFLOW_API_KEY}} | 配置文件备份 |
| agents/siliconflow_api_usage.md | - | {{SILICONFLOW_API_KEY}} | 开发文档 |
| agents/ai_analysis_diagnostic_report.md | - | {{SILICONFLOW_API_KEY}} | 诊断报告 |
| agents/ai_analysis_fix_complete_report.md | - | {{SILICONFLOW_API_KEY}} | 修复报告 |
| agents/WECHAT_AI_FIX_VERIFICATION.md | - | {{SILICONFLOW_API_KEY}} | 验证报告 |
| agents/WECHAT_AI_FIX_REPORT.md | - | {{SILICONFLOW_API_KEY}} | 修复报告 |
| agents/WECHAT_EMAIL_SUCCESS.md | - | {{SILICONFLOW_API_KEY}} | 部署报告 |
| agents/WECHAT_EMAIL_SETUP.md | - | {{SILICONFLOW_API_KEY}} | 配置文档 |
| agents/WECHAT_FIX_SUMMARY.md | - | {{SILICONFLOW_API_KEY}} | 修复总结 |
| agents/EMAIL_CONFIG_SYNC.md | - | {{SILICONFLOW_API_KEY}} | 配置同步 |
| agents/OLD_TESTS_CLEANUP_PLAN.md | - | {{SILICONFLOW_API_KEY}} | 测试计划 |
| agents/ARCHITECTURE_REVIEW_2026.md | - | {{SILICONFLOW_API_KEY}} | 架构文档 |
| agents/FINAL_TEST_SUMMARY.md | - | {{SILICONFLOW_API_KEY}} | 测试总结 |
| agents/podcast_migration_summary.md | - | {{SILICONFLOW_API_KEY}} | 迁移文档 |
| agents/system_code_review_20260213.md | - | {{SILICONFLOW_API_KEY}} | 代码审查 |
| agents/DEPLOY_UPDATE_v5.20.0.md | - | {{SILICONFLOW_API_KEY}} | 部署更新 |
| agents/tasks/20260128_task.txt | - | {{SILICONFLOW_API_KEY}} | 任务记录 |
| agents/test_ai_proxy_fix.py | - | {{SILICONFLOW_API_KEY}} | 测试代码 |
| batch_process_podcasts.py | - | {{SILICONFLOW_API_KEY}} | Python 脚本 |
| retry_single.py | - | {{SILICONFLOW_API_KEY}} | Python 脚本 |
| reanalyze_podcasts.py | - | {{SILICONFLOW_API_KEY}} | Python 脚本 |

### 2. 邮箱授权码

**变量**: `{{EMAIL_AUTH_CODE}}`
**涉及文件数**: 8个

| 文件 | 行号 | 占位符 | 说明 |
|------|------|--------|------|
| config/config.yaml | 11 | {{EMAIL_AUTH_CODE}} | 邮件发送配置 |
| config/config.yaml | 262 | {{EMAIL_AUTH_CODE}} | 公众号模块邮件配置 |
| config/system.yaml | 71 | {{EMAIL_AUTH_CODE}} | 系统邮件配置 |
| agents/.env | 33 | {{EMAIL_AUTH_CODE}} | Docker 环境变量 |
| agents/system.yaml.backup.20260209_183832 | 71 | {{EMAIL_AUTH_CODE}} | 配置文件备份 |
| agents/wechat_auth_code_check_report.md | - | {{EMAIL_AUTH_CODE}} | 授权码检查报告 |
| agents/wechat_push_task_execution_report.md | - | {{EMAIL_AUTH_CODE}} | 任务执行报告 |
| agents/wechat_deployment_update_report.md | - | {{EMAIL_AUTH_CODE}} | 部署更新报告 |
| agents/email_auth_code_update_report.md | - | {{EMAIL_AUTH_CODE}} | 授权码更新报告 |

### 3. 邮箱地址

**变量**: `{{EMAIL_ADDRESS}}`

| 文件 | 行号 | 占位符 | 说明 |
|------|------|--------|------|
| config/config.yaml | 10,12 | {{EMAIL_ADDRESS}} | 邮件配置 |
| config/system.yaml | 70,72 | {{EMAIL_ADDRESS}} | 系统邮件配置 |
| agents/.env | 32,34 | {{EMAIL_ADDRESS}} | Docker 环境变量 |

### 4. WeWe RSS 授权码

**变量**: `{{WEWE_RSS_AUTH_CODE}}`
**涉及文件数**: 1个

| 文件 | 行号 | 占位符 | 说明 |
|------|------|--------|------|
| config/system.yaml | 163 | {{WEWE_RSS_AUTH_CODE}} | WeWe RSS 授权码 |

### 5. AssemblyAI API Key

**变量**: `{{ASSEMBLYAI_API_KEY}}`
**涉及文件数**: 2个

| 文件 | 行号 | 占位符 | 说明 |
|------|------|--------|------|
| config/config.yaml | 557 | {{ASSEMBLYAI_API_KEY}} | AssemblyAI API (语音转文字 + 说话人分离) |
| agents/.env | 119 | {{ASSEMBLYAI_API_KEY}} | Docker 环境变量 |

---

## 部署配置指南

### 方式一: 修改配置文件

编辑 `config/config.yaml`:

```yaml
# 邮件配置
EMAIL_FROM: "{{EMAIL_ADDRESS}}"
EMAIL_PASSWORD: "{{EMAIL_AUTH_CODE}}"
EMAIL_TO: "{{EMAIL_ADDRESS}}"

# 播客分析
podcast:
  analysis:
    api_key: "{{SILICONFLOW_API_KEY}}"

# 公众号分析
wechat:
  ai:
    api_key: "{{SILICONFLOW_API_KEY}}"

# 社区分析
community:
  analysis:
    api_key: "{{SILICONFLOW_API_KEY}}"

# 投资分析
investment:
  analysis:
    api_key: "{{SILICONFLOW_API_KEY}}"
```

编辑 `config/system.yaml`:

```yaml
ai:
  api_key: "{{SILICONFLOW_API_KEY}}"

notification:
  channels:
    email:
      from: "{{EMAIL_ADDRESS}}"
      password: "{{EMAIL_AUTH_CODE}}"
      to: "{{EMAIL_ADDRESS}}"

wewe_rss:
  auth_code: "{{WEWE_RSS_AUTH_CODE}}"
```

### 方式二: 环境变量

编辑 `agents/.env`:

```bash
# 邮箱配置
EMAIL_FROM={{EMAIL_ADDRESS}}
EMAIL_PASSWORD={{EMAIL_AUTH_CODE}}
EMAIL_TO={{EMAIL_ADDRESS}}

# AI API Key
AI_API_KEY={{SILICONFLOW_API_KEY}}

# AssemblyAI (语音转文字 + 说话人分离)
ASSEMBLYAI_API_KEY={{ASSEMBLYAI_API_KEY}}
```

---

## 批量部署脚本模板

```bash
#!/bin/bash

# 配置变量
export AI_API_KEY="{{SILICONFLOW_API_KEY}}"
export EMAIL_PASSWORD="{{EMAIL_AUTH_CODE}}"
export EMAIL_FROM="{{EMAIL_ADDRESS}}"
export EMAIL_TO="{{EMAIL_ADDRESS}}"
export ASSEMBLYAI_API_KEY="{{ASSEMBLYAI_API_KEY}}"
export TELEGRAM_CHAT_ID="{{TELEGRAM_CHAT_ID}}"

# 启动服务
docker-compose up -d
```

---

## 验证配置

配置完成后，运行以下命令验证:

```bash
# 检查环境变量
python -c "from dotenv import load_dotenv; load_dotenv('agents/.env'); import os; print('AI_API_KEY:', bool(os.getenv('AI_API_KEY'))); print('EMAIL_PASSWORD:', bool(os.getenv('EMAIL_PASSWORD')))"

# 测试发送邮件
python debug_email_config.py
```
