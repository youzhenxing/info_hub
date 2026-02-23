-- ═════════════════════════════════════════════════════════════
-- 播客数据库清理脚本（简化版迁移）
-- ═════════════════════════════════════════════════════════════
--
-- ⚠️ 重要：只清理中间状态，保留 completed 和 failed 记录！
--
-- 清理的记录（改为 failed）：
--   - pending (62 条) - 中间状态，新逻辑不再使用
--   - skipped_old (91 条) - 中间状态，新逻辑不再使用
--   - downloading/transcribing/analyzing/notifying (2 条) - 卡死的中间状态
--
-- 保留的记录（不会被修改）：
--   ✅ completed (5 条) - 已成功处理，用于 _is_new_episode() 判断去重
--   ✅ failed (11 条) - 已处理失败，同样用于去重避免重复尝试
--
-- ═════════════════════════════════════════════════════════════

BEGIN TRANSACTION;

-- 1. 只清理中间状态（pending/skipped_old/downloading/transcribing等）
-- 保留 completed 和 failed，避免重复处理
UPDATE podcast_episodes
SET status = 'failed',
    error_message = '简化版迁移：清理旧中间状态'
WHERE status IN ('pending', 'skipped_old', 'downloading', 'transcribing', 'analyzing', 'notifying');

-- 2. 验证清理结果
SELECT '-- 清理后状态分布 --' as info;
SELECT status, COUNT(*) as count
FROM podcast_episodes
GROUP BY status
ORDER BY count DESC;

COMMIT;

-- ═════════════════════════════════════════════════════════════
-- 预期结果：
-- ═════════════════════════════════════════════════════════════
-- completed | 5    (保持不变)
-- failed    | 166  (11 + 62 + 91 + 2 = 166)
-- ═════════════════════════════════════════════════════════════
