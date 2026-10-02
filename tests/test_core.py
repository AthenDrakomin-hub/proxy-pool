"""代理池核心单元测试"""
import sys
import os
import tempfile
import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.models import Proxy
from app.database import (
    upsert_proxy, get_proxy_by_id, list_proxies,
    get_random_proxy, get_stats, update_check_result,
    cleanup_dead, delete_proxy, get_conn,
)
import app.config as config_mod
import app.database as db_mod


@pytest.fixture(autouse=True)
def setup_test_db():
    """每个测试用独立的临时数据库"""
    old_config = config_mod._CONFIG
    tmpdb = tempfile.mktemp(suffix=".db")
    config_mod._CONFIG = {
        "database": {"path": tmpdb},
        "server": {"host": "127.0.0.1", "port": 8080},
        "sources": {},
        "checker": {"timeout": 5, "max_workers": 10},
        "scheduler": {},
    }
    # 重置数据库连接
    db_mod._conn = None
    get_conn()
    yield
    # 清理
    if db_mod._conn:
        db_mod._conn.close()
        db_mod._conn = None
    if os.path.exists(tmpdb):
        os.unlink(tmpdb)
    config_mod._CONFIG = old_config


class TestProxyModel:
    def test_proxy_url_http(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        assert p.proxy_url == "http://1.2.3.4:8080"

    def test_proxy_url_socks5(self):
        p = Proxy(ip="1.2.3.4", port=1080, protocol="socks5")
        assert p.proxy_url == "socks5://1.2.3.4:1080"

    def test_proxy_url_with_auth(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http",
                  username="user", password="pass")
        assert p.proxy_url == "http://user:pass@1.2.3.4:8080"

    def test_success_rate(self):
        p = Proxy(ip="1.2.3.4", port=80, protocol="http",
                  success_count=8, fail_count=2)
        assert p.success_rate == 0.8

    def test_success_rate_no_checks(self):
        p = Proxy(ip="1.2.3.4", port=80, protocol="http")
        assert p.success_rate == 0.0


class TestDatabase:
    def test_upsert_and_get(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http", country="US", source="test")
        pid = upsert_proxy(p)
        assert pid > 0
        fetched = get_proxy_by_id(pid)
        assert fetched.ip == "1.2.3.4"
        assert fetched.port == 8080
        assert fetched.protocol == "http"
        assert fetched.country == "US"

    def test_upsert_dedup(self):
        p1 = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        p2 = Proxy(ip="1.2.3.4", port=8080, protocol="http", source="another")
        id1 = upsert_proxy(p1)
        id2 = upsert_proxy(p2)
        assert id1 == id2  # 同一 ip:port:protocol 应去重

    def test_update_check_success(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        update_check_result(pid, success=True, latency=1.5)
        fetched = get_proxy_by_id(pid)
        assert fetched.status == "working"
        assert fetched.success_count == 1
        assert fetched.fail_streak == 0
        assert abs(fetched.latency - 1.5) < 0.01

    def test_update_check_fail_streak(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        for _ in range(5):
            update_check_result(pid, success=False, latency=0)
        fetched = get_proxy_by_id(pid)
        assert fetched.status == "dead"
        assert fetched.fail_count == 5
        assert fetched.fail_streak == 5

    def test_get_random_working(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        update_check_result(pid, success=True, latency=1.0)
        random_p = get_random_proxy()
        assert random_p is not None
        assert random_p.ip == "1.2.3.4"

    def test_get_random_filter_protocol(self):
        p1 = Proxy(ip="1.1.1.1", port=80, protocol="http")
        p2 = Proxy(ip="2.2.2.2", port=1080, protocol="socks5")
        id1 = upsert_proxy(p1)
        id2 = upsert_proxy(p2)
        update_check_result(id1, True, 1.0)
        update_check_result(id2, True, 1.0)
        http_p = get_random_proxy(protocol="http")
        assert http_p.protocol == "http"
        socks_p = get_random_proxy(protocol="socks5")
        assert socks_p.protocol == "socks5"

    def test_list_proxies_filter(self):
        p1 = Proxy(ip="1.1.1.1", port=80, protocol="http")
        p2 = Proxy(ip="2.2.2.2", port=1080, protocol="socks5")
        upsert_proxy(p1)
        upsert_proxy(p2)
        http_list = list_proxies(protocol="http")
        assert len(http_list) == 1
        assert http_list[0].protocol == "http"

    def test_stats(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        update_check_result(pid, True, 1.0)
        stats = get_stats()
        assert stats["total"] == 1
        assert stats["working"] == 1
        assert stats["by_protocol"]["http"] == 1

    def test_cleanup_dead(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        for _ in range(5):
            update_check_result(pid, False, 0)
        deleted = cleanup_dead()
        assert deleted == 1
        assert get_proxy_by_id(pid) is None

    def test_delete_proxy(self):
        p = Proxy(ip="1.2.3.4", port=8080, protocol="http")
        pid = upsert_proxy(p)
        assert delete_proxy(pid) is True
        assert get_proxy_by_id(pid) is None


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
