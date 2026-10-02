"""Geonode API 抓取源"""
import requests
from typing import List
from .base import BaseSource
from ..models import Proxy


class GeonodeSource(BaseSource):
    """从 Geonode 免费代理 API 抓取"""

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}

    def fetch(self) -> List[Proxy]:
        proxies = []
        try:
            url = self.config["url"].format(limit=self.config.get("limit", 300))
            r = requests.get(url, timeout=20, headers=self.HEADERS)
            r.raise_for_status()
            data = r.json().get("data", [])
            for item in data:
                ip = item.get("ip")
                port = item.get("port")
                protocols = item.get("protocols", [])
                country = item.get("country", "")
                if not ip or not port:
                    continue
                for proto in protocols:
                    proto = proto.lower()
                    if proto in ("http", "https", "socks4", "socks5"):
                        proxies.append(Proxy(
                            ip=ip,
                            port=int(port),
                            protocol=proto,
                            country=country,
                            source=self.name,
                        ))
        except Exception as e:
            print(f"[Geonode] 抓取失败: {type(e).__name__}: {e}")
        return proxies
