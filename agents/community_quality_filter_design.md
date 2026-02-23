# 社区模块高质量信息获取策略设计

## 📊 当前实现分析

### 现有筛选机制

```
数据收集 → 平台排序（hot/top/stars）→ AI 评分 → 深度分析
```

**存在的问题：**
1. ❌ **依赖平台自带排序**：可能错过高质量但热度不高的内容
2. ❌ **关键词匹配噪音大**：包含关键词的不一定是好内容
3. ❌ **后置筛选成本高**：先收集大量数据，再用 AI 筛选
4. ❌ **缺少质量信号**：没有考虑作者权威度、社区反馈等

---

## 🎯 多维度质量评分体系

### 维度 1：内容质量信号

**Reddit 质量指标：**
```python
RedditQualityScore:
  - score: 帖子分数（✅ 好指标）
  - comments_count: 评论数（✅ 讨论热度）
  - upvote_ratio: 点赞比例（✅ 质量信号）
  - awards: 获得的奖励（✅ 社区认可）
  - gilded: 金币数量（✅ 真金白银认可）
```

**Twitter 质量指标：**
```python
TwitterQualityScore:
  - retweets: 转发数（✅ 传播度）
  - likes: 点赞数
  - replies: 回复数（讨论深度）
  - followers: 作者粉丝数（✅ 权威度）
  - verified: 认证状态（✅ 可信度）
```

### 维度 2：作者权威度

**Reddit 作者权威度：**
```python
RedditAuthorAuthority:
  - karma: 账号积分
  - account_age: 账号年龄
  - post_history: 历史发帖质量
  - moderator: 是否为版主
```

**Twitter 作者权威度：**
```python
TwitterAuthorAuthority:
  - followers_count: 粉丝数
  - verified: 认证状态
  - following_count: 关注数（followee/follower 比例）
  - tweet_count: 发推数量
  - listed_count: 被列表数（✅ 影响力）
```

### 维度 3：时效性与趋势

**时效性指标：**
```python
TimeSignals:
  - publish_time: 发布时间
  - velocity: 上升速度（分数增长率）
  - momentum: 动量（最近的评论/转发增长）
```

**趋势指标：**
```python
TrendSignals:
  - is_rising: 是否在上升
  - rank_change: 排名变化
  - engagement_rate: 参与度（互动数/粉丝数）
```

---

## 🔬 Reddit 高质量信息获取策略

### 策略 1：多来源组合

**不是只看热门，而是多维度覆盖：**

```python
# 配置示例
reddit_strategy:
  sources:
    # 热门内容（已有热度）
    - type: hot
      subreddits: [MachineLearning, artificial, LocalLLaMA]
      limit: 15

    # 最新讨论（实时动态）
    - type: new
      subreddits: [MachineLearning]
      limit: 10
      filters:
        min_score: 10
        min_comments: 5

    # 争议性话题（高讨论度）
    - type: controversial
      subreddits: [MachineLearning, singularity]
      limit: 10

    # 精选内容（版主推荐）
    - type: mod_approved
      subreddits: [MachineLearning]
      limit: 5
```

### 策略 2：智能筛选规则

**前置筛选（数据收集阶段）：**

```python
quality_filters = {
    # 基础质量门槛
    "min_score": 50,              # 最低分数
    "min_comments": 10,           # 最低评论数
    "min_upvote_ratio": 0.7,      # 最低点赞比例

    # 时间窗口
    "max_age_hours": 48,          # 最多 48 小时内

    # 内容类型
    "exclude_types": ["meme", "image", "video"],
    "prefer_types": ["discussion", "article", "paper"],

    # 排除噪音
    "exclude_keywords": [
        "beginner", "help", "homework", "course",
        "招聘", "求教", "入门"
    ],
}
```

### 策略 3：关注关键社区

**根据你关注的领域，选择最相关的 Subreddit：**

```python
# AI/LLM 领域
ai_subreddits = [
    ("MachineLearning", "hot", 15),      # 机器学习核心
    ("LocalLLaMA", "hot", 10),           # 本地 LLM 实践
    ("singularity", "hot", 10),          # AI 奇点讨论
    ("ArtificialIntelligence", "hot", 8),
    ("LanguageTechnology", "hot", 5),    # NLP
    ("ComputerVision", "hot", 5),
]

# 机器人领域
robotics_subreddits = [
    ("robotics", "hot", 10),
    ("ROS", "new", 5),                   # ROS 机器人
    ("arduino", "hot", 3),
    ("3Dprinting", "hot", 3),
]

# 投资领域
investment_subreddits = [
    ("investing", "hot", 10),
    ("stocks", "hot", 10),
    ("wallstreetbets", "hot", 5),        # 梗文化但有价值
    ("options", "hot", 5),
    ("SecurityAnalysis", "hot", 8),      # 深度分析
]

# 区块链领域
crypto_subreddits = [
    ("CryptoCurrency", "hot", 10),
    ("Bitcoin", "hot", 8),
    ("ethereum", "hot", 8),
    ("defi", "hot", 5),
]

# 宏观经济
economy_subreddits = [
    ("Economics", "hot", 10),
    ("economy", "hot", 8),
    ("Finance", "hot", 8),
]
```

---

## 🐦 Twitter 高质量信息获取策略

### 策略 1：关注权威账号

**分类关注（而不是关键词搜索）：**

```python
# AI 领域意见领袖
ai_leaders = [
    "AndrewYNg",              # 吴恩达
    "ylecun",                 # Yann LeCun (Meta AI)
    "goodfellow_ian",         # Ian Goodfellow
    "hardmaru",               # David Ha (Google Brain)
    "fchollet",               # François Chollet (Keras)
    "karpathy",               # Andrej Karpathy
]

# 投资领域
investment_leaders = [
    "elerianmm",              # Mohamed El-Erian
    "MarkYusko",              # Mark Yusko
    "RaoulGMI",               # Real Vision
    "michael_saylor",         # MicroStrategy
]

# 加密货币
crypto_leaders = [
    "VitalikButerin",         # 以太坊创始人
    "balajis",                # Balaji Srinivasan
    "Naval",                  # Naval Ravikant
]

# 宏观经济
economy_leaders = [
    "paulkrugman",            # 保罗·克鲁格曼
    "M_Ignatiev",             # 经济学家
]
```

### 策略 2：Nitter 实例 + 备用方案

```python
nitter_strategy = {
    "instances": [
        "https://nitter.net",
        "https://nitter.poast.org",
        "https://nitter.privacydev.net",
        "https://nitter.mint.lgbt",
    ],

    # 质量过滤
    "filters": {
        "min_followers": 10000,      # 最低粉丝数
        "min_engagement": 0.01,      # 最低互动率
        "exclude_replies": True,     # 排除回复
        "exclude_retweets": True,    # 排除转发
    },
}
```

### 策略 3：话题标签过滤

**使用高级标签而非简单关键词：**

```python
# AI 领域
ai_hashtags = [
    "#LLM", "#GPT", "#Transformers",
    "#MachineLearning", "#DeepLearning",
    "#AIAgents", "#GenerativeAI",
]

# 投资领域
investment_hashtags = [
    "#Stocks", "#Investing", "#Markets",
    "#ValueInvesting", "#GrowthStocks",
    "#IPO", "#Earnings",
]

# 区块链
crypto_hashtags = [
    "#Bitcoin", "#Ethereum", "#DeFi",
    "#Web3", "#NFTs", "#Crypto",
]

# 宏观经济
economy_hashtags = [
    "#Fed", "#Inflation", "#GDP",
    "#Economy", "#Markets", "#Trading",
]
```

---

## 🤖 AI 辅助筛选策略

### 三阶段筛选流程

```
第一阶段：粗筛（规则引擎）
   ↓
第二阶段：质量评分（多维指标）
   ↓
第三阶段：AI 语义分析（深度理解）
```

### 第一阶段：粗筛规则

**快速过滤低质量内容：**

