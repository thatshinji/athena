"""Athena 配置模块 — 从 .env 和环境变量读取配置"""

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# 加载项目根目录 .env
_project_root = Path(__file__).resolve().parent.parent
load_dotenv(_project_root / ".env")


@dataclass
class Settings:
    """Athena 全局配置"""

    # Longbridge 行情
    longbridge_app_key: str = field(
        default_factory=lambda: os.getenv("LONGBRIDGE_APP_KEY", "")
    )
    longbridge_app_secret: str = field(
        default_factory=lambda: os.getenv("LONGBRIDGE_APP_SECRET", "")
    )
    longbridge_access_token: str = field(
        default_factory=lambda: os.getenv("LONGBRIDGE_ACCESS_TOKEN", "")
    )
    longbridge_http_url: str = field(
        default_factory=lambda: os.getenv(
            "LONGBRIDGE_HTTP_URL", "https://openapi.longbridge.com"
        )
    )

    # DeepSeek LLM
    deepseek_api_key: str = field(
        default_factory=lambda: os.getenv("DEEPSEEK_API_KEY", "")
    )
    deepseek_model: str = "deepseek-v4-flash"
    deepseek_base_url: str = "https://api.deepseek.com"

    # 数据
    default_days: int = 250  # 默认拉取 250 个交易日
    default_horizon_months: str = "3-6m"

    # Quiver Quantitative (国会交易/内幕)
    quiver_api_key: str = field(
        default_factory=lambda: os.getenv("QUIVER_API_KEY", "")
    )

    @property
    def longbridge_configured(self) -> bool:
        return bool(self.longbridge_app_key and self.longbridge_app_secret)

    @property
    def deepseek_configured(self) -> bool:
        return bool(self.deepseek_api_key)

    @property
    def quiver_configured(self) -> bool:
        return bool(self.quiver_api_key)


# 全局单例
settings = Settings()
