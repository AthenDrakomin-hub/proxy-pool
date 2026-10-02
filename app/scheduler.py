"""定时任务调度器"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from .config import get_config
from .fetcher import fetch_all
from .checker import check_all
from .database import cleanup_dead

_scheduler: BackgroundScheduler = None


def start_scheduler():
    """启动定时任务调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        return _scheduler

    cfg = get_config()
    sched_cfg = cfg.get("scheduler", {})
    fetch_min = sched_cfg.get("fetch_interval_minutes", 30)
    check_min = sched_cfg.get("check_interval_minutes", 10)
    cleanup_hours = sched_cfg.get("cleanup_interval_hours", 6)

    _scheduler = BackgroundScheduler()

    _scheduler.add_job(
        fetch_all,
        trigger=IntervalTrigger(minutes=fetch_min),
        id="fetch_proxies",
        name="抓取代理",
        replace_existing=True,
    )
    _scheduler.add_job(
        check_all,
        trigger=IntervalTrigger(minutes=check_min),
        id="check_proxies",
        name="验证代理",
        replace_existing=True,
    )
    _scheduler.add_job(
        cleanup_dead,
        trigger=IntervalTrigger(hours=cleanup_hours),
        id="cleanup_dead",
        name="清理死代理",
        replace_existing=True,
    )

    _scheduler.start()
    print(f"[调度器] 已启动: 抓取每{fetch_min}分钟, 验证每{check_min}分钟, 清理每{cleanup_hours}小时")
    return _scheduler


def stop_scheduler():
    """停止调度器"""
    global _scheduler
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        print("[调度器] 已停止")