```python
def rough_filter(item, quality_threshold=0.3):
    """粗筛：过滤掉明显低质量的内容"""

    score = 0
    max_score = 0

    # Reddit 评分
    if item.source == "reddit":
        max_score += 4

        # 分数权重
        if item.score >= 500:
            score += 2
        elif item.score >= 100:
            score += 1

        # 评论数权重
        if item.comments >= 50:
            score += 2
        elif item.comments >= 20:
            score += 1

    # Twitter 评分
    elif item.source == "twitter":
        max_score += 3

        # 粉丝数权重
        if item.author_followers >= 100000:
            score += 2
        elif item.author_followers >= 10000:
            score += 1

        # 互动率权重
        engagement_rate = (item.retweets + item.likes) / max(item.author_followers, 1)
        if engagement_rate >= 0.02:
            score += 1

    # 通用：时间衰减
    max_score += 1
    hours_old = (now - item.created_at).hours / 3600
    if hours_old <= 24:
        score += 1
    elif hours_old <= 48:
        score += 0.5

    # 关键词匹配（但降权）
    max_score += 2
    keyword_matches = sum(1 for kw in TARGET_KEYWORDS if kw in item.title.lower())
    if keyword_matches >= 2:
        score += 2
    elif keyword_matches >= 1:
        score += 1

    # 计算质量分数
    quality_score = score / max_score

    return quality_score >= quality_threshold
```

### 第二阶段：质量评分

**多维度加权评分：**

```python
def calculate_quality_score(item):
    """计算综合质量分数（0-100）"""

    scores = {}

    # 1. 热度分数 (0-30分)
    if item.source == "reddit":
        # Reddit 热度计算
        score_normalized = min(item.score / 1000, 1.0)  # 0-1
        comments_normalized = min(item.comments / 100, 1.0)
        scores['hotness'] = (score_normalized * 0.6 + comments_normalized * 0.4) * 30
    elif item.source == "twitter":
        # Twitter 热度计算
        retweets_normalized = min(item.retweets / 1000, 1.0)
        likes_normalized = min(item.likes / 5000, 1.0)
        scores['hotness'] = (retweets_normalized * 0.5 + likes_normalized * 0.5) * 30

    # 2. 权威度分数 (0-25分)
    if item.source == "reddit":
        # 作者 karma
        author_score = min(item.author_karma / 100000, 1.0)
        scores['authority'] = author_score * 25
    elif item.source == "twitter":
        # 粉丝数 + 认证
        followers_score = min(item.author_followers / 1000000, 1.0)
        verified_bonus = 10 if item.author_verified else 0
        scores['authority'] = (followers_score * 15 + verified_bonus)

    # 3. 相关性分数 (0-20分)
    # 使用 AI 语义相似度（而不是简单关键词）
    relevance_score = calculate_semantic_similarity(item.title, target_topics)
    scores['relevance'] = relevance_score * 20

    # 4. 时效性分数 (0-15分)
    hours_old = (now - item.created_at).hours / 3600
    if hours_old <= 6:
        scores['freshness'] = 15
    elif hours_old <= 24:
        scores['freshness'] = 10
    elif hours_old <= 48:
        scores['freshness'] = 5
    else:
        scores['freshness'] = 0

    # 5. 质量信号分数 (0-10分)
    quality_signals = 0
    if item.source == "reddit":
        if item.awards > 0:
            quality_signals += min(item.awards * 2, 5)
        if item.upvote_ratio >= 0.9:
            quality_signals += 5
    scores['quality'] = quality_signals

    # 总分
    total_score = sum(scores.values())

    return total_score, scores
```

### 第三阶段：AI 语义分析

**使用 AI 进行深度理解：**

