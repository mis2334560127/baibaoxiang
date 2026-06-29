"""
百宝箱 - 屏幕录制页面
支持全屏/区域录制、帧率和编码器设置、录制计时。
"""
import os
import time
from datetime import datetime
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QFrame,
    QSpinBox, QComboBox, QListWidget, QListWidgetItem, QFileDialog, QMessageBox
)
from PyQt6.QtCore import Qt, pyqtSlot, QTimer

from src.worker_threads import RecordWorker
from src.config import AppConfig, get_config
from src.signals import bus
from src.database import get_recent_records
from src.modules.screen_recorder import _find_ffmpeg


class RecorderPage(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setObjectName("recorderPage")
        self._config = get_config()
        self._worker: RecordWorker | None = None
        self._is_recording = False
        self._start_time = 0
        self._timer = QTimer()
        self._timer.timeout.connect(self._update_timer)

        self._setup_ui()
        self._load_recent()

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

        # === 录制控制台 ===
        console = QFrame()
        console.setProperty("class", "card")
        console_lay = QVBoxLayout(console)
        console_lay.setSpacing(16)

        # 参数行
        params = QHBoxLayout()
        params.setSpacing(16)

        # FPS
        params.addWidget(QLabel("帧率:"))
        self.spin_fps = QSpinBox()
        self.spin_fps.setRange(5, 60)
        self.spin_fps.setValue(self._config.record_fps)
        self.spin_fps.setSuffix(" FPS")
        params.addWidget(self.spin_fps)

        # 编码器
        params.addWidget(QLabel("编码器:"))
        self.combo_codec = QComboBox()
        self.combo_codec.addItem("H.264 (推荐)", "libx264")
        self.combo_codec.addItem("MPEG-4", "mpeg4")
        params.addWidget(self.combo_codec)

        # 格式
        params.addWidget(QLabel("格式:"))
        self.combo_fmt = QComboBox()
        self.combo_fmt.addItem("MP4", "mp4")
        self.combo_fmt.addItem("AVI", "avi")
        params.addWidget(self.combo_fmt)

        # 录制模式
        params.addWidget(QLabel("模式:"))
        self.combo_mode = QComboBox()
        self.combo_mode.addItem("全屏录制", "full")
        self.combo_mode.addItem("区域录制（需先选择）", "region")
        params.addWidget(self.combo_mode)

        params.addStretch()
        console_lay.addLayout(params)

        # 输出路径
        path_row = QHBoxLayout()
        path_row.addWidget(QLabel("输出路径:"))
        self.output_dir_label = QLabel(self._config.get_output_dir())
        self.output_dir_label.setStyleSheet("color: #5A6B85; font-size: 12px;")
        self.btn_change_dir = QPushButton("更改")
        self.btn_change_dir.setFixedWidth(60)
        self.btn_change_dir.clicked.connect(self._change_output_dir)
        path_row.addWidget(self.output_dir_label)
        path_row.addWidget(self.btn_change_dir)
        path_row.addStretch()
        console_lay.addLayout(path_row)

        # 计时器 + 控制按钮
        center_row = QHBoxLayout()
        center_row.addStretch()

        self.timer_label = QLabel("00:00:00")
        self.timer_label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #1a2640; "
            "font-family: 'Consolas', monospace;")
        center_row.addWidget(self.timer_label)
        center_row.addStretch()

        console_lay.addLayout(center_row)

        # 按钮行
        btn_row = QHBoxLayout()
        btn_row.addStretch()

        self.btn_start = QPushButton("🔴 开始录制")
        self.btn_start.setFixedSize(140, 42)
        self.btn_start.clicked.connect(self._toggle_recording)

        self.btn_pause = QPushButton("⏸️ 暂停")
        self.btn_pause.setFixedSize(100, 42)
        self.btn_pause.setProperty("class", "secondary-btn")
        self.btn_pause.setVisible(False)

        self.btn_stop = QPushButton("⏹️ 停止")
        self.btn_stop.setFixedSize(100, 42)
        self.btn_stop.setProperty("class", "danger-btn")
        self.btn_stop.setVisible(False)
        self.btn_stop.clicked.connect(self._stop_recording)

        btn_row.addWidget(self.btn_pause)
        btn_row.addWidget(self.btn_stop)
        btn_row.addWidget(self.btn_start)
        console_lay.addLayout(btn_row)

        layout.addWidget(console)

        # === 状态提示 ===
        self.status_label = QLabel("准备就绪，点击「开始录制」即可全屏录制")
        self.status_label.setStyleSheet("color: #5A6B85; font-size: 12px;")
        self.status_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(self.status_label)

        # === 最近录制 ===
        recent_label = QLabel("最近录屏文件")
        recent_label.setObjectName("pageTitle")
        layout.addWidget(recent_label)

        self.recent_list = QListWidget()
        self.recent_list.setMinimumHeight(120)
        self.recent_list.setAlternatingRowColors(True)
        self.recent_list.itemDoubleClicked.connect(self._open_record_file)
        layout.addWidget(self.recent_list)

        # 提示
        hint = QLabel("💡 录制文件保存为 H.264 MP4，可直接在任意播放器中打开。需要 FFmpeg 支持。")
        hint.setStyleSheet("color: #94A3B8; font-size: 11px;")
        layout.addWidget(hint)

    # ---- 录制控制 ----
    def _toggle_recording(self):
        if self._is_recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        if self._worker and self._worker.isRunning():
            return

        # 验证 FFmpeg
        ffmpeg_path = self._config.ffmpeg_path or ""
        found = _find_ffmpeg(ffmpeg_path)
        if not found:
            QMessageBox.critical(
                self, "FFmpeg 未找到",
                "屏幕录制需要 FFmpeg 来编码视频，但未在系统中找到它。\n\n"
                "请按以下步骤安装：\n"
                "1. 下载 FFmpeg: https://ffmpeg.org/download.html\n"
                '   （推荐 Windows 版本: gyan.dev → ffmpeg-release-full.7z）\n'
                "2. 解压到如 D:\\ffmpeg\\ 目录\n"
                "3. 打开「设置」页面，在「FFmpeg 路径」中填写完整路径\n"
                '   如: D:\\ffmpeg\\bin\\ffmpeg.exe\n\n'
                "或使用 winget 一键安装:\n"
                "   winget install Gyan.FFmpeg"
            )
            return

        # 生成输出路径
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        out_dir = self._config.get_output_dir()
        fmt = self.combo_fmt.currentData()
        out_path = os.path.join(out_dir, f"录屏_{timestamp}.{fmt}")

        codec = self.combo_codec.currentData()
        fps = self.spin_fps.value()

        self._worker = RecordWorker(
            output_path=out_path,
            fps=fps,
            codec=codec,
            fmt=fmt,
            ffmpeg_path=ffmpeg_path,
        )
        self._worker.record_finished.connect(self._on_record_finished)
        self._worker.record_error.connect(self._on_record_error)

        self._worker.start()

        self._is_recording = True
        self._start_time = time.time()
        self._timer.start(200)

        self.btn_start.setVisible(False)
        self.btn_stop.setVisible(True)
        self.status_label.setText(f"🔴 录制中... (FPS: {fps}, 编码: {codec})")
        self.status_label.setStyleSheet("color: #DC2626; font-size: 13px; font-weight: bold;")

    def _stop_recording(self):
        if self._worker and self._worker.isRunning():
            self._worker.stop()
            # 等待线程结束最多 3 秒
            self._worker.wait(3000)

        self._timer.stop()
        self._is_recording = False
        self.btn_start.setVisible(True)
        self.btn_stop.setVisible(False)
        self.status_label.setText("⏹️ 录制已停止，正在保存文件...")
        self.status_label.setStyleSheet("color: #5A6B85; font-size: 12px;")

    def _update_timer(self):
        if self._is_recording:
            elapsed = int(time.time() - self._start_time)
            h, m, s = elapsed // 3600, (elapsed % 3600) // 60, elapsed % 60
            self.timer_label.setText(f"{h:02d}:{m:02d}:{s:02d}")
            # 闪烁红点效果
            if elapsed % 2 == 0:
                self.timer_label.setStyleSheet(
                    "font-size: 48px; font-weight: bold; color: #DC2626; "
                    "font-family: 'Consolas', monospace;")
            else:
                self.timer_label.setStyleSheet(
                    "font-size: 48px; font-weight: bold; color: #1a2640; "
                    "font-family: 'Consolas', monospace;")

    @pyqtSlot(str)
    def _on_record_finished(self, path: str):
        self._timer.stop()
        self._is_recording = False
        self.btn_start.setVisible(True)
        self.btn_stop.setVisible(False)
        size_mb = os.path.getsize(path) / (1024 * 1024)
        self.status_label.setText(f"✅ 录制完成! {os.path.basename(path)} ({size_mb:.1f} MB)")
        self.status_label.setStyleSheet("color: #0D9E6A; font-size: 13px; font-weight: bold;")
        self.timer_label.setText("00:00:00")
        self.timer_label.setStyleSheet(
            "font-size: 48px; font-weight: bold; color: #1a2640; "
            "font-family: 'Consolas', monospace;")
        bus.history_updated.emit()
        self._load_recent()

    @pyqtSlot(str)
    def _on_record_error(self, error: str):
        self._timer.stop()
        self._is_recording = False
        self.btn_start.setVisible(True)
        self.btn_stop.setVisible(False)
        self.status_label.setText(f"❌ 录制失败: {error}")
        self.status_label.setStyleSheet("color: #DC2626; font-size: 12px;")

    # ---- 最近记录 ----
    def _load_recent(self):
        self.recent_list.clear()
        try:
            for r in get_recent_records(15):
                ts = r["created_at"][:16].replace("T", " ")
                item = QListWidgetItem(
                    f"🎬 {r['file_name']}  |  {r['duration_sec']}秒  |  "
                    f"{r['file_size_mb']}MB  |  {ts}"
                )
                item.setData(Qt.ItemDataRole.UserRole, r["file_path"])
                self.recent_list.addItem(item)
        except Exception:
            pass

    def _open_record_file(self, item: QListWidgetItem):
        path = item.data(Qt.ItemDataRole.UserRole)
        if path and os.path.exists(path):
            os.startfile(os.path.dirname(path))

    def _change_output_dir(self):
        folder = QFileDialog.getExistingDirectory(self, "选择输出目录")
        if folder:
            self._config.output_dir = folder
            self._config.save()
            self.output_dir_label.setText(folder)

    def closeEvent(self, event):
        if self._is_recording:
            self._stop_recording()
        super().closeEvent(event)
