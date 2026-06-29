"""
屏幕录制模块
使用 Windows GDI (pywin32) 逐帧截图 + FFmpeg 管道编码，
输出 H.264 MP4 文件。

方案：
1. pywin32 获取屏幕 DC，按指定 FPS 截图 (BGRA 原始数据)
2. FFmpeg 直接接收 BGRA 格式 → 无需 Python 层像素转换
3. 独立写入线程 + 帧队列 → 解耦截图与编码，防止 pipe 阻塞
4. 录制完成后返回文件路径和时长
"""
import os
import sys
import time
import queue
import subprocess
import threading
from pathlib import Path


def _find_ffmpeg(custom_path: str = "") -> str:
    """
    查找 FFmpeg 可执行文件。

    优先级：
    1. 用户指定的自定义路径
    2. 项目内置 ffmpeg 目录
    3. 常见安装路径
    4. 系统 PATH
    """
    # 0. 用户自定义路径
    if custom_path and os.path.isfile(custom_path):
        return custom_path

    # 1. 项目自带 ffmpeg（打包时可能嵌入）
    import sys
    if getattr(sys, 'frozen', False):
        app_dir = os.path.dirname(sys.executable)
    else:
        app_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    bundled = os.path.join(app_dir, "ffmpeg", "ffmpeg.exe")
    if os.path.isfile(bundled):
        return bundled

    # 2. 常见安装路径
    common_paths = [
        os.path.join(os.environ.get("ProgramFiles", "C:\\Program Files"), "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"), "ffmpeg", "bin", "ffmpeg.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe"),
        os.path.expandvars(r"%USERPROFILE%\ffmpeg\bin\ffmpeg.exe"),
        r"D:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for p in common_paths:
        if os.path.isfile(p):
            return p

    # 3. 系统 PATH
    import shutil
    found = shutil.which("ffmpeg")
    if found:
        return found

    return ""  # 未找到，返回空字符串


def _get_screen_size():
    """获取主显示器分辨率"""
    try:
        import win32api
        w = win32api.GetSystemMetrics(0)
        h = win32api.GetSystemMetrics(1)
        return w, h
    except ImportError:
        # 回退：使用 tkinter（PyQt 运行时可能不可用）
        import ctypes
        user32 = ctypes.windll.user32
        return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def _capture_frame_dc(x, y, w, h) -> bytes:
    """
    使用 Windows GDI 捕获指定区域屏幕。
    返回原始 BGRA 像素数据。
    """
    import win32gui
    import win32ui
    import win32con
    import win32api

    hdesktop = win32gui.GetDesktopWindow()
    hwnd_dc = win32gui.GetWindowDC(hdesktop)
    mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
    save_dc = mfc_dc.CreateCompatibleDC()

    bitmap = win32ui.CreateBitmap()
    bitmap.CreateCompatibleBitmap(mfc_dc, w, h)
    save_dc.SelectObject(bitmap)

    # 使用 BitBlt 可能失败，改用 StretchBlt 或直接读
    try:
        save_dc.BitBlt((0, 0), (w, h), mfc_dc, (x, y), win32con.SRCCOPY)
    except Exception:
        # 某些显卡驱动不支持 BitBlt，尝试 StretchBlt
        save_dc.StretchBlt((0, 0), (w, h), mfc_dc, (x, y), (w, h), win32con.SRCCOPY)

    bmp_info = bitmap.GetInfo()
    bmp_str = bitmap.GetBitmapBits(True)

    # 清理
    win32gui.DeleteObject(bitmap.GetHandle())
    save_dc.DeleteDC()
    mfc_dc.DeleteDC()
    win32gui.ReleaseDC(hdesktop, hwnd_dc)

    return bmp_str, bmp_info['bmWidth'], bmp_info['bmHeight']


