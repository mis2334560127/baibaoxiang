"""
百宝箱 后台工作线程
所有耗时操作（压缩、转换、录制、广告请求）均放入 QThread 执行，
避免阻塞 UI 线程。
"""
import os
import time
import tempfile
import threading
from pathlib import Path

from PyQt6.QtCore import QThread, pyqtSignal

from src.signals import bus


class CompressWorker(QThread):
    """图片批量压缩线程"""
    file_progress = pyqtSignal(int, int)          # (current_idx, total)
    file_done = pyqtSignal(str, bool, str)         # (filename, success, msg)
    item_progress = pyqtSignal(str, int, int)      # (filename, current, total) ─ 单文件内部进度

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
            filename = os.path.basename(fp)

            # 进度回调：二分搜索迭代进度（"size" 模式下约 1-12 步，"quality" 模式直接完成）
            def _on_progress(step: int, steps: int):
                self.item_progress.emit(filename, step, steps)

            try:
                orig_kb = os.path.getsize(fp) / 1024
                result_path = compress_image(
                    fp, self.target_kb, self.quality, self.mode, self.output_dir,
                    self.max_width, self.max_height,
                    progress_callback=_on_progress,
                )
                self.item_progress.emit(filename, 1, 1)  # 完成
                final_kb = os.path.getsize(result_path) / 1024
                log_compress(filename, fp, orig_kb, final_kb, self.quality, self.mode)
                self.file_done.emit(filename, True,
                    f"压缩成功: {orig_kb:.0f}KB → {final_kb:.0f}KB (节省{(1-final_kb/orig_kb)*100:.0f}%)")
                success += 1
            except Exception as e:
                self.file_done.emit(filename, False, f"失败: {str(e)}")
                fail += 1

        bus.compress_all_done.emit(success, fail)


class ConvertWorker(QThread):
    """PDF 转 Word 线程"""
    file_progress = pyqtSignal(int, int)
    file_done = pyqtSignal(str, bool, str)
    item_progress = pyqtSignal(str, int, int)      # (filename, page, total_pages) ─ 页级进度

    def __init__(self, files: list[str], preserve_fmt: bool = True,
                 preserve_img: bool = True, output_dir: str = "",
                 force_ocr: bool = False, ocr_lang: str = "ch",
                 preserve_layout: bool = True):
        super().__init__()
        self.files = files
        self.preserve_fmt = preserve_fmt
        self.preserve_img = preserve_img
        self.output_dir = output_dir
        self.force_ocr = force_ocr
        self.ocr_lang = ocr_lang
        self.preserve_layout = preserve_layout
        self._cancelled = False

    def cancel(self):
        """协作式取消"""
        self._cancelled = True

    def run(self):
        from src.modules.pdf_converter import convert_pdf_to_docx, get_pdf_page_count
        from src.database import log_convert

        # ── 预计算所有文件的总页数（进度条按页面数推进，与详情显示对应） ──
        page_counts: list[int] = []
        for fp in self.files:
            try:
                pc = get_pdf_page_count(fp)
                page_counts.append(pc if pc > 0 else 1)
            except Exception:
                page_counts.append(1)
        total_pages = sum(page_counts)
        cumulative_pages = 0          # 已完成文件的总页数
        total_files = len(self.files)
        success = fail = 0

        for i, fp in enumerate(self.files):
            if self._cancelled:
                break
            filename = os.path.basename(fp)
            file_page_count = page_counts[i]

            # 进度回调：页级进度（累加到进度条）
            def _on_progress(page: int, _total: int):
                self.item_progress.emit(filename, page, _total)
                if _total > 1:
                    # OCR 逐页模式：进度条平滑推进
                    self.file_progress.emit(cumulative_pages + page, total_pages)
                elif page >= _total:
                    # pdf2docx 黑盒完成（_report(1,1) 触发）：一次性加上文件页数
                    self.file_progress.emit(cumulative_pages + file_page_count, total_pages)
                else:
                    # pdf2docx 开始（_report(0,1) 触发）
                    self.file_progress.emit(cumulative_pages, total_pages)

            try:
                result_path = convert_pdf_to_docx(
                    fp, self.output_dir, self.preserve_fmt, self.preserve_img,
                    force_ocr=self.force_ocr, ocr_lang=self.ocr_lang,
                    pure_ocr=not self.preserve_layout,
                    progress_callback=_on_progress,
                )
                cumulative_pages += file_page_count
                self.file_progress.emit(cumulative_pages, total_pages)  # 确保进度条到位
                self.item_progress.emit(filename, 1, 1)                 # UI 显示"完成"
                log_convert(filename, fp, 0)  # page count filled by converter
                self.file_done.emit(filename, True,
                    f"转换成功 → {os.path.basename(result_path)}")
                success += 1
            except Exception as e:
                cumulative_pages += file_page_count
                self.file_progress.emit(cumulative_pages, total_pages)
                self.file_done.emit(os.path.basename(fp), False, f"失败: {str(e)}")
                fail += 1

        bus.convert_all_done.emit(success, fail)


