"""
百宝箱 全局信号总线
使用 Qt 信号/槽机制在各页面和模块间传递状态变化。

注意：必须在 QApplication 创建之后才能访问 bus 实例。
      所有导入本模块的代码应在函数/方法内部 import，
      或通过 get_bus() 懒加载方式访问。
"""
from PyQt6.QtCore import QObject, pyqtSignal


class SignalBus(QObject):
    """全局单例信号总线 —— 必须在 QApplication 存在后实例化"""

    # 主题切换
    theme_changed = pyqtSignal(str)

    # 状态栏消息
    status_message = pyqtSignal(str, int)  # (message, timeout_ms)

    # 页面导航
    navigate_to = pyqtSignal(str)  # page_id

    # 压缩进度
    compress_progress = pyqtSignal(int, int)          # (current, total)
    compress_file_done = pyqtSignal(str, bool, str)   # (filename, success, msg)
    compress_all_done = pyqtSignal(int, int)           # (success_count, fail_count)

    # PDF转换进度
    convert_progress = pyqtSignal(int, int)
    convert_file_done = pyqtSignal(str, bool, str)
    convert_all_done = pyqtSignal(int, int)

    # 录制状态
    record_started = pyqtSignal()
    record_stopped = pyqtSignal(str)          # output file path
    record_error = pyqtSignal(str)

    # 广告更新
    ad_updated = pyqtSignal(str, str, str)    # (title, image_url, link_url)
    ad_cleared = pyqtSignal()

    # Excel合并进度
    merge_progress = pyqtSignal(int, int)
    merge_file_done = pyqtSignal(str, bool, str)
    merge_all_done = pyqtSignal(int, int)

    # 历史记录刷新
    history_updated = pyqtSignal()


# ---------------------------------------------------------------
# 懒加载单例 —— 在 QApplication 创建后才真正实例化
# ---------------------------------------------------------------
_bus_instance: "SignalBus | None" = None


def get_bus() -> SignalBus:
    """获取全局 SignalBus 单例（线程安全地在 QApplication 之后创建）"""
    global _bus_instance
    if _bus_instance is None:
        _bus_instance = SignalBus()
    return _bus_instance


# 兼容旧代码直接使用 `from src.signals import bus` 的写法：
# 通过 __getattr__ 在模块级别实现懒加载代理
def __getattr__(name: str):
    if name == "bus":
        return get_bus()
    raise AttributeError(f"module 'src.signals' has no attribute {name!r}")