def record_screen(
    output_path: str,
    fps: int = 15,
    codec: str = "libx264",
    fmt: str = "mp4",
    region: tuple | None = None,
    stop_event: threading.Event | None = None,
    ffmpeg_path: str = "",
) -> tuple[str, float]:
    """
    录制屏幕。

    Args:
        output_path:  输出视频路径
        fps:          帧率
        codec:        编码器 (libx264 / mpeg4)
        fmt:          容器格式 (mp4 / avi)
        region:       录制区域 (x, y, w, h)，None=全屏
        stop_event:   外部停止信号
        ffmpeg_path:  自定义 FFmpeg 路径（空=自动查找）

    Returns:
        (output_path, duration_seconds)
    """
    ffmpeg = _find_ffmpeg(ffmpeg_path)
    if not ffmpeg:
        raise RuntimeError(
            "未找到 FFmpeg，屏幕录制功能需要 FFmpeg 编码视频。\n\n"
            "请按以下步骤安装：\n"
            "1. 下载 FFmpeg: https://ffmpeg.org/download.html\n"
            '   （推荐 Windows 版本: gyan.dev → ffmpeg-release-full.7z）\n'
            '2. 解压到如 D:\\ffmpeg\\ 目录（路径不要含中文）\n'
            "3. 在百宝箱「设置页面」中指定 ffmpeg.exe 的完整路径\n"
            "   如: D:\\ffmpeg\\bin\\ffmpeg.exe\n\n"
            "或使用 winget 一键安装:\n"
            "   winget install Gyan.FFmpeg"
        )

    if region:
        x, y, rw, rh = region
    else:
        x, y = 0, 0
        rw, rh = _get_screen_size()

    # 确保宽高为偶数（某些编码器要求）
    rw = rw if rw % 2 == 0 else rw - 1
    rh = rh if rh % 2 == 0 else rh - 1

    # 启动 FFmpeg 进程（BGRA 原生输入，无需像素转换）
    cmd = [
        ffmpeg,
        "-y",                          # 覆盖输出
        "-f", "rawvideo",
        "-pixel_format", "bgra",       # 直接接收 GDI 输出的 BGRA 格式
        "-video_size", f"{rw}x{rh}",
        "-framerate", str(fps),
        "-i", "pipe:0",               # 从 stdin 读取
        "-c:v", codec,
        "-preset", "ultrafast",
        "-crf", "23",
        "-pix_fmt", "yuv420p",
        output_path,
    ]

    # 静默 FFmpeg 输出（避免控制台刷屏）
    startupinfo = None
    if sys.platform == "win32":
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        startupinfo.wShowWindow = subprocess.SW_HIDE

    proc = subprocess.Popen(
        cmd,
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        startupinfo=startupinfo,
    )

    start_time = time.time()
    frame_interval = 1.0 / fps
    frames_captured = 0

    # ---- 帧队列：解耦截图与编码 ----
    frame_queue = queue.Queue(maxsize=30)
    write_error = [None]  # 用列表承载以便闭包修改

    def _writer_thread():
        """独立写入线程：从队列取帧写入 FFmpeg stdin"""
        try:
            while not (stop_event and stop_event.is_set()) or not frame_queue.empty():
                try:
                    data = frame_queue.get(timeout=0.5)
                    proc.stdin.write(data)
                    proc.stdin.flush()
                except queue.Empty:
                    continue
        except (BrokenPipeError, OSError) as e:
            write_error[0] = e
        except Exception as e:
            write_error[0] = e

    writer = threading.Thread(target=_writer_thread, daemon=True)
    writer.start()

    try:
        while not (stop_event and stop_event.is_set()):
            loop_start = time.time()

            try:
                raw_data, bw, bh = _capture_frame_dc(x, y, rw, rh)
                # FFmpeg 配置为 bgra 格式，无需转换，直接入队
                frame_queue.put(raw_data, timeout=1.0)
                frames_captured += 1
            except queue.Full:
                # 队列满则丢弃当前帧（防止内存暴涨）
                pass
            except (BrokenPipeError, OSError):
                break
            except Exception:
                # 单帧捕获失败不中断录制
                pass

            # 控制帧率
            elapsed = time.time() - loop_start
            sleep_time = frame_interval - elapsed
            if sleep_time > 0:
                time.sleep(sleep_time)

    finally:
        # 等待写入线程清空队列
        writer.join(timeout=5)
        # 关闭 FFmpeg stdin，等待其完成编码
        try:
            proc.stdin.close()
        except Exception:
            pass
        proc.wait(timeout=10)

        if write_error[0]:
            raise RuntimeError(f"编码写入失败: {write_error[0]}")

    duration = time.time() - start_time

    if not os.path.exists(output_path) or os.path.getsize(output_path) == 0:
        raise RuntimeError("录制失败：输出文件为空")

    return output_path, duration


def get_available_codecs() -> list[dict]:
    """返回可用的编码器列表"""
    return [
        {"id": "libx264", "name": "H.264 (推荐)", "ext": "mp4"},
        {"id": "mpeg4",   "name": "MPEG-4",       "ext": "avi"},
    ]
