#!/usr/bin/env python3
# coding=utf-8
"""重试单期播客"""

import os, sys, re, time, requests, markdown, smtplib
from pathlib import Path
from datetime import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

ASSEMBLYAI_API_KEY = "{{ASSEMBLYAI_API_KEY}}"
SILICONFLOW_API_KEY = "{{SILICONFLOW_API_KEY}}"
EMAIL_FROM = "{{EMAIL_ADDRESS}}"
EMAIL_PASSWORD = "{{EMAIL_AUTH_CODE}}"
EMAIL_TO = "{{EMAIL_ADDRESS}}"
EMAIL_SMTP = "smtp.163.com"
EMAIL_PORT = 465

OUTPUT_DIR = Path("/home/zxy/Documents/code/TrendRadar/output/podcast/batch")

# 正确的音频URL
AUDIO_URL = "https://media.xyzcdn.net/626b46ea9cbbf0451cf5a962/lk_UTklYIZcaJcEa0AJvX95W15mZ.m4a"
TITLE = "124. 年终对话【站在2025年之外】和戴雨森聊2026年预期、The Year of R、回调、我们如何下注"
PODCAST_NAME = "张小珺Jùn｜商业访谈录"

def log(msg, level="INFO"):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] [{level}] {msg}", flush=True)

def download_audio(url: str, output_path: str) -> bool:
    log(f"下载音频...")
    try:
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

def transcribe_audio(audio_path: str, max_retries: int = 3) -> tuple:
    """带重试的转写"""
    for attempt in range(max_retries):
        try:
            log(f"上传音频 (尝试 {attempt+1}/{max_retries})...")
            with open(audio_path, 'rb') as f:
                upload_response = requests.post(
                    "https://api.assemblyai.com/v2/upload",
                    headers={"authorization": ASSEMBLYAI_API_KEY},
                    data=f,
                    timeout=900
                )
            upload_url = upload_response.json()['upload_url']
            log("上传完成，开始转写...")
            
            transcript_response = requests.post(
                "https://api.assemblyai.com/v2/transcript",
                headers={"authorization": ASSEMBLYAI_API_KEY, "content-type": "application/json"},
                json={"audio_url": upload_url, "language_code": "zh", "speaker_labels": True},
                timeout=60
            )
            transcript_id = transcript_response.json()['id']
            
            while True:
                result = requests.get(
                    f"https://api.assemblyai.com/v2/transcript/{transcript_id}",
                    headers={"authorization": ASSEMBLYAI_API_KEY},
                    timeout=30
                ).json()
                
                if result['status'] == 'completed':
                    break
                elif result['status'] == 'error':
                    raise Exception(result.get('error', '未知错误'))
                time.sleep(10)
            
            utterances = result.get('utterances', [])
            if utterances:
                lines = []
                speaker_map = {}
                speaker_idx = 0
                for u in utterances:
                    spk = u['speaker']
                    if spk not in speaker_map:
                        speaker_map[spk] = chr(65 + speaker_idx)
                        speaker_idx += 1
                    lines.append(f"[SPEAKER_{speaker_map[spk]}] {u['text']}")
                return "\n\n".join(lines), len(speaker_map)
            return result.get('text', ''), 1
            
        except Exception as e:
            log(f"尝试 {attempt+1} 失败: {e}", "ERROR")
            if attempt < max_retries - 1:
                wait = 60 * (attempt + 1)
                log(f"等待 {wait} 秒后重试...")
                time.sleep(wait)
    return None, 0