class ExcelMergeWorker(QThread):
    """批量合并 Excel 线程（支持直接 Excel 文件 + 压缩包提取）"""
    file_progress = pyqtSignal(int, int)          # (current_idx, total)
    file_done = pyqtSignal(str, bool, str)        # (filename, success, msg)

    def __init__(self, input_files: list[str], output_path: str):
        super().__init__()
        self.input_files = input_files
        self.output_path = output_path
        self._cancelled = False

    def cancel(self):
        """协作式取消"""
        self._cancelled = True

    def run(self):
        from src.modules.excel_merger import (
            ARCHIVE_EXTS, EXCEL_EXTS,
            extract_excel_from_archive, read_excel_data, merge_and_write,
        )

        all_rows: list[list] = []
        all_headers: list | None = None
        success = fail = 0
        total = len(self.input_files)

        with tempfile.TemporaryDirectory() as temp_dir:
            for i, file_path in enumerate(self.input_files):
                if self._cancelled:
                    break
                self.file_progress.emit(i + 1, total)
                filename = os.path.basename(file_path)
                ext = os.path.splitext(file_path)[1].lower()

                try:
                    # 判断文件类型：压缩包需要解压提取，Excel 文件直接读取
                    if ext in ARCHIVE_EXTS:
                        # ── 压缩包路径 ──
                        excel_files = extract_excel_from_archive(file_path, temp_dir)
                        if not excel_files:
                            self.file_done.emit(filename, False, "压缩包内未找到 Excel 文件")
                            fail += 1
                            continue

                        file_count = len(excel_files)
                        for ef in excel_files:
                            if self._cancelled:
                                break
                            try:
                                headers, rows = read_excel_data(ef)
                                if all_headers is None:
                                    all_headers = headers
                                    all_rows.extend(rows)
                                else:
                                    all_rows.extend(rows)
                            except Exception as e:
                                self.file_done.emit(
                                    os.path.basename(ef), False,
                                    f"读取失败: {str(e)}"
                                )
                                fail += 1
                                continue

                        self.file_done.emit(
                            filename, True,
                            f"成功读取 {file_count} 个 Excel（从压缩包提取）"
                        )
                        success += 1

                    elif ext in EXCEL_EXTS:
                        # ── 直接 Excel 文件 ──
                        try:
                            headers, rows = read_excel_data(file_path)
                            if all_headers is None:
                                all_headers = headers
                                all_rows.extend(rows)
                            else:
                                all_rows.extend(rows)
                        except Exception as e:
                            self.file_done.emit(filename, False, f"读取失败: {str(e)}")
                            fail += 1
                            continue

                        self.file_done.emit(
                            filename, True,
                            f"成功读取（直接 Excel 文件）"
                        )
                        success += 1

                    else:
                        self.file_done.emit(filename, False, "不支持的文件格式")
                        fail += 1

                except ImportError as e:
                    self.file_done.emit(filename, False, str(e))
                    fail += 1
                except Exception as e:
                    self.file_done.emit(filename, False, f"处理失败: {str(e)}")
                    fail += 1

            # 写入合并结果
            if all_headers is not None and all_rows:
                try:
                    merge_and_write(all_headers, all_rows, self.output_path)
                except Exception as e:
                    bus.merge_all_done.emit(success, fail)
                    return
            elif all_headers is None:
                # 没有读取到任何数据
                pass

        bus.merge_all_done.emit(success, fail)

