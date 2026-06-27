"""
广告位管理模块
职责：
1. 从远程 API 拉取广告数据（JSON 格式）
2. 本地 SQLite 缓存广告内容
3. 提供简单的内容轮播逻辑
4. 所有网络操作失败时静默降级，不影响主功能
"""
import json
import time
import threading
from datetime import datetime, timedelta
from pathlib import Path

from src.config import AppConfig
from src.database import get_db


class AdManager:
    """
    广告管理器 (单例)
    在独立线程中定期从配置的 API URL 拉取广告内容。
    """

    _instance = None
    _lock = threading.Lock()

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._config = AppConfig.load()
        self._current_ad = None
        self._fetch_thread: threading.Thread | None = None
        self._running = False

    @property
    def is_enabled(self) -> bool:
        return self._config.ad_enabled and bool(self._config.ad_api_url)

    def start(self):
        """启动广告拉取（如果启用）"""
        if not self.is_enabled:
            return
        self._running = True
        self._fetch_thread = threading.Thread(target=self._fetch_loop, daemon=True)
        self._fetch_thread.start()

    def stop(self):
        """停止广告拉取"""
        self._running = False

    def refresh_config(self):
        """配置变更后刷新"""
        self.stop()
        self._config = AppConfig.load()
        self.start()

    def get_current_ad(self) -> dict | None:
        """获取当前广告内容"""
        if not self.is_enabled:
            return None
        return self._current_ad

    def _fetch_loop(self):
        """后台拉取循环"""
        interval = max(self._config.ad_refresh_minutes, 5) * 60
        while self._running:
            self._try_fetch()
            # 分段等待以响应停止信号
            for _ in range(int(interval)):
                if not self._running:
                    return
                time.sleep(1)

    def _try_fetch(self):
        """尝试从远程 API 拉取广告"""
        if not self._config.ad_api_url:
            return
        try:
            import urllib.request

            req = urllib.request.Request(
                self._config.ad_api_url,
                headers={
                    "Authorization": f"Bearer {self._config.ad_api_key}",
                    "Content-Type": "application/json",
                    "User-Agent": "BaibaoBOX/1.0",
                },
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                data = json.loads(resp.read().decode("utf-8"))
                ads = data.get("ads", [])
                if ads:
                    self._current_ad = ads[0]
                    self._cache_ad(ads[0])
        except Exception:
            # 静默失败，使用缓存
            self._current_ad = self._load_cached_ad()

    def _cache_ad(self, ad: dict):
        """缓存广告到 SQLite"""
        try:
            conn = get_db()
            now = datetime.now().isoformat()
            expires = (datetime.now() + timedelta(hours=2)).isoformat()
            conn.execute(
                "INSERT OR REPLACE INTO ad_cache (ad_id, title, image_url, link_url, "
                "position, active, fetched_at, expires_at) VALUES (?,?,?,?,?,?,?,?)",
                (
                    ad.get("id", "default"),
                    ad.get("title", ""),
                    ad.get("image_url", ""),
                    ad.get("link_url", ""),
                    ad.get("position", "top"),
                    1,
                    now,
                    expires,
                ),
            )
            conn.commit()
            conn.close()
        except Exception:
            pass

    def _load_cached_ad(self) -> dict | None:
        """从缓存加载广告"""
        try:
            conn = get_db()
            row = conn.execute(
                "SELECT * FROM ad_cache WHERE active=1 AND expires_at > ? "
                "ORDER BY fetched_at DESC LIMIT 1",
                (datetime.now().isoformat(),),
            ).fetchone()
            conn.close()
            if row:
                return dict(row)
        except Exception:
            pass
        return None
