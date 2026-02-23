#!/usr/bin/env python3
# coding=utf-8
"""
重新分析已转写的播客

使用更新后的 prompt（含信息提取+分段落详述）对已有转写文本重新进行 AI 分析并发送邮件
"""

import os
import sys
import re
import time
import requests
import markdown
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
SILICONFLOW_API_KEY = "{{SILICONFLOW_API_KEY}}"
EMAIL_FROM = "{{EMAIL_ADDRESS}}"
EMAIL_PASSWORD = "{{EMAIL_AUTH_CODE}}"
EMAIL_TO = "{{EMAIL_ADDRESS}}"
EMAIL_SMTP = "smtp.163.com"
EMAIL_PORT = 465

# 路径
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "agents" / "podcast_full_test"

# 待分析的播客
PODCASTS = [
    {
        "name": "硅谷101",
        "transcript_file": "transcript_硅谷101.txt",
        "language": "zh",
        "title": "E222｜紧身裤消失，谁在定义时尚潮流？",
        "url": "https://www.xiaoyuzhoufm.com/episode/6976affadf36db2a39862937",
    },
    {
        "name": "张小珺Jùn｜商业访谈录",
        "transcript_file": "transcript_张小珺jùn｜商业访谈录.txt",
        "language": "zh",
        "title": "最新一期",
        "url": "https://www.xiaoyuzhoufm.com/podcast/626b46ea9cbbf0451cf5a962",
    },
    {
        "name": "罗永浩的十字路口",
        "transcript_file": "transcript_罗永浩的十字路口.txt",
        "language": "zh",
        "title": "最新一期",
        "url": "https://www.xiaoyuzhoufm.com/podcast/68981df29e7bcd326eb91d88",
    },
    {
        "name": "The a16z Show",
        "transcript_file": "transcript_the_a16z_show.txt",
        "language": "en",
        "title": "Marc Andreessen on Why This Is the Most Important Time in Tech History",
        "url": "https://a16z.simplecast.com/episodes",
    },
]


def log(msg, level="INFO"):
    """日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}")


def analyze_with_new_prompt(transcript: str, podcast_name: str, title: str, language: str) -> str:
    """使用新 prompt 进行 AI 分析"""
    
    # 限制转写文本长度
    max_length = 50000
    if len(transcript) > max_length:
        head_len = int(max_length * 0.7)
        tail_len = int(max_length * 0.25)
        transcript = (
            transcript[:head_len] +
            f"\n\n[...中间内容已截断，原文共 {len(transcript)} 字符...]\n\n" +
            transcript[-tail_len:]
        )
        log(f"文本已截断: {len(transcript)} 字符")
    
    # 构建 prompt
    lang_name = "中文" if language == "zh" else "英文"
    is_chinese = language == "zh"
    
    system_prompt = """你是一位专业的播客内容分析师，擅长从对话中提炼关键信息和深度洞察。

你的任务是对播客转写文本进行深度分析和结构化总结。请注意：
1. 转写文本可能包含说话人标签，如 [SPEAKER_A]、[SPEAKER_B]
2. 保持客观中立，忠实于原文内容
3. 提炼核心观点，而非简单复述
4. **语言规则**：中文播客仅输出中文；非中文播客输出中英双语（英文在前，中文在后）"""

    if is_chinese:
        output_instruction = "请用**中文**输出分析结果。"
    else:
        output_instruction = "请输出**中英双语**分析结果（英文在前，中文翻译在后）。"
    
    user_prompt = f"""请分析以下播客内容：

## 播客信息
- 播客名称：{podcast_name}
- 节目标题：{title}
- 原文语言：{lang_name}

## 转写文本
{transcript}

---

{output_instruction}

请按以下结构输出（Markdown 格式）：

## 核心摘要 / Summary
（3-5 句话概括主题和核心观点）

## 关键要点 / Key Points
（5-8 条最重要的观点，每条 1-2 句）

## 嘉宾观点 / Guest Opinions
（分别总结不同说话人的主要观点）

## 精彩金句 / Notable Quotes
（3-5 句有启发性的原话）

## 关键词 / Tags
（在一行内用逗号分隔，如：AI, 创业, Marc Andreessen）

## 信息提取 / Key Information
（提取对话中的高价值具体信息）

### 数据与数字 / Data & Numbers
（提取对话中提到的具体数据、统计、百分比、金额、时间节点等可量化信息）
- [数据内容] — 来源/背景说明

### 事件与动态 / Events & News
（提取提到的具体事件、行业动态、公司新闻、产品发布、人事变动等）
- [事件描述] — 时间/相关方

### 内幕与洞察 / Insider Insights
（提取未公开的信息、行业内幕、独家爆料、非公开数据、预测判断等高价值信息）
- [内幕信息] — 信息来源

## 分段落详述 / Detailed Discussion
（将全文按讨论话题划分为 3-6 个主要段落，**深度提炼**每个段落的核心内容）

**重要**：避免空洞表述如"探讨了..."、"分析了..."，要写出**具体内容是什么**。

格式：
### 话题1: [话题标题]
**讨论概要**: （概括核心问题、主要观点和结论，要有实质内容，篇幅不限）

**发言摘要**:
- **[说话人姓名/角色]**: （详细提炼此人核心观点 + 支撑论据/案例 + 结论建议，让读者不看原文也能了解核心信息，篇幅不限）
- **[说话人姓名/角色]**: （同上，内容详实完整，包含具体数据、人名、事件等）

