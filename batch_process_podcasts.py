#!/usr/bin/env python3
# coding=utf-8
"""
批量处理播客：获取最新N期，进行ASR转写 + AI分析 + 邮件推送
"""

import os
import sys
import re
import time
import requests
import feedparser
import markdown
import smtplib
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# 配置
ASSEMBLYAI_API_KEY = "{{ASSEMBLYAI_API_KEY}}"
SILICONFLOW_API_KEY = "{{SILICONFLOW_API_KEY}}"
EMAIL_FROM = "{{EMAIL_ADDRESS}}"
EMAIL_PASSWORD = "{{EMAIL_AUTH_CODE}}"
EMAIL_TO = "{{EMAIL_ADDRESS}}"
EMAIL_SMTP = "smtp.163.com"
EMAIL_PORT = 465

# 路径
PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "output" / "podcast" / "batch"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

# 要处理的播客
PODCASTS = [
    {
        "id": "guigu101",
        "name": "硅谷101",
        "url": "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/5e5c52c9418a84a04625e6cc",
        "language": "zh",
        "max_episodes": 10,
    },
    {
        "id": "zhangxiaojun",
        "name": "张小珺Jùn｜商业访谈录",
        "url": "https://rsshub.bestblogs.dev/xiaoyuzhou/podcast/626b46ea9cbbf0451cf5a962",
        "language": "zh",
        "max_episodes": 10,
    },
]


def log(msg, level="INFO"):
    """日志输出"""
    timestamp = datetime.now().strftime("%H:%M:%S")
    print(f"[{timestamp}] [{level}] {msg}", flush=True)


def get_episodes(rss_url: str, max_episodes: int = 10) -> list:
    """从RSS获取最新N期节目"""
    log(f"获取RSS: {rss_url}")
    feed = feedparser.parse(rss_url)
    
    episodes = []
    for entry in feed.entries[:max_episodes]:
        # 查找音频URL
        audio_url = None
        if hasattr(entry, 'enclosures') and entry.enclosures:
            for enc in entry.enclosures:
                if 'audio' in enc.get('type', ''):
                    audio_url = enc.get('href')
                    break
        
        if not audio_url:
            continue
        
        episodes.append({
            "title": entry.get('title', '未知标题'),
            "audio_url": audio_url,
            "published": entry.get('published', ''),
            "link": entry.get('link', ''),
            "summary": entry.get('summary', '')[:3000],  # 截取 show notes
        })
    
    log(f"获取到 {len(episodes)} 期节目")
    return episodes


def download_audio(url: str, output_path: str) -> bool:
    """下载音频文件"""
    try:
        log(f"下载音频: {url[:60]}...")
        response = requests.get(url, stream=True, timeout=600)
        response.raise_for_status()
        
        with open(output_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        
        size_mb = os.path.getsize(output_path) / (1024 * 1024)
        log(f"下载完成: {size_mb:.1f} MB")
        return True
    except Exception as e:
        log(f"下载失败: {e}", "ERROR")
        return False


def transcribe_audio(audio_path: str, language: str = "zh", max_retries: int = 3) -> tuple:
    """使用AssemblyAI转写音频（带重试机制）"""
    
    for attempt in range(max_retries):
        try:
            log(f"上传音频到AssemblyAI (尝试 {attempt+1}/{max_retries})...")
            
            # 上传文件
            with open(audio_path, 'rb') as f:
                upload_response = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers={"authorization": ASSEMBLYAI_API_KEY},
                    data=f,
                    timeout=900  # 大文件上传超时增加
                )
            upload_url = upload_response.json()['upload_url']
            log("上传完成，开始转写...")
            
            # 创建转写任务
            lang_code = "zh" if language == "zh" else "en"
            transcript_response = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={
                    "authorization": ASSEMBLYAI_API_KEY,
                    "content-type": "application/json"
                },
                json={
                    "audio_url": upload_url,
                    "language_code": lang_code,
                    "speaker_labels": True,
                },
                timeout=60
            )
            transcript_id = transcript_response.json()['id']
            
            # 轮询等待完成
            while True:
                result = requests.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers={"authorization": ASSEMBLYAI_API_KEY},
                    timeout=30
                ).json()
                
                status = result['status']
                if status == 'completed':
                    break
                elif status == 'error':
                    raise Exception(result.get('error', '未知错误'))
                
                time.sleep(10)
            
            # 格式化输出（带说话人标签）
            utterances = result.get('utterances', [])
            if utterances:
                lines = []
                speaker_map = {}
                speaker_idx = 0
                for u in utterances:
                    spk = u['speaker']
                    if spk not in speaker_map:
                        speaker_map[spk] = chr(65 + speaker_idx)  # A, B, C, ...
                        speaker_idx += 1
                    speaker = f"[SPEAKER_{speaker_map[spk]}]"
                    lines.append(f"{speaker} {u['text']}")
                transcript_text = "\n\n".join(lines)
                speaker_count = len(speaker_map)
            else:
                transcript_text = result.get('text', '')
                speaker_count = 1
            
            log(f"转写完成: {len(transcript_text)} 字符, {speaker_count} 位说话人")
            return transcript_text, speaker_count
            
        except Exception as e:
            log(f"转写尝试 {attempt+1} 失败: {e}", "ERROR")
            if attempt < max_retries - 1:
                wait_time = 60 * (attempt + 1)  # 递增等待时间：60s, 120s, 180s
                log(f"等待 {wait_time} 秒后重试...")
                time.sleep(wait_time)
    
    log("转写最终失败，已尝试所有重试", "ERROR")
    return None, 0