def analyze_with_ai(transcript: str, podcast_name: str, title: str) -> str:
    max_length = 50000
    if len(transcript) > max_length:
        head_len = int(max_length * 0.7)
        tail_len = int(max_length * 0.25)
        transcript = transcript[:head_len] + f"\n\n[...截断...]\n\n" + transcript[-tail_len:]
    
    system_prompt = "你是一位专业的播客内容分析师。请注意转写文本包含说话人标签。保持客观中立，提炼核心观点。"
    user_prompt = f"""分析以下播客：

播客：{podcast_name}
标题：{title}

{transcript}

---

请用中文按以下结构输出（Markdown格式）：

## 核心摘要
## 关键要点
## 嘉宾观点
## 精彩金句
## 关键词
## 信息提取
### 数据与数字
### 事件与动态
### 内幕与洞察
## 分段落详述
## 延伸思考"""

    log("调用AI分析...")
    response = requests.post(
        "https://api.siliconflow.cn/v1/chat/completions",
        headers={"Authorization": f"Bearer {SILICONFLOW_API_KEY}", "Content-Type": "application/json"},
        json={
            "model": "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B",
            "messages": [{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            "max_tokens": 8000
        },
        timeout=600
    )
    result = response.json()
    if "choices" not in result:
        log(f"AI分析返回错误: {result}", "ERROR")
        return None
    return result["choices"][0]["message"]["content"]

def send_email(podcast_name: str, title: str, analysis: str) -> bool:
    analysis = re.sub(r'^```\w*\n?', '', analysis.strip())
    analysis = re.sub(r'\n?```$', '', analysis)
    analysis_html = markdown.markdown(analysis, extensions=['tables', 'fenced_code'])
    
    html = f"""<!DOCTYPE html><html><head><meta charset="utf-8"><style>
body{{font-family:-apple-system,sans-serif;font-size:16px;line-height:1.75;color:#333;padding:16px;}}
.header{{border-bottom:3px solid #07c160;padding-bottom:12px;margin-bottom:16px;}}
h1{{font-size:22px;}}h2{{font-size:18px;color:#07c160;margin:16px 0 10px;}}
blockquote{{background:#f7f7f7;border-left:3px solid #07c160;padding:12px 16px;margin:12px 0;}}
.footer{{margin-top:24px;padding-top:16px;border-top:1px solid #eee;font-size:13px;color:#999;}}
</style></head><body>
<div class="header"><h1>{podcast_name}</h1><div>{title}</div></div>
<div>{analysis_html}</div>
<div class="footer">TrendRadar · AssemblyAI 转写 · DeepSeek R1 分析</div>
</body></html>"""

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
        log("邮件发送成功")
        return True
    except Exception as e:
        log(f"邮件失败: {e}", "ERROR")
        return False

def main():
    print("=" * 60)
    print("🔄 重试失败的播客")
    print("=" * 60)
    
    safe_title = re.sub(r'[<>:"/\\|?*]', '_', TITLE)[:50]
    audio_file = OUTPUT_DIR / f"retry_{safe_title}.m4a"
    
    # 下载音频
    if not download_audio(AUDIO_URL, str(audio_file)):
        return
    
    # 转写（带重试）
    transcript, speaker_count = transcribe_audio(str(audio_file), max_retries=3)
    if not transcript:
        log("转写最终失败", "ERROR")
        return
    
    log(f"转写完成: {len(transcript)} 字符, {speaker_count} 位说话人")
    
    # 保存转写
    transcript_file = OUTPUT_DIR / f"retry_{safe_title}_transcript.txt"
    transcript_file.write_text(transcript, encoding='utf-8')
    
    # AI分析
    analysis = analyze_with_ai(transcript, PODCAST_NAME, TITLE)
    if not analysis:
        log("AI分析失败", "ERROR")
        return
    
    log(f"分析完成: {len(analysis)} 字符")
    
    # 保存分析
    analysis_file = OUTPUT_DIR / f"retry_{safe_title}_analysis.md"
    analysis_file.write_text(analysis, encoding='utf-8')
    
    # 发送邮件
    send_email(PODCAST_NAME, TITLE, analysis)
    
    # 清理音频
    if audio_file.exists():
        audio_file.unlink()
        log("已清理音频文件")
    
    print("\n✅ 重试完成！")

if __name__ == "__main__":
    main()
