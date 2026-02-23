#!/usr/bin/env python3
# coding=utf-8
"""
版本首次启动引导脚本（Bootstrap）

触发条件: module_status.bootstrapped_version != APP_VERSION
模块触发顺序: investment → community → podcast（依序执行，避免 AI API 并发限流）
后台运行: entrypoint.sh 以 & 启动，不阻塞 supercronic (PID 1)
日志: 同时写入 stdout（docker logs 可查）和 output/system/bootstrap.log（持久化）
"""

import sys
import os
import logging
import subprocess
import time

# 添加项目路径
sys.path.insert(0, '/app')

# ─── 初始化 Logger（双写）───────────────────────────────
LOG_FILE = "/app/output/system/bootstrap.log"
bootstrap_logger = logging.getLogger("bootstrap")
bootstrap_logger.setLevel(logging.INFO)

_fmt = logging.Formatter('%(asctime)s %(message)s', datefmt='%Y-%m-%d %H:%M:%S')
_sh = logging.StreamHandler()
_sh.setFormatter(_fmt)
bootstrap_logger.addHandler(_sh)
try:
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
    _fh = logging.FileHandler(LOG_FILE)
    _fh.setFormatter(_fmt)
    bootstrap_logger.addHandler(_fh)
except Exception:
    pass

log = bootstrap_logger


def _trigger_subprocess(module: str, script: str, timeout: int) -> bool:
    """用 subprocess 触发模块脚本，返回是否成功"""
    log.info(f"[Bootstrap] ─── 触发 {module} (开始) ───")
    log.info(f"[Bootstrap]   开始时间: {time.strftime('%Y-%m-%dT%H:%M:%S')}")

    start = time.time()
    try:
        result = subprocess.run(
            [sys.executable, script],
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd="/app",
        )
        elapsed = time.time() - start
        log.info(f"[Bootstrap] ─── 触发 {module} (结束) ───")
        log.info(f"[Bootstrap]   退码: {result.returncode} | 耗时: {elapsed:.1f}s")

        # 转发子进程 stdout 末尾到 bootstrap log
        if result.stdout:
            for line in result.stdout.strip().splitlines()[-10:]:
                log.info(f"[Bootstrap]   stdout: {line}")

        if result.returncode != 0 and result.stderr:
            stderr_tail = result.stderr.strip().splitlines()[-3:]
            log.info(f"[Bootstrap]   stderr 末尾: {' | '.join(stderr_tail)}")
            return False
        return result.returncode == 0

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start
        log.warning(f"[Bootstrap] ─── 触发 {module} 超时 ({timeout}s) ───")
        return False
    except Exception as e:
        elapsed = time.time() - start
        log.error(f"[Bootstrap] ─── 触发 {module} 异常: {e} | 耗时: {elapsed:.1f}s ───")
        return False


def _trigger_podcast(timeout: int = 600) -> bool:
    """直接 import 触发播客模块（bootstrap_mode=True）"""
    log.info("[Bootstrap] ─── 触发 podcast (开始) ───")
    log.info(f"[Bootstrap]   开始时间: {time.strftime('%Y-%m-%dT%H:%M:%S')}")

    start = time.time()
    try:
        from trendradar.core import load_config
        from trendradar.podcast.processor import PodcastProcessor

        config = load_config()
        # 强制启用播客模块
        if "podcast" not in config:
            config["podcast"] = {}
        config["podcast"]["enabled"] = True

        processor = PodcastProcessor.from_config(config, bootstrap_mode=True)
        results = processor.run()

        elapsed = time.time() - start
        success_count = sum(1 for r in results if r.status == "completed")
        log.info(f"[Bootstrap] ─── 触发 podcast (结束) ───")
        log.info(f"[Bootstrap]   耗时: {elapsed:.1f}s | 成功: {success_count}/{len(results)}")
        return True

    except Exception as e:
        elapsed = time.time() - start
        log.error(f"[Bootstrap] ─── 触发 podcast 异常: {e} | 耗时: {elapsed:.1f}s ───")
        import traceback
        log.error(f"[Bootstrap]   {traceback.format_exc().splitlines()[-1]}")
        return False


