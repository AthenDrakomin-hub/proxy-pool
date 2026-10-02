"""GitHub Raw 文本抓取源（通用）"""
import re
import requests
from typing import List
from .base import BaseSource
from ..models import Proxy


class GithubRawSource(BaseSource):
    """从 GitHub raw 文本文件抓取代理（每行 ip:port 或 ip:port:user:pass）"""

    HEADERS = {"User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36"}
    PATTERN = re.compile(
        r'^(\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}):(\d{1,5})(?::(.+):(.+))?$'
    )

    def fetch(self) -> List[Proxy]:
        proxies = []
        try:
            r = requests.get(self.config["url"], timeout=20, headers=self.HEADERS)
            r.raise_for_status()
            protocol = self.config.get("protocol", "http")
            limit = self.config.get("limit", 200)
            lines = r.text.strip().split("\n")[:limit]
            for line in lines:
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                m = self.PATTERN.match(line)
                if not m:
                    continue
                ip, port = m.group(1), int(m.group(2))
                user, pwd = m.group(3), m.group(4)
                proxies.append(Proxy(
                    ip=ip,
                    port=port,
                    protocol=protocol,
                    username=user,
                    password=pwd,
                    source=self.name,
                ))
        except Exception as e:
            print(f"[GithubRaw:{self.name}] 抓取失败: {type(e).__name__}: {e}")
        return proxies
