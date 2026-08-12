"""阶段五·2D 飞轮：APScheduler 集成。

为什么不单独跑 cron pod：
- 内存里 APScheduler 够用
- 启动期一并初始化，省运维

触发节奏：
- production（KG_ENV=production 或 settings.KG_ENV=production）：
    每周一 03:00 Asia/Shanghai
- dev/staging：每 5 分钟跑一次（方便联调）

misfire_grace_time=3600s 让 job 错过 1 小时内还能补救。

依赖缺失（apscheduler 未装）时 start_scheduler 是 no-op —
test / 离线环境也能 import kg.* 不报错。
"""
from __future__ import annotations

import logging
from typing import Any

from config import settings


log = logging.getLogger(__name__)

_scheduler: Any | None = None


def start_scheduler() -> Any | None:
    """启动 APScheduler。已运行则返回已有实例。

    Returns: 启动后的 AsyncIOScheduler（测试用），None 表示启动失败 / 依赖缺失。
    """
    global _scheduler
    if _scheduler is not None:
        return _scheduler

    try:
        from apscheduler.schedulers.asyncio import AsyncIOScheduler
        from apscheduler.triggers.cron import CronTrigger
    except Exception as e:
        log.warning("[scheduler] apscheduler 未装: %s — scheduler 跳过", e)
        return None

    try:
        from kg.flywheel import weekly_flywheel_update  # noqa: F401
    except Exception as e:  # pragma: no cover
        log.warning("[scheduler] flywheel import failed: %s — scheduler 跳过", e)
        return None

    try:
        _scheduler = AsyncIOScheduler()
        env = (settings.KG_ENV or "production").lower()
        if env == "production":
            _scheduler.add_job(
                weekly_flywheel_update,
                CronTrigger(day_of_week="mon", hour=3, minute=0,
                            timezone="Asia/Shanghai"),
                id="weekly_flywheel",
                replace_existing=True,
                misfire_grace_time=3600,
            )
            log.info("[scheduler] weekly_flywheel scheduled at Mon 03:00 (Asia/Shanghai)")
        else:
            # dev / staging：5 分钟跑一次便于观察
            _scheduler.add_job(
                weekly_flywheel_update,
                "interval", minutes=5,
                id="weekly_flywheel_test",
                replace_existing=True,
            )
            log.info("[scheduler] KG_ENV=%s → test mode: every 5 min", env)
        _scheduler.start()
    except Exception as e:
        log.warning("[scheduler] start failed: %s", e)
        _scheduler = None
    return _scheduler


def stop_scheduler() -> None:
    """停 scheduler。FastAPI lifespan shutdown 时调用。"""
    global _scheduler
    if _scheduler is not None:
        try:
            _scheduler.shutdown(wait=False)
        except Exception:
            pass
        _scheduler = None