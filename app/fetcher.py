"""多源抓取引擎"""
import concurrent.futures
from typing import List, Dict
from .models import Proxy
from .database import batch_upsert
from .config import get_config
from .sources.geonode import GeonodeSource
from .sources.github_raw import GithubRawSource


def build_sources() -> Dict[str, object]:
    """根据配置构建抓取源实例"""
    cfg = get_config()
    sources_cfg = cfg.get("sources", {})
    sources = {}

    for name, scfg in sources_cfg.items():
        if not scfg.get("enabled", True):
            continue
        if name == "geonode":
            sources[name] = GeonodeSource(name, scfg)
        elif name.startswith("github_"):
            sources[name] = GithubRawSource(name, scfg)
    return sources


def fetch_all() -> dict:
    """并行抓取所有源，写入数据库，返回统计"""
    sources = build_sources()
    if not sources:
        return {"total": 0, "by_source": {}}

    all_proxies: List[Proxy] = []
    by_source = {}

    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(sources), 8)) as executor:
        futures = {executor.submit(src.fetch): name for name, src in sources.items()}
        for future in concurrent.futures.as_completed(futures):
            name = futures[future]
            try:
                proxies = future.result()
                by_source[name] = len(proxies)
                all_proxies.extend(proxies)
                print(f"  [抓取] {name}: +{len(proxies)} 条")
            except Exception as e:
                by_source[name] = f"error: {e}"
                print(f"  [抓取] {name}: 失败 {e}")

    inserted = batch_upsert(all_proxies)
    print(f"  [抓取] 总计 {len(all_proxies)} 条，写入/更新 {inserted} 条")
    return {"total": len(all_proxies), "inserted": inserted, "by_source": by_source}


def fetch_from_sources(source_names: List[str], persist: bool = False) -> List[Proxy]:
    """从指定源名列表抓取代理，返回 Proxy 列表"""
    cfg = get_config()
    sources_cfg = cfg.get("sources", {})
    sources = {}
    for name in source_names:
        scfg = sources_cfg.get(name)
        if not scfg:
            continue
        if name == "geonode":
            sources[name] = GeonodeSource(name, scfg)
        elif name.startswith("github_"):
            sources[name] = GithubRawSource(name, scfg)

    if not sources:
        return []

    all_proxies: List[Proxy] = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=min(len(sources), 8)) as executor:
        futures = {executor.submit(src.fetch): name for name, src in sources.items()}
        for future in concurrent.futures.as_completed(futures):
            try:
                all_proxies.extend(future.result())
            except Exception as e:
                print(f"  [搜索抓取] 失败: {e}")

    if persist:
        batch_upsert(all_proxies)
    return all_proxies


def list_available_sources() -> List[dict]:
    """返回所有可用源的元信息（前端配置面板用）"""
    cfg = get_config()
    sources_cfg = cfg.get("sources", {})
    result = []
    for name, scfg in sources_cfg.items():
        result.append({
            "name": name,
            "enabled": scfg.get("enabled", True),
            "protocol": scfg.get("protocol", "mixed"),
            "limit": scfg.get("limit", 0),
        })
    return result
