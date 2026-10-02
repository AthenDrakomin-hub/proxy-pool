# Proxy Pool — 智能代理池系统

自建代理池：多源抓取 → 多线程验证 → 性能评分 → 智能精选 → 实时监控 → 一键导出。

零外部依赖（SQLite 存储），开箱即用。

---

## 功能特性

| 模块 | 说明 |
|------|------|
| **多源抓取** | 插件化抓取源，支持 Geonode API + GitHub Raw 列表，并行抓取 |
| **批量验证** | 50 并发线程池，HTTP/HTTPS 双目标交叉验证，8 秒超时 |
| **健康评分** | 延迟(40%) + 成功率(30%) + 稳定性(30%) → S/A/B/C/D 五级 + 百分制 |
| **自动淘汰** | 连续失败 5 次自动标记 dead，定时清理 |
| **智能精选** | 自定义源/国家/协议 → 一键搜索 → 评分排序 → Top N 展示 |
| **实时监控** | 每 15 秒健康轮询，倒计时进度条，失效自动预警+移除补位 |
| **一键导出** | TXT / JSON / CSV 三种格式，含完整元数据 |
| **REST API** | 完整 RESTful 接口，支持过滤、分页、随机获取 |
| **定时调度** | APScheduler 后台任务：抓取 30min / 验证 10min / 清理 6h |
| **Web 面板** | 暗色主题管理面板，配置搜索 + 代理卡片 + 实时监控 |

---

## 技术栈

- **Python 3.10+**
- **FastAPI** — Web 框架 + REST API
- **SQLite** — 零配置存储（标准库 sqlite3）
- **APScheduler** — 定时任务调度
- **requests + pysocks** — HTTP/SOCKS 代理验证
- **原生 HTML/JS** — 前端面板（无构建步骤）

---

## 快速开始

### 1. 克隆项目

```bash
git clone https://github.com/AthenDrakomin-hub/proxy-pool.git
cd proxy-pool
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

依赖清单：
```
fastapi>=0.104.0
uvicorn>=0.24.0
requests>=2.31.0
pysocks>=1.7.1
apscheduler>=3.10.0
pyyaml>=6.0
```

### 3. 启动服务

```bash
# 完整模式（启动定时调度：抓取/验证/清理）
python main.py

# 手动模式（不启动定时任务，仅 API + Web）
python main.py --no-scheduler
```

启动后访问：
- **Web 面板**：http://localhost:8090/
- **API 文档**：http://localhost:8090/docs（Swagger UI）
- **统计信息**：http://localhost:8090/api/stats

### 4. 首次使用

1. 打开 Web 面板 → 勾选代理源 → 选择协议/国家 → 点「开始搜索」
2. 等待 10-30 秒（抓取+验证），系统展示评分最高的 5 个代理
3. 点「📋 复制」获取代理链接，或导出 TXT/JSON/CSV
4. 卡片实时显示倒计时，失效时自动预警并移除

---

## 项目结构

```
proxy-pool/
├── main.py                  # 入口：启动 FastAPI + 定时调度
├── config.yaml              # 全局配置（源/验证/调度/端口）
├── requirements.txt         # Python 依赖
├── README.md                # 本文档
├── .gitignore               # Git 忽略规则
├── app/
│   ├── __init__.py
│   ├── config.py            # 配置加载（YAML → dict）
│   ├── models.py            # Proxy 数据模型 + to_dict()
│   ├── database.py          # SQLite 操作（建表/CRUD/批量/统计）
│   ├── fetcher.py           # 多源抓取引擎（并行/自定义源）
│   ├── checker.py           # 代理验证器（单条/批量/并发）
│   ├── performance.py       # 性能评分引擎 + TTL 预估
│   ├── scheduler.py         # APScheduler 定时任务
│   ├── api.py               # FastAPI 路由（全部 REST 端点）
│   └── sources/
│       ├── __init__.py
│       ├── base.py          # 抓取源基类（抽象接口）
│       ├── geonode.py       # Geonode API 源
│       └── github_raw.py    # GitHub Raw 文本源
├── web/
│   └── index.html           # Web 管理面板（单文件，原生 JS）
└── tests/
    └── test_core.py         # 单元测试（15 用例）
```

---

## 配置说明（config.yaml）

```yaml
# 服务端口
port: 8090

# 数据库路径
database:
  path: proxy_pool.db

# 代理源配置（插件化，可增删）
sources:
  geonode:
    enabled: true
    url: "https://proxylist.geonode.com/api/proxy-list?limit=500&page=1&sort_by=lastChecked&sort_type=desc"
    protocol: mixed          # mixed/http/https/socks4/socks5
    limit: 500

  github_proxy_free_http:
    enabled: true
    url: "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/http.txt"
    protocol: http

  github_proxy_free_socks5:
    enabled: true
    url: "https://raw.githubusercontent.com/proxy-free/free-proxy-list/master/socks5.txt"
    protocol: socks5

  github_dinoz0rg_http:
    enabled: true
    url: "https://raw.githubusercontent.com/dinoz0rg/proxy-list/master/http.txt"
    protocol: http

  github_dinoz0rg_socks5:
    enabled: true
    url: "https://raw.githubusercontent.com/dinoz0rg/proxy-list/master/socks5.txt"
    protocol: socks5

