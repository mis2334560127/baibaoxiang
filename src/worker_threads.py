"""
百宝箱 后台工作线程
所有耗时操作（压缩、转换、录制、广告请求）均放入 QThread 执行，
避免阻塞 UI 线程。
"""
import os
import time
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.signals import bus


class CompressWorker(QThread):
    """图片批量压缩线程"""
    file_progress = pyqtSignal(int, int)          # (current_idx, total)
    file_done = pyqtSignal(str, bool, str)         # (filename, success, msg)

    def __init__(self, files: list[str], target_kb: int = 500,
                 quality: int = 75, mode: str = "size",
                 output_dir: str = "", max_width: int = 0, max_height: int = 0):
        super().__init__()
        self.files = files
        self.target_kb = target_kb
        self.quality = quality
        self.mode = mode        # "size" or "quality"
        self.output_dir = output_dir
        self.max_width = max_width
        self.max_height = max_height
        self._cancelled = False

    def cancel(self):
        """协作式取消：设置标志让线程自然退出（安全替代 terminate()）"""
        self._cancelled = True

    def run(self):
        from src.modules.image_compressor import compress_image
        from src.database import log_compress

        total = len(self.files)
        success = fail = 0

        for i, fp in enumerate(self.files):
            if self._cancelled:
                break
            self.file_progress.emit(i + 1, total)
            try:
                orig_kb = os.path.getsize(fp) / 1024
                result_path = compress_image(
                    fp, self.target_kb, self.quality, self.mode, self.output_dir,
                    self.max_width, self.max_height
                )
                final_kb = os.path.getsize(result_path) / 1024
                filename = os.path.basename(fp)
                log_compress(filename, fp, orig_kb, final_kb, self.quality, self.mode)
                self.file_done.emit(filename, True,
                    f"压缩成功: {orig_kb:.0f}KB → {final_kb:.0f}KB (节省{(1-final_kb/orig_kb)*100:.0f}%)")
                success += 1
            except Exception as e:
                self.file_done.emit(os.path.basename(fp), False, f"失败: {str(e)}")
                fail += 1

        bus.compress_all_done.emit(success, fail)


class ConvertWorker(QThread):
    """PDF 转 Word 线程"""
    file_progress = pyqtSignal(int, int)
    file_done = pyqtSignal(str, bool, str)

    def __init__(self, files: list[str], preserve_fmt: bool = True,
                 preserve_img: bool = True, output_dir: str = "",
                 force_ocr: bool = False):
        super().__init__()
        self.files = files
        self.preserve_fmt = preserve_fmt
        self.preserve_img = preserve_img
        self.output_dir = output_dir
        self.force_ocr = force_ocr
        self._cancelled = False

    def cancel(self):
        """协作式取消"""
        self._cancelled = True

    def run(self):
        from src.modules.pdf_converter import convert_pdf_to_docx
        from src.database import log_convert

        total = len(self.files)
        success = fail = 0

        for i, fp in enumerate(self.files):
            if self._cancelled:
                break
            self.file_progress.emit(i + 1, total)
            try:
                result_path = convert_pdf_to_docx(
                    fp, self.output_dir, self.preserve_fmt, self.preserve_img,
                    force_ocr=self.force_ocr
                )
                filename = os.path.basename(fp)
                log_convert(filename, fp, 0)  # page count filled by converter
                self.file_done.emit(filename, True,
                    f"转换成功 → {os.path.basename(result_path)}")
                success += 1
            except Exception as e:
                self.file_done.emit(os.path.basename(fp), False, f"失败: {str(e)}")
                fail += 1

        bus.convert_all_done.emit(success, fail)


class RecordWorker(QThread):
    """
    屏幕录制线程
    使用 pywin32 + FFmpeg 进程序幕捕获并编码。
    运行在独立线程中，通过标志位控制启停。
    """
    record_finished = pyqtSignal(str)    # output path
    record_error = pyqtSignal(str)

    def __init__(self, output_path: str, fps: int = 15,
                 codec: str = "libx264", fmt: str = "mp4",
                 region: tuple | None = None):
        super().__init__()
        self.output_path = output_path
        self.fps = fps
        self.codec = codec
        self.format = fmt
        self.region = region       # (x, y, w, h) or None for full screen
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    def run(self):
        try:
            from src.modules.screen_recorder import record_screen
            clip_path, duration = record_screen(
                output_path=self.output_path,
                fps=self.fps,
                codec=self.codec,
                fmt=self.format,
                region=self.region,
                stop_event=self._stop_event,
            )
            # 记录到数据库
            from src.database import log_record
            file_size_mb = os.path.getsize(clip_path) / (1024 * 1024) if os.path.exists(clip_path) else 0
            log_record(os.path.basename(clip_path), clip_path,
                       int(duration), file_size_mb)
            self.record_finished.emit(clip_path)
        except Exception as e:
            self.record_error.emit(str(e))
