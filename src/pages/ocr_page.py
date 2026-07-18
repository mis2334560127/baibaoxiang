"""
图片 OCR 识别页面
支持批量拖拽/选择图片，使用 Tesseract OCR 识别文字并输出 .txt 文件。
"""
import os
import time

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QListWidget, QListWidgetItem, QFileDialog, QProgressBar,
    QTextEdit, QComboBox, QCheckBox, QLineEdit, QFrame,
    QMessageBox, QAbstractItemView, QSizePolicy,
)
from PyQt6.QtCore import Qt, pyqtSlot, QSize
from PyQt6.QtGui import QDragEnterEvent, QDropEvent, QFont

from src.worker_threads import OcrWorker
from src.config import get_config
from src.signals import bus
from src.database import get_recent_ocr
from src.modules.ocr_recognizer import (
    SUPPORTED_IMAGE_EXTS, get_image_files, find_tesseract, is_valid_tesseract,
)


# 常见 OCR 语言选项
LANG_OPTIONS = [
    ("chi_sim+eng", "中文简体 + 英文（推荐）"),
    ("chi_sim",     "中文简体"),
    ("chi_tra",     "中文繁体"),
    ("eng",         "英文"),
    ("jpn",         "日文"),
    ("kor",         "韩文"),
    ("fra",         "法文"),
    ("deu",         "德文"),
    ("rus",         "俄文"),
    ("spa",         "西班牙文"),
]


class OcrPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("ocrPage")
        self.setAcceptDrops(True)

        self._files: list[str] = []
        self._worker: OcrWorker | None = None
        self._config = get_config()
        self._start_times: dict[str, float] = {}
        self._elapsed_list: list[float] = []

        self._setup_ui()
        self._connect_signals()

    # ── UI 构建 ──────────────────────────────────────────────

    def _setup_ui(self):
        root = QVBoxLayout(self)
        root.setContentsMargins(24, 20, 24, 20)
        root.setSpacing(16)

        # ── 参数区域 ──
        params_frame = QFrame()
        params_frame.setObjectName("card")
        params_lay = QVBoxLayout(params_frame)
        params_lay.setContentsMargins(20, 16, 20, 16)
        params_lay.setSpacing(12)

        # 第一行：语言选择 + 输出模式
        row1 = QHBoxLayout()
        row1.setSpacing(16)

        lang_label = QLabel("识别语言：")
        lang_label.setFixedWidth(70)
        self.lang_combo = QComboBox()
        for code, label in LANG_OPTIONS:
            self.lang_combo.addItem(label, code)
        # 从配置恢复上次选择
        saved_lang = self._config.ocr_lang
        for i in range(self.lang_combo.count()):
            if self.lang_combo.itemData(i) == saved_lang:
                self.lang_combo.setCurrentIndex(i)
                break
        self.lang_combo.setMinimumWidth(200)

        self.combine_check = QCheckBox("合并到单个文件")
        self.combine_check.setToolTip("将所有识别结果合并到一个 TXT 文件中")
        self.combine_check.setChecked(False)

        row1.addWidget(lang_label)
        row1.addWidget(self.lang_combo)
        row1.addStretch()
        row1.addWidget(self.combine_check)
        params_lay.addLayout(row1)

        # 第二行：输出目录
        row2 = QHBoxLayout()
        row2.setSpacing(8)
        out_label = QLabel("输出目录：")
        out_label.setFixedWidth(70)
        self.output_dir_input = QLineEdit()
        self.output_dir_input.setReadOnly(True)
        self.output_dir_input.setPlaceholderText("默认：桌面/百宝箱输出")
        default_dir = self._config.get_output_dir()
        self.output_dir_input.setText(default_dir if os.path.isdir(default_dir) else "")

        self.browse_out_btn = QPushButton("浏览...")
        self.browse_out_btn.setFixedWidth(80)
        self.browse_out_btn.clicked.connect(self._browse_output_dir)

        row2.addWidget(out_label)
        row2.addWidget(self.output_dir_input)
        row2.addWidget(self.browse_out_btn)
        params_lay.addLayout(row2)

        root.addWidget(params_frame)

        # ── 文件选择区域 ──
        select_frame = QFrame()
        select_frame.setObjectName("card")
        select_lay = QVBoxLayout(select_frame)
        select_lay.setContentsMargins(20, 16, 20, 16)
        select_lay.setSpacing(8)

        select_row = QHBoxLayout()
        select_row.setSpacing(8)
        self.add_files_btn = QPushButton("📂 添加图片")
        self.add_files_btn.clicked.connect(self._browse_files)
        self.add_dir_btn = QPushButton("📁 添加文件夹")
        self.add_dir_btn.clicked.connect(self._browse_dir)
        self.clear_btn = QPushButton("清空列表")
        self.clear_btn.clicked.connect(self._clear_files)

        file_count_label = QLabel("已选择 0 个文件")
        file_count_label.setObjectName("fileCountLabel")
        self._file_count_label = file_count_label

        select_row.addWidget(self.add_files_btn)
        select_row.addWidget(self.add_dir_btn)
        select_row.addWidget(self.clear_btn)
        select_row.addStretch()
        select_row.addWidget(file_count_label)
        select_lay.addLayout(select_row)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setAlternatingRowColors(True)
        self.file_list.setSelectionMode(QAbstractItemView.SelectionMode.ExtendedSelection)
        self.file_list.setMinimumHeight(120)
        select_lay.addWidget(self.file_list)

        root.addWidget(select_frame)

        # ── 操作按钮 ──
        action_row = QHBoxLayout()
        action_row.setSpacing(12)

        self.start_btn = QPushButton("▶ 开始识别")
        self.start_btn.setObjectName("primaryBtn")
        self.start_btn.setMinimumHeight(40)
        self.start_btn.clicked.connect(self._start_ocr)

        self.cancel_btn = QPushButton("■ 取消")
        self.cancel_btn.setMinimumHeight(40)
        self.cancel_btn.setEnabled(False)
        self.cancel_btn.clicked.connect(self._cancel_ocr)

        action_row.addStretch()
        action_row.addWidget(self.start_btn)
        action_row.addWidget(self.cancel_btn)
        root.addLayout(action_row)

        # ── 进度条 ──
        progress_frame = QFrame()
        progress_frame.setObjectName("card")
        progress_lay = QVBoxLayout(progress_frame)
        progress_lay.setContentsMargins(20, 12, 20, 12)
        progress_lay.setSpacing(8)

        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        self.progress_label = QLabel()
        self.progress_label.setVisible(False)
        progress_lay.addWidget(self.progress_bar)
        progress_lay.addWidget(self.progress_label)
        root.addWidget(progress_frame)

        # ── 日志区域 ──
        log_frame = QFrame()
        log_frame.setObjectName("card")
        log_lay = QVBoxLayout(log_frame)
        log_lay.setContentsMargins(20, 12, 20, 12)
        log_lay.setSpacing(8)

        log_header = QHBoxLayout()
        log_title = QLabel("处理日志")
        log_title.setStyleSheet("font-weight: bold; font-size: 13px;")
        self.clear_log_btn = QPushButton("清空日志")
        self.clear_log_btn.clicked.connect(self._clear_log)
        log_header.addWidget(log_title)
        log_header.addStretch()
        log_header.addWidget(self.clear_log_btn)
        log_lay.addLayout(log_header)

        self.log_area = QTextEdit()
        self.log_area.setReadOnly(True)
        self.log_area.setObjectName("logArea")
        log_lay.addWidget(self.log_area)
        root.addWidget(log_frame, stretch=1)

    # ── 信号连接 ──

    def _connect_signals(self):
        bus.ocr_all_done.connect(self._on_all_done)

    # ── 文件操作 ──

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        urls = event.mimeData().urls()
        paths = [u.toLocalFile() for u in urls if u.isLocalFile()]
        self._add_file_paths(paths)

    def _browse_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择图片文件",
            "",
            "图片文件 (*.png *.jpg *.jpeg *.bmp *.webp *.tiff *.tif);;所有文件 (*.*)"
        )
        if files:
            self._add_file_paths(files)

    def _browse_dir(self):
        directory = QFileDialog.getExistingDirectory(self, "选择图片文件夹")
        if directory:
            self._add_file_paths([directory])

    def _add_file_paths(self, paths: list[str]):
        """添加文件/目录路径到列表（自动过滤非图片文件、去重）"""
        new_files = get_image_files(paths, recursive=True)
        existing = set(self._files)
        added = 0
        for f in new_files:
            if f not in existing:
                self._files.append(f)
                existing.add(f)
                item = QListWidgetItem(os.path.basename(f))
                item.setToolTip(f)
                self.file_list.addItem(item)
                added += 1
        if added > 0:
            self._update_file_count()

    def _clear_files(self):
        self._files.clear()
        self.file_list.clear()
        self._update_file_count()

    def _update_file_count(self):
        self._file_count_label.setText(f"已选择 {len(self._files)} 个文件")

    def _browse_output_dir(self):
        directory = QFileDialog.getExistingDirectory(
            self, "选择输出目录",
            self.output_dir_input.text() or self._config.get_output_dir()
        )
        if directory:
            self.output_dir_input.setText(directory)

    # ── 核心流程 ──

    def _start_ocr(self):
        """开始 OCR 识别"""
        if not self._files:
            QMessageBox.information(self, "提示", "请先添加需要识别的图片文件。")
            return

        # 查找 Tesseract（仅作为 PaddleOCR 的降级方案，非必需）
        tess_path = self._config.ocr_tesseract_path or ""
        if tess_path and not is_valid_tesseract(tess_path):
            reply = QMessageBox.question(
                self, "Tesseract 路径无效",
                f"设置中指定的 Tesseract 路径无效：\n{tess_path}\n\n"
                "是否忽略该路径继续（将使用 PaddleOCR 识别）？",
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
            )
            if reply == QMessageBox.StandardButton.No:
                return
            tess_path = ""

        found = find_tesseract(tess_path)  # 找到就作为降级方案，找不到也不影响
        if found:
            self._append_log(f"✅ 已找到 Tesseract（降级方案）：{found}")
        else:
            self._append_log("ℹ️ 使用 PaddleOCR（主引擎），未配置 Tesseract 降级方案")

        # 输出目录
        output_dir = self.output_dir_input.text().strip()
        if not output_dir or not os.path.isdir(output_dir):
            output_dir = self._config.get_output_dir()
            self.output_dir_input.setText(output_dir)

        # 获取语言设置
        lang = self.lang_combo.currentData()

        # 保存配置
        self._config.ocr_lang = lang
        self._config.save()

        # 重置 ETA 追踪
        self._start_times.clear()
        self._elapsed_list.clear()

        # 更新 UI 状态
        self._set_ui_running(True)
        self.log_area.clear()
        self._append_log(f"📝 开始 OCR 识别，共 {len(self._files)} 个文件")
        self._append_log(f"🔤 语言：{self.lang_combo.currentText()}")
        self._append_log(f"📂 输出目录：{output_dir}")
        if self.combine_check.isChecked():
            self._append_log("📄 模式：合并到单个文件")
        else:
            self._append_log("📄 模式：每个图片独立输出 .txt")

        # 创建并启动工作线程
        self._worker = OcrWorker(
            files=list(self._files),
            output_dir=output_dir,
            tesseract_path=found,
            lang=lang,
            combine_to_one=self.combine_check.isChecked(),
        )
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.item_progress.connect(self._on_item_progress)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _cancel_ocr(self):
        if self._worker:
            self._worker.cancel()
            self._append_log("⏹️ 用户取消操作，等待当前任务完成...")

    def _set_ui_running(self, running: bool):
        self.start_btn.setEnabled(not running)
        self.cancel_btn.setEnabled(running)
        self.add_files_btn.setEnabled(not running)
        self.add_dir_btn.setEnabled(not running)
        self.clear_btn.setEnabled(not running)
        self.lang_combo.setEnabled(not running)
        self.combine_check.setEnabled(not running)
        self.browse_out_btn.setEnabled(not running)
        self.progress_bar.setVisible(running)
        self.progress_label.setVisible(running)
        if not running:
            self.progress_bar.setValue(0)
            self.progress_label.setText("")

    # ── 信号槽 ──

    @pyqtSlot(int, int)
    def _on_file_progress(self, current: int, total: int):
        self.progress_bar.setMaximum(total)
        self.progress_bar.setValue(current)
        msg = f"正在处理：{current} / {total}"
        if self._elapsed_list and current > 0:
            avg = sum(self._elapsed_list) / len(self._elapsed_list)
            remaining = avg * (total - current)
            if remaining >= 60:
                msg += f" | 预计剩余约 {remaining/60:.0f} 分 {remaining%60:.0f} 秒"
            else:
                msg += f" | 预计剩余约 {remaining:.0f} 秒"
        self.progress_label.setText(msg)

    @pyqtSlot(str, bool, str)
    def _on_file_done(self, filename: str, success: bool, msg: str):
        prefix = "✅" if success else "❌"
        self._append_log(f"{prefix} {filename}: {msg}")

    @pyqtSlot(str, int, int)
    def _on_item_progress(self, filename: str, step: int, total: int):
        if step <= 1:
            self._start_times[filename] = time.time()
        if step >= total:
            start = self._start_times.pop(filename, None)
            if start:
                self._elapsed_list.append(time.time() - start)
                if len(self._elapsed_list) > 20:
                    self._elapsed_list.pop(0)
        self.progress_label.setText(f"正在识别：{filename} ({step}/{total})")

    @pyqtSlot(int, int)
    def _on_all_done(self, success: int, fail: int):
        total = success + fail
        self._append_log(
            f"\n{'='*40}\n"
            f"✅ 处理完成：成功 {success} / 失败 {fail} / 总计 {total}"
        )
        self._set_ui_running(False)
        self._worker = None
        bus.history_updated.emit()
        bus.status_message.emit(f"OCR 完成：成功 {success}，失败 {fail}", 5000)

    def _on_worker_finished(self):
        """线程结束时的清理（确保 UI 恢复）"""
        if self._worker and not self._worker.isRunning():
            self._worker = None

    def _append_log(self, text: str):
        self.log_area.append(text)
        # 自动滚动到底部
        scrollbar = self.log_area.verticalScrollBar()
        if scrollbar:
            scrollbar.setValue(scrollbar.maximum())

    def _clear_log(self):
        self.log_area.clear()
