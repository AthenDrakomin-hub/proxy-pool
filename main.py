#!/usr/bin/env python3
"""代理池入口：启动 API 服务 + 定时调度器"""
import sys
import os
import argparse
import uvicorn
from fastapi import FastAPI

# 确保项目根目录在 path 中
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.config import load_config
from app.api import router, web_router
from app.scheduler import start_scheduler, stop_scheduler
from app.database import get_conn


def create_app() -> FastAPI:
    """创建 FastAPI 应用"""
    app = FastAPI(
        title="Proxy Pool",
        description="自建代理池 - 自动抓取/验证/评分/API取用",
        version="1.0.0",
    )
    app.include_router(router)
    app.include_router(web_router)
    return app


def main():
    parser = argparse.ArgumentParser(description="代理池服务")
    parser.add_argument("--config", "-c", help="配置文件路径", default=None)
    parser.add_argument("--no-scheduler", action="store_true", help="不启动定时调度器")
    parser.add_argument("--fetch-only", action="store_true", help="只执行一次抓取后退出")
    parser.add_argument("--check-only", action="store_true", help="只执行一次验证后退出")
    args = parser.parse_args()

    # 加载配置
    load_config(args.config)
    # 初始化数据库
    get_conn()

    # 单次执行模式
    if args.fetch_only:
        from app.fetcher import fetch_all
        fetch_all()
        return
    if args.check_only:
        from app.checker import check_all
        check_all()
        return

    # 服务模式
    app = create_app()
    cfg = load_config()
    host = cfg["server"]["host"]
    port = cfg["server"]["port"]

    if not args.no_scheduler:
        start_scheduler()

    print(f"\n{'='*50}")
    print(f"  代理池服务启动中...")
    print(f"  API:    http://{host}:{port}/api/")
    print(f"  面板:   http://{host}:{port}/")
    print(f"  文档:   http://{host}:{port}/docs")
    print(f"{'='*50}\n")

    try:
        uvicorn.run(app, host=host, port=port, log_level="info")
    except (KeyboardInterrupt, SystemExit):
        pass
    finally:
        stop_scheduler()


if __name__ == "__main__":
    main()
