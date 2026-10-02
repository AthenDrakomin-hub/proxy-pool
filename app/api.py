"""FastAPI 路由"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from pydantic import BaseModel
from typing import Optional, List
import os
import json
import csv
import io

from .database import (
    get_random_proxy, list_proxies, get_stats,
    get_proxy_by_id, delete_proxy, cleanup_dead,
    upsert_proxy, update_check_result,
)
from .fetcher import fetch_all, fetch_from_sources, list_available_sources
from .checker import check_all, test_single
from .config import get_config
from .performance import calculate_score, estimate_ttl

router = APIRouter(prefix="/api")
web_router = APIRouter()


class SearchRequest(BaseModel):
    sources: List[str] = []
    countries: List[str] = []
    protocol: Optional[str] = None
    limit: int = 5


class ExportRequest(BaseModel):
    ids: List[int] = []
    format: str = "txt"


@router.get("/stats")
def api_stats():
    return get_stats()


@router.get("/proxy/random")
def api_random_proxy(
    protocol: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    max_latency: Optional[float] = Query(None),
):
    if protocol and protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(status_code=400, detail="protocol 必须是 http/https/socks4/socks5")
    proxy = get_random_proxy(protocol=protocol, country=country, max_latency=max_latency)
    if not proxy:
        raise HTTPException(status_code=404, detail="没有符合条件的可用代理")
    return proxy.to_dict()


@router.get("/proxies")
def api_list_proxies(
    status: Optional[str] = Query("working"),
    protocol: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    proxies = list_proxies(status=status, protocol=protocol, country=country, limit=limit, offset=offset)
    return {"total": len(proxies), "items": [p.to_dict() for p in proxies]}


@router.get("/proxy/{proxy_id}")
def api_get_proxy(proxy_id: int):
    proxy = get_proxy_by_id(proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
    return proxy.to_dict()


@router.delete("/proxy/{proxy_id}")
def api_delete_proxy(proxy_id: int):
    if not delete_proxy(proxy_id):
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"ok": True, "id": proxy_id}


@router.post("/fetch")
def api_fetch():
    result = fetch_all()
    return {"ok": True, **result}


@router.post("/check")
def api_check():
    result = check_all()
    return {"ok": True, **result}


@router.post("/cleanup")
def api_cleanup():
    deleted = cleanup_dead()
    return {"ok": True, "deleted": deleted}


# ========== 智能搜索 ==========

@router.post("/search")
def api_search(req: SearchRequest):
    if not req.sources:
        raise HTTPException(status_code=400, detail="至少选择一个代理源")
    if req.limit < 1 or req.limit > 20:
        raise HTTPException(status_code=400, detail="数量必须在 1-20 之间")
    if req.protocol and req.protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(status_code=400, detail="protocol 必须是 http/https/socks4/socks5")

    raw_proxies = fetch_from_sources(req.sources, persist=False)
    filtered = []
    for p in raw_proxies:
        if req.protocol and p.protocol != req.protocol:
            continue
        if req.countries and p.country and p.country not in req.countries:
            continue
        filtered.append(p)

    if not filtered:
        return {"total": 0, "items": [], "message": "没有符合条件的代理"}

    cfg = get_config()
    checker_cfg = cfg.get("checker", {})
    timeout = checker_cfg.get("timeout", 8)
    max_workers = checker_cfg.get("max_workers", 50)
    test_url_http = checker_cfg.get("test_url_http", "http://httpbin.org/ip")
    test_url_https = checker_cfg.get("test_url_https", "https://httpbin.org/ip")

    to_test = filtered[:300]
    working = []
    import concurrent.futures
    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(test_single, p, timeout, test_url_http, test_url_https): p for p in to_test}
        for future in concurrent.futures.as_completed(futures):
            proxy, success, latency = future.result()
            if success:
                proxy.latency = latency
                proxy.success_count = 1
                working.append(proxy)

    if not working:
        return {"total": 0, "items": [], "message": "所有代理均验证失败，请更换条件重试"}

    scored = []
    for p in working:
        perf = calculate_score(p.latency, p.success_rate, p.success_count, p.fail_count)
        ttl = estimate_ttl(perf["score"], p.latency)
        pid = upsert_proxy(p)
        update_check_result(pid, True, p.latency)
        item = p.to_dict()
        item["score"] = perf["score"]
        item["grade"] = perf["grade"]
        item["ttl"] = ttl
        item["id"] = pid
        scored.append(item)

    scored.sort(key=lambda x: x["score"], reverse=True)
    top = scored[:req.limit]
    return {"total": len(top), "items": top, "tested": len(to_test), "working": len(working)}


# ========== 健康检查 ==========

@router.get("/proxy/{proxy_id}/health")
def api_proxy_health(proxy_id: int):
    proxy = get_proxy_by_id(proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
    cfg = get_config()
    checker_cfg = cfg.get("checker", {})
    timeout = checker_cfg.get("timeout", 8)
    test_url_http = checker_cfg.get("test_url_http", "http://httpbin.org/ip")
    test_url_https = checker_cfg.get("test_url_https", "https://httpbin.org/ip")
    _, success, latency = test_single(proxy, timeout, test_url_http, test_url_https)
    update_check_result(proxy_id, success, latency)
    proxy = get_proxy_by_id(proxy_id)
    perf = calculate_score(proxy.latency, proxy.success_rate, proxy.success_count, proxy.fail_count)
    ttl = estimate_ttl(perf["score"], proxy.latency) if success else 0
    return {
        "id": proxy_id, "status": proxy.status, "alive": success,
        "latency": round(latency, 3) if success else 0,
        "score": perf["score"], "grade": perf["grade"], "ttl": ttl,
        "success_count": proxy.success_count, "fail_count": proxy.fail_count,
    }


# ========== 导出 ==========

@router.post("/export")
def api_export(req: ExportRequest):
    if req.format not in ("txt", "json", "csv"):
        raise HTTPException(status_code=400, detail="format 必须是 txt/json/csv")
    if req.ids:
        proxies = [get_proxy_by_id(pid) for pid in req.ids]
        proxies = [p for p in proxies if p]
    else:
        proxies = list_proxies(status="working", limit=500)
    if not proxies:
        raise HTTPException(status_code=404, detail="没有可导出的代理")
    if req.format == "txt":
        lines = []
        for p in proxies:
            auth = f":{p.username}:{p.password}" if p.username and p.password else ""
            lines.append(f"{p.ip}:{p.port}{auth}")
        return PlainTextResponse("\n".join(lines), media_type="text/plain")
    elif req.format == "json":
        data = [p.to_dict() for p in proxies]
        return PlainTextResponse(json.dumps(data, indent=2, ensure_ascii=False), media_type="application/json")
    elif req.format == "csv":
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["ip", "port", "protocol", "country", "source", "latency", "success_rate", "status"])
        for p in proxies:
            writer.writerow([p.ip, p.port, p.protocol, p.country, p.source, round(p.latency, 3), round(p.success_rate, 3), p.status])
        return PlainTextResponse(output.getvalue(), media_type="text/csv")


# ========== 元信息 ==========

@router.get("/meta")
def api_meta():
    sources = list_available_sources()
    from .database import get_conn
    with get_conn() as conn:
        cur = conn.cursor()
        cur.execute("SELECT DISTINCT country FROM proxies WHERE country != '' ORDER BY country")
        countries = [row[0] for row in cur.fetchall()]
    common = ["US", "CN", "JP", "KR", "SG", "DE", "FR", "GB", "RU", "BR", "IN", "ID", "VN", "TH", "PH", "CA", "AU", "NL", "SE", "TR"]
    for c in common:
        if c not in countries:
            countries.append(c)
    countries.sort()
    return {"sources": sources, "protocols": ["http", "https", "socks4", "socks5"], "countries": countries}


# ========== Web 面板 ==========

@web_router.get("/", response_class=HTMLResponse)
def web_panel():
    html_path = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
