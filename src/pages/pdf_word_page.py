"""
百宝箱 - PDF 转 Word 页面
支持拖拽添加 PDF 文件、格式保留、批量转换。
"""
import os
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QListWidget, QListWidgetItem, QProgressBar, QCheckBox, QComboBox,
    QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot
from PyQt6.QtGui import QDragEnterEvent, QDropEvent

from src.modules.pdf_converter import (
    detect_pdf_type, get_pdf_page_count,
    check_paddleocr_available, get_ocr_languages,
)
from src.worker_threads import ConvertWorker
from src.config import AppConfig, get_config
from src.signals import bus


_OCR_LANG_LABELS = {
    "ch": "中文（简体/繁体/英文）",
    "en": "英文",
    "chinese_cht": "中文繁体",
    "japan": "日文",
    "korean": "韩文",
    "french": "法文",
    "german": "德文",
}


class PdfWordPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("pdfWordPage")
        self.setAcceptDrops(True)
        self._files: list[str] = []
        self._worker: ConvertWorker | None = None
        self._config = get_config()

        self._setup_ui()
        self._connect_signals()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # 广告位
        ad = QLabel("📢  广告位（预留）")
        ad.setObjectName("adBanner")
        ad.setAlignment(Qt.AlignmentFlag.AlignCenter)
        ad.setFixedHeight(44)
        layout.addWidget(ad)

        # 拖拽区
        self.drop_zone = QLabel("📄  拖拽 PDF 文件到此处，或点击选择\n支持文字型 PDF 直接转换 · 扫描型 PDF 自动 OCR 识别")
        self.drop_zone.setObjectName("dropZone")
        self.drop_zone.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.drop_zone.setFixedHeight(110)
        self.drop_zone.mousePressEvent = self._on_drop_clicked
        layout.addWidget(self.drop_zone)

        # 工具栏
        toolbar = QHBoxLayout()
        self.btn_add = QPushButton("➕ 添加 PDF")
        self.btn_add.clicked.connect(self._add_files)
        self.btn_add_fld = QPushButton("📂 批量导入")
        self.btn_add_fld.clicked.connect(self._add_folder)
        self.btn_clear = QPushButton("清空列表")
        self.btn_clear.setProperty("class", "outline-btn")
        self.btn_clear.clicked.connect(self._clear_files)
        toolbar.addWidget(self.btn_add)
        toolbar.addWidget(self.btn_add_fld)
        toolbar.addWidget(self.btn_clear)
        toolbar.addStretch()
        self.count_label = QLabel("已添加 0 个文件")
        self.count_label.setStyleSheet("color: #5A6B85;")
        toolbar.addWidget(self.count_label)
        layout.addLayout(toolbar)

        # 文件列表
        self.file_list = QListWidget()
        self.file_list.setMinimumHeight(140)
        self.file_list.setAlternatingRowColors(True)
        layout.addWidget(self.file_list)

        # 转换选项
        opts = QHBoxLayout()

        self.chk_format = QCheckBox("保留原始格式（推荐）")
        self.chk_format.setChecked(self._config.pdf_preserve_formatting)
        self.chk_format.setToolTip(
            "【pdf2docx 模式生效】\n"
            "勾选：尽可能保留原 PDF 的字体、字号、颜色、段落样式和对齐方式\n"
            "不勾选：仅提取文字内容，使用 Word 默认样式排版\n"
            "注意：仅对文字型 PDF 有效，扫描型 PDF 不受此选项影响"
        )

        self.chk_images = QCheckBox("保留图片")
        self.chk_images.setChecked(self._config.pdf_preserve_images)
        self.chk_images.setToolTip(
            "【pdf2docx 模式生效】\n"
            "勾选：将 PDF 中的图片提取到 images 子文件夹，并嵌入 Word 文档\n"
            "不勾选：忽略 PDF 中的图片，只转换文字内容\n"
            "注意：仅对文字型 PDF 有效，扫描型 PDF 不受此选项影响"
        )

        self.chk_force_ocr = QCheckBox("强制 OCR 识别")
        self.chk_force_ocr.setToolTip(
            "【OCR 模式】\n"
            "勾选：无论 PDF 是否包含文字层，一律渲染为图片后用 Tesseract OCR 识别\n"
            "不勾选：自动检测 PDF 类型，文字型用 pdf2docx 直接转换，扫描型才用 OCR\n"
            "适用场景：混合型 PDF（部分页无文字层）、排版复杂导致 pdf2docx 效果不佳"
        )

        self.chk_layout = QCheckBox("保留格式排版")
        self.chk_layout.setToolTip(
            "【OCR 模式生效】\n"
            "勾选：对 OCR 识别结果进行排版分析（分栏检测、表格识别、段落归类、\n"
            "　　　标题/正文字号区分、粗体斜体保留、对齐方式还原）\n"
            "不勾选：纯文本提取模式，逐页 OCR 识别文字后直接输出，不做排版处理\n"
            "　　　速度更快，适合只需提取文字内容的场景"
        )
        self.chk_layout.setChecked(True)

        opts.addWidget(self.chk_format)
        opts.addWidget(self.chk_images)
        opts.addWidget(self.chk_force_ocr)
        opts.addWidget(self.chk_layout)
        opts.addStretch()
        layout.addLayout(opts)

        # OCR 语言状态
        self.ocr_warning = QLabel()
        self.ocr_warning.setWordWrap(True)
        self.ocr_warning.setVisible(False)
        layout.addWidget(self.ocr_warning)

        # OCR 语言选择
        ocr_lang_layout = QHBoxLayout()
        ocr_lang_layout.addWidget(QLabel("OCR 识别语言:"))
        self.cmb_ocr_lang = QComboBox()
        self.cmb_ocr_lang.setFixedWidth(200)
        ocr_lang_layout.addWidget(self.cmb_ocr_lang)
        ocr_lang_layout.addStretch()
        layout.addLayout(ocr_lang_layout)

        # 刷新 OCR 语言列表
        self._refresh_ocr_languages()

        # 提示
        hint = QLabel("💡 转换后的 .docx 文件将保存到桌面「百宝箱输出」文件夹\n💡 扫描型 PDF 使用 PaddleOCR 深度学习引擎识别中文\n💡 取消「保留格式排版」可跳过排版分析，仅提取纯文字，速度更快")
        hint.setStyleSheet("color: #94A3B8; font-size: 12px;")
        layout.addWidget(hint)

        # 操作按钮
        action = QHBoxLayout()
        action.addStretch()
        self.btn_convert = QPushButton("🚀 开始转换")
        self.btn_convert.setFixedHeight(40)
        self.btn_convert.setFixedWidth(140)
        self.btn_convert.clicked.connect(self._start_convert)
        self.btn_convert.setEnabled(False)
        self.btn_cancel = QPushButton("停止")
        self.btn_cancel.setFixedHeight(40)
        self.btn_cancel.setProperty("class", "danger-btn")
        self.btn_cancel.clicked.connect(self._cancel)
        self.btn_cancel.setVisible(False)
        action.addWidget(self.btn_cancel)
        action.addWidget(self.btn_convert)
        layout.addLayout(action)

        # 进度
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        layout.addWidget(self.progress_bar)

        # === 实时进度详情（页级进度） ===
        self.progress_detail = QLabel("")
        self.progress_detail.setStyleSheet("color: #3B9EFF; font-size: 12px; font-weight: bold;")
        self.progress_detail.setVisible(False)
        self.progress_detail.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.progress_detail)

        # 日志
        self.log_output = QLabel("等待添加文件...")
        self.log_output.setObjectName("logOutput")
        self.log_output.setWordWrap(True)
        self.log_output.setMinimumHeight(80)
        self.log_output.setAlignment(Qt.AlignmentFlag.AlignTop)
        layout.addWidget(self.log_output)

    def _connect_signals(self):
        bus.convert_all_done.connect(self._on_all_done)

    # ---- 文件操作 ----
    def _add_files(self):
        files, _ = QFileDialog.getOpenFileNames(
            self, "选择 PDF 文件", "", "PDF 文件 (*.pdf);;所有文件 (*.*)"
        )
        self._append_files(files)

    def _add_folder(self):
        folder = QFileDialog.getExistingDirectory(self, "选择包含 PDF 的文件夹")
        if folder:
            from pathlib import Path
            files = [str(p) for p in Path(folder).glob("*.pdf")]
            if files:
                self._append_files(files)
            else:
                QMessageBox.information(self, "提示", "所选文件夹中没有 PDF 文件。")

    def _append_files(self, files: list[str]):
        new_count = 0
        for fp in files:
            if fp not in self._files and fp.lower().endswith('.pdf'):
                self._files.append(fp)
                # 检测 PDF 类型
                pdf_type, text_p, total_p = detect_pdf_type(fp)
                type_label = {
                    "text": f"📝 文字型 ({total_p}页)",
                    "scanned": f"🖼️ 扫描型 ({total_p}页·需OCR)",
                    "mixed": f"📝🖼️ 混合型 ({text_p}/{total_p}页有文字)",
                }.get(pdf_type, f"{total_p}页")
                item = QListWidgetItem(f"📄 {os.path.basename(fp)}  [{type_label}]")
                self.file_list.addItem(item)
                new_count += 1
        self._update_count()
        self.btn_convert.setEnabled(len(self._files) > 0)
        self._log(f"✅ 添加了 {new_count} 个 PDF 文件")

    def _clear_files(self):
        self._files.clear()
        self.file_list.clear()
        self._update_count()
        self.btn_convert.setEnabled(False)
        self._log("🗑️ 已清空文件列表")

    def _update_count(self):
        self.count_label.setText(f"已添加 {len(self._files)} 个文件")

    def _refresh_ocr_languages(self):
        """刷新 OCR 语言列表和状态提示"""
        available, msg = check_paddleocr_available()
        langs = get_ocr_languages()

        # 更新下拉框：显示中文标签，data 保存实际语言代码
        self.cmb_ocr_lang.clear()
        if langs:
            for lang in langs:
                label = _OCR_LANG_LABELS.get(lang, lang)
                self.cmb_ocr_lang.addItem(label, userData=lang)
            saved_lang = self._config.pdf_ocr_lang if hasattr(self._config, 'pdf_ocr_lang') else "ch"
            self._set_ocr_lang_by_code(saved_lang)
        else:
            self.cmb_ocr_lang.addItem(_OCR_LANG_LABELS.get("ch", "ch"), userData="ch")

        # PaddleOCR 不可用时显示警告
        if not available:
            self.ocr_warning.setText(f"⚠️ {msg}")
            self.ocr_warning.setStyleSheet(
                "color: #FF9800; background: #FFF3E0; border: 1px solid #FFE0B2; "
                "padding: 10px; border-radius: 6px; font-size: 12px;"
            )
            self.ocr_warning.setVisible(True)
        else:
            self.ocr_warning.setVisible(False)

    def _set_ocr_lang_by_code(self, lang_code: str):
        """根据语言代码设置下拉框当前选中项"""
        for i in range(self.cmb_ocr_lang.count()):
            if self.cmb_ocr_lang.itemData(i) == lang_code:
                self.cmb_ocr_lang.setCurrentIndex(i)
                return
        # 回退到默认中文
        for i in range(self.cmb_ocr_lang.count()):
            if self.cmb_ocr_lang.itemData(i) == "ch":
                self.cmb_ocr_lang.setCurrentIndex(i)
                return

    def _on_drop_clicked(self, e):
        self._add_files()

    def dragEnterEvent(self, event: QDragEnterEvent):
        if event.mimeData().hasUrls():
            event.acceptProposedAction()

    def dropEvent(self, event: QDropEvent):
        files = [url.toLocalFile() for url in event.mimeData().urls()
                 if url.toLocalFile().lower().endswith('.pdf')]
        if files:
            self._append_files(files)

    # ---- 转换 ----
    def _start_convert(self):
        if not self._files or (self._worker and self._worker.isRunning()):
            return

        ocr_lang = self.cmb_ocr_lang.currentData() or "ch"

        self._worker = ConvertWorker(
            files=self._files.copy(),
            preserve_fmt=self.chk_format.isChecked(),
            preserve_img=self.chk_images.isChecked(),
            output_dir=self._config.get_output_dir(),
            force_ocr=self.chk_force_ocr.isChecked(),
            ocr_lang=ocr_lang,
            preserve_layout=self.chk_layout.isChecked(),
        )

        # 持久化
        self._config.pdf_ocr_lang = ocr_lang
        self._config.pdf_preserve_formatting = self.chk_format.isChecked()
        self._config.pdf_preserve_images = self.chk_images.isChecked()
        self._config.save()
        self._worker.file_progress.connect(self._on_progress)
        self._worker.file_done.connect(self._on_file_done)
        self._worker.item_progress.connect(self._on_item_progress)

        self.btn_convert.setVisible(False)
        self.btn_cancel.setVisible(True)
        self.progress_bar.setVisible(True)
        self.progress_detail.setVisible(True)
        # 预计算总页数作为进度条最大值（与详情显示的页级进度对应）
        total_pages = 0
        for fp in self._files:
            try:
                pc = get_pdf_page_count(fp)
                total_pages += (pc if pc > 0 else 1)
            except Exception:
                total_pages += 1
        self.progress_bar.setMaximum(total_pages)
        self._log(f"🚀 开始转换 {len(self._files)} 个 PDF 文件（共 {total_pages} 页）")
        self._worker.start()

    def _cancel(self):
        if self._worker and self._worker.isRunning():
            self._worker.cancel()         # 协作式取消，安全退出
            self._worker.wait(5000)       # 等待线程自然结束
            self._log("⛔ 转换已取消")
        self._reset_ui()

    @pyqtSlot(int, int)
    def _on_progress(self, current: int, total: int):
        self.progress_bar.setValue(current)

    @pyqtSlot(str, int, int)
    def _on_item_progress(self, filename: str, current: int, total: int):
        """PDF 页级实时进度（OCR 逐页识别 / pdf2docx 转换）"""
        if current >= total:
            self.progress_detail.setText(f"✅ {filename} 完成")
        elif total <= 1:
            # pdf2docx 黑盒模式：不显示页数，只显示正在转换
            self.progress_detail.setText(f"⏳ 正在转换: {filename}")
        else:
            self.progress_detail.setText(f"⏳ 正在转换: {filename}  第{current}/{total}页")

    @pyqtSlot(str, bool, str)
    def _on_file_done(self, filename: str, success: bool, msg: str):
        icon = "✅" if success else "❌"
        self._log(f"{icon} {filename}: {msg}")

    @pyqtSlot(int, int)
    def _on_all_done(self, success: int, fail: int):
        self._log(f"\n🏁 转换完成! 成功: {success}, 失败: {fail}")
        bus.history_updated.emit()
        self._reset_ui()

    def _reset_ui(self):
        self.btn_convert.setVisible(True)
        self.btn_cancel.setVisible(False)
        self.progress_bar.setVisible(False)
        self.progress_detail.setVisible(False)
        self._worker = None

    def _log(self, text: str):
        current = self.log_output.text() or ""
        self.log_output.setText(current + "\n" + text)