class OcrWorker(QThread):
    """批量图片 OCR 识别线程"""
    file_progress = pyqtSignal(int, int)          # (current_idx, total)
    file_done = pyqtSignal(str, bool, str)        # (filename, success, msg)
    item_progress = pyqtSignal(str, int, int)     # (filename, step, total_steps)

    def __init__(self, files: list[str], output_dir: str,
                 tesseract_path: str = "", lang: str = "chi_sim+eng",
                 combine_to_one: bool = False):
        super().__init__()
        self.files = files
        self.output_dir = output_dir
        self.tesseract_path = tesseract_path
        self.lang = lang
        self.combine_to_one = combine_to_one  # 是否合并为一个 txt
        self._cancelled = False

    def cancel(self):
        """协作式取消"""
        self._cancelled = True

    def run(self):
        from src.modules.ocr_recognizer import recognize_image, save_text_to_file
        from src.database import log_ocr

        total = len(self.files)
        success = fail = 0
        all_texts: list[tuple[str, str]] = []  # (filename, text)

        for i, fp in enumerate(self.files):
            if self._cancelled:
                break
            self.file_progress.emit(i + 1, total)
            filename = os.path.basename(fp)

            try:
                def _on_progress(step: int, steps: int):
                    self.item_progress.emit(filename, step, steps)

                text = recognize_image(
                    fp,
                    tesseract_path=self.tesseract_path,
                    lang=self.lang,
                    progress_callback=_on_progress,
                )
                self.item_progress.emit(filename, 1, 1)

                if self.combine_to_one:
                    all_texts.append((filename, text))
                    self.file_done.emit(filename, True,
                        f"识别完成（{len(text)} 字符，待合并）")
                else:
                    # 每个图片单独保存 .txt
                    base = os.path.splitext(filename)[0]
                    txt_path = os.path.join(self.output_dir, f"{base}.txt")
                    save_text_to_file(text, txt_path)
                    self.file_done.emit(filename, True,
                        f"识别完成（{len(text)} 字符）→ {base}.txt")

                log_ocr(filename, fp, len(text), text, self.lang)
                success += 1

            except Exception as e:
                self.file_done.emit(filename, False, f"失败: {str(e)}")
                fail += 1

        # 如果选择合并模式，写入一个合并文件
        if self.combine_to_one and all_texts:
            try:
                combined_path = os.path.join(self.output_dir, "OCR合并结果.txt")
                lines = []
                for fname, txt in all_texts:
                    lines.append(f"===== {fname} =====")
                    lines.append(txt)
                    lines.append("")
                save_text_to_file("\n".join(lines), combined_path)
            except Exception as e:
                pass  # 合并失败不影响单个结果

        bus.ocr_all_done.emit(success, fail)


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
                 region: tuple | None = None, ffmpeg_path: str = ""):
        super().__init__()
        self.output_path = output_path
        self.fps = fps
        self.codec = codec
        self.format = fmt
        self.region = region       # (x, y, w, h) or None for full screen
        self.ffmpeg_path = ffmpeg_path
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
                ffmpeg_path=self.ffmpeg_path,
            )
            # 记录到数据库
            from src.database import log_record
            file_size_mb = os.path.getsize(clip_path) / (1024 * 1024) if os.path.exists(clip_path) else 0
            log_record(os.path.basename(clip_path), clip_path,
                       int(duration), file_size_mb)
            self.record_finished.emit(clip_path)
        except Exception as e:
            self.record_error.emit(str(e))
