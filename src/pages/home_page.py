"""
百宝箱 - 首页仪表盘
显示统计面板、快捷入口、最近记录。
"""
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QFrame, QScrollArea,
    QListWidget, QListWidgetItem
)
from PyQt6.QtCore import Qt, pyqtSlot
from datetime import datetime

from src.database import get_summary_stats, get_recent_compress, get_recent_convert, get_recent_records
from src.signals import bus


class HomePage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("homePage")
        self.stat_value_labels: dict[str, QLabel] = {}  # 持有值 Label 引用
        self._setup_ui()
        self._connect_signals()
        self.refresh()

    def _setup_ui(self):
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(16)

        # === 统计卡片行 ===
        self.stats_layout = QHBoxLayout()
        self.stats_layout.setSpacing(12)

        self.stat_compress = self._make_stat_card("📷", "图片压缩次数", "0")
        self.stat_convert = self._make_stat_card("📄", "PDF 转换次数", "0")
        self.stat_record = self._make_stat_card("🎬", "屏幕录制次数", "0")
        self.stat_saved = self._make_stat_card("💾", "累计节省空间", "0 MB")

        self.stats_layout.addWidget(self.stat_compress)
        self.stats_layout.addWidget(self.stat_convert)
        self.stats_layout.addWidget(self.stat_record)
        self.stats_layout.addWidget(self.stat_saved)
        layout.addLayout(self.stats_layout)

        # === 欢迎横幅 ===
        banner = QFrame()
        banner.setObjectName("welcomeBanner")
        banner.setStyleSheet(
            "#welcomeBanner { background: qlineargradient(x1:0,y1:0,x2:1,y2:1,"
            "stop:0 #1877F2, stop:1 #0C5BC4); border-radius: 12px; padding: 24px; }"
        )
        banner_layout = QHBoxLayout(banner)
        text_block = QVBoxLayout()
        title = QLabel("欢迎使用百宝箱")
        title.setStyleSheet("font-size: 20px; font-weight: bold; color: #FFFFFF;")
        subtitle = QLabel("一站式图片压缩 · PDF 转 Word · 屏幕录制，全部本地处理，数据不上传")
        subtitle.setStyleSheet("font-size: 13px; color: rgba(255,255,255,0.85);")
        text_block.addWidget(title)
        text_block.addWidget(subtitle)

        hint = QLabel("🔒 仅本地运行 · 数据不上传")
        hint.setStyleSheet(
            "background: rgba(255,255,255,0.15); color: #FFFFFF; padding: 6px 14px; "
            "border-radius: 16px; font-size: 12px;"
        )
        hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        banner_layout.addLayout(text_block)
        banner_layout.addStretch()
        banner_layout.addWidget(hint, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(banner)

        # === 快捷入口 ===
        quick_label = QLabel("快捷功能")
        quick_label.setObjectName("pageTitle")
        layout.addWidget(quick_label)

        quick_layout = QHBoxLayout()
        quick_layout.setSpacing(12)
        cards_data = [
            ("📷", "图片批量压缩", "支持按大小/质量压缩，批量处理，专为政府网站上传优化", "compress"),
            ("📄", "PDF 转 Word", "保留原始格式，支持多页文档转换，一键输出 .docx", "pdf2word"),
            ("🎬", "屏幕录制", "全屏/区域录制，H.264 编码，输出 MP4 格式", "recorder"),
        ]
        self.quick_cards = []
        for icon, title_text, desc, target in cards_data:
            card = self._make_quick_card(icon, title_text, desc, target)
            quick_layout.addWidget(card)
            self.quick_cards.append(card)
        layout.addLayout(quick_layout)

        # === 最近记录 ===
        recent_label = QLabel("最近操作记录")
        recent_label.setObjectName("pageTitle")
        layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(150)
        self.recent_list.setAlternatingRowColors(True)
        layout.addWidget(self.recent_list)

        layout.addStretch()

    def _make_stat_card(self, icon: str, label: str, value: str) -> QFrame:
        card = QFrame()
        card.setObjectName("stat-card")
        card.setProperty("class", "stat-card")
        lay = QVBoxLayout(card)
        lay.setSpacing(6)
        icon_lbl = QLabel(icon)
        icon_lbl.setStyleSheet("font-size: 24px;")
        val_lbl = QLabel(value)
        val_lbl.setProperty("class", "stat-value")
        lbl = QLabel(label)
        lbl.setProperty("class", "stat-label")
        lay.addWidget(icon_lbl)
        lay.addWidget(val_lbl)
        lay.addWidget(lbl)
        # 持有值 Label 引用，refresh() 时直接更新
        self.stat_value_labels[label] = val_lbl
        return card

    def _make_quick_card(self, icon: str, title_text: str, desc: str, target: str) -> QFrame:
        card = QFrame()
        card.setProperty("class", "feature-card")
        card.setCursor(Qt.CursorShape.PointingHandCursor)
        card.mousePressEvent = lambda e, t=target: bus.navigate_to.emit(t)
        lay = QVBoxLayout(card)
        lay.setSpacing(8)
        icon_lbl = QLabel(f"{icon}  {title_text}")
        icon_lbl.setStyleSheet("font-size: 16px; font-weight: bold;")
        desc_lbl = QLabel(desc)
        desc_lbl.setStyleSheet("font-size: 12px; color: #5A6B85;")
        desc_lbl.setWordWrap(True)
        lay.addWidget(icon_lbl)
        lay.addWidget(desc_lbl)
        lay.addStretch()
        return card

    def _connect_signals(self):
        bus.history_updated.connect(self.refresh)

    @pyqtSlot()
    def refresh(self):
        """刷新首页数据"""
        # 更新统计值（直接使用持有的 Label 引用）
        try:
            stats = get_summary_stats()
            self.stat_value_labels.get("图片压缩次数", QLabel("0")).setText(str(stats["total_compress"]))
            self.stat_value_labels.get("PDF 转换次数", QLabel("0")).setText(str(stats["total_convert"]))
            self.stat_value_labels.get("屏幕录制次数", QLabel("0")).setText(str(stats["total_record"]))
            self.stat_value_labels.get("累计节省空间", QLabel("0")).setText(f"{stats['saved_mb']} MB")
        except Exception:
            pass

        # 加载最近记录
        self.recent_list.clear()
        try:
            items = []
            for c in get_recent_compress(5):
                ts = c["created_at"][:16].replace("T", " ")
                items.append((ts, f"[图片压缩] {c['file_name']} - {c['orig_size_kb']:.0f}KB → {c['final_size_kb']:.0f}KB"))
            for c in get_recent_convert(3):
                ts = c["created_at"][:16].replace("T", " ")
                items.append((ts, f"[PDF转换] {c['file_name']} → .docx"))
            for r in get_recent_records(3):
                ts = r["created_at"][:16].replace("T", " ")
                items.append((ts, f"[屏幕录制] {r['file_name']} - {r['duration_sec']}秒"))
            items.sort(key=lambda x: x[0], reverse=True)
            for ts, text in items[:15]:
                item = QListWidgetItem(f"{ts}  {text}")
                self.recent_list.addItem(item)
        except Exception:
            pass
