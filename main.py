"""
百宝箱 (BaibaoBOX) - 主入口
Windows 桌面效率小工具 · 图片压缩 / PDF 转 Word / 屏幕录制
"""
import sys
import os

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt
    from src.main_window import MainWindow
    from src.config import get_config

    # 高 DPI 适配
    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )

    app = QApplication(sys.argv)
    app.setApplicationName("百宝箱")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("BaibaoBOX")

    # 在 QApplication 存在后立即初始化信号总线单例
    from src.signals import get_bus
    get_bus()  # 触发懒加载，确保全局唯一实例

    # 加载配置
    config = get_config()

    # 启动广告管理器（如果启用）
    try:
        from src.modules.ad_manager import AdManager
        AdManager().start()
    except Exception:
        pass

    # 在 aboutToQuit 时做全局清理（防止孤儿 FFmpeg 进程）
    def _on_quit():
        try:
            from src.modules.ad_manager import AdManager
            AdManager().stop()
        except Exception:
            pass

    app.aboutToQuit.connect(_on_quit)

    # 创建主窗口
    window = MainWindow()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()