### 话题2: [话题标题]
...（每个话题都要有充实的内容）

## 延伸思考 / Further Thoughts
（2-3 个值得探讨的问题）"""

    # 调用 API
    log(f"调用 AI 分析: {podcast_name}...")
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {SILICONFLOW_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            "max_tokens": 8000  # 增加 token 限制以容纳分段落详述
        },
        timeout=300
    )
    
    result = response.json()
    if "choices" not in result:
        raise ValueError(f"AI 分析失败: {result}")
    
    analysis = result["choices"][0]["message"]["content"]
    log(f"分析完成: {len(analysis)} 字符")
    
    return analysis


def clean_markdown(text: str) -> str:
    """清理 markdown 代码块包裹"""
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return text.strip()


def generate_email_html(podcast_name: str, title: str, analysis: str, url: str) -> str:
    """生成邮件 HTML"""
    analysis_clean = clean_markdown(analysis)
    analysis_html = markdown.markdown(analysis_clean, extensions=['tables', 'fenced_code'])
    
    html = f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ 
            font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif;
            font-size: 16px;
            line-height: 1.75;
            color: #333;
            background: #fff;
            padding: 16px;
        }}
        .header {{
            border-bottom: 3px solid #07c160;
            padding-bottom: 12px;
            margin-bottom: 16px;
        }}
        .header h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; }}
        .meta {{ font-size: 14px; color: #888; }}
        h1, h2, h3 {{ margin: 16px 0 10px 0; }}
        h2 {{ font-size: 18px; color: #07c160; }}
        h3 {{ font-size: 16px; color: #333; margin-top: 20px; }}
        p {{ margin-bottom: 12px; text-align: justify; }}
        ul, ol {{ padding-left: 20px; margin: 10px 0; }}
        li {{ margin-bottom: 8px; }}
        strong {{ color: #07c160; }}
        hr {{ border: none; border-top: 1px solid #eee; margin: 20px 0; }}
        blockquote {{
            background: #f7f7f7;
            border-left: 3px solid #07c160;
            padding: 12px 16px;
            margin: 12px 0;
            color: #555;
        }}
        a {{ color: #07c160; text-decoration: none; }}
        .footer {{
            margin-top: 24px;
            padding-top: 16px;
            border-top: 1px solid #eee;
            font-size: 13px;
            color: #999;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{podcast_name}</h1>
        <div class="meta">{title}</div>
    </div>
    <div class="analysis">
        {analysis_html}
    </div>
    <div class="footer">
        <a href="{url}">收听完整节目 →</a><br><br>
        TrendRadar · AssemblyAI 转写 · DeepSeek R1 分析（含信息提取+分段落详述）
    </div>
</body>
</html>
"""
    return html


def send_email(subject: str, html: str) -> bool:
    """发送邮件"""
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        server = smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, EMAIL_TO.split(','), msg.as_string())
        server.quit()
        
        log(f"邮件发送成功: {subject[:40]}...")
        return True
    except Exception as e:
        log(f"邮件发送失败: {e}", "ERROR")
        return False


def process_podcast(podcast: dict) -> bool:
    """处理单个播客"""
    name = podcast["name"]
    log(f"=" * 50)
    log(f"开始处理: {name}")
    
    # 读取转写文本
    transcript_path = OUTPUT_DIR / podcast["transcript_file"]
    if not transcript_path.exists():
        log(f"转写文件不存在: {transcript_path}", "ERROR")
        return False
    
    transcript = transcript_path.read_text(encoding='utf-8')
    log(f"读取转写文本: {len(transcript)} 字符")
    
    # AI 分析
    try:
        analysis = analyze_with_new_prompt(
            transcript=transcript,
            podcast_name=name,
            title=podcast["title"],
            language=podcast["language"]
        )
    except Exception as e:
        log(f"AI 分析失败: {e}", "ERROR")
        return False
    
    # 保存分析结果
    analysis_file = podcast["transcript_file"].replace("transcript_", "analysis_v2_").replace(".txt", ".md")
    analysis_path = OUTPUT_DIR / analysis_file
    analysis_path.write_text(analysis, encoding='utf-8')
    log(f"保存分析结果: {analysis_path.name}")
    
    # 生成邮件
    html = generate_email_html(name, podcast["title"], analysis, podcast["url"])
    
    # 保存邮件 HTML
    email_file = podcast["transcript_file"].replace("transcript_", "email_v2_").replace(".txt", ".html")
    email_path = OUTPUT_DIR / email_file
    email_path.write_text(html, encoding='utf-8')
    
    # 发送邮件
    subject = f"🎙️ [{name}] {podcast['title'][:30]}..."
    success = send_email(subject, html)
    
    return success


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🎙️ 播客重新分析（含信息提取+分段落详述）")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"播客数量: {len(PODCASTS)}")
    print("=" * 60 + "\n")
    
    results = []
    for podcast in PODCASTS:
        success = process_podcast(podcast)
        results.append((podcast["name"], success))
        time.sleep(2)  # 避免 API 限流
    
    # 打印汇总
    print("\n" + "=" * 60)
    print("📊 处理汇总")
    print("=" * 60)
    
    for name, success in results:
        status = "✅ 成功" if success else "❌ 失败"
        print(f"{name}: {status}")
    
    success_count = sum(1 for _, s in results if s)
    print(f"\n总计: {success_count}/{len(results)} 成功")
    print("=" * 60)


if __name__ == "__main__":
    main()
