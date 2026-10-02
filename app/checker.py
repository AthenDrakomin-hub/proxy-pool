"""多线程代理验证引擎"""
import time
import requests
import concurrent.futures
from typing import List, Tuple
from .models import Proxy
from .database import get_all_for_check, update_check_result
from .config import get_config


HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}


def test_single(proxy: Proxy, timeout: int,
                 test_url_http: str, test_url_https: str) -> Tuple[Proxy, bool, float]:
    """测试单条代理，返回 (proxy, success, latency_seconds)"""
    proxy_url = proxy.proxy_url
    # HTTPS 代理测 HTTPS 目标，其他测 HTTP 目标
    url = test_url_https if proxy.protocol == "https" else test_url_http
    try:
        start = time.time()
        r = requests.get(
            url,
            proxies={"http": proxy_url, "https": proxy_url},
            timeout=timeout,
            headers=HEADERS,
        )
        elapsed = time.time() - start
        success = r.status_code == 200
        return (proxy, success, elapsed)
    except Exception:
        return (proxy, False, 0.0)


def check_all() -> dict:
    """全量验证所有非 dead 代理，更新数据库，返回统计"""
    cfg = get_config()
    checker_cfg = cfg.get("checker", {})
    timeout = checker_cfg.get("timeout", 8)
    max_workers = checker_cfg.get("max_workers", 50)
    test_url_http = checker_cfg.get("test_url_http", "http://httpbin.org/ip")
    test_url_https = checker_cfg.get("test_url_https", "https://httpbin.org/ip")

    proxies = get_all_for_check()
    if not proxies:
        return {"total": 0, "working": 0, "failed": 0}

    print(f"  [验证] 开始测试 {len(proxies)} 条代理 (并发={max_workers}, 超时={timeout}s)")
    working = 0
    failed = 0

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(test_single, p, timeout, test_url_http, test_url_https): p
            for p in proxies
        }
        done = 0
        for future in concurrent.futures.as_completed(futures):
            proxy, success, latency = future.result()
            done += 1
            if proxy.id:
                update_check_result(proxy.id, success, latency)
            if success:
                working += 1
            else:
                failed += 1
            if done % 100 == 0:
                print(f"  [验证] 进度 {done}/{len(proxies)}, 可用 {working}")

    print(f"  [验证] 完成: 总{len(proxies)} 可用{working} 失败{failed}")
    return {"total": len(proxies), "working": working, "failed": failed}
