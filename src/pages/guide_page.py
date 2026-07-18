"""
百宝箱 - 使用指南页面
包含安装指南、各功能操作说明、FAQ。
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame,
    QScrollArea, QTabWidget
)
from PyQt6.QtCore import Qt


class GuidePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("guidePage")
        self._setup_ui()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)

        title = QLabel("📖  使用指南")
        title.setObjectName("pageTitle")
        layout.addWidget(title)

        tabs = QTabWidget()
        tabs.addTab(self._build_install_tab(), "安装指南")
        tabs.addTab(self._build_features_tab(), "功能操作")
        tabs.addTab(self._build_faq_tab(), "常见问题")
        layout.addWidget(tabs)

    def _build_install_tab(self) -> QWidget:
        """安装指南标签页"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        steps = [
            ("系统要求", "Windows 10 / 11（64位），内存 ≥ 4GB，磁盘空间 ≥ 500MB。\n无需联网即可使用全部本地功能。"),
            ("下载安装包", "从官方渠道下载 BaibaoBOX_Setup.exe 安装包。\n安装包大小约 100MB，包含所有依赖和运行环境。"),
            ("运行安装向导", "双击安装包，按照向导提示完成安装。\n可选择自定义安装目录，建议使用默认路径。"),
            ("PaddleOCR 自动下载（首次使用扫描型PDF时）", "首次使用 OCR 识别扫描型 PDF 时，PaddleOCR 会自动下载中文识别模型（约 100MB）。\n请保持网络连接，下载完成后即可离线使用。\n无需额外安装任何 OCR 引擎，开箱即用。"),
            ("启动百宝箱", "桌面双击「百宝箱」图标即可启动。\n首次启动会在桌面创建「百宝箱输出」文件夹，所有处理结果默认保存于此。"),
        ]

        for i, (title_text, desc) in enumerate(steps, 1):
            card = QFrame()
            card.setProperty("class", "card")
            cl = QHBoxLayout(card)
            num = QLabel(f"{i}")
            num.setFixedSize(32, 32)
            num.setStyleSheet(
                "background: #1877F2; color: white; border-radius: 16px; "
                "font-size: 16px; font-weight: bold;"
            )
            num.setAlignment(Qt.AlignmentFlag.AlignCenter)
            cl.addWidget(num)

            text_block = QVBoxLayout()
            step_title = QLabel(title_text)
            step_title.setStyleSheet("font-size: 14px; font-weight: bold;")
            step_desc = QLabel(desc)
            step_desc.setStyleSheet("color: #5A6B85; font-size: 13px;")
            step_desc.setWordWrap(True)
            text_block.addWidget(step_title)
            text_block.addWidget(step_desc)
            cl.addLayout(text_block)
            cl.addStretch()
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    def _build_features_tab(self) -> QWidget:
        """功能操作标签页"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(16)

        features = [
            ("📷 图片批量压缩", """操作步骤：
1. 点击「添加文件」选择图片，或直接拖拽图片到窗口中
2. 选择压缩模式：
   · 按目标大小：设置期望的文件大小（如 500KB），算法自动逼近
   · 按质量压缩：拖动滑块选择 5%-100% 的压缩质量
3. 点击「开始压缩」，等待处理完成
4. 压缩后的文件自动保存到「百宝箱输出」文件夹

支持的格式：JPG、JPEG、PNG、BMP、WebP、TIFF
注意事项：PNG 带透明通道的图片会转换为 JPG 格式（无透明）"""),

            ("📄 PDF 转 Word", """操作步骤：
1. 点击「添加 PDF」选择文件，或拖拽 PDF 到窗口
2. 文件列表会显示 PDF 类型：文字型/扫描型/混合型
3. 勾选「保留原始格式」以尽可能保持排版（仅文字型生效）
4. 勾选「保留图片」以保留文档中的图片（仅文字型生效）
5. 扫描型 PDF 可勾选「强制 OCR 识别」
6. 点击「开始转换」
7. 转换完成后，.docx 文件自动保存到「百宝箱输出」文件夹

支持类型：
· 文字型 PDF：直接转换，速度快，格式保留好
· 扫描型 PDF：自动使用 PaddleOCR 深度学习引擎识别
· 混合型 PDF：文字页直接转换，图片页 OCR 识别
注意事项：OCR 识别速度较慢，质量取决于原图清晰度"""),
        ]

        for title_text, desc in features:
            card = QFrame()
            card.setProperty("class", "card")
            cl = QVBoxLayout(card)
            ft = QLabel(title_text)
            ft.setStyleSheet("font-size: 15px; font-weight: bold;")
            fd = QLabel(desc)
            fd.setStyleSheet("color: #5A6B85; font-size: 13px;")
            fd.setWordWrap(True)
            cl.addWidget(ft)
            cl.addWidget(fd)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll

    def _build_faq_tab(self) -> QWidget:
        """常见问题标签页"""
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet("QScrollArea { border: none; }")

        w = QWidget()
        lay = QVBoxLayout(w)
        lay.setSpacing(12)

        faqs = [
            ("Q: 百宝箱会收集我的数据吗？",
             "A: 不会。本软件所有功能均在本地电脑上运行，不会上传任何文件到网络。图片压缩、PDF 转换、OCR 识别、Excel 合并全部在本地完成。唯一的网络请求是预留的广告位（默认关闭），且仅在您主动配置后才生效。"),
            ("Q: 为什么压缩后的图片比目标大小大？",
             "A: 算法使用二分搜索逼近目标大小，通常误差在 ±20KB 以内。如果原始图片非常大（如 10MB+），可能需要多次迭代。您也可以尝试「按质量压缩」模式手动控制。"),
            ("Q: PDF 转 Word 后还是图片、无法编辑怎么办？",
             "A: 这说明您的 PDF 是扫描型（图片型），文字实际是图片的一部分。本软件会自动检测并切换为 OCR 识别模式（使用 PaddleOCR 深度学习引擎）。如需强制 OCR，可勾选「强制 OCR 识别」重试。首次使用 OCR 时会自动下载模型（约 100MB），请保持网络连接。"),
            ("Q: 屏幕录制报错「找不到 FFmpeg」怎么解决？",
             "A: 屏幕录制功能已移除。如需使用请通过源码构建。"),
            ("Q: 可以自定义输出路径吗？",
             "A: 可以。在「系统设置」页面中修改默认输出目录，或在各功能的输出路径处直接更改。"),
            ("Q: 支持哪些 Windows 版本？",
             "A: Windows 10 和 Windows 11（64位）。32 位系统和 Windows 7/8 未经过测试，可能无法正常运行。"),
        ]

        for q, a in faqs:
            card = QFrame()
            card.setProperty("class", "card")
            cl = QVBoxLayout(card)
            ql = QLabel(q)
            ql.setStyleSheet("font-size: 13px; font-weight: bold; color: #1877F2;")
            al = QLabel(a)
            al.setStyleSheet("font-size: 13px; color: #5A6B85;")
            al.setWordWrap(True)
            cl.addWidget(ql)
            cl.addWidget(al)
            lay.addWidget(card)

        lay.addStretch()
        scroll.setWidget(w)
        return scroll
