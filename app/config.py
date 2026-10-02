"""配置加载模块"""
import os
import yaml
from pathlib import Path

_CONFIG = None

def load_config(config_path: str = None) -> dict:
    """加载 YAML 配置，单例模式"""
    global _CONFIG
    if _CONFIG is not None:
        return _CONFIG

    if config_path is None:
        config_path = os.environ.get(
            "PROXY_POOL_CONFIG",
            str(Path(__file__).parent.parent / "config.yaml")
        )

    with open(config_path, "r", encoding="utf-8") as f:
        _CONFIG = yaml.safe_load(f)

    return _CONFIG

def get_config() -> dict:
    """获取已加载的配置"""
    if _CONFIG is None:
        return load_config()
    return _CONFIG