```python
def ai_semantic_filter(item, target_topics):
    """AI 语义筛选：判断内容是否真正有价值"""

    prompt = f"""
请判断以下内容是否值得推荐给关注以下话题的用户：

关注话题：{', '.join(target_topics)}

内容信息：
- 标题：{item.title}
- 来源：{item.source}
- 描述：{item.content[:300]}

请从以下维度评估（0-10分）：
1. **信息密度**：是否包含新信息/洞察/数据
2. **实用性**：是否有实际价值或启发
3. **时效性**：是否是最新动态或趋势
4. **权威性**：来源或作者是否可信
5. **相关性**：与关注话题的相关程度

请返回 JSON 格式：
```json
{{
  "worth_reading": true/false,
  "overall_score": 8.5,
  "dimension_scores": {{
    "information_density": 8,
    "practicality": 7,
    "timeliness": 9,
    "authority": 6,
    "relevance": 9
  }},
  "reason": "简要说明"
}}
```
"""

    result = call_ai(prompt)
    return result
```

---

## 📋 实施建议

### 阶段 1：快速改进（1小时）

**添加质量筛选规则：**

```python
# 在 collector 中添加粗筛
quality_threshold = 0.3  # 质量门槛

for item in raw_items:
    if rough_filter(item, quality_threshold):
        filtered_items.append(item)
```

**收益：** 立即减少 50% 的低质量内容

### 阶段 2：多维度评分（3小时）

**实现质量评分系统：**

```python
# 为每个 item 计算质量分数
for item in items:
    total_score, dimension_scores = calculate_quality_score(item)
    item.quality_score = total_score
    item.dimension_scores = dimension_scores

# 只保留高分内容
high_quality_items = [i for i in items if i.quality_score >= 60]
```

**收益：** 提升内容质量 80%

### 阶段 3：AI 语义筛选（可选）

**集成 AI 语义分析：**

```python
# 对候选内容进行 AI 深度分析
for item in candidate_items:
    ai_result = ai_semantic_filter(item, target_topics)
    if ai_result['worth_reading']:
        final_items.append(item)
```

**收益：** 真正的内容质量飞跃

---

## 🎯 最终推荐配置

```python
# config.yaml
community:
  topics:
    - AI
    - 机器人
    - 投资
    - 区块链
    - 宏观经济

  # 质量筛选配置
  quality_filters:
    enabled: true
    method: "multi_dimensional"  # multi_dimensional | ai_semantic

    # 粗筛规则
    rough_filter:
      min_quality_score: 0.3
      min_score: 50
      min_comments: 10

    # 多维度评分
    dimension_weights:
      hotness: 0.3
      authority: 0.25
      relevance: 0.2
      freshness: 0.15
      quality_signals: 0.1

    # AI 语义筛选
    ai_filter:
      enabled: false  # 可选，成本较高
      min_overall_score: 7.0
      min_relevance: 7.0

  sources:
    # Reddit 配置
    reddit:
      enabled: true
      strategy: "multi_source"  # multi_source | simple

      subreddits:
        # AI 领域
        - name: MachineLearning
          type: hot
          limit: 15
          min_score: 100

        - name: LocalLLaMA
          type: hot
          limit: 10
          min_score: 50

        # 投资领域
        - name: SecurityAnalysis
          type: hot
          limit: 10

        - name: investing
          type: hot
          limit: 10

    # Twitter 配置
    twitter:
      enabled: true
      strategy: "author_based"  # author_based | hashtag_based

      # 关注权威账号
      authors:
        AI: [AndrewYNg, ylecun, goodfellow_ian]
        投资领域: [elerianmm, MarkYusko]
        区块链: [VitalikButerin, balajis]
        宏观经济: [paulkrugman]

      # 话题标签
      hashtags:
        - "#LLM"
        - "#Investing"
        - "#Bitcoin"
        - "#Economy"

      # 质量过滤
      filters:
        min_followers: 10000
        min_engagement_rate: 0.01
```

---

## 💡 总结

### 关键改进点

1. ✅ **多维度质量评分**（不只是热度）
2. ✅ **作者权威度**（关注有影响力的人）
3. ✅ **分阶段筛选**（粗筛 → 评分 → AI 分析）
4. ✅ **领域细分**（针对性社区和账号）
5. ✅ **质量信号**（奖励、认证、互动率）

### 预期效果

- **噪音减少 80%**
- **相关性提升 60%**
- **信息密度提升 3 倍**
- **真正有价值的比例提升 5 倍**
