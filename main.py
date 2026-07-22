"""
百宝箱 (BaibaoBOX) - 主入口
Windows 桌面效率小工具 · 图片压缩 / PDF 转 Word / OCR 识别 / Excel 合并
"""
import sys
import os

# 确保项目根目录在 Python 路径中
_PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


def main():
    from PyQt6.QtWidgets import QApplication
    from PyQt6.QtCore import Qt, QTimer
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

    # 在 aboutToQuit 时做全局清理（停止广告拉取线程等）
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

    # 非阻塞预检 OCR 引擎可用性（延迟到主窗口显示后）
    QTimer.singleShot(500, _check_ocr_ready)

    sys.exit(app.exec())


def _check_ocr_ready() -> None:
    """后台预检 OCR 引擎，若不可用则在状态栏提示"""
    from src.config import get_config
    from src.modules.ocr_recognizer import pre_check_ocr

    cfg = get_config()
    status = pre_check_ocr(tesseract_path=cfg.ocr_tesseract_path)
    if not status["ready"]:
        from src.signals import get_bus
        get_bus().status_message.emit(
            "⚠️ OCR 引擎未就绪，请安装 Tesseract-OCR 或在设置中配置", 0
        )


if __name__ == "__main__":
    main()
