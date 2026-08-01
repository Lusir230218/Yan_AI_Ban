"""每日 02:00 跑一次：把 user_kp_mastery 当前 score 写入 mastery_snapshots"""
import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import text

from core.database import async_session

logger = logging.getLogger("snapshot_mastery")


async def snapshot_user_mastery() -> int:
    """把 24h 内有更新的 user_kp_mastery 写快照。返回写入行数。"""
    async with async_session() as db:
        rows = (await db.execute(text("""
            SELECT user_id, kp_id, subject, score
            FROM user_kp_mastery
            WHERE updated_at >= now() - interval '1 day'
        """))).all()

        written = 0
        for r in rows:
            prev = (await db.execute(text("""
                SELECT score FROM mastery_snapshots
                WHERE user_id = :u AND kp_id = :k
                ORDER BY captured_at DESC LIMIT 1
            """), {"u": r.user_id, "k": r.kp_id})).scalar()
            delta = (r.score - prev) if prev is not None else None
            await db.execute(text("""
                INSERT INTO mastery_snapshots
                  (user_id, kp_id, subject, score, delta, captured_at)
                VALUES (:u, :k, :s, :sc, :d, now())
            """), {"u": r.user_id, "k": r.kp_id, "s": r.subject,
                   "sc": r.score, "d": delta})
            written += 1
        await db.commit()
        logger.info(f"snapshot_mastery wrote {written} rows")
        return written


async def snapshot_cron_loop(hour: int = 2):
    """asyncio 循环：每天 hour:00 触发一次"""
    while True:
        now = datetime.now(timezone.utc)
        next_run = now.replace(hour=hour, minute=0, second=0, microsecond=0)
        if next_run <= now:
            next_run += timedelta(days=1)
        wait_sec = (next_run - now).total_seconds()
        logger.info(f"snapshot_cron next run in {wait_sec:.0f}s")
        await asyncio.sleep(wait_sec)
        try:
            await snapshot_user_mastery()
        except Exception as e:
            logger.error(f"snapshot_user_mastery failed: {e}")
