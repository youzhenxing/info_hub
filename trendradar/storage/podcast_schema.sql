-- ═══════════════════════════════════════════════════════════════
--                    播客数据表结构
--                      Version: 1.0.0
-- ═══════════════════════════════════════════════════════════════

-- 播客节目表
-- 存储每个播客节目的元信息和处理状态
CREATE TABLE IF NOT EXISTS podcast_episodes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,

    -- 基础信息
    feed_id TEXT NOT NULL,              -- 播客源 ID（对应 config 中的 feeds[].id）
    feed_name TEXT,                     -- 播客源名称
    title TEXT NOT NULL,                -- 节目标题
    url TEXT,                           -- 节目页面 URL
    guid TEXT,                          -- RSS 条目唯一标识

    -- 音频信息
    audio_url TEXT NOT NULL,            -- 音频文件 URL
    audio_type TEXT,                    -- 音频 MIME 类型 (audio/mpeg, audio/mp3, etc.)
    audio_length INTEGER DEFAULT 0,     -- 音频文件大小（字节）
    duration TEXT,                      -- 音频时长 (来自 itunes:duration)

    -- 发布信息
    published_at TEXT,                  -- 发布时间 (ISO 8601)
    author TEXT,                        -- 作者/主播
    summary TEXT,                       -- 节目简介

    -- 处理状态
    status TEXT DEFAULT 'pending',      -- 状态: pending | downloading | transcribing | analyzing | completed | failed
    error_message TEXT,                 -- 错误信息（如果 status=failed）

    -- 新增：失败次数跟踪
    failure_count INTEGER DEFAULT 0,    -- 失败次数（超过3次后永久忽略）
    last_error_time TEXT,               -- 最后一次失败时间

    -- 处理结果
    transcript TEXT,                    -- ASR 转写文本
    analysis TEXT,                      -- AI 分析结果 (Markdown)

    -- 时间戳
    first_crawl_time TEXT NOT NULL,     -- 首次抓取时间
    download_time TEXT,                 -- 下载完成时间
    transcribe_time TEXT,               -- 转写完成时间
    analyze_time TEXT,                  -- 分析完成时间
    notify_time TEXT,                   -- 推送完成时间

    -- 唯一约束：同一播客源的同一音频 URL 不重复
    UNIQUE(feed_id, audio_url)
);

-- 索引：按状态查询待处理的节目
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_status
ON podcast_episodes(status);

-- 索引：按播客源查询
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_feed_id
ON podcast_episodes(feed_id);

-- 索引：按发布时间排序
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_published_at
ON podcast_episodes(published_at DESC);

-- 索引：按首次抓取时间排序
CREATE INDEX IF NOT EXISTS idx_podcast_episodes_crawl_time
ON podcast_episodes(first_crawl_time DESC);


-- 播客推送记录表
-- 记录已推送的节目，避免重复推送
CREATE TABLE IF NOT EXISTS podcast_push_records (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    episode_id INTEGER NOT NULL,        -- 关联的节目 ID
    channel TEXT NOT NULL,              -- 推送渠道 (email, feishu, etc.)
    push_time TEXT NOT NULL,            -- 推送时间
    success INTEGER DEFAULT 1,          -- 是否成功 (1=成功, 0=失败)
    error_message TEXT,                 -- 错误信息（如果失败）

    FOREIGN KEY (episode_id) REFERENCES podcast_episodes(id),
    UNIQUE(episode_id, channel)         -- 每个节目每个渠道只推送一次
);

-- 索引：按节目查询推送记录
CREATE INDEX IF NOT EXISTS idx_podcast_push_records_episode
ON podcast_push_records(episode_id);
