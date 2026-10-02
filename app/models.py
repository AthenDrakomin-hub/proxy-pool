"""数据模型"""
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Proxy:
    """代理实体"""
    ip: str
    port: int
    protocol: str           # http / https / socks4 / socks5
    username: Optional[str] = None
    password: Optional[str] = None
    country: str = ""
    source: str = ""
    status: str = "unchecked"   # unchecked / working / dead
    success_count: int = 0
    fail_count: int = 0
    fail_streak: int = 0        # 连续失败次数
    latency: float = 0.0        # 最近一次延迟(秒)
    last_checked: Optional[str] = None
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    id: Optional[int] = None

    @property
    def success_rate(self) -> float:
        """成功率"""
        total = self.success_count + self.fail_count
        if total == 0:
            return 0.0
        return self.success_count / total

    @property
    def addr(self) -> str:
        """ip:port 格式"""
        return f"{self.ip}:{self.port}"

    @property
    def proxy_url(self) -> str:
        """构造 requests 可用的代理 URL"""
        auth = ""
        if self.username and self.password:
            auth = f"{self.username}:{self.password}@"
        proto = self.protocol
        if proto == "https":
            proto = "http"  # HTTPS 代理底层仍用 http:// 连接
        return f"{proto}://{auth}{self.ip}:{self.port}"

    def to_dict(self) -> dict:
        """转为字典（API 响应用）"""
        return {
            "id": self.id,
            "ip": self.ip,
            "port": self.port,
            "protocol": self.protocol,
            "country": self.country,
            "source": self.source,
            "status": self.status,
            "success_count": self.success_count,
            "fail_count": self.fail_count,
            "success_rate": round(self.success_rate, 3),
            "latency": round(self.latency, 3),
            "last_checked": self.last_checked,
            "created_at": self.created_at,
            "proxy_url": self.proxy_url,
        }