# 验证器配置
checker:
  timeout: 8                 # 单条验证超时（秒）
  max_workers: 50            # 并发线程数
  test_url_http: "http://httpbin.org/ip"
  test_url_https: "https://httpbin.org/ip"
  max_fail_streak: 5         # 连续失败 N 次标记 dead

# 定时调度
scheduler:
  fetch_interval: 30         # 抓取间隔（分钟）
  check_interval: 10         # 验证间隔（分钟）
  cleanup_interval: 360      # 清理间隔（分钟）
```

---

## API 文档

### 基础信息

- Base URL: `http://localhost:8090/api`
- 所有响应为 JSON（导出端点除外）

### 端点列表

#### 1. 统计信息

```
GET /api/stats
```

返回代理池整体统计（总数/可用/死亡/按协议分布/按国家分布）。

#### 2. 随机获取代理

```
GET /api/proxy/random?protocol=http&country=US&max_latency=2.0
```

| 参数 | 类型 | 说明 |
|------|------|------|
| protocol | string | 过滤协议：http/https/socks4/socks5 |
| country | string | 过滤国家代码，如 US/JP/CN |
| max_latency | float | 最大延迟（秒） |

#### 3. 分页查询代理

```
GET /api/proxies?status=working&protocol=http&limit=50&offset=0
```

| 参数 | 类型 | 默认 | 说明 |
|------|------|------|------|
| status | string | working | working/dead/unchecked |
| protocol | string | - | 协议过滤 |
| country | string | - | 国家过滤 |
| limit | int | 100 | 1-500 |
| offset | int | 0 | 偏移量 |

#### 4. 代理详情

```
GET /api/proxy/{id}
```

#### 5. 删除代理

```
DELETE /api/proxy/{id}
```

#### 6. 手动触发抓取

```
POST /api/fetch
```

并行抓取所有已启用源，写入数据库。

#### 7. 手动触发验证

```
POST /api/check
```

批量验证池中所有代理。

#### 8. 清理死代理

```
POST /api/cleanup
```

删除所有 status=dead 的代理。

#### 9. 智能搜索（核心）

```
POST /api/search
Content-Type: application/json

{
  "sources": ["geonode", "github_dinoz0rg_http"],
  "countries": ["US", "JP"],
  "protocol": "http",
  "limit": 5
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| sources | string[] | 是 | 抓取源名称列表（见 /api/meta） |
| countries | string[] | 否 | 国家代码过滤，空=全部 |
| protocol | string | 否 | http/https/socks4/socks5，null=全部 |
| limit | int | 否 | 返回数量 1-20，默认 5 |

**响应**：
```json
{
  "total": 3,
  "tested": 290,
  "working": 55,
  "items": [
    {
      "id": 16,
      "ip": "172.236.242.244",
      "port": 3128,
      "protocol": "http",
      "country": "US",
      "latency": 0.441,
      "score": 91.9,
      "grade": "S",
      "ttl": 773,
      "proxy_url": "http://172.236.242.244:3128",
      "success_count": 1,
      "fail_count": 0
    }
  ]
}
```

流程：抓取指定源 → 按国家/协议过滤 → 最多验证 300 条 → 评分排序 → 返回 Top N。

#### 10. 单次健康检查

```
GET /api/proxy/{id}/health
```

实时验证该代理，返回最新状态 + 评分 + TTL。前端每 15 秒调用一次。

**响应**：
```json
{
  "id": 16,
  "status": "working",
  "alive": true,
  "latency": 0.505,
  "score": 89.6,
  "grade": "S",
  "ttl": 763,
  "success_count": 2,
  "fail_count": 0
}
```

#### 11. 导出代理

```
POST /api/export
Content-Type: application/json

{
  "ids": [16, 29, 46],
  "format": "txt"
}
```

| 字段 | 类型 | 说明 |
|------|------|------|
| ids | int[] | 要导出的代理 ID，空=导出全部可用 |
| format | string | txt / json / csv |

- **TXT**：每行 `ip:port`（含认证时追加 `:user:pass`）
- **JSON**：完整代理对象数组
- **CSV**：ip,port,protocol,country,source,latency,success_rate,status

#### 12. 元信息（前端配置用）

```
GET /api/meta
```

返回可用源列表 + 支持协议 + 国家列表。

```json
{
  "sources": [{"name": "geonode", "enabled": true, "protocol": "mixed", "limit": 500}],
  "protocols": ["http", "https", "socks4", "socks5"],
  "countries": ["US", "CN", "JP", "KR", ...]
}
```

---

## 开发指南

### 新增抓取源

1. 在 `app/sources/` 下创建新文件，如 `my_source.py`：

```python
from .base import BaseSource
from ..models import Proxy

