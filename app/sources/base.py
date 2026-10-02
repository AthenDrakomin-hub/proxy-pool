"""抓取源基类"""
from abc import ABC, abstractmethod
from typing import List
from ..models import Proxy


class BaseSource(ABC):
    """所有抓取源必须实现此接口"""

    def __init__(self, name: str, config: dict):
        self.name = name
        self.config = config

    @abstractmethod
    def fetch(self) -> List[Proxy]:
        """抓取代理列表"""
        pass
