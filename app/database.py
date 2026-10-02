"""SQLite 数据库封装"""
import sqlite3
import threading
from datetime import datetime
from typing import List, Optional
from contextlib import contextmanager

from .models import Proxy
from .config import get_config

_lock = threading.Lock()
_conn: Optional[sqlite3.Connection] = None


def get_conn() -> sqlite3.Connection:
    """获取数据库连接（单例，线程安全）"""
    global _conn
    if _conn is None:
        cfg = get_config()
        db_path = cfg["database"]["path"]
        _conn = sqlite3.connect(db_path, check_same_thread=False)
        _conn.row_factory = sqlite3.Row
        _conn.execute("PRAGMA journal_mode=WAL")
        _init_tables()
    return _conn


@contextmanager
def cursor():
    """线程安全的游标上下文"""
    with _lock:
        conn = get_conn()
        cur = conn.cursor()
        try:
            yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            cur.close()


def _init_tables():
    """初始化数据库表"""
    with _lock:
        conn = get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS proxies (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ip TEXT NOT NULL,
                port INTEGER NOT NULL,
                protocol TEXT NOT NULL,
                username TEXT,
                password TEXT,
                country TEXT DEFAULT '',
                source TEXT DEFAULT '',
                status TEXT DEFAULT 'unchecked',
                success_count INTEGER DEFAULT 0,
                fail_count INTEGER DEFAULT 0,
                fail_streak INTEGER DEFAULT 0,
                latency REAL DEFAULT 0,
                last_checked TEXT,
                created_at TEXT DEFAULT (datetime('now','localtime')),
                UNIQUE(ip, port, protocol)
            );
            CREATE INDEX IF NOT EXISTS idx_proxies_status ON proxies(status);
            CREATE INDEX IF NOT EXISTS idx_proxies_protocol ON proxies(protocol);
            CREATE INDEX IF NOT EXISTS idx_proxies_country ON proxies(country);
            CREATE INDEX IF NOT EXISTS idx_proxies_latency ON proxies(latency);
        """)
        conn.commit()


def _row_to_proxy(row: sqlite3.Row) -> Proxy:
    """Row 转 Proxy 对象"""
    return Proxy(
        id=row["id"],
        ip=row["ip"],
        port=row["port"],
        protocol=row["protocol"],
        username=row["username"],
        password=row["password"],
        country=row["country"] or "",
        source=row["source"] or "",
        status=row["status"],
        success_count=row["success_count"],
        fail_count=row["fail_count"],
        fail_streak=row["fail_streak"],
        latency=row["latency"] or 0.0,
        last_checked=row["last_checked"],
        created_at=row["created_at"],
    )


def upsert_proxy(proxy: Proxy) -> int:
    """插入或更新代理（按 ip:port:protocol 去重），返回 id"""
    with cursor() as cur:
        cur.execute("""
            INSERT INTO proxies (ip, port, protocol, username, password, country, source)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(ip, port, protocol) DO UPDATE SET
                source=excluded.source,
                country=COALESCE(NULLIF(excluded.country,''), proxies.country)
            RETURNING id
        """, (proxy.ip, proxy.port, proxy.protocol,
              proxy.username, proxy.password, proxy.country, proxy.source))
        row = cur.fetchone()
        return row[0] if row else 0


def batch_upsert(proxies: List[Proxy]) -> int:
    """批量插入，返回新增数量"""
    count = 0
    for p in proxies:
        upsert_proxy(p)
        count += 1
    return count


def update_check_result(proxy_id: int, success: bool, latency: float):
    """更新验证结果"""
    now = datetime.now().isoformat()
    with cursor() as cur:
        if success:
            cur.execute("""
                UPDATE proxies SET
                    status='working',
                    success_count=success_count+1,
                    fail_streak=0,
                    latency=?,
                    last_checked=?
                WHERE id=?
            """, (latency, now, proxy_id))
        else:
            cur.execute("""
                UPDATE proxies SET
                    fail_count=fail_count+1,
                    fail_streak=fail_streak+1,
                    last_checked=?,
                    status=CASE
                        WHEN fail_streak+1 >= 5 THEN 'dead'
                        ELSE status
                    END
                WHERE id=?
            """, (now, proxy_id))


def get_proxy_by_id(proxy_id: int) -> Optional[Proxy]:
    with cursor() as cur:
        cur.execute("SELECT * FROM proxies WHERE id=?", (proxy_id,))
        row = cur.fetchone()
        return _row_to_proxy(row) if row else None


def get_random_proxy(protocol: str = None, country: str = None,
                     max_latency: float = None) -> Optional[Proxy]:
    """随机获取一个可用代理"""
    sql = "SELECT * FROM proxies WHERE status='working'"
    params = []
    if protocol:
        sql += " AND protocol=?"
        params.append(protocol)
    if country:
        sql += " AND country=?"
        params.append(country)
    if max_latency:
        sql += " AND latency<=?"
        params.append(max_latency)
    sql += " ORDER BY RANDOM() LIMIT 1"
    with cursor() as cur:
        cur.execute(sql, params)
        row = cur.fetchone()
        return _row_to_proxy(row) if row else None


def list_proxies(status: str = None, protocol: str = None,
                 country: str = None, limit: int = 100,
                 offset: int = 0) -> List[Proxy]:
    """分页查询代理列表"""
    sql = "SELECT * FROM proxies WHERE 1=1"
    params = []
    if status:
        sql += " AND status=?"
        params.append(status)
    if protocol:
        sql += " AND protocol=?"
        params.append(protocol)
    if country:
        sql += " AND country=?"
        params.append(country)
    sql += " ORDER BY latency ASC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    with cursor() as cur:
        cur.execute(sql, params)
        return [_row_to_proxy(row) for row in cur.fetchall()]


def get_all_for_check() -> List[Proxy]:
    """获取所有需要验证的代理（非 dead 状态）"""
    with cursor() as cur:
        cur.execute("SELECT * FROM proxies WHERE status != 'dead'")
        return [_row_to_proxy(row) for row in cur.fetchall()]


def get_stats() -> dict:
    """获取统计信息"""
    with cursor() as cur:
        cur.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN status='working' THEN 1 ELSE 0 END) as working,
                SUM(CASE WHEN status='dead' THEN 1 ELSE 0 END) as dead,
                SUM(CASE WHEN status='unchecked' THEN 1 ELSE 0 END) as unchecked,
                AVG(CASE WHEN status='working' THEN latency END) as avg_latency
            FROM proxies
        """)
        row = cur.fetchone()
        cur.execute("""
            SELECT protocol, COUNT(*) as cnt
            FROM proxies WHERE status='working'
            GROUP BY protocol
        """)
        by_protocol = {r["protocol"]: r["cnt"] for r in cur.fetchall()}
        cur.execute("""
            SELECT country, COUNT(*) as cnt
            FROM proxies WHERE status='working' AND country != ''
            GROUP BY country ORDER BY cnt DESC LIMIT 10
        """)
        by_country = {r["country"]: r["cnt"] for r in cur.fetchall()}
        return {
            "total": row["total"] or 0,
            "working": row["working"] or 0,
            "dead": row["dead"] or 0,
            "unchecked": row["unchecked"] or 0,
            "avg_latency": round(row["avg_latency"] or 0, 3),
            "by_protocol": by_protocol,
            "top_countries": by_country,
        }


def cleanup_dead():
    """清理 dead 状态的代理（删除）"""
    with cursor() as cur:
        cur.execute("DELETE FROM proxies WHERE status='dead'")
        return cur.rowcount


def delete_proxy(proxy_id: int) -> bool:
    with cursor() as cur:
        cur.execute("DELETE FROM proxies WHERE id=?", (proxy_id,))
        return cur.rowcount > 0
