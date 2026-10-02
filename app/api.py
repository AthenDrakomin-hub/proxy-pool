"""FastAPI 路由"""
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import HTMLResponse
from typing import Optional
import os

from .database import (
    get_random_proxy, list_proxies, get_stats,
    get_proxy_by_id, delete_proxy, cleanup_dead,
)
from .fetcher import fetch_all
from .checker import check_all

router = APIRouter(prefix="/api")
web_router = APIRouter()  # 无前缀，挂根路径


@router.get("/stats")
def api_stats():
    """获取代理池统计信息"""
    return get_stats()


@router.get("/proxy/random")
def api_random_proxy(
    protocol: Optional[str] = Query(None, description="http/https/socks4/socks5"),
    country: Optional[str] = Query(None, description="国家代码, 如 US/CN/JP"),
    max_latency: Optional[float] = Query(None, description="最大延迟(秒)"),
):
    """随机获取一个可用代理"""
    if protocol and protocol not in ("http", "https", "socks4", "socks5"):
        raise HTTPException(status_code=400, detail="protocol 必须是 http/https/socks4/socks5")
    proxy = get_random_proxy(protocol=protocol, country=country, max_latency=max_latency)
    if not proxy:
        raise HTTPException(status_code=404, detail="没有符合条件的可用代理")
    return proxy.to_dict()


@router.get("/proxies")
def api_list_proxies(
    status: Optional[str] = Query("working", description="working/dead/unchecked"),
    protocol: Optional[str] = Query(None),
    country: Optional[str] = Query(None),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
):
    """分页查询代理列表"""
    proxies = list_proxies(status=status, protocol=protocol, country=country,
                            limit=limit, offset=offset)
    return {"total": len(proxies), "items": [p.to_dict() for p in proxies]}


@router.get("/proxy/{proxy_id}")
def api_get_proxy(proxy_id: int):
    """获取单个代理详情"""
    proxy = get_proxy_by_id(proxy_id)
    if not proxy:
        raise HTTPException(status_code=404, detail="代理不存在")
    return proxy.to_dict()


@router.delete("/proxy/{proxy_id}")
def api_delete_proxy(proxy_id: int):
    """删除代理"""
    if not delete_proxy(proxy_id):
        raise HTTPException(status_code=404, detail="代理不存在")
    return {"ok": True, "id": proxy_id}


@router.post("/fetch")
def api_fetch():
    """手动触发抓取"""
    result = fetch_all()
    return {"ok": True, **result}


@router.post("/check")
def api_check():
    """手动触发全量验证"""
    result = check_all()
    return {"ok": True, **result}


@router.post("/cleanup")
def api_cleanup():
    """手动清理死代理"""
    deleted = cleanup_dead()
    return {"ok": True, "deleted": deleted}


# ========== Web 面板 ==========

@web_router.get("/", response_class=HTMLResponse)
def web_panel():
    """极简 Web 管理面板"""
    html_path = os.path.join(os.path.dirname(__file__), "..", "web", "index.html")
    with open(html_path, "r", encoding="utf-8") as f:
        return f.read()
