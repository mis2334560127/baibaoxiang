"""
百宝箱 - 图片批量压缩页面
支持拖拽添加文件、按大小/按质量两种模式、批量处理与进度展示。
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QProgressBar, QSpinBox, QSlider,
    QRadioButton, QButtonGroup, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from src.modules.image_compressor import SUPPORTED_FORMATS
from src.worker_threads import CompressWorker
from src.config import AppConfig, get_config
from src.signals import bus


class CompressPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("compressPage")
        self.setAcceptDrops(True)
        self._files: list[str] = []
        self._worker: CompressWorker | None = None
        self._config = get_config()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # === 广告位 ===
        ad = QLabel("📢  广告位（预留）")
        ad.setObjectName("adBanner")
        ad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ad.setFixedHeight(44)
        layout.addWidget(ad)

        # === 拖拽上传区 ===
        self.drop_zone = QLabel("📁  拖拽图片到此处，或点击选择文件\n支持 JPG / PNG / BMP / WebP / TIFF")
        self.drop_zone.setObjectName("dropZone")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setFixedHeight(120)
        self.drop_zone.mousePressEvent = self._on_drop_clicked
        layout.addWidget(self.drop_zone)

        # === 工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_add = QPushButton("➕ 添加文件")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_add_fld = QPushButton("📂 添加文件夹")
        self.btn_add_fld.clicked.connect(self._add_folder)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setProperty("class", "outline-btn")
        self.btn_clear.clicked.connect(self._clear_files)

        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_add_fld)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()

        self.file_count_label = QLabel("已添加 0 个文件")
        self.file_count_label.setStyleSheet("color: #5A6B85;")
        toolbar.addWidget(self.file_count_label)

        layout.addLayout(toolbar)

        # === 文件列表 ===
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(150)
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)

        # === 压缩模式选择 ===
        mode_layout = QHBoxLayout()
        mode_label = QLabel("压缩模式：")
        mode_label.setStyleSheet("font-weight: bold;")

        self.mode_group = QButtonGroup(self)
        self.radio_size = QRadioButton("按目标大小压缩")
        self.radio_quality = QRadioButton("按质量压缩")
        self.radio_size.setChecked(True)
        self.mode_group.addButton(self.radio_size, 1)
        self.mode_group.addButton(self.radio_quality, 2)

        mode_layout.addWidget(mode_label)
        mode_layout.addWidget(self.radio_size)
        mode_layout.addWidget(self.radio_quality)
        mode_layout.addStretch()
        layout.addLayout(mode_layout)

        # === 参数区 ===
        params = QHBoxLayout()
        params.setSpacing(20)

        # 目标大小
        self.size_widget = QWidget()
        size_lay = QHBoxLayout(self.size_widget)
        size_lay.setContentsMargins(0, 0, 0, 0)
        size_lay.addWidget(QLabel("目标大小:"))
        self.spin_target_kb = QSpinBox()
        self.spin_target_kb.setRange(50, 5000)
        self.spin_target_kb.setValue(self._config.compress_target_size_kb)
        self.spin_target_kb.setSuffix(" KB")
        self.spin_target_kb.setFixedWidth(100)
        size_lay.addWidget(self.spin_target_kb)
        size_lay.addStretch()

        # 质量
        self.quality_widget = QWidget()
        qual_lay = QHBoxLayout(self.quality_widget)
        qual_lay.setContentsMargins(0, 0, 0, 0)
        qual_lay.addWidget(QLabel("压缩质量:"))
        self.slider_quality = QSlider(Qt.Orientation.Horizontal)
        self.slider_quality.setRange(5, 100)
        self.slider_quality.setValue(self._config.compress_quality)
        self.slider_quality.setFixedWidth(200)
        self.spin_quality = QSpinBox()
        self.spin_quality.setRange(5, 100)
        self.spin_quality.setValue(self._config.compress_quality)
        self.spin_quality.setSuffix("%")
        self.slider_quality.valueChanged.connect(self.spin_quality.setValue)
        self.spin_quality.valueChanged.connect(self.slider_quality.setValue)
        qual_lay.addWidget(self.slider_quality)
        qual_lay.addWidget(self.spin_quality)
        qual_lay.addStretch()

        self.quality_widget.setVisible(False)

        params.addWidget(self.size_widget)
        params.addWidget(self.quality_widget)
        layout.addLayout(params)

        # 模式切换
        self.radio_size.toggled.connect(
            lambda checked: self.size_widget.setVisible(checked))
        self.radio_quality.toggled.connect(
            lambda checked: self.quality_widget.setVisible(checked))

        # === 尺寸限制区 ===
        resize_frame = QFrame()
        resize_frame.setObjectName("resizeFrame")
        resize_layout = QHBoxLayout(resize_frame)
        resize_layout.setContentsMargins(0, 0, 0, 0)
        resize_layout.setSpacing(10)

        self.chk_resize = QPushButton("📐 限制图片尺寸")
        self.chk_resize.setCheckable(True)
        self.chk_resize.setProperty("class", "outline-btn")
        self.chk_resize.setFixedWidth(140)
        resize_layout.addWidget(self.chk_resize)

        self.resize_params = QWidget()
        rp_lay = QHBoxLayout(self.resize_params)
        rp_lay.setContentsMargins(0, 0, 0, 0)
        rp_lay.setSpacing(6)
        rp_lay.addWidget(QLabel("最大宽度:"))
        self.spin_max_w = QSpinBox()
        self.spin_max_w.setRange(100, 10000)
        self.spin_max_w.setValue(self._config.compress_max_width or 1920)
        self.spin_max_w.setSuffix(" px")
        self.spin_max_w.setFixedWidth(100)
        rp_lay.addWidget(self.spin_max_w)
        rp_lay.addSpacing(10)
        rp_lay.addWidget(QLabel("最大高度:"))
        self.spin_max_h = QSpinBox()
        self.spin_max_h.setRange(100, 10000)
        self.spin_max_h.setValue(self._config.compress_max_height or 1080)
        self.spin_max_h.setSuffix(" px")
        self.spin_max_h.setFixedWidth(100)
        rp_lay.addWidget(self.spin_max_h)
        rp_lay.addStretch()

        self.resize_params.setVisible(False)

        resize_layout.addWidget(self.resize_params)
        resize_layout.addStretch()
        layout.addWidget(resize_frame)

        # 开关联动
        self.chk_resize.toggled.connect(
            lambda checked: self.resize_params.setVisible(checked))

        # === 操作按钮 ===
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_compress = QPushButton("🚀 开始压缩")
        self.btn_compress.setFixedHeight(40)
        self.btn_compress.setFixedWidth(140)
        self.btn_compress.clicked.connect(self._start_compress)
        self.btn_compress.setEnabled(False)

        self.btn_cancel = QPushButton("停止")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setProperty("class", "danger-btn")
        self.btn_cancel.clicked.connect(self._cancel_compress)
        self.btn_cancel.setVisible(False)

        action_layout.addWidget(self.btn_cancel)
        action_layout.addWidget(self.btn_compress)
        layout.addLayout(action_layout)

        # === 整体进度 ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # === 实时进度详情（单文件内部进度） ===
        self.progress_detail = QLabel("")
        self.progress_detail.setStyleSheet("color: #3B9EFF; font-size: 12px; font-weight: bold;")
        self.progress_detail.setVisible(False)
        self.progress_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_detail)

        # === 日志输出 ===
        self.log_output = QLabel("等待添加文件...")
        self.log_output.setObjectName("logOutput")
        self.log_output.setWordWrap(True)
        self.log_output.setMinimumHeight(80)
        self.log_output.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.log_output)

    def _connect_signals(self):
        bus.compress_all_done.connect(self._on_all_done)

    # ---- 文件操作 ----

    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件", "",
            "图片文件 (*.jpg *.jpeg *.png *.bmp *.webp *.tiff);;所有文件 (*.*)"
        )
        if files:
            self._append_files(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含图片的文件夹")
        if folder:
            from src.modules.image_compressor import get_image_files_from_dir
            files = get_image_files_from_dir(folder)
            if files:
                self._append_files(files)
            else:
                QMessageBox.information(self, "提示", "所选文件夹中没有支持的图片文件。")

    def _append_files(self, files: list[str]):
        new_count = 0
        for fp in files:
            if fp not in self._files and os.path.splitext(fp)[1].lower() in SUPPORTED_FORMATS:
                self._files.append(fp)
                item = QListWidgetItem(f"{os.path.basename(fp)}  ({os.path.getsize(fp)/1024:.0f} KB)")
                self.file_list.addItem(item)
                new_count += 1
        self._update_file_count()
        self.btn_compress.setEnabled(len(self._files) > 0)
        self._append_log(f"✅ 添加了 {new_count} 个文件")

    def _clear_files(self):
        self._files.clear()
        self.file_list.clear()
        self._update_file_count()
        self.btn_compress.setEnabled(False)
        self._append_log("🗑️ 已清空文件列表")

    def _update_file_count(self):
        total_kb = sum(os.path.getsize(f) / 1024 for f in self._files)
        self.file_count_label.setText(
            f"已添加 {len(self._files)} 个文件  ({total_kb/1024:.1f} MB)")

    # ---- 拖拽支持 ----

    # 保存拖拽区原始样式，避免 dragLeaveEvent 清空全局 QSS
    _drop_zone_orig_style = ""

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if not self._drop_zone_orig_style:
                self._drop_zone_orig_style = self.drop_zone.styleSheet()
            self.drop_zone.setStyleSheet(
                "#dropZone { background: #E8F1FF; border-color: #1877F2; color: #1877F2; "
                "border: 2px dashed #1877F2; border-radius: 12px; font-size: 14px; }")

    def dragLeaveEvent(self, event):
        self.drop_zone.setStyleSheet(self._drop_zone_orig_style)

    def dropEvent(self, event: QDropEvent):
        self.drop_zone.setStyleSheet(self._drop_zone_orig_style)
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path):
                files.append(path)
        if files:
            self._append_files(files)

    def _on_drop_clicked(self, event):
        self._add_files()

    # ---- 压缩逻辑 ----

    def _start_compress(self):
        if not self._files:
            return
        if self._worker and self._worker.isRunning():
            return

        mode = "size" if self.radio_size.isChecked() else "quality"
        target_kb = self.spin_target_kb.value()
        quality = self.spin_quality.value()
        output_dir = self._config.get_output_dir()
        max_width = self.spin_max_w.value() if self.chk_resize.isChecked() else 0
        max_height = self.spin_max_h.value() if self.chk_resize.isChecked() else 0

        self._worker = CompressWorker(
            files=self._files.copy(),
            target_kb=target_kb,
            quality=quality,
            mode=mode,
            output_dir=output_dir,
            max_width=max_width,
            max_height=max_height,
        )
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.item_progress.connect(self._on_item_progress)

        self.btn_compress.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_detail.setVisible(True)
        self.progress_bar.setMaximum(len(self._files))
        self.progress_bar.setValue(0)

        # 持久化当前参数
        self._config.compress_max_width = max_width
        self._config.compress_max_height = max_height
        self._config.compress_target_size_kb = target_kb
        self._config.compress_quality = quality
        self._config.compress_mode = mode
        self._config.save()

        self._append_log(f"🚀 开始压缩 {len(self._files)} 个文件 (模式: {mode})")
        self._worker.start()

    def _cancel_compress(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()         # 协作式取消，安全退出
            self._worker.wait(5000)       # 等待线程自然结束
            self._append_log("⛔ 压缩已取消")
        self._reset_ui()

    @pyqtSlot(int, int)
    def _on_file_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        bus.status_message.emit(f"压缩中 {current}/{total}", 0)

    @pyqtSlot(str, int, int)
    def _on_item_progress(self, filename: str, current: int, total: int):
        """单文件内部实时进度（二分搜索迭代 / 直接压缩）"""
        if current >= total:
            self.progress_detail.setText(f"✅ {filename} 完成")
        else:
            self.progress_detail.setText(f"⏳ 正在压缩: {filename}  ({current}/{total})")

    @pyqtSlot(str, bool, str)
    def _on_file_done(self, filename: str, success: bool, msg: str):
        icon = "✅" if success else "❌"
        self._append_log(f"{icon} {filename}: {msg}")
        # 标记列表
        for i in range(self.file_list.count()):
            item = self.file_list.item(i)
            if filename in item.text():
                if success:
                    item.setText(f"{item.text()}  ✓")
                    item.setForeground(Qt.GlobalColor.darkGreen)
                else:
                    item.setForeground(Qt.GlobalColor.red)
                break

    @pyqtSlot(int, int)
    def _on_all_done(self, success: int, fail: int):
        self._append_log(f"\n🏁 压缩完成! 成功: {success}, 失败: {fail}")
        bus.history_updated.emit()
        self._reset_ui()

    def _reset_ui(self):
        self.btn_compress.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_detail.setVisible(False)
        self._worker = None

    def _append_log(self, text: str):
        current = self.log_output.text() or ""
        self.log_output.setText(current + "\n" + text)
