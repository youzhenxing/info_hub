# coding=utf-8
"""
模块状态数据库

存储和管理模块执行状态：
- 执行历史
- 最后执行时间
- 健康检查结果
- 告警信息
"""

import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any

from .base import ModuleStatus


class StatusDB:
    """
    状态数据库
    
    使用 SQLite 存储模块执行状态和健康检查结果。
    """
    
    def __init__(self, db_path: str = "output/system/status.db"):
        """
        初始化状态数据库
        
        Args:
            db_path: 数据库文件路径
        """
        self.db_path = db_path
        self._ensure_db_exists()
    
    def _ensure_db_exists(self) -> None:
        """确保数据库和表存在"""
        # 创建目录
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        
        # 创建表
        conn = self._get_connection()
        cursor = conn.cursor()
        
        # 模块执行历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS module_runs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT NOT NULL,
                status TEXT NOT NULL,
                message TEXT,
                stats TEXT,
                error TEXT,
                started_at TEXT NOT NULL,
                finished_at TEXT,
                duration_seconds REAL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 模块最新状态表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS module_status (
                module TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                last_run_at TEXT,
                last_success_at TEXT,
                last_error TEXT,
                run_count INTEGER DEFAULT 0,
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                updated_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 健康检查历史表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS health_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                overall_status TEXT NOT NULL,
                checks TEXT NOT NULL,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 告警表
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS alerts (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                module TEXT,
                level TEXT NOT NULL,
                message TEXT NOT NULL,
                details TEXT,
                acknowledged INTEGER DEFAULT 0,
                created_at TEXT DEFAULT CURRENT_TIMESTAMP
            )
        """)
        
        # 创建索引
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_module_runs_module ON module_runs(module)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_module_runs_started ON module_runs(started_at)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_alerts_created ON alerts(created_at)")

        # 迁移: 为已有的 module_status 表添加 bootstrapped_version 列
        cursor.execute("PRAGMA table_info(module_status)")
        columns = [row[1] for row in cursor.fetchall()]
        if 'bootstrapped_version' not in columns:
            cursor.execute("ALTER TABLE module_status ADD COLUMN bootstrapped_version TEXT")

        conn.commit()
        conn.close()
    
    def _get_connection(self) -> sqlite3.Connection:
        """获取数据库连接"""
        return sqlite3.connect(self.db_path)
    
    def update_module_status(
        self,
        module: str,
        status: ModuleStatus,
        started_at: datetime,
        finished_at: Optional[datetime] = None,
        stats: Optional[Dict] = None,
        error: Optional[str] = None,
        message: Optional[str] = None
    ) -> None:
        """
        更新模块状态
        
        Args:
            module: 模块名称
            status: 执行状态
            started_at: 开始时间
            finished_at: 结束时间
            stats: 统计信息
            error: 错误信息
            message: 执行消息
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        finished_at = finished_at or datetime.now()
        duration = (finished_at - started_at).total_seconds()
        
        # 插入执行历史
        cursor.execute("""
            INSERT INTO module_runs (module, status, message, stats, error, started_at, finished_at, duration_seconds)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            module,
            status.value,
            message,
            json.dumps(stats) if stats else None,
            error,
            started_at.isoformat(),
            finished_at.isoformat(),
            duration
        ))
        
        # 更新最新状态
        is_success = status == ModuleStatus.SUCCESS
        
        cursor.execute("""
            INSERT INTO module_status (module, status, last_run_at, last_success_at, last_error, run_count, success_count, fail_count)
            VALUES (?, ?, ?, ?, ?, 1, ?, ?)
            ON CONFLICT(module) DO UPDATE SET
                status = excluded.status,
                last_run_at = excluded.last_run_at,
                last_success_at = CASE WHEN excluded.status = 'success' THEN excluded.last_run_at ELSE last_success_at END,
                last_error = CASE WHEN excluded.status != 'success' THEN excluded.last_error ELSE last_error END,
                run_count = run_count + 1,
                success_count = success_count + CASE WHEN excluded.status = 'success' THEN 1 ELSE 0 END,
                fail_count = fail_count + CASE WHEN excluded.status != 'success' THEN 1 ELSE 0 END,
                updated_at = CURRENT_TIMESTAMP
        """, (
            module,
            status.value,
            finished_at.isoformat(),
            finished_at.isoformat() if is_success else None,
            error if not is_success else None,
            1 if is_success else 0,
            0 if is_success else 1
        ))
        
        conn.commit()
        conn.close()
    
    def get_module_status(self, module: str) -> Optional[Dict]:
        """
        获取模块最新状态
        
        Args:
            module: 模块名称
        
        Returns:
            模块状态
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, last_run_at, last_success_at, last_error, run_count, success_count, fail_count
            FROM module_status
            WHERE module = ?
        """, (module,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "status": row[0],
                "last_run_at": row[1],
                "last_success_at": row[2],
                "last_error": row[3],
                "run_count": row[4],
                "success_count": row[5],
                "fail_count": row[6],
            }
        return None
    
    def get_all_modules_status(self) -> Dict[str, Dict]:
        """获取所有模块状态"""
        modules = ["podcast", "investment", "community", "wechat"]
        status = {}
        
        for module in modules:
            status[module] = self.get_module_status(module) or {
                "status": "idle",
                "last_run_at": None,
                "run_count": 0,
            }
        
        return status
    
    def get_last_run(self, module: str) -> Optional[Dict]:
        """
        获取模块最后一次执行记录
        
        Args:
            module: 模块名称
        
        Returns:
            执行记录
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT status, message, stats, error, started_at, finished_at, duration_seconds
            FROM module_runs
            WHERE module = ?
            ORDER BY started_at DESC
            LIMIT 1
        """, (module,))
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "status": row[0],
                "message": row[1],
                "stats": json.loads(row[2]) if row[2] else {},
                "error": row[3],
                "started_at": row[4],
                "finished_at": row[5],
                "duration_seconds": row[6],
            }
        return None
    
    def get_module_history(self, module: str, days: int = 7) -> List[Dict]:
        """
        获取模块执行历史
        
        Args:
            module: 模块名称
            days: 获取最近几天的记录
        
        Returns:
            执行历史列表
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(days=days)).isoformat()
        
        cursor.execute("""
            SELECT status, message, stats, error, started_at, finished_at, duration_seconds
            FROM module_runs
            WHERE module = ? AND started_at >= ?
            ORDER BY started_at DESC
        """, (module, since))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "status": row[0],
                "message": row[1],
                "stats": json.loads(row[2]) if row[2] else {},
                "error": row[3],
                "started_at": row[4],
                "finished_at": row[5],
                "duration_seconds": row[6],
            }
            for row in rows
        ]
    
    def get_execution_timeline(self, hours: int = 24) -> List[Dict]:
        """
        获取执行时间线
        
        Args:
            hours: 获取最近几小时的记录
        
        Returns:
            时间线数据
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        since = (datetime.now() - timedelta(hours=hours)).isoformat()
        
        cursor.execute("""
            SELECT module, status, started_at, finished_at, duration_seconds
            FROM module_runs
            WHERE started_at >= ?
            ORDER BY started_at ASC
        """, (since,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "module": row[0],
                "status": row[1],
                "started_at": row[2],
                "finished_at": row[3],
                "duration_seconds": row[4],
            }
            for row in rows
        ]
    
    def save_health_check(self, result: Dict) -> None:
        """
        保存健康检查结果
        
        Args:
            result: 健康检查结果
        """
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO health_checks (overall_status, checks)
            VALUES (?, ?)
        """, (
            result.get("overall", "unknown"),
            json.dumps(result.get("checks", {}))
        ))
        
        conn.commit()
        conn.close()
    
    def get_latest_health_check(self) -> Optional[Dict]:
        """获取最新健康检查结果"""
        import json
        
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT overall_status, checks, created_at
            FROM health_checks
            ORDER BY created_at DESC
            LIMIT 1
        """)
        
        row = cursor.fetchone()
        conn.close()
        
        if row:
            return {
                "overall": row[0],
                "checks": json.loads(row[1]),
                "created_at": row[2],
            }
        return None
    
    def add_alert(self, module: Optional[str], level: str, message: str, details: Optional[str] = None) -> None:
        """
        添加告警
        
        Args:
            module: 模块名称
            level: 告警级别（info, warning, error）
            message: 告警消息
            details: 详细信息
        """
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            INSERT INTO alerts (module, level, message, details)
            VALUES (?, ?, ?, ?)
        """, (module, level, message, details))
        
        conn.commit()
        conn.close()
    
    def get_active_alerts(self, limit: int = 10) -> List[Dict]:
        """获取未确认的告警"""
        conn = self._get_connection()
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT id, module, level, message, details, created_at
            FROM alerts
            WHERE acknowledged = 0
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,))
        
        rows = cursor.fetchall()
        conn.close()
        
        return [
            {
                "id": row[0],
                "module": row[1],
                "level": row[2],
                "message": row[3],
                "details": row[4],
                "created_at": row[5],
            }
            for row in rows
        ]
    
    def acknowledge_alert(self, alert_id: int) -> None:
        """确认告警"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            UPDATE alerts SET acknowledged = 1 WHERE id = ?
        """, (alert_id,))

        conn.commit()
        conn.close()

    def check_bootstrap_needed(self, module: str, current_version: str) -> bool:
        """检查模块是否需要当前版本的引导触发"""
        conn = self._get_connection()
        try:
            cursor = conn.execute(
                "SELECT bootstrapped_version FROM module_status WHERE module = ?",
                (module,)
            )
            row = cursor.fetchone()
            if row is None or row[0] is None:
                return True
            return row[0] != current_version
        finally:
            conn.close()

    def mark_bootstrapped(self, module: str, current_version: str) -> None:
        """标记模块已在当前版本完成引导"""
        conn = self._get_connection()
        try:
            conn.execute("""
                INSERT INTO module_status (module, status, bootstrapped_version)
                VALUES (?, 'idle', ?)
                ON CONFLICT(module) DO UPDATE SET
                    bootstrapped_version = excluded.bootstrapped_version
            """, (module, current_version))
            conn.commit()
        finally:
            conn.close()
