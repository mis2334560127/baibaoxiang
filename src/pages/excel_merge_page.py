"""
百宝箱 - 批量合并 Excel 页面
支持直接添加 Excel 文件，也支持从压缩包中提取 Excel → 合并到单个文件
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QProgressBar, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from src.modules.excel_merger import ALL_SUPPORTED_EXTS
from src.worker_threads import ExcelMergeWorker
from src.config import get_config
from src.signals import bus


class ExcelMergePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("excelMergePage")
        self.setAcceptDrops(True)
        self._files: list[str] = []
        self._worker: ExcelMergeWorker | None = None
        self._config = get_config()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # === 拖拽上传区 ===
        self.drop_zone = QLabel(
            "📦  拖拽文件到此处，或点击选择文件\n"
            "支持 .xlsx / .xls / .xlsm 直接合并\n"
            "也支持 .zip / .rar / .7z（自动提取压缩包内的 Excel）"
        )
        self.drop_zone.setObjectName("dropZone")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setFixedHeight(120)
        self.drop_zone.mousePressEvent = self._on_drop_clicked
        layout.addWidget(self.drop_zone)

        # === 工具栏 ===
        toolbar = QHBoxLayout()
        toolbar.setSpacing(10)

        self.btn_add = QPushButton("📦 添加文件")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setProperty("class", "outline-btn")
        self.btn_clear.clicked.connect(self._clear_files)

        toolbar.addWidget(self.btn_add)
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

        # === 输出路径 ===
        out_layout = QHBoxLayout()
        out_layout.setSpacing(10)
        out_layout.addWidget(QLabel("输出路径："))
        self.out_path_label = QLabel("（点击右侧按钮选择保存位置）")
        self.out_path_label.setStyleSheet("color: #5A6B85;")
        self.out_path_label.setWordWrap(True)
        out_layout.addWidget(self.out_path_label, stretch=1)
        self.btn_output = QPushButton("📁 选择输出位置")
        self.btn_output.clicked.connect(self._choose_output)
        out_layout.addWidget(self.btn_output)
        layout.addLayout(out_layout)

        # === 操作按钮 ===
        action_layout = QHBoxLayout()
        action_layout.addStretch()

        self.btn_merge = QPushButton("🚀 开始合并")
        self.btn_merge.setFixedHeight(40)
        self.btn_merge.setFixedWidth(140)
        self.btn_merge.clicked.connect(self._start_merge)
        self.btn_merge.setEnabled(False)

        self.btn_cancel = QPushButton("停止")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setProperty("class", "danger-btn")
        self.btn_cancel.clicked.connect(self._cancel_merge)
        self.btn_cancel.setVisible(False)

        action_layout.addWidget(self.btn_cancel)
        action_layout.addWidget(self.btn_merge)
        layout.addLayout(action_layout)

        # === 整体进度 ===
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # === 日志输出 ===
        self.log_output = QLabel("等待添加文件...")
        self.log_output.setObjectName("logOutput")
        self.log_output.setWordWrap(True)
        self.log_output.setMinimumHeight(100)
        self.log_output.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.log_output)

    def _connect_signals(self):
        bus.merge_all_done.connect(self._on_all_done)

    # ---- 文件操作 ----

    def _add_files(self):
        filter_str = "所有支持格式 (*.xlsx *.xls *.xlsm *.zip *.rar *.7z);;Excel 文件 (*.xlsx *.xls *.xlsm);;压缩包 (*.zip *.rar *.7z);;所有文件 (*.*)"
        files, _ = QFileDialog.getOpenFileNames(self, "选择压缩包", "", filter_str)
        if files:
            self._append_files(files)

    def _append_files(self, files: list[str]):
        new_count = 0
        for fp in files:
            ext = os.path.splitext(fp)[1].lower()
            if ext in ALL_SUPPORTED_EXTS and fp not in self._files:
                self._files.append(fp)
                size_mb = os.path.getsize(fp) / (1024 * 1024)
                self.file_list.addItem(
                    QListWidgetItem(f"{os.path.basename(fp)}  ({size_mb:.1f} MB)")
                )
                new_count += 1
        self._update_file_count()
        self.btn_merge.setEnabled(len(self._files) > 0)
        if new_count > 0:
            self._append_log(f"✅ 添加了 {new_count} 个文件")

    def _clear_files(self):
        self._files.clear()
        self.file_list.clear()
        self._update_file_count()
        self.btn_merge.setEnabled(False)
        self._append_log("🗑️ 已清空文件列表")

    def _update_file_count(self):
        total_mb = sum(os.path.getsize(f) / (1024 * 1024) for f in self._files)
        self.file_count_label.setText(
            f"已添加 {len(self._files)} 个文件  ({total_mb:.1f} MB)"
        )

    def _choose_output(self):
        path, _ = QFileDialog.getSaveFileName(
            self, "保存合并后的 Excel", "合并数据.xlsx",
            "Excel 文件 (*.xlsx)"
        )
        if path:
            self.out_path_label.setText(path)
            self.out_path_label.setStyleSheet("color: #333; font-weight: bold;")

    # ---- 拖拽支持 ----

    _drop_zone_orig_style = ""

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
            if not self._drop_zone_orig_style:
                self._drop_zone_orig_style = self.drop_zone.styleSheet()
            self.drop_zone.setStyleSheet(
                "#dropZone { background: #E8F1FF; border-color: #1877F2; color: #1877F2; "
                "border: 2px dashed #1877F2; border-radius: 12px; font-size: 14px; }"
            )

    def dragLeaveEvent(self, event):
        self.drop_zone.setStyleSheet(self._drop_zone_orig_style)

    def dropEvent(self, event: QDropEvent):
        self.drop_zone.setStyleSheet(self._drop_zone_orig_style)
        files = []
        for url in event.mimeData().urls():
            path = url.toLocalFile()
            if os.path.isfile(path) and os.path.splitext(path)[1].lower() in ALL_SUPPORTED_EXTS:
                files.append(path)
        if files:
            self._append_files(files)

    def _on_drop_clicked(self, event):
        self._add_files()

    # ---- 合并操作 ----

    def _start_merge(self):
        if not self._files:
            QMessageBox.warning(self, "提示", "请先添加 Excel 或压缩包文件。")
            return

        output_path = self.out_path_label.text()
        if not output_path or output_path.startswith("（"):
            QMessageBox.warning(self, "提示", "请先选择输出文件的保存位置。")
            return

        if not output_path.lower().endswith('.xlsx'):
            output_path += '.xlsx'

        self._set_ui_running(True)
        self.progress_bar.setVisible(True)
        self.progress_bar.setMaximum(len(self._files))
        self.progress_bar.setValue(0)
        self._append_log(f"🚀 开始处理 {len(self._files)} 个文件...")
        self._append_log(f"📤 输出文件：{output_path}")

        self._worker = ExcelMergeWorker(self._files, output_path)
        self._worker.file_progress.connect(self._on_file_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.start()

    def _cancel_merge(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()
            self._append_log("⏹️ 正在停止...")
            self.btn_cancel.setEnabled(False)

    @pyqtSlot(int, int)
    def _on_file_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)
        self.progress_bar.setMaximum(total)

    @pyqtSlot(str, bool, str)
    def _on_file_done(self, filename: str, success: bool, msg: str):
        icon = "✅" if success else "❌"
        self._append_log(f"{icon} {filename}：{msg}")

    @pyqtSlot(int, int)
    def _on_all_done(self, success: int, fail: int):
        self._set_ui_running(False)
        total = success + fail
        if fail == 0:
            self._append_log(f"🎉 全部完成！成功处理 {success} 个文件。")
            QMessageBox.information(self, "完成", f"成功合并 {success} 个文件中的数据！\n\n输出文件：{self.out_path_label.text()}")
        else:
            self._append_log(f"⚠️ 处理完成：成功 {success} 个，失败 {fail} 个。")

    # ---- UI 辅助 ----

    def _set_ui_running(self, running: bool):
        self.btn_merge.setVisible(not running)
        self.btn_cancel.setVisible(running)
        self.btn_add.setEnabled(not running)
        self.btn_clear.setEnabled(not running)
        self.btn_output.setEnabled(not running)
        self.drop_zone.setVisible(not running)
        if not running:
            self.btn_cancel.setEnabled(True)
            self.progress_bar.setVisible(False)

    def _append_log(self, text: str):
        current = self.log_output.text()
        if current == "等待添加压缩包..." or current == "等待添加文件...":
            current = ""
        # 限制日志行数，避免过多
        lines = current.split("\n") if current else []
        lines.append(text)
        if len(lines) > 50:
            lines = lines[-50:]
        self.log_output.setText("\n".join(lines))