def analyze_with_ai(transcript: str, podcast_name: str, title: str, language: str, show_notes: str = "") -> str:
    """使用DeepSeek R1进行AI分析"""
    
    # 构建完整文本
    full_text = f"【节目说明】\n{show_notes}\n\n【转写文本】\n{transcript}" if show_notes else transcript
    
    # 截断处理
    max_length = 50000
    if len(full_text) > max_length:
        head_len = int(max_length * 0.7)
        tail_len = int(max_length * 0.25)
        full_text = (
            full_text[:head_len] +
            f"\n\n[...中间内容已截断，原文共 {len(full_text)} 字符...]\n\n" +
            full_text[-tail_len:]
        )
    
    lang_name = "中文" if language == "zh" else "英文"
    is_chinese = language == "zh"
    
    system_prompt = """你是一位专业的播客内容分析师，擅长从对话中提炼关键信息和深度洞察。
请注意：
1. 转写文本可能包含说话人标签，如 [SPEAKER_A]、[SPEAKER_B]
2. 保持客观中立，忠实于原文内容
3. 提炼核心观点，而非简单复述
4. 语言规则：中文播客仅输出中文；非中文播客输出中英双语"""

    output_instruction = "请用**中文**输出分析结果。" if is_chinese else "请输出**中英双语**分析结果。"
    
    user_prompt = f"""请分析以下播客内容：

## 播客信息
- 播客名称：{podcast_name}
- 节目标题：{title}
- 原文语言：{lang_name}

## 内容
{full_text}

---

{output_instruction}

请按以下结构输出（Markdown 格式）：

## 核心摘要
（3-5 句话概括主题和核心观点）

## 关键要点
（5-8 条最重要的观点，每条 1-2 句）

## 嘉宾观点
（分别总结不同说话人的主要观点）

## 精彩金句
（3-5 句有启发性的原话）

## 关键词
（在一行内用逗号分隔）

## 信息提取

### 数据与数字
（提取对话中提到的具体数据、统计、百分比、金额等）

### 事件与动态
（提取提到的具体事件、行业动态、公司新闻等）

### 内幕与洞察
（提取未公开的信息、行业内幕、独家爆料等）

## 分段落详述
（将全文按讨论话题划分为 3-6 个主要段落，深度提炼每个段落的核心内容）

格式：
### 话题1: [话题标题]
**讨论概要**: （概括核心问题、主要观点和结论，要有实质内容，篇幅不限）

**发言摘要**:
- **[说话人姓名/角色]**: （详细提炼此人核心观点 + 支撑论据/案例 + 结论建议，篇幅不限）

## 延伸思考
（2-3 个值得探讨的问题）"""

    log(f"调用AI分析...")
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
            "max_tokens": 8000
        },
        timeout=600
    )
    
    result = response.json()
    if "choices" not in result:
        log(f"AI分析失败: {result}", "ERROR")
        return None
    
    analysis = result["choices"][0]["message"]["content"]
    log(f"分析完成: {len(analysis)} 字符")
    return analysis


def clean_markdown(text: str) -> str:
    """清理markdown代码块包裹"""
    text = text.strip()
    if text.startswith('```'):
        text = re.sub(r'^```\w*\n?', '', text)
        text = re.sub(r'\n?```$', '', text)
    return text.strip()