class MySource(BaseSource):
    def fetch(self):
        """返回 List[Proxy]"""
        # 1. 请求你的 API / 页面
        # 2. 解析为 Proxy 对象列表
        # 3. 返回
        proxies = []
        # ... 你的抓取逻辑 ...
        return proxies
```

2. 在 `app/fetcher.py` 的 `build_sources()` 和 `fetch_from_sources()` 中注册：

```python
from .sources.my_source import MySource

# 在 build_sources() 中添加：
if name == "my_source":
    sources[name] = MySource(name, scfg)
```

3. 在 `config.yaml` 中添加配置：

```yaml
sources:
  my_source:
    enabled: true
    url: "https://your-api.com/proxies"
    protocol: mixed
```

### 数据模型（Proxy）

```python
Proxy(
    id: int              # 自增主键
    ip: str              # IP 地址
    port: int            # 端口
    protocol: str        # http/https/socks4/socks5
    country: str         # 国家代码（可选）
    username: str        # 认证用户名（可选）
    password: str        # 认证密码（可选）
    source: str          # 来源名称
    status: str          # unchecked/working/dead
    latency: float       # 最近验证延迟（秒）
    success_count: int   # 成功次数
    fail_count: int      # 失败次数
    fail_streak: int     # 连续失败次数
    last_check: str      # 最后验证时间 ISO8601
    created_at: str      # 创建时间 ISO8601
)
```

`proxy.to_dict()` 返回完整字典，含计算字段 `success_rate` 和 `proxy_url`。

### 性能评分算法

```
延迟分(0-100):
  <0.5s → 100 | <1s → 92 | <2s → 80 | <3s → 65 | <5s → 48 | <8s → 30 | else → 12

成功率分(0-100): success_rate × 100

稳定性分(0-100):
  无记录 → 50 | 零失败 → min(70 + success_count×3, 100) | 有失败 → (success/total)×80 + 20

综合分 = 延迟×0.40 + 成功率×0.30 + 稳定性×0.30

等级: S≥88 | A≥75 | B≥60 | C≥45 | D<45

TTL预估 = 300 + (score/10)×45 + 延迟奖励(<2s:+60, <5s:+30)，上限 1800s
```

### 运行测试

```bash
# 安装测试依赖
pip install pytest pytest-asyncio

# 运行全部测试
python -m pytest tests/ -v

# 运行单个文件
python -m pytest tests/test_core.py -v
```

测试覆盖：模型序列化、数据库 CRUD、配置加载、评分计算、TTL 预估、抓取源解析等 15 个用例。

---

## 部署方式

### 本地开发

```bash
python main.py --no-scheduler
```

### 生产部署（systemd）

创建 `/etc/systemd/system/proxy-pool.service`：

```ini
[Unit]
Description=Proxy Pool Service
After=network.target

[Service]
Type=simple
User=www-data
WorkingDirectory=/opt/proxy-pool
ExecStart=/usr/bin/python3 /opt/proxy-pool/main.py
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl daemon-reload
sudo systemctl enable proxy-pool
sudo systemctl start proxy-pool
sudo systemctl status proxy-pool
```

### Docker（可选）

```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
EXPOSE 8090
CMD ["python", "main.py"]
```

```bash
docker build -t proxy-pool .
docker run -d -p 8090:8090 -v $(pwd)/data:/app/data proxy-pool
```

### Nginx 反向代理（可选）

```nginx
server {
    listen 80;
    server_name proxy.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:8090;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 120s;
    }
}
```

---

## 常见问题

**Q: 启动后搜不到代理？**
A: 免费代理源稳定性差，建议多选几个源同时搜索。HTTP 协议的可用率通常最高（~40%），SOCKS5 次之。

**Q: 验证很慢？**
A: 调整 `config.yaml` 中 `checker.max_workers`（默认 50）和 `timeout`（默认 8s）。搜索时最多验证 300 条，50 并发约需 30-60 秒。

**Q: 数据库文件越来越大？**
A: 调用 `POST /api/cleanup` 清理死代理，或直接删除 `proxy_pool.db` 重新开始（会丢失历史数据）。

**Q: 如何添加需要认证的代理？**
A: 代理源返回的 Proxy 对象设置 `username` 和 `password` 字段即可，导出和复制时会自动包含认证信息。

**Q: 前端页面打不开？**
A: 确认服务已启动（`python main.py`），端口 8090 未被占用，防火墙已放行。API 文档地址 `http://localhost:8090/docs` 可用于排查。

---

## License

MIT
