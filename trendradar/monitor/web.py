# coding=utf-8
"""
监控网页服务

使用 Python 内置 http.server 提供本地监控仪表板。
无需额外依赖。

功能：
- 模块状态实时监控
- 调度时间表查看
- 健康检查
- Wewe-RSS 账号管理（嵌入）
- 自动/手动刷新

启动方式：
- trend monitor start
- python -m trendradar.monitor.web
"""

import http.server
import json
import os
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

from ..core.loader import load_system_config
from ..core.status import StatusDB
from ..core.scheduler import Scheduler
from .health import HealthChecker


class MonitorHandler(http.server.BaseHTTPRequestHandler):
    """监控服务请求处理器"""
    
    system_config = None
    
    def log_message(self, format, *args):
        """自定义日志格式"""
        pass  # 禁用默认日志
    
    def do_GET(self):
        """处理 GET 请求"""
        parsed = urllib.parse.urlparse(self.path)
        path = parsed.path
        
        # 路由
        if path == "/" or path == "/dashboard":
            self.serve_dashboard()
        elif path == "/schedule":
            self.serve_schedule()
        elif path == "/wewe":
            self.serve_wewe()
        elif path.startswith("/api/"):
            self.serve_api(path[5:])
        else:
            self.send_error(404, "Not Found")
    
    def do_POST(self):
        """处理 POST 请求"""
        if self.path == "/api/health/check":
            checker = HealthChecker(self.system_config)
            result = checker.check_all()
            self.send_json(result)
        elif self.path == "/api/refresh":
            # 强制刷新所有数据
            self.send_json({"success": True, "message": "刷新成功"})
        else:
            self.send_error(404, "Not Found")
    
    def send_html(self, content: str):
        """发送 HTML 响应"""
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", len(content.encode("utf-8")))
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))
    
    def send_json(self, data: Any):
        """发送 JSON 响应"""
        content = json.dumps(data, ensure_ascii=False, default=str)
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Content-Length", len(content.encode("utf-8")))
        self.end_headers()
        self.wfile.write(content.encode("utf-8"))
    
    def get_status_db(self) -> StatusDB:
        """获取状态数据库"""
        db_path = self.system_config.get("MONITOR", {}).get("STATUS_DB", "output/system/status.db")
        return StatusDB(db_path)
    
    def serve_dashboard(self):
        """渲染仪表板"""
        wewe_config = self.system_config.get("WEWE_RSS", {})
        wewe_url = wewe_config.get("EXTERNAL_URL", wewe_config.get("BASE_URL", "http://localhost:4000"))
        
        html = DASHBOARD_HTML.format(
            wewe_url=wewe_url
        )
        self.send_html(html)
    
    def serve_schedule(self):
        """渲染调度时间表页面"""
        scheduler = Scheduler(self.system_config)
        now = datetime.now()
        
        # 配置表格
        config_html = ""
        for module, cfg in scheduler.get_config().items():
            if cfg.get("type") == "interval":
                trigger = f"每 {cfg.get('interval_hours', 2)} 小时"
            else:
                trigger = ", ".join(cfg.get("times", []))
            
            enabled = cfg.get("enabled", True)
            enabled_str = "✓ 启用" if enabled else "✗ 禁用"
            enabled_cls = "enabled" if enabled else "disabled"
            
            config_html += f'''
            <tr>
                <td>{module}</td>
                <td>{cfg.get("type", "")}</td>
                <td>{trigger}</td>
                <td class="{enabled_cls}">{enabled_str}</td>
            </tr>'''
        
        # 下次执行表格
        next_runs_html = ""
        for module, next_time in scheduler.get_next_runs().items():
            if next_time:
                time_str = next_time.strftime("%Y-%m-%d %H:%M")
                delta = (next_time - now).total_seconds()
                if delta < 3600:
                    delta_str = f"{int(delta / 60)} 分钟"
                elif delta < 86400:
                    delta_str = f"{int(delta / 3600)} 小时 {int((delta % 3600) / 60)} 分钟"
                else:
                    delta_str = f"{int(delta / 86400)} 天"
            else:
                time_str = "-"
                delta_str = "-"
            
            next_runs_html += f'''
            <tr>
                <td>{module}</td>
                <td>{time_str}</td>
                <td>{delta_str}</td>
            </tr>'''
        
        # 今日时间线
        timeline_html = ""
        current_hour = now.strftime("%H")
        for item in scheduler.get_today_schedule():
            item_hour = item["time"][:2]
            if item["done"]:
                cls = "done"
            elif item_hour == current_hour:
                cls = "current"
            else:
                cls = "upcoming"
            
            icon = "✓" if item["done"] else "○"
            timeline_html += f'''
            <div class="timeline-item {cls}">
                <span class="timeline-time">{item["time"]}</span>
                <span class="timeline-module">{item["module"]}</span>
                <span>{icon}</span>
            </div>'''
        
        html = SCHEDULE_HTML.format(
            now=now.strftime("%Y-%m-%d %H:%M:%S"),
            config_html=config_html,
            next_runs_html=next_runs_html,
            timeline_html=timeline_html
        )
        
        self.send_html(html)
    
    def serve_wewe(self):
        """渲染 Wewe-RSS 管理页面（独立页面）"""
        wewe_config = self.system_config.get("WEWE_RSS", {})
        wewe_url = wewe_config.get("EXTERNAL_URL", wewe_config.get("BASE_URL", "http://localhost:4000"))
        
        html = WEWE_HTML.format(wewe_url=wewe_url)
        self.send_html(html)
    
    def serve_api(self, path: str):
        """处理 API 请求"""
        status_db = self.get_status_db()
        
        if path == "status":
            self.send_json(status_db.get_all_modules_status())
        
        elif path == "health":
            result = status_db.get_latest_health_check()
            self.send_json(result or {"overall": "unknown", "checks": {}})
        
        elif path == "health/run":
            # 执行健康检查
            checker = HealthChecker(self.system_config)
            result = checker.check_all()
            self.send_json(result)
        
        elif path == "schedule":
            scheduler = Scheduler(self.system_config)
            self.send_json({
                "config": scheduler.get_config(),
                "today": scheduler.get_today_schedule(),
                "next_runs": {
                    k: v.isoformat() if v else None
                    for k, v in scheduler.get_next_runs().items()
                }
            })
        
        elif path == "timeline":
            self.send_json(status_db.get_execution_timeline(hours=24))
        
        elif path == "alerts":
            self.send_json(status_db.get_active_alerts())
        
        elif path == "all":
            # 返回所有数据（用于一次性刷新）
            scheduler = Scheduler(self.system_config)
            environment = self.system_config.get("APP", {}).get("ENVIRONMENT", "development")
            self.send_json({
                "environment": environment,
                "modules": status_db.get_all_modules_status(),
                "health": status_db.get_latest_health_check() or {"overall": "unknown", "checks": {}},
                "schedule": scheduler.get_today_schedule()[:12],
                "next_runs": {
                    k: v.isoformat() if v else None
                    for k, v in scheduler.get_next_runs().items()
                },
                "alerts": status_db.get_active_alerts(),
                "timeline": status_db.get_execution_timeline(hours=24)[-20:],
                "timestamp": datetime.now().isoformat()
            })
        
        else:
            self.send_error(404, "API Not Found")


