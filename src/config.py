"""
百宝箱 全局配置管理
负责读取/写入用户配置（JSON），管理路径、主题等全局参数。
"""
import os
import json
from pathlib import Path
from dataclasses import dataclass, field, asdict
from typing import Optional

# ---- 基础路径 ----
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
CONFIG_FILE = DATA_DIR / "config.json"
LOG_DIR = DATA_DIR / "logs"
CACHE_DIR = DATA_DIR / "cache"

# 确保目录存在
for d in (DATA_DIR, LOG_DIR, CACHE_DIR):
    d.mkdir(parents=True, exist_ok=True)

# ---- 支持的主题 ----
THEMES = {
    "blue":    {"name": "海天蓝", "primary": "#1877F2", "primary_dark": "#0C5BC4", "accent": "#3B9EFF"},
    "teal":    {"name": "青翠绿", "primary": "#0D9488", "primary_dark": "#0F766E", "accent": "#14B8A6"},
    "purple":  {"name": "星空紫", "primary": "#7C3AED", "primary_dark": "#6D28D9", "accent": "#8B5CF6"},
    "amber":   {"name": "暖阳橙", "primary": "#D97706", "primary_dark": "#B45309", "accent": "#F59E0B"},
    "rose":    {"name": "玫瑰红", "primary": "#E11D48", "primary_dark": "#BE123C", "accent": "#FB7185"},
}


@dataclass
class AppConfig:
    """应用配置"""
    # 主题
    theme: str = "blue"
    # 工作路径
    output_dir: str = ""          # 压缩/转换输出目录（空=用户选择）
    ffmpeg_path: str = ""         # FFmpeg 路径（空=自动查找）
    # 广告位
    ad_enabled: bool = False
    ad_api_url: str = ""
    ad_api_key: str = ""
    ad_refresh_minutes: int = 30
    # 窗口
    window_width: int = 1100
    window_height: int = 720
    window_maximized: bool = False
    # 压缩默认参数
    compress_target_size_kb: int = 500
    compress_quality: int = 75
    compress_mode: str = "size"   # "size" or "quality"
    compress_max_width: int = 0   # 0=不限制宽度
    compress_max_height: int = 0  # 0=不限制高度
    # 录制默认参数
    record_fps: int = 15
    record_codec: str = "libx264"
    record_format: str = "mp4"
    # PDF 默认参数
    pdf_preserve_formatting: bool = True
    pdf_preserve_images: bool = True

    @classmethod
    def load(cls) -> "AppConfig":
        """从 JSON 加载配置，不存在则用默认值"""
        if CONFIG_FILE.exists():
            try:
                data = json.loads(CONFIG_FILE.read_text(encoding="utf-8"))
                # 过滤掉未知字段
                known = {f.name for f in cls.__dataclass_fields__.values()}
                filtered = {k: v for k, v in data.items() if k in known}
                return cls(**filtered)
            except Exception:
                pass
        return cls()

    def save(self):
        """保存配置到 JSON"""
        CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        CONFIG_FILE.write_text(
            json.dumps(asdict(self), indent=2, ensure_ascii=False),
            encoding="utf-8"
        )

    def get_theme_colors(self) -> dict:
        """获取当前主题色配置"""
        return THEMES.get(self.theme, THEMES["blue"])

    def get_output_dir(self) -> str:
        """获取输出目录（默认用户桌面/百宝箱输出）"""
        if self.output_dir and os.path.isdir(self.output_dir):
            return self.output_dir
        desktop = Path.home() / "Desktop" / "百宝箱输出"
        desktop.mkdir(parents=True, exist_ok=True)
        return str(desktop)


# ---- 全局配置单例 ----
_current_config: Optional[AppConfig] = None


def get_config() -> AppConfig:
    """获取全局唯一配置实例（懒加载）"""
    global _current_config
    if _current_config is None:
        _current_config = AppConfig.load()
    return _current_config


def reload_config() -> AppConfig:
    """重新加载配置（用户修改设置后调用）"""
    global _current_config
    _current_config = AppConfig.load()
    return _current_config
