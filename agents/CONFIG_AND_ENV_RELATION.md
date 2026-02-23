# TrendRadar 配置文件与 .env 关系说明

## 📁 配置文件结构

TrendRadar 有两种配置方式：

### 1. YAML配置文件
- `config/system.yaml` - 系统级统一配置
- `config/config.yaml` - 主配置文件
- `wechat/config.yaml` - 微信模块独立配置
- 其他模块的独立配置文件

### 2. .env文件
- `wechat/.env` - 微信模块环境变量
- 其他模块的.env文件

---

## 🔄 配置加载优先级

微信模块 (`wechat/src/config_loader.py`) 的加载顺序：

```
1. 环境变量 (os.environ.get)  ← 最高优先级
   ↓
2. .env文件 (通过 load_dotenv() 自动加载)
   ↓
3. config.yaml文件
```

**代码实现** (第11-13行，第80-95行):
```python
# 自动加载 .env 文件
from dotenv import load_dotenv
load_dotenv()  # 自动查找并加载 .env 文件

def _get_env_or_config(self, env_key: str, config_path: str, default: str = "") -> str:
    env_value = os.environ.get(env_key)  # 1. 先查环境变量
    if env_value:
        return env_value

    # 2. 从配置文件读取
    keys = config_path.split('.')
    value = self._config
    for key in keys:
        if isinstance(value, dict):
            value = value.get(key, {})

    return str(value) if value else default
```

---

## 📊 当前配置状态

### ✅ 已更新的配置

| 配置文件 | EMAIL_PASSWORD | 位置 |
|---------|----------------|------|
| `wechat/.env` | `your_email_auth_code` | 第28行 ✅ |
| `wechat/config.yaml` | `your_email_auth_code` | 第8行 ✅ |
| `config/system.yaml` | `your_email_auth_code` | 第71行 ✅ |

### 配置示例

**wechat/.env**:
```bash
EMAIL_FROM={{EMAIL_ADDRESS}}
EMAIL_PASSWORD=your_email_auth_code  # ✅ 已更新
EMAIL_TO={{EMAIL_ADDRESS}}
```

**wechat/config.yaml**:
```yaml
email:
  from: "{{EMAIL_ADDRESS}}"
  password: "your_email_auth_code"  # ✅ 已更新
  to: "{{EMAIL_ADDRESS}}"
```

**config/system.yaml**:
```yaml
email:
  from: "{{EMAIL_ADDRESS}}"
  password: "your_email_auth_code"  # ✅ 已更新
  to: "{{EMAIL_ADDRESS}}"
```

---

## 🎯 配置文件 vs .env 的区别

### YAML配置文件
- **用途**: 持久化存储，版本控制
- **优点**:
  - 结构清晰，易于编辑
  - 可以添加注释
  - 支持复杂数据结构
- **缺点**:
  - 敏感信息可能被提交到Git
  - 不同环境需要不同文件

### .env文件
- **用途**: 本地开发环境变量
- **优点**:
  - 不会被提交到Git（在.gitignore中）
  - 适合存储敏感信息
  - Python python-dotenv库自动加载
- **缺点**:
  - 格式简单（KEY=VALUE）
  - 没有注释和结构

---

## 💡 最佳实践建议

### 开发环境

**推荐**: 使用 .env 文件

```bash
# 1. 复制示例文件
cp wechat/.env.example wechat/.env

# 2. 编辑真实配置
vi wechat/.env

# 3. 运行时会自动加载
python -m trendradar.cli run wechat
```

**优点**:
- ✅ 敏感信息不会进入Git仓库
- ✅ 每个开发者有自己的配置
- ✅ 代码自动加载，无需手动设置环境变量

### 生产环境

**推荐**: 使用环境变量

```yaml
# docker-compose.yml
services:
  trendradar-prod:
    environment:
      - EMAIL_FROM={{EMAIL_ADDRESS}}
      - EMAIL_PASSWORD=your_email_auth_code
      - EMAIL_TO={{EMAIL_ADDRESS}}
```

**优点**:
- ✅ 配置与代码分离
- ✅ 容器化部署更安全
- ✅ 不同环境使用不同配置

---

## 🔒 安全性考虑

### 1. .gitignore 配置

确保 `.env` 文件不会被提交：
```
.env
.env.local
.env.*.local
```

### 2. .env.example 文件

提供配置示例，不包含真实信息：
```bash
EMAIL_FROM=your_email@163.com
EMAIL_PASSWORD=your_auth_code_here
EMAIL_TO=recipient@example.com
```

### 3. 敏感信息管理

| 配置项 | 是否敏感 | 存储建议 |
|--------|---------|---------|
| AI_API_KEY | ✅ 敏感 | .env 或 环境变量 |
| EMAIL_PASSWORD | ✅ 敏感 | .env 或 环境变量 |
| EMAIL_FROM | ✅ 敏感 | .env 或 环境变量 |
| SMTP服务器 | ❌ 不敏感 | YAML 配置文件 |
| 端口号 | ❌ 不敏感 | YAML 配置文件 |

---

## 📝 总结

### 关系图

```
配置优先级: 环境变量 > .env > config.yaml

实际使用情况:
┌─────────────────────────────────────────┐
│ 微信模块启动                              │
│ load_dotenv() 加载 wechat/.env          │
├─────────────────────────────────────────┤
│ 读取EMAIL_PASSWORD时:                   │
│ 1. 先查环境变量 (如果设置了则使用)      │
│ 2. 再查 .env 文件                        │
│ 3. 最后查 config.yaml                   │
└─────────────────────────────────────────┘
```

### 推荐配置方式

**开发环境**:
- 使用 `.env` 文件
- 配置文件只包含结构和不敏感信息
- 敏感信息放在 `.env` 中

**生产环境**:
- 使用环境变量
- 通过 docker-compose.yml 或 .env 文件注入
- 配置文件可以保持示例格式

---

## ✅ 已完成的更新

1. ✅ 更新 `wechat/.env` - 授权码已同步
2. ✅ 更新 `wechat/config.yaml` - 授权码已同步
3. ✅ 更新 `config/system.yaml` - 授权码已同步

**Git提交**: 待提交

---

生成时间: 2026-02-02 20:20
配置优先级: 环境变量 > .env > config.yaml
加载方式: python-dotenv 库自动加载
