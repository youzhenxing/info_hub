"""
数据存储模块 - SQLite 数据库操作
"""

import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Optional
from contextlib import contextmanager

from .models import Article, FeedType

logger = logging.getLogger(__name__)


class Storage:
    """SQLite 数据存储"""
    
    def __init__(self, db_path: str):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()
    
    def _init_db(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            conn.executescript("""
                -- 文章表
                CREATE TABLE IF NOT EXISTS articles (
                    id TEXT PRIMARY KEY,
                    feed_id TEXT NOT NULL,
                    feed_name TEXT NOT NULL,
                    feed_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    published_at TIMESTAMP,
                    collected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    ai_summary TEXT,
                    processed INTEGER DEFAULT 0
                );
                
                -- 索引
                CREATE INDEX IF NOT EXISTS idx_articles_feed_id ON articles(feed_id);
                CREATE INDEX IF NOT EXISTS idx_articles_published_at ON articles(published_at);
                CREATE INDEX IF NOT EXISTS idx_articles_collected_at ON articles(collected_at);
                CREATE INDEX IF NOT EXISTS idx_articles_processed ON articles(processed);
                
                -- 推送记录表
                CREATE TABLE IF NOT EXISTS push_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    push_type TEXT NOT NULL,
                    push_date DATE NOT NULL,
                    push_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    article_count INTEGER DEFAULT 0,
                    success INTEGER DEFAULT 1
                );
                
                CREATE INDEX IF NOT EXISTS idx_push_records_date ON push_records(push_date);
            """)
    
    @contextmanager
    def _get_connection(self):
        """获取数据库连接"""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()
    
    def save_article(self, article: Article) -> bool:
        """
        保存文章（去重）
        
        Returns:
            True 如果是新文章，False 如果已存在
        """
        with self._get_connection() as conn:
            # 检查是否已存在
            existing = conn.execute(
                "SELECT id FROM articles WHERE id = ?",
                (article.id,)
            ).fetchone()
            
            if existing:
                return False
            
            # 插入新文章
            conn.execute("""
                INSERT INTO articles (
                    id, feed_id, feed_name, feed_type, title, url,
                    content, summary, published_at, collected_at, ai_summary
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                article.id,
                article.feed_id,
                article.feed_name,
                article.feed_type.value,
                article.title,
                article.url,
                article.content,
                article.summary,
                article.published_at,
                article.collected_at,
                article.ai_summary
            ))
            
            return True
    
    def update_ai_summary(self, article_id: str, ai_summary: str):
        """更新文章的 AI 摘要"""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE articles SET ai_summary = ?, processed = 1 WHERE id = ?",
                (ai_summary, article_id)
            )
    
    def mark_processed(self, article_ids: List[str]):
        """标记文章为已处理"""
        with self._get_connection() as conn:
            placeholders = ','.join('?' * len(article_ids))
            conn.execute(
                f"UPDATE articles SET processed = 1 WHERE id IN ({placeholders})",
                article_ids
            )
    
    def get_today_articles(self, feed_type: Optional[FeedType] = None) -> List[Article]:
        """
        获取最近3天发布的文章（按发布时间筛选）

        Args:
            feed_type: 公众号类型（可选）

        Returns:
            文章列表

        注意：
            - 使用 published_at（发布时间）而非 collected_at（采集时间）
            - 确保邮件包含"最近发布的文章"，避免跨天采集导致的文章延迟
            - 可能会有少量文章在多天邮件中出现（已接受的权衡）
        """
        from datetime import timedelta
        cutoff_date = (datetime.now() - timedelta(days=3)).date()

        query = """
            SELECT * FROM articles
            WHERE DATE(published_at) >= ?
        """
        params = [cutoff_date]

        if feed_type:
            query += " AND feed_type = ?"
            params.append(feed_type.value)

        query += " ORDER BY published_at DESC"

        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_article(row) for row in rows]
    
    def get_unprocessed_articles(self, feed_type: Optional[FeedType] = None) -> List[Article]:
        """获取未处理的文章"""
        query = "SELECT * FROM articles WHERE processed = 0"
        params = []
        
        if feed_type:
            query += " AND feed_type = ?"
            params.append(feed_type.value)
        
        query += " ORDER BY published_at DESC"
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_article(row) for row in rows]
    
    def get_articles_by_date(
        self,
        date: datetime,
        feed_type: Optional[FeedType] = None
    ) -> List[Article]:
        """获取指定日期的文章"""
        query = """
            SELECT * FROM articles 
            WHERE DATE(collected_at) = ?
        """
        params = [date.date()]
        
        if feed_type:
            query += " AND feed_type = ?"
            params.append(feed_type.value)
        
        query += " ORDER BY published_at DESC"
        
        with self._get_connection() as conn:
            rows = conn.execute(query, params).fetchall()
            return [self._row_to_article(row) for row in rows]
    
    def has_pushed_today(self, push_type: str = "daily") -> bool:
        """检查今日是否已推送"""
        today = datetime.now().date()
        
        with self._get_connection() as conn:
            row = conn.execute(
                "SELECT id FROM push_records WHERE push_type = ? AND push_date = ? AND success = 1",
                (push_type, today)
            ).fetchone()
            return row is not None
    
    def record_push(self, push_type: str, article_count: int, success: bool = True):
        """记录推送"""
        today = datetime.now().date()
        
        with self._get_connection() as conn:
            conn.execute("""
                INSERT INTO push_records (push_type, push_date, article_count, success)
                VALUES (?, ?, ?, ?)
            """, (push_type, today, article_count, 1 if success else 0))
    
    def cleanup_old_data(self, retention_days: int):
        """清理过期数据（保留以兼容旧代码）"""
        return self.archive_old_data(retention_days)
    
    def archive_old_data(self, retention_days: int):
        """
        归档过期数据（不删除，保留历史文本）
        
        将超过 retention_days 的文章移到归档表
        """
        if retention_days <= 0:
            return 0
        
        cutoff = datetime.now() - timedelta(days=retention_days)
        
        with self._get_connection() as conn:
            # 创建归档表（如果不存在）
            conn.execute("""
                CREATE TABLE IF NOT EXISTS articles_archive (
                    id TEXT PRIMARY KEY,
                    feed_id TEXT NOT NULL,
                    feed_name TEXT NOT NULL,
                    feed_type TEXT NOT NULL,
                    title TEXT NOT NULL,
                    url TEXT NOT NULL,
                    content TEXT,
                    summary TEXT,
                    published_at TIMESTAMP,
                    collected_at TIMESTAMP,
                    ai_summary TEXT,
                    processed INTEGER DEFAULT 0,
                    archived_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # 复制到归档表
            cursor = conn.execute("""
                INSERT OR IGNORE INTO articles_archive 
                (id, feed_id, feed_name, feed_type, title, url, content, 
                 summary, published_at, collected_at, ai_summary, processed)
                SELECT id, feed_id, feed_name, feed_type, title, url, content,
                       summary, published_at, collected_at, ai_summary, processed
                FROM articles
                WHERE collected_at < ?
            """, (cutoff,))
            archived = cursor.rowcount
            
            # 从主表删除（已归档的）
            conn.execute(
                "DELETE FROM articles WHERE collected_at < ?",
                (cutoff,)
            )
            
            # 清理推送记录
            conn.execute(
                "DELETE FROM push_records WHERE push_date < ?",
                (cutoff.date(),)
            )
            
            return archived
    
    def get_archived_articles(self, limit: int = 100, offset: int = 0) -> List[Article]:
        """获取归档的文章"""
        with self._get_connection() as conn:
            # 检查归档表是否存在
            table_exists = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='articles_archive'
            """).fetchone()
            
            if not table_exists:
                return []
            
            rows = conn.execute("""
                SELECT * FROM articles_archive
                ORDER BY collected_at DESC
                LIMIT ? OFFSET ?
            """, (limit, offset)).fetchall()
            
            return [self._row_to_article(row) for row in rows]
    
    def get_article_stats(self) -> dict:
        """获取文章统计信息"""
        with self._get_connection() as conn:
            stats = {
                'total_articles': 0,
                'processed_articles': 0,
                'archived_articles': 0,
                'articles_by_feed': {},
                'articles_by_date': {}
            }
            
            # 主表统计
            row = conn.execute("SELECT COUNT(*) as cnt FROM articles").fetchone()
            stats['total_articles'] = row['cnt'] if row else 0
            
            row = conn.execute("SELECT COUNT(*) as cnt FROM articles WHERE processed = 1").fetchone()
            stats['processed_articles'] = row['cnt'] if row else 0
            
            # 归档表统计
            table_exists = conn.execute("""
                SELECT name FROM sqlite_master 
                WHERE type='table' AND name='articles_archive'
            """).fetchone()
            
            if table_exists:
                row = conn.execute("SELECT COUNT(*) as cnt FROM articles_archive").fetchone()
                stats['archived_articles'] = row['cnt'] if row else 0
            
            # 按公众号统计
            rows = conn.execute("""
                SELECT feed_name, COUNT(*) as cnt 
                FROM articles GROUP BY feed_name
            """).fetchall()
            stats['articles_by_feed'] = {row['feed_name']: row['cnt'] for row in rows}
            
            # 按日期统计
            rows = conn.execute("""
                SELECT DATE(collected_at) as date, COUNT(*) as cnt 
                FROM articles 
                GROUP BY DATE(collected_at)
                ORDER BY date DESC
                LIMIT 30
            """).fetchall()
            stats['articles_by_date'] = {str(row['date']): row['cnt'] for row in rows}
            
            return stats
    
    def export_articles_json(self, output_path: str, include_archived: bool = True):
        """
        导出文章数据为 JSON 格式
        
        用于数据备份和迁移
        """
        import json
        
        articles_data = []
        
        with self._get_connection() as conn:
            # 导出主表
            rows = conn.execute("SELECT * FROM articles").fetchall()
            for row in rows:
                articles_data.append({
                    'id': row['id'],
                    'feed_id': row['feed_id'],
                    'feed_name': row['feed_name'],
                    'feed_type': row['feed_type'],
                    'title': row['title'],
                    'url': row['url'],
                    'content': row['content'],
                    'summary': row['summary'],
                    'published_at': row['published_at'],
                    'collected_at': row['collected_at'],
                    'ai_summary': row['ai_summary'],
                    'processed': row['processed'],
                    'archived': False
                })
            
            # 导出归档表
            if include_archived:
                table_exists = conn.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='articles_archive'
                """).fetchone()
                
                if table_exists:
                    rows = conn.execute("SELECT * FROM articles_archive").fetchall()
                    for row in rows:
                        articles_data.append({
                            'id': row['id'],
                            'feed_id': row['feed_id'],
                            'feed_name': row['feed_name'],
                            'feed_type': row['feed_type'],
                            'title': row['title'],
                            'url': row['url'],
                            'content': row['content'],
                            'summary': row['summary'],
                            'published_at': row['published_at'],
                            'collected_at': row['collected_at'],
                            'ai_summary': row['ai_summary'],
                            'processed': row['processed'],
                            'archived': True
                        })
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(articles_data, f, ensure_ascii=False, indent=2, default=str)
        
        return len(articles_data)
    
    def _row_to_article(self, row: sqlite3.Row) -> Article:
        """将数据库行转换为 Article 对象"""
        published_at = None
        if row['published_at']:
            try:
                published_at = datetime.fromisoformat(row['published_at'])
            except:
                pass
        
        collected_at = datetime.now()
        if row['collected_at']:
            try:
                collected_at = datetime.fromisoformat(row['collected_at'])
            except:
                pass
        
        return Article(
            id=row['id'],
            feed_id=row['feed_id'],
            feed_name=row['feed_name'],
            feed_type=FeedType(row['feed_type']),
            title=row['title'],
            url=row['url'],
            content=row['content'] or '',
            summary=row['summary'],
            published_at=published_at,
            collected_at=collected_at,
            ai_summary=row['ai_summary']
        )
