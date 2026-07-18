"""
百宝箱 - 主窗口
管理侧边栏导航、页面切换、主题加载、全局状态栏。
"""
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QHBoxLayout, QVBoxLayout, QLabel,
    QPushButton, QStackedWidget, QFrame, QButtonGroup,
    QStatusBar, QApplication
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QIcon

from src.config import AppConfig, THEMES, get_config
from src.signals import bus
from src.pages.home_page import HomePage
from src.pages.compress_page import CompressPage
from src.pages.pdf_word_page import PdfWordPage

from src.pages.guide_page import GuidePage
from src.pages.settings_page import SettingsPage
from src.pages.excel_merge_page import ExcelMergePage
from src.pages.ocr_page import OcrPage

# 侧边栏导航项配置
NAV_ITEMS = [
    {"id": "home",         "icon": "🏠", "label": "首页总览",     "tip": "使用统计与快捷入口"},
    {"id": "compress",     "icon": "📷", "label": "图片压缩",     "tip": "批量压缩图片，支持按大小/质量"},
    {"id": "pdf2word",     "icon": "📄", "label": "PDF 转 Word",  "tip": "将 PDF 文档转换为可编辑 Word"},

    {"id": "excel_merge",  "icon": "📊", "label": "Excel 合并",   "tip": "批量解压压缩包并合并 Excel 数据"},
    {"id": "ocr",          "icon": "🔍", "label": "图片 OCR",     "tip": "批量识别图片中的文字并输出 TXT"},
    {"id": "guide",        "icon": "📖", "label": "使用指南",     "tip": "安装步骤、操作说明、常见问题"},
    {"id": "settings",     "icon": "⚙️", "label": "系统设置",    "tip": "主题、路径、广告位配置"},
]


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self._config = get_config()
        self._current_theme = self._config.theme
        self._setup_window()
        self._setup_ui()
        self._load_theme()
        self._connect_signals()

        # 默认显示首页
        self._nav_buttons["home"].setChecked(True)
        self._switch_page("home")

        # 状态栏消息定时清除
        self._status_timer = QTimer()
        self._status_timer.setSingleShot(True)
        self._status_timer.timeout.connect(lambda: self.statusBar().showMessage("就绪"))

    def _setup_window(self):
        """窗口基础配置"""
        self.setWindowTitle("百宝箱 BaibaoBOX")
        self.setMinimumSize(960, 600)
        self.resize(self._config.window_width, self._config.window_height)
        if self._config.window_maximized:
            self.showMaximized()

        # 窗口图标（如果有）
        icon_path = Path(__file__).resolve().parent / "resources" / "icons" / "app.ico"
        if icon_path.exists():
            self.setWindowIcon(QIcon(str(icon_path)))

    def _setup_ui(self):
        """构建主界面布局"""
        central = QWidget()
        self.setCentralWidget(central)
        root = QHBoxLayout(central)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        # ===== 侧边栏 =====
        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(210)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        # Logo 区域
        logo_frame = QFrame()
        logo_frame.setFixedHeight(64)
        logo_lay = QHBoxLayout(logo_frame)
        logo_lay.setContentsMargins(16, 0, 16, 0)
        logo_icon = QLabel("📦")
        logo_icon.setStyleSheet("font-size: 24px;")
        logo_text = QLabel("百宝箱")
        logo_text.setStyleSheet("font-size: 16px; font-weight: bold; color: #1a2640;")
        logo_lay.addWidget(logo_icon)
        logo_lay.addWidget(logo_text)
        logo_lay.addStretch()
        sidebar_layout.addWidget(logo_frame)

        # 分割线
        sep = QFrame()
        sep.setObjectName("separator")
        sep.setFixedHeight(1)
        sidebar_layout.addWidget(sep)

        # 导航按钮
        nav_layout = QVBoxLayout()
        nav_layout.setContentsMargins(0, 8, 0, 8)
        nav_layout.setSpacing(2)

        self._nav_buttons: dict[str, QPushButton] = {}
        nav_group = QButtonGroup(self)
        nav_group.setExclusive(True)

        for item in NAV_ITEMS:
            btn = QPushButton(f"  {item['icon']}  {item['label']}")
            btn.setCheckable(True)
            btn.setToolTip(item["tip"])
            btn.setCursor(Qt.CursorShape.PointingHandCursor)
            btn.clicked.connect(lambda checked, i=item["id"]: self._switch_page(i))
            nav_group.addButton(btn)
            self._nav_buttons[item["id"]] = btn
            nav_layout.addWidget(btn)

        sidebar_layout.addLayout(nav_layout)
        sidebar_layout.addStretch()

        # 底部信息
        bot_frame = QFrame()
        bot_lay = QVBoxLayout(bot_frame)
        bot_lay.setContentsMargins(16, 12, 16, 16)
        bot_lay.setSpacing(4)

        privacy = QLabel("🔒 仅本地运行 · 数据不上传")
        privacy.setStyleSheet("font-size: 11px; color: #94A3B8;")
        privacy.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bot_lay.addWidget(privacy)

        version = QLabel("v1.0.0")
        version.setStyleSheet("font-size: 10px; color: #CBD5E1;")
        version.setAlignment(Qt.AlignmentFlag.AlignCenter)
        bot_lay.addWidget(version)

        sidebar_layout.addWidget(bot_frame)

        root.addWidget(sidebar)

        # ===== 右侧内容区 =====
        right = QFrame()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        right_layout.setSpacing(0)

        # 标题栏
        title_bar = QFrame()
        title_bar.setObjectName("titleBar")
        title_bar.setFixedHeight(50)
        title_lay = QHBoxLayout(title_bar)
        title_lay.setContentsMargins(24, 0, 16, 0)

        self.page_title = QLabel("首页总览")
        self.page_title.setObjectName("pageTitle")
        title_lay.addWidget(self.page_title)
        title_lay.addStretch()

        # 主题快捷切换色点
        for key, info in THEMES.items():
            dot = QPushButton()
            dot.setFixedSize(16, 16)
            dot.setToolTip(info["name"])
            dot.setStyleSheet(
                f"QPushButton {{ background: {info['primary']}; border-radius: 8px; "
                f"border: 2px solid transparent; }}"
                f"QPushButton:hover {{ border-color: {info['primary_dark']}; }}"
            )
            dot.setCursor(Qt.CursorShape.PointingHandCursor)
            dot.clicked.connect(lambda checked, k=key: self._quick_theme_switch(k))
            title_lay.addWidget(dot)

        right_layout.addWidget(title_bar)

        # 内容页面堆栈
        self.stack = QStackedWidget()
        self._pages = {}

        self._pages["home"] = HomePage()
        self._pages["compress"] = CompressPage()
        self._pages["pdf2word"] = PdfWordPage()
        self._pages["excel_merge"] = ExcelMergePage()
        self._pages["ocr"] = OcrPage()
        self._pages["guide"] = GuidePage()
        self._pages["settings"] = SettingsPage()

        for key, page in self._pages.items():
            self.stack.addWidget(page)

        right_layout.addWidget(self.stack)

        root.addWidget(right)

        # ===== 状态栏 =====
        status = QStatusBar()
        status.setObjectName("statusBar")
        status.showMessage("就绪")
        self.setStatusBar(status)

    def _load_theme(self):
        """加载当前主题 QSS"""
        theme_key = self._config.theme
        qss_path = Path(__file__).resolve().parent / "theme" / f"{theme_key}.qss"
        if qss_path.exists():
            style = qss_path.read_text(encoding="utf-8")
            self.setStyleSheet(style)

    def _connect_signals(self):
        """连接全局信号"""
        bus.theme_changed.connect(self._on_theme_changed)
        bus.status_message.connect(self._on_status_message)
        bus.navigate_to.connect(self._switch_page)

    @pyqtSlot(str)
    def _on_theme_changed(self, theme_key: str):
        self._config.theme = theme_key
        self._config.save()
        self._current_theme = theme_key
        self._load_theme()

    @pyqtSlot(str, int)
    def _on_status_message(self, message: str, timeout_ms: int):
        self.statusBar().showMessage(message, timeout_ms or 5000)

    @pyqtSlot(str)
    def _switch_page(self, page_id: str):
        """切换显示页面"""
        if page_id in self._pages:
            self.stack.setCurrentWidget(self._pages[page_id])
            # 更新标题
            for item in NAV_ITEMS:
                if item["id"] == page_id:
                    self.page_title.setText(f"{item['icon']}  {item['label']}")
                    break
            # 刷新首页数据
            if page_id == "home" and hasattr(self._pages["home"], "refresh"):
                self._pages["home"].refresh()

    def _quick_theme_switch(self, key: str):
        """标题栏色点快捷切换主题"""
        bus.theme_changed.emit(key)

    def closeEvent(self, event):
        """窗口关闭时安全停止所有后台任务并保存状态"""
        # 1. 停止广告拉取
        try:
            from src.modules.ad_manager import AdManager
            AdManager().stop()
        except Exception:
            pass
        # 3. 保存窗口状态
        self._config.window_width = self.width()
        self._config.window_height = self.height()
        self._config.window_maximized = self.isMaximized()
        self._config.save()
        event.accept()