# ═══════════════════════════════════════════════════════════════
# HTML 模板
# ═══════════════════════════════════════════════════════════════

DASHBOARD_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>TrendRadar 系统监控</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
            --accent-yellow: #d29922;
            --accent-red: #f85149;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
            position: sticky;
            top: 0;
            z-index: 100;
        }}
        .header h1 {{
            font-size: 20px;
            font-weight: 600;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .env-badge {{
            font-size: 11px;
            padding: 3px 8px;
            border-radius: 4px;
            font-weight: 500;
            text-transform: uppercase;
            margin-left: 8px;
        }}
        .env-badge.dev {{
            background: #1f6feb;
            color: white;
        }}
        .env-badge.prod {{
            background: #238636;
            color: white;
        }}
        .header-right {{
            display: flex;
            align-items: center;
            gap: 16px;
        }}
        .header .time {{
            color: var(--text-secondary);
            font-size: 13px;
        }}
        .refresh-info {{
            display: flex;
            align-items: center;
            gap: 8px;
            font-size: 12px;
            color: var(--text-secondary);
        }}
        .refresh-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background: var(--accent-green);
            animation: pulse 2s infinite;
        }}
        @keyframes pulse {{
            0%, 100% {{ opacity: 1; }}
            50% {{ opacity: 0.5; }}
        }}
        .btn {{
            background: transparent;
            border: 1px solid var(--border-color);
            color: var(--text-primary);
            padding: 8px 16px;
            border-radius: 6px;
            cursor: pointer;
            font-size: 13px;
            display: flex;
            align-items: center;
            gap: 6px;
            transition: all 0.2s;
        }}
        .btn:hover {{ background: rgba(255, 255, 255, 0.05); }}
        .btn-primary {{
            background: var(--accent-blue);
            border-color: var(--accent-blue);
            color: white;
        }}
        .btn-primary:hover {{ background: #4c9aed; }}
        .btn.loading {{ opacity: 0.6; pointer-events: none; }}
        nav {{
            display: flex;
            gap: 0;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 0 24px;
        }}
        nav a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 14px;
            padding: 12px 16px;
            border-bottom: 2px solid transparent;
            transition: all 0.2s;
        }}
        nav a:hover {{ color: var(--text-primary); }}
        nav a.active {{
            color: var(--accent-blue);
            border-bottom-color: var(--accent-blue);
        }}
        .main {{ padding: 24px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(320px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }}
        .card-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        .card-title {{
            font-size: 14px;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }}
        .card-body {{ padding: 16px; }}
        .status-badge {{
            padding: 4px 10px;
            border-radius: 12px;
            font-size: 11px;
            font-weight: 500;
        }}
        .status-ok {{ background: rgba(63, 185, 80, 0.2); color: var(--accent-green); }}
        .status-warning {{ background: rgba(210, 153, 34, 0.2); color: var(--accent-yellow); }}
        .status-error {{ background: rgba(248, 81, 73, 0.2); color: var(--accent-red); }}
        .status-idle {{ background: rgba(139, 148, 158, 0.2); color: var(--text-secondary); }}
        .module-list {{ display: flex; flex-direction: column; gap: 8px; }}
        .module-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 6px;
            transition: background 0.2s;
        }}
        .module-item:hover {{ background: rgba(255, 255, 255, 0.04); }}
        .module-info {{ display: flex; flex-direction: column; gap: 4px; }}
        .module-name {{ font-weight: 500; font-size: 14px; }}
        .module-meta {{ font-size: 12px; color: var(--text-secondary); }}
        .schedule-list {{ display: flex; flex-direction: column; gap: 4px; }}
        .schedule-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 0;
            border-bottom: 1px solid var(--border-color);
        }}
        .schedule-item:last-child {{ border-bottom: none; }}
        .schedule-time {{
            font-family: 'SF Mono', Consolas, monospace;
            font-size: 13px;
            color: var(--accent-blue);
            width: 50px;
        }}
        .schedule-module {{ flex: 1; font-size: 13px; }}
        .schedule-status {{ width: 20px; text-align: center; }}
        .done {{ color: var(--accent-green); }}
        .pending {{ color: var(--text-secondary); }}
        .health-list {{ display: flex; flex-direction: column; gap: 8px; }}
        .health-item {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 10px 0;
            border-bottom: 1px solid var(--border-color);
        }}
        .health-item:last-child {{ border-bottom: none; }}
        .health-name {{ font-size: 13px; }}
        .health-status {{ font-size: 12px; }}
        .alerts {{ display: flex; flex-direction: column; gap: 8px; }}
        .alert-item {{
            padding: 12px;
            border-radius: 6px;
            font-size: 13px;
        }}
        .alert-error {{
            background: rgba(248, 81, 73, 0.1);
            border-left: 3px solid var(--accent-red);
        }}
        .alert-warning {{
            background: rgba(210, 153, 34, 0.1);
            border-left: 3px solid var(--accent-yellow);
        }}
        .no-data {{ color: var(--text-secondary); font-style: italic; font-size: 13px; padding: 20px 0; text-align: center; }}
        .timeline {{
            display: flex;
            flex-direction: column;
            gap: 4px;
            max-height: 280px;
            overflow-y: auto;
        }}
        .timeline-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 4px;
        }}
        .timeline-time {{
            font-family: 'SF Mono', Consolas, monospace;
            font-size: 12px;
            color: var(--text-secondary);
            width: 45px;
        }}
        .timeline-module {{ font-size: 13px; width: 90px; }}
        .timeline-status {{ flex: 1; font-size: 12px; }}
        .timeline-duration {{ font-size: 12px; color: var(--text-secondary); }}
        /* Wewe-RSS 嵌入区域 */
        .wewe-section {{
            margin-top: 24px;
        }}
        .wewe-frame {{
            width: 100%;
            height: 500px;
            border: none;
            border-radius: 8px;
            background: var(--card-bg);
        }}
        .wewe-link {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 12px;
        }}
        .wewe-link a {{
            color: var(--accent-blue);
            text-decoration: none;
            font-size: 13px;
        }}
        .wewe-link a:hover {{ text-decoration: underline; }}
        /* 刷新动画 */
        .refreshing {{ animation: spin 1s linear infinite; }}
        @keyframes spin {{ 100% {{ transform: rotate(360deg); }} }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📊 TrendRadar 系统监控 <span id="env-badge" class="env-badge" style="display:none;"></span></h1>
        <div class="header-right">
            <div class="refresh-info">
                <span class="refresh-dot"></span>
                <span id="last-update">更新中...</span>
            </div>
            <button class="btn" onclick="runHealthCheck()" id="health-btn">
                <span>🔍</span> 健康检查
            </button>
            <button class="btn btn-primary" onclick="refreshAll()" id="refresh-btn">
                <span id="refresh-icon">🔄</span> 刷新
            </button>
        </div>
    </div>
    
    <nav>
        <a href="/" class="active">仪表板</a>
        <a href="/schedule">调度时间表</a>
        <a href="/wewe">公众号管理</a>
    </nav>
    
    <div class="main">
        <div class="grid">
            <!-- 模块状态 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">模块状态</span>
                </div>
                <div class="card-body">
                    <div class="module-list" id="modules-list">
                        <div class="no-data">加载中...</div>
                    </div>
                </div>
            </div>
            
            <!-- 今日调度 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">今日调度</span>
                </div>
                <div class="card-body">
                    <div class="schedule-list" id="schedule-list">
                        <div class="no-data">加载中...</div>
                    </div>
                </div>
            </div>
            
            <!-- 健康检查 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">健康检查</span>
                    <span class="status-badge status-idle" id="health-overall">检查中</span>
                </div>
                <div class="card-body">
                    <div class="health-list" id="health-list">
                        <div class="no-data">加载中...</div>
                    </div>
                </div>
            </div>
            
            <!-- 告警 -->
            <div class="card">
                <div class="card-header">
                    <span class="card-title">告警</span>
                </div>
                <div class="card-body">
                    <div class="alerts" id="alerts-list">
                        <div class="no-data">加载中...</div>
                    </div>
                </div>
            </div>
        </div>
        
        <!-- 执行时间线 -->
        <div class="card">
            <div class="card-header">
                <span class="card-title">执行时间线（最近24小时）</span>
            </div>
            <div class="card-body">
                <div class="timeline" id="timeline-list">
                    <div class="no-data">加载中...</div>
                </div>
            </div>
        </div>
        
        <!-- Wewe-RSS 管理（嵌入） -->
        <div class="wewe-section">
            <div class="card">
                <div class="card-header">
                    <span class="card-title">微信公众号账号管理 (Wewe-RSS)</span>
                    <div class="wewe-link">
                        <a href="{wewe_url}" target="_blank">在新窗口打开 ↗</a>
                    </div>
                </div>
                <div class="card-body" style="padding: 0;">
                    <iframe src="{wewe_url}" class="wewe-frame" id="wewe-frame"></iframe>
                </div>
            </div>
        </div>
    </div>
    
    <script>
        // 自动刷新间隔（毫秒）
        const REFRESH_INTERVAL = 30000;
        let refreshTimer = null;
        
        // 初始化
        document.addEventListener('DOMContentLoaded', () => {{
            refreshAll();
            startAutoRefresh();
        }});
        
        // 启动自动刷新
        function startAutoRefresh() {{
            if (refreshTimer) clearInterval(refreshTimer);
            refreshTimer = setInterval(refreshAll, REFRESH_INTERVAL);
        }}
        
        // 刷新所有数据
        async function refreshAll() {{
            const btn = document.getElementById('refresh-btn');
            const icon = document.getElementById('refresh-icon');
            btn.classList.add('loading');
            icon.classList.add('refreshing');
            
            try {{
                const response = await fetch('/api/all');
                const data = await response.json();
                
                updateEnvironment(data.environment);
                updateModules(data.modules);
                updateSchedule(data.schedule);
                updateHealth(data.health);
                updateAlerts(data.alerts);
                updateTimeline(data.timeline);
                updateLastUpdate();
            }} catch (e) {{
                console.error('刷新失败:', e);
            }} finally {{
                btn.classList.remove('loading');
                icon.classList.remove('refreshing');
            }}
        }}
        
        // 执行健康检查
        async function runHealthCheck() {{
            const btn = document.getElementById('health-btn');
            btn.classList.add('loading');
            btn.textContent = '检查中...';
            
            try {{
                const response = await fetch('/api/health/run');
                const data = await response.json();
                updateHealth(data);
            }} catch (e) {{
                console.error('健康检查失败:', e);
            }} finally {{
                btn.classList.remove('loading');
                btn.innerHTML = '<span>🔍</span> 健康检查';
            }}
        }}
        
        // 更新环境标识
        function updateEnvironment(env) {{
            const badge = document.getElementById('env-badge');
            if (!env) return;
            
            badge.style.display = 'inline-block';
            if (env === 'production') {{
                badge.className = 'env-badge prod';
                badge.textContent = '生产环境';
            }} else {{
                badge.className = 'env-badge dev';
                badge.textContent = '开发环境';
            }}
        }}
        
        // 更新模块状态
        function updateModules(modules) {{
            const container = document.getElementById('modules-list');
            if (!modules || Object.keys(modules).length === 0) {{
                container.innerHTML = '<div class="no-data">暂无数据</div>';
                return;
            }}
            
            let html = '';
            for (const [name, status] of Object.entries(modules)) {{
                const statusVal = status.status || 'idle';
                let lastRun = status.last_run_at || '';
                if (lastRun) lastRun = lastRun.substring(0, 16).replace('T', ' ');
                else lastRun = '未执行';
                
                let badgeClass = 'status-idle';
                let badgeText = 'idle';
                if (statusVal === 'success') {{ badgeClass = 'status-ok'; badgeText = '✓ success'; }}
                else if (statusVal === 'failed') {{ badgeClass = 'status-error'; badgeText = '✗ failed'; }}
                else if (statusVal === 'running') {{ badgeClass = 'status-warning'; badgeText = '⏳ running'; }}
                
                html += `
                <div class="module-item">
                    <div class="module-info">
                        <span class="module-name">${{name}}</span>
                        <span class="module-meta">最后执行: ${{lastRun}}</span>
                    </div>
                    <span class="status-badge ${{badgeClass}}">${{badgeText}}</span>
                </div>`;
            }}
            container.innerHTML = html;
        }}
        
        // 更新调度
        function updateSchedule(schedule) {{
            const container = document.getElementById('schedule-list');
            if (!schedule || schedule.length === 0) {{
                container.innerHTML = '<div class="no-data">暂无数据</div>';
                return;
            }}
            
            let html = '';
            for (const item of schedule.slice(0, 10)) {{
                const doneClass = item.done ? 'done' : 'pending';
                const icon = item.done ? '✓' : '○';
                html += `
                <div class="schedule-item">
                    <span class="schedule-time">${{item.time}}</span>
                    <span class="schedule-module">${{item.module}}</span>
                    <span class="schedule-status ${{doneClass}}">${{icon}}</span>
                </div>`;
            }}
            container.innerHTML = html;
        }}
        
        // 更新健康检查
        function updateHealth(health) {{
            const container = document.getElementById('health-list');
            const overall = document.getElementById('health-overall');
            
            if (!health || !health.checks) {{
                container.innerHTML = '<div class="no-data">暂无检查结果</div>';
                overall.className = 'status-badge status-idle';
                overall.textContent = 'unknown';
                return;
            }}
            
            // 更新总体状态
            const overallStatus = health.overall || 'unknown';
            overall.className = `status-badge status-${{overallStatus === 'ok' ? 'ok' : (overallStatus === 'warning' ? 'warning' : (overallStatus === 'error' ? 'error' : 'idle'))}}`;
            overall.textContent = overallStatus;
            
            // 检查项名称映射
            const nameMap = {{
                'ai_service': 'AI 服务',
                'email_service': '邮件服务',
                'databases': '数据库',
                'wewe_rss': 'Wewe-RSS',
                'wewe_login': '微信读书登录'
            }};
            
            let html = '';
            for (const [name, check] of Object.entries(health.checks)) {{
                const displayName = nameMap[name] || name;
                const status = check.status || 'unknown';
                const message = check.message || '';
                
                let icon = '○';
                let cls = 'status-idle';
                if (status === 'ok') {{ icon = '✓'; cls = 'status-ok'; }}
                else if (status === 'warning') {{ icon = '⚠'; cls = 'status-warning'; }}
                else if (status === 'error') {{ icon = '✗'; cls = 'status-error'; }}
                
                html += `
                <div class="health-item">
                    <span class="health-name">${{displayName}}</span>
                    <span class="health-status ${{cls}}">${{icon}} ${{message.substring(0, 25)}}</span>
                </div>`;
            }}
            container.innerHTML = html || '<div class="no-data">暂无检查结果</div>';
        }}
        
        // 更新告警
        function updateAlerts(alerts) {{
            const container = document.getElementById('alerts-list');
            if (!alerts || alerts.length === 0) {{
                container.innerHTML = '<div class="no-data">暂无告警 ✓</div>';
                return;
            }}
            
            let html = '';
            for (const alert of alerts) {{
                const level = alert.level || 'warning';
                const module = alert.module || '系统';
                const message = alert.message || '';
                const created = (alert.created_at || '').substring(0, 16).replace('T', ' ');
                
                html += `
                <div class="alert-item alert-${{level}}">
                    <strong>${{module}}</strong>: ${{message}}
                    <small style="display:block;margin-top:4px;color:var(--text-secondary);">${{created}}</small>
                </div>`;
            }}
            container.innerHTML = html;
        }}
        
        // 更新时间线
        function updateTimeline(timeline) {{
            const container = document.getElementById('timeline-list');
            if (!timeline || timeline.length === 0) {{
                container.innerHTML = '<div class="no-data">暂无执行记录</div>';
                return;
            }}
            
            let html = '';
            for (const item of [...timeline].reverse()) {{
                const time = item.started_at ? item.started_at.substring(11, 16) : '-';
                const status = item.status || 'unknown';
                const duration = (item.duration_seconds || 0).toFixed(1);
                
                let cls = 'status-idle';
                if (status === 'success') cls = 'status-ok';
                else if (status === 'failed') cls = 'status-error';
                
                html += `
                <div class="timeline-item">
                    <span class="timeline-time">${{time}}</span>
                    <span class="timeline-module">${{item.module || ''}}</span>
                    <span class="timeline-status ${{cls}}">${{status}}</span>
                    <span class="timeline-duration">${{duration}}s</span>
                </div>`;
            }}
            container.innerHTML = html;
        }}
        
        // 更新最后刷新时间
        function updateLastUpdate() {{
            const el = document.getElementById('last-update');
            const now = new Date();
            el.textContent = `${{now.getHours().toString().padStart(2, '0')}}:${{now.getMinutes().toString().padStart(2, '0')}}:${{now.getSeconds().toString().padStart(2, '0')}} 更新`;
        }}
    </script>
</body>
</html>'''

SCHEDULE_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>调度时间表 - TrendRadar</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
            --accent-green: #3fb950;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
        }}
        .header h1 {{ font-size: 20px; font-weight: 600; }}
        .header .time {{ color: var(--text-secondary); font-size: 13px; }}
        nav {{
            display: flex;
            gap: 0;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 0 24px;
        }}
        nav a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 14px;
            padding: 12px 16px;
            border-bottom: 2px solid transparent;
        }}
        nav a:hover {{ color: var(--text-primary); }}
        nav a.active {{ color: var(--accent-blue); border-bottom-color: var(--accent-blue); }}
        .main {{ padding: 24px; }}
        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(400px, 1fr));
            gap: 20px;
        }}
        .card {{
            background: var(--card-bg);
            border: 1px solid var(--border-color);
            border-radius: 8px;
            overflow: hidden;
        }}
        .card-header {{
            padding: 16px;
            border-bottom: 1px solid var(--border-color);
        }}
        .card-title {{ font-size: 14px; font-weight: 600; text-transform: uppercase; }}
        .card-body {{ padding: 16px; }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid var(--border-color); }}
        th {{ font-weight: 500; color: var(--text-secondary); font-size: 12px; text-transform: uppercase; }}
        td {{ font-size: 14px; }}
        .enabled {{ color: var(--accent-green); }}
        .disabled {{ color: var(--text-secondary); }}
        .timeline {{ display: flex; flex-direction: column; gap: 4px; }}
        .timeline-item {{
            display: flex;
            align-items: center;
            gap: 12px;
            padding: 8px 12px;
            background: rgba(255, 255, 255, 0.02);
            border-radius: 4px;
        }}
        .timeline-time {{
            font-family: 'SF Mono', Consolas, monospace;
            font-size: 14px;
            color: var(--accent-blue);
            width: 60px;
        }}
        .timeline-module {{ flex: 1; font-size: 14px; }}
        .done {{ color: var(--text-secondary); text-decoration: line-through; }}
        .current {{ background: rgba(88, 166, 255, 0.1); border-left: 3px solid var(--accent-blue); }}
        .upcoming {{ color: var(--text-primary); }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📅 调度时间表</h1>
        <div class="time">{now}</div>
    </div>
    <nav>
        <a href="/">仪表板</a>
        <a href="/schedule" class="active">调度时间表</a>
        <a href="/wewe">公众号管理</a>
    </nav>
    <div class="main">
        <div class="grid">
            <div class="card">
                <div class="card-header"><span class="card-title">调度配置</span></div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>模块</th><th>类型</th><th>触发规则</th><th>状态</th></tr></thead>
                        <tbody>{config_html}</tbody>
                    </table>
                </div>
            </div>
            <div class="card">
                <div class="card-header"><span class="card-title">下次执行时间</span></div>
                <div class="card-body">
                    <table>
                        <thead><tr><th>模块</th><th>时间</th><th>距离现在</th></tr></thead>
                        <tbody>{next_runs_html}</tbody>
                    </table>
                </div>
            </div>
        </div>
        <div class="card" style="margin-top: 20px;">
            <div class="card-header"><span class="card-title">今日时间线</span></div>
            <div class="card-body">
                <div class="timeline">{timeline_html}</div>
            </div>
        </div>
    </div>
</body>
</html>'''

WEWE_HTML = '''<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>公众号管理 - TrendRadar</title>
    <style>
        :root {{
            --bg-color: #0d1117;
            --card-bg: #161b22;
            --border-color: #30363d;
            --text-primary: #c9d1d9;
            --text-secondary: #8b949e;
            --accent-blue: #58a6ff;
        }}
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background-color: var(--bg-color);
            color: var(--text-primary);
            min-height: 100vh;
        }}
        .header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 16px 24px;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
        }}
        .header h1 {{ font-size: 20px; font-weight: 600; }}
        nav {{
            display: flex;
            gap: 0;
            background: var(--card-bg);
            border-bottom: 1px solid var(--border-color);
            padding: 0 24px;
        }}
        nav a {{
            color: var(--text-secondary);
            text-decoration: none;
            font-size: 14px;
            padding: 12px 16px;
            border-bottom: 2px solid transparent;
        }}
        nav a:hover {{ color: var(--text-primary); }}
        nav a.active {{ color: var(--accent-blue); border-bottom-color: var(--accent-blue); }}
        .main {{ height: calc(100vh - 100px); }}
        iframe {{
            width: 100%;
            height: 100%;
            border: none;
        }}
        .open-link {{
            position: fixed;
            top: 16px;
            right: 24px;
            background: var(--accent-blue);
            color: white;
            padding: 8px 16px;
            border-radius: 6px;
            text-decoration: none;
            font-size: 13px;
            z-index: 100;
        }}
        .open-link:hover {{ background: #4c9aed; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>📱 微信公众号管理 (Wewe-RSS)</h1>
    </div>
    <nav>
        <a href="/">仪表板</a>
        <a href="/schedule">调度时间表</a>
        <a href="/wewe" class="active">公众号管理</a>
    </nav>
    <a href="{wewe_url}" target="_blank" class="open-link">在新窗口打开 ↗</a>
    <div class="main">
        <iframe src="{wewe_url}"></iframe>
    </div>
</body>
</html>'''


def create_app(system_config: Optional[dict] = None):
    """创建监控服务器"""
    system_config = system_config or load_system_config()
    MonitorHandler.system_config = system_config
    return MonitorHandler


def start_server(port: int = 8088, host: str = "127.0.0.1"):
    """启动监控服务器"""
    system_config = load_system_config()
    port = system_config.get("MONITOR", {}).get("WEB_PORT", port)
    
    handler = create_app(system_config)
    server = http.server.HTTPServer((host, port), handler)
    
    print(f"🌐 监控服务器启动: http://{host}:{port}")
    print(f"   - 仪表板: http://{host}:{port}/")
    print(f"   - 调度表: http://{host}:{port}/schedule")
    print(f"   - 公众号: http://{host}:{port}/wewe")
    print("按 Ctrl+C 停止")
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n监控服务器已停止")
        server.server_close()


def main():
    """命令行入口"""
    start_server()


if __name__ == "__main__":
    main()