def main():
    app_version = os.getenv("APP_VERSION", "")

    log.info("[Bootstrap] ═══ 启动引导 ═══")
    log.info(f"[Bootstrap] APP_VERSION = {app_version}")

    # ==================== 版本一致性验证 ====================
    # 检查代码版本标记（如果存在）
    code_version_marker = "/app/.deployed_version"
    if os.path.exists(code_version_marker):
        try:
            import yaml
            with open(code_version_marker, 'r') as f:
                marker_data = yaml.safe_load(f)

            deployed_version = marker_data.get('version', '').replace('v', '')
            container_version = app_version.replace('v', '')

            if deployed_version and deployed_version != container_version:
                log.warning(f"[Bootstrap] ⚠️  版本不一致警告！")
                log.warning(f"[Bootstrap]   代码标记版本: {deployed_version}")
                log.warning(f"[Bootstrap]   容器运行版本: {container_version}")
                log.warning(f"[Bootstrap]   可能原因：代码更新后未重新部署")
                log.warning(f"[Bootstrap]   建议：执行 'cd deploy && yes \"y\" | bash deploy.sh' 重新部署")
            elif deployed_version:
                log.info(f"[Bootstrap] ✓ 版本一致性检查通过: v{container_version}")
        except Exception as e:
            log.warning(f"[Bootstrap] 版本标记读取失败: {e}")
    else:
        log.info("[Bootstrap] 未找到版本标记文件（首次部署）")
    # ==================== 验证结束 ====================

    if not app_version:
        log.warning("[Bootstrap] APP_VERSION 未设置，跳过引导")
        return

    # 初始化 StatusDB
    from trendradar.core.status import StatusDB
    status_db = StatusDB()

    # 各模块定义: (模块名, 触发方式, 超时秒数)
    # ⚡ 提高超时以提高实时性，避免网络不稳定导致的失败
    modules = [
        ("investment", "subprocess", 900),      # ✅ 从 300 提高到 900（15分钟）
        ("community", "subprocess", 1200),    # ✅ 从 900 提高到 1200（20分钟）
        ("podcast",    "import",     1800),   # ✅ 从 600 提高到 1800（30分钟）
    ]

    script_map = {
        "investment": "/app/run_investment.py",
        "community":  "/app/run_community.py",
    }

    # 逐模块查询状态并判断
    log.info("[Bootstrap] 各模块状态查询:")
    needs_bootstrap = []
    for module, _, _ in modules:
        needed = status_db.check_bootstrap_needed(module, app_version)
        if needed:
            # 查出当前 bootstrapped_version 用于 trace
            conn = status_db._get_connection()
            try:
                cur = conn.execute(
                    "SELECT bootstrapped_version FROM module_status WHERE module = ?",
                    (module,)
                )
                row = cur.fetchone()
                cur_ver = row[0] if row and row[0] else "NULL"
            finally:
                conn.close()
            log.info(f"[Bootstrap]   {module}: bootstrapped_version={cur_ver} → 需要引导")
            needs_bootstrap.append(module)
        else:
            log.info(f"[Bootstrap]   {module}: bootstrapped_version={app_version} → 跳过（已是当前版本）")

    if not needs_bootstrap:
        log.info(f"[Bootstrap] 所有模块已是当前版本 v{app_version}，跳过引导")
        log.info("[Bootstrap] ═══ 引导完成 ═══")
        return

    # 依序触发需要引导的模块
    for module, trigger_type, timeout in modules:
        if module not in needs_bootstrap:
            continue

        try:
            if trigger_type == "subprocess":
                success = _trigger_subprocess(module, script_map[module], timeout)
            else:
                success = _trigger_podcast(timeout)

            # 无论成功与否都标记已引导（避免重复触发）
            status_db.mark_bootstrapped(module, app_version)
            if success:
                log.info(f"[Bootstrap]   → 标记已引导 ✅")
            else:
                log.info(f"[Bootstrap]   → 标记已引导 ⚠️ (带 error)")

        except Exception as e:
            log.error(f"[Bootstrap] {module} 触发异常: {e}")
            # 仍然标记已引导
            try:
                status_db.mark_bootstrapped(module, app_version)
                log.info(f"[Bootstrap]   → 标记已引导 ⚠️ (异常)")
            except Exception:
                pass

    log.info("[Bootstrap] ═══ 引导完成 ═══")


if __name__ == "__main__":
    main()
