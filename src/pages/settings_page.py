"""
百宝箱 - 系统设置页面
主题切换、路径配置、广告位远程数据库配置。
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QScrollArea, QLineEdit, QSpinBox, QCheckBox, QFileDialog,
    QButtonGroup, QRadioButton, QGroupBox, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot

from src.config import AppConfig, THEMES, get_config, reload_config
from src.signals import bus
from src.modules.screen_recorder import _is_valid_ffmpeg
from src.modules.ocr_recognizer import is_valid_tesseract


class SettingsPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("settingsPage")
        self._config = get_config()
        self._setup_ui()
        self._load_values()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        title = QLabel("⚙️  系统设置")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        sl = QVBoxLayout(w)
        sl.setSpacing(20)

        # === 主题设置 ===
        theme_group = QGroupBox("🎨 主题颜色")
        theme_lay = QVBoxLayout(theme_group)

        self.theme_buttons = {}
        theme_btn_group = QButtonGroup(self)

        colors_row = QHBoxLayout()
        colors_row.setSpacing(10)
        for key, info in THEMES.items():
            btn = QPushButton(info["name"])
            btn.setCheckable(True)
            btn.setFixedSize(90, 36)
            btn.setStyleSheet(
                f"QPushButton {{ background: {info['primary']}; color: white; "
                f"border-radius: 6px; font-weight: 500; }}"
                f"QPushButton:checked {{ border: 3px solid {info['primary_dark']}; }}"
            )
            btn.clicked.connect(lambda checked, k=key: self._on_theme_changed(k))
            self.theme_buttons[key] = btn
            theme_btn_group.addButton(btn)
            colors_row.addWidget(btn)
        colors_row.addStretch()
        theme_lay.addLayout(colors_row)

        self.theme_preview = QLabel()
        self.theme_preview.setFixedHeight(60)
        self.theme_preview.setStyleSheet(
            "background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            "stop:0 #1877F2, stop:1 #0C5BC4); border-radius: 8px; color: white; "
            "font-size: 16px; font-weight: bold; padding: 16px;")
        self.theme_preview.setText("百宝箱 - 当前主题预览")
        self.theme_preview.setAlignment(Qt.AlignmentFlag.AlignCenter)
        theme_lay.addWidget(self.theme_preview)

        sl.addWidget(theme_group)

        # === 路径设置 ===
        path_group = QGroupBox("📁 存储路径")
        path_lay = QVBoxLayout(path_group)

        out_row = QHBoxLayout()
        out_row.addWidget(QLabel("默认输出目录:"))
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setReadOnly(True)
        out_row.addWidget(self.output_dir_input)
        btn_browse = QPushButton("浏览")
        btn_browse.clicked.connect(self._browse_output_dir)
        out_row.addWidget(btn_browse)
        path_lay.addLayout(out_row)

        ffmpeg_row = QHBoxLayout()
        ffmpeg_row.addWidget(QLabel("FFmpeg 路径:"))
        self.ffmpeg_input = QLineEdit()
        self.ffmpeg_input.setPlaceholderText("留空则自动查找（PATH 或常见路径）")
        ffmpeg_row.addWidget(self.ffmpeg_input)
        btn_ffmpeg = QPushButton("浏览")
        btn_ffmpeg.clicked.connect(self._browse_ffmpeg)
        ffmpeg_row.addWidget(btn_ffmpeg)
        path_lay.addLayout(ffmpeg_row)

        tess_row = QHBoxLayout()
        tess_row.addWidget(QLabel("Tesseract 路径:"))
        self.tesseract_input = QLineEdit()
        self.tesseract_input.setPlaceholderText("可选（降级方案），默认使用 PaddleOCR")
        tess_row.addWidget(self.tesseract_input)
        btn_tesseract = QPushButton("浏览")
        btn_tesseract.clicked.connect(self._browse_tesseract)
        tess_row.addWidget(btn_tesseract)
        path_lay.addLayout(tess_row)

        sl.addWidget(path_group)

        # === 广告位配置 ===
        ad_group = QGroupBox("📢 广告位设置（远程数据库）")
        ad_lay = QVBoxLayout(ad_group)

        ad_note = QLabel(
            "广告位为预留功能，当前默认关闭。启用后将定期从远程 API 拉取广告内容展示。"
        )
        ad_note.setWordWrap(True)
        ad_note.setStyleSheet("color: #5A6B85; font-size: 12px;")
        ad_lay.addWidget(ad_note)

        self.ad_enabled_chk = QCheckBox("启用广告位")
        self.ad_enabled_chk.toggled.connect(self._toggle_ad_fields)
        ad_lay.addWidget(self.ad_enabled_chk)

        api_row = QHBoxLayout()
        api_row.addWidget(QLabel("API 地址:"))
        self.ad_api_input = QLineEdit()
        self.ad_api_input.setPlaceholderText("https://example.com/api/ads")
        api_row.addWidget(self.ad_api_input)
        ad_lay.addLayout(api_row)

        key_row = QHBoxLayout()
        key_row.addWidget(QLabel("API 密钥:"))
        self.ad_key_input = QLineEdit()
        self.ad_key_input.setPlaceholderText("Bearer Token")
        self.ad_key_input.setEchoMode(QLineEdit.EchoMode.Password)
        key_row.addWidget(self.ad_key_input)
        ad_lay.addLayout(key_row)

        interval_row = QHBoxLayout()
        interval_row.addWidget(QLabel("刷新间隔:"))
        self.ad_interval = QSpinBox()
        self.ad_interval.setRange(5, 1440)
        self.ad_interval.setSuffix(" 分钟")
        self.ad_interval.setValue(self._config.ad_refresh_minutes)
        interval_row.addWidget(self.ad_interval)
        interval_row.addStretch()
        ad_lay.addLayout(interval_row)

        sl.addWidget(ad_group)

        # === 关于 ===
        about_group = QGroupBox("ℹ️ 关于百宝箱")
        about_lay = QVBoxLayout(about_group)
        about_text = QLabel(
            "百宝箱 v1.0.0\n"
            "Windows 桌面效率小工具\n"
            "技术栈：Python 3 + PyQt6 + Pillow + pdf2docx + FFmpeg\n"
            "所有功能本地运行，数据不上传\n"
            "© 2026 BaibaoBOX"
        )
        about_text.setStyleSheet("color: #5A6B85; font-size: 12px;")
        about_lay.addWidget(about_text)
        sl.addWidget(about_group)

        sl.addStretch()
        scroll.setWidget(w)
        layout.addWidget(scroll)

        # 保存按钮
        save_row = QHBoxLayout()
        save_row.addStretch()
        btn_save = QPushButton("💾 保存设置")
        btn_save.setFixedSize(140, 40)
        btn_save.clicked.connect(self._save_settings)
        save_row.addWidget(btn_save)
        layout.addLayout(save_row)

    def _load_values(self):
        """从配置加载值到 UI"""
        self.output_dir_input.setText(self._config.get_output_dir())
        self.ffmpeg_input.setText(self._config.ffmpeg_path)
        self.tesseract_input.setText(self._config.ocr_tesseract_path)
        self.ad_enabled_chk.setChecked(self._config.ad_enabled)
        self.ad_api_input.setText(self._config.ad_api_url)
        self.ad_key_input.setText(self._config.ad_api_key)
        self.ad_interval.setValue(self._config.ad_refresh_minutes)

        # 主题按钮
        theme_key = self._config.theme
        if theme_key in self.theme_buttons:
            self.theme_buttons[theme_key].setChecked(True)
            self._update_theme_preview(theme_key)

        self._toggle_ad_fields(self._config.ad_enabled)

    def _toggle_ad_fields(self, enabled: bool):
        self.ad_api_input.setEnabled(enabled)
        self.ad_key_input.setEnabled(enabled)
        self.ad_interval.setEnabled(enabled)

    def _on_theme_changed(self, key: str):
        self._update_theme_preview(key)

    def _update_theme_preview(self, key: str):
        info = THEMES.get(key, THEMES["blue"])
        self.theme_preview.setStyleSheet(
            f"background: qlineargradient(x1:0,y1:0,x2:1,y2:0,"
            f"stop:0 {info['primary']}, stop:1 {info['primary_dark']}); "
            f"border-radius: 8px; color: white; "
            f"font-size: 16px; font-weight: bold; padding: 16px;")

    def _browse_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self.output_dir_input.setText(folder)

    def _browse_ffmpeg(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "选择 FFmpeg 可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*.*)")
        if file:
            self.ffmpeg_input.setText(file)

    def _browse_tesseract(self):
        file, _ = QFileDialog.getOpenFileName(
            self, "选择 Tesseract OCR 可执行文件", "",
            "可执行文件 (*.exe);;所有文件 (*.*)")
        if file:
            self.tesseract_input.setText(file)

    def _save_settings(self):
        """保存全部设置"""
        # 主题
        for key, btn in self.theme_buttons.items():
            if btn.isChecked():
                old_theme = self._config.theme
                self._config.theme = key
                if old_theme != key:
                    bus.theme_changed.emit(key)
                break

        # 路径
        self._config.output_dir = self.output_dir_input.text()
        ffmpeg_path = self.ffmpeg_input.text().strip()
        self._config.ffmpeg_path = ffmpeg_path

        # 如果用户填写了自定义 FFmpeg 路径，进行有效性提示
        if ffmpeg_path and not _is_valid_ffmpeg(ffmpeg_path):
            QMessageBox.warning(
                self, "FFmpeg 路径无效",
                "填写的 FFmpeg 路径不是有效的 Windows 可执行文件，\n"
                "录屏功能可能无法使用。请重新下载或留空使用自动查找。"
            )

        tess_path = self.tesseract_input.text().strip()
        self._config.ocr_tesseract_path = tess_path
        if tess_path and not is_valid_tesseract(tess_path):
            QMessageBox.warning(
                self, "Tesseract 路径无效",
                "填写的 Tesseract 路径不是有效的可执行文件，\n"
                "OCR 功能可能无法使用。请重新安装或留空使用自动查找。"
            )

        # 广告
        self._config.ad_enabled = self.ad_enabled_chk.isChecked()
        self._config.ad_api_url = self.ad_api_input.text()
        self._config.ad_api_key = self.ad_key_input.text()
        self._config.ad_refresh_minutes = self.ad_interval.value()

        self._config.save()
        reload_config()  # 刷新全局单例，其他页面下次获取时获得新配置
        QMessageBox.information(self, "保存成功", "设置已保存。主题切换将立即生效。")

        # 通知广告管理器刷新
        try:
            from src.modules.ad_manager import AdManager
            AdManager().refresh_config()
        except Exception:
            pass
