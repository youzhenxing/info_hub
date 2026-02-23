#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从播客数据库导出一份完整转写文案，用于调试 AI 分析 prompt"""

import sqlite3
from pathlib import Path

DB_PATH = Path(__file__).resolve().parent.parent / "output" / "news" / "podcast.db"
OUT_PATH = Path(__file__).resolve().parent / "podcast_transcript_for_prompt_debug.txt"


def main():
    if not DB_PATH.exists():
        print(f"数据库不存在: {DB_PATH}")
        return

    conn = sqlite3.connect(str(DB_PATH))
    row = conn.execute("""
        SELECT feed_id, feed_name, title, published_at, author, summary, transcript
        FROM podcast_episodes
        WHERE transcript IS NOT NULL
        ORDER BY id DESC
        LIMIT 1
    """).fetchone()
    conn.close()

    if not row:
        print("没有找到带转写内容的节目")
        return

    feed_id, feed_name, title, published_at, author, summary, transcript = row

    lines = [
        "=" * 60,
        "播客转写文案（用于调试 AI 分析 prompt）",
        "=" * 60,
        "",
        "【元信息】",
        f"  播客名称: {feed_name}",
        f"  播客ID:   {feed_id}",
        f"  节目标题: {title}",
        f"  发布时间: {published_at or '-'}",
        f"  作者:     {author or '-'}",
        "",
        "【节目简介】",
        (summary or "(无)").strip(),
        "",
        "=" * 60,
        "【转写正文】",
        "=" * 60,
        "",
        (transcript or "").strip(),
        "",
    ]

    out_text = "\n".join(lines)
    OUT_PATH.write_text(out_text, encoding="utf-8")
    print(f"已导出: {OUT_PATH}")
    print(f"  节目标题: {title}")
    print(f"  转写长度: {len(transcript or '')} 字符")


if __name__ == "__main__":
    main()