def send_email(podcast_name: str, title: str, analysis: str, link: str) -> bool:
    """发送邮件"""
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
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'PingFang SC', sans-serif; font-size: 16px; line-height: 1.75; color: #333; background: #fff; padding: 16px; }}
        .header {{ border-bottom: 3px solid #07c160; padding-bottom: 12px; margin-bottom: 16px; }}
        .header h1 {{ font-size: 22px; font-weight: 600; margin-bottom: 8px; }}
        .meta {{ font-size: 14px; color: #888; }}
        h2 {{ font-size: 18px; color: #07c160; margin: 16px 0 10px 0; }}
        h3 {{ font-size: 16px; color: #333; margin-top: 20px; }}
        p {{ margin-bottom: 12px; text-align: justify; }}
        ul, ol {{ padding-left: 20px; margin: 10px 0; }}
        li {{ margin-bottom: 8px; }}
        strong {{ color: #07c160; }}
        blockquote {{ background: #f7f7f7; border-left: 3px solid #07c160; padding: 12px 16px; margin: 12px 0; color: #555; }}
        a {{ color: #07c160; text-decoration: none; }}
        .footer {{ margin-top: 24px; padding-top: 16px; border-top: 1px solid #eee; font-size: 13px; color: #999; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>{podcast_name}</h1>
        <div class="meta">{title}</div>
    </div>
    <div class="analysis">{analysis_html}</div>
    <div class="footer">
        <a href="{link}">收听完整节目 →</a><br><br>
        TrendRadar · AssemblyAI 转写 · DeepSeek R1 分析
    </div>
</body>
</html>"""

    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f"🎙️ [{podcast_name}] {title[:40]}"
        msg['From'] = EMAIL_FROM
        msg['To'] = EMAIL_TO
        msg.attach(MIMEText(html, 'html', 'utf-8'))
        
        server = smtplib.SMTP_SSL(EMAIL_SMTP, EMAIL_PORT)
        server.login(EMAIL_FROM, EMAIL_PASSWORD)
        server.sendmail(EMAIL_FROM, [EMAIL_TO], msg.as_string())
        server.quit()
        
        log(f"邮件发送成功")
        return True
    except Exception as e:
        log(f"邮件发送失败: {e}", "ERROR")
        return False


def process_episode(podcast: dict, episode: dict, index: int) -> bool:
    """处理单个节目"""
    podcast_name = podcast["name"]
    title = episode["title"]
    
    log(f"\n{'='*60}")
    log(f"[{podcast_name}] 第 {index+1} 期: {title}")
    log(f"{'='*60}")
    
    # 创建安全的文件名
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', title)[:50]
    safe_name = re.sub(r'[<>:"/\\|?*]', '_', podcast_name)
    
    # 检查是否已处理过
    analysis_file = OUTPUT_DIR / f"{safe_name}_{safe_title}_analysis.md"
    if analysis_file.exists():
        log(f"已处理过，跳过")
        return True
    
    # 下载音频
    audio_path = OUTPUT_DIR / f"{safe_name}_{safe_title}.mp3"
    if not audio_path.exists():
        if not download_audio(episode["audio_url"], str(audio_path)):
            return False
    
    # 转写
    transcript_file = OUTPUT_DIR / f"{safe_name}_{safe_title}_transcript.txt"
    if transcript_file.exists():
        log("使用已有转写文件")
        transcript = transcript_file.read_text(encoding='utf-8')
        speaker_count = transcript.count('[SPEAKER_')
    else:
        transcript, speaker_count = transcribe_audio(str(audio_path), podcast["language"])
        if not transcript:
            return False
        transcript_file.write_text(transcript, encoding='utf-8')
    
    # AI分析
    analysis = analyze_with_ai(
        transcript=transcript,
        podcast_name=podcast_name,
        title=title,
        language=podcast["language"],
        show_notes=episode.get("summary", "")
    )
    if not analysis:
        return False
    
    analysis_file.write_text(analysis, encoding='utf-8')
    
    # 发送邮件
    send_email(podcast_name, title, analysis, episode.get("link", ""))
    
    # 清理音频文件
    if audio_path.exists():
        audio_path.unlink()
        log("已清理音频文件")
    
    return True


def main():
    """主函数"""
    print("\n" + "=" * 60)
    print("🎙️ 播客批量处理")
    print("=" * 60)
    print(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"播客数量: {len(PODCASTS)}")
    print(f"输出目录: {OUTPUT_DIR}")
    print("=" * 60 + "\n")
    
    total_success = 0
    total_failed = 0
    
    for podcast_idx, podcast in enumerate(PODCASTS):
        # 播客之间的间隔保护
        if podcast_idx > 0:
            log("播客切换间隔：等待 60 秒...")
            time.sleep(60)
        
        log(f"\n{'#'*60}")
        log(f"开始处理播客: {podcast['name']} ({podcast_idx+1}/{len(PODCASTS)})")
        log(f"{'#'*60}")
        
        # 获取节目列表
        try:
            episodes = get_episodes(podcast["url"], podcast["max_episodes"])
        except Exception as e:
            log(f"获取RSS失败: {e}", "ERROR")
            continue
        
        # 处理每期节目
        for i, episode in enumerate(episodes):
            try:
                success = process_episode(podcast, episode, i)
                if success:
                    total_success += 1
                else:
                    total_failed += 1
            except Exception as e:
                log(f"处理失败: {e}", "ERROR")
                total_failed += 1
            
            # 任务间隔保护：60秒，避免API限流
            if i < len(episodes) - 1:  # 最后一个不需要等待
                log("任务间隔保护：等待 60 秒...")
                time.sleep(60)
    
    # 汇总
    print("\n" + "=" * 60)
    print("📊 处理汇总")
    print("=" * 60)
    print(f"成功: {total_success}")
    print(f"失败: {total_failed}")
    print(f"总计: {total_success + total_failed}")
    print("=" * 60)


if __name__ == "__main__":
    main()
