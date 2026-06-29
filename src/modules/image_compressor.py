"""
图片批量压缩模块
核心算法：基于 Pillow，支持按目标大小（二分搜索逼近）和按质量两种模式。
"""
import os
import io
from pathlib import Path
from PIL import Image


# 支持的图片格式
SUPPORTED_FORMATS = {'.jpg', '.jpeg', '.png', '.bmp', '.webp', '.tiff', '.gif'}

# 二分搜索精度（KB）
SIZE_TOLERANCE_KB = 5
MAX_ITERATIONS = 12


def compress_image(
    file_path: str,
    target_kb: int = 500,
    quality: int = 75,
    mode: str = "size",
    output_dir: str = "",
    max_width: int = 0,
    max_height: int = 0,
    progress_callback: callable = None,
) -> str:
    """
    压缩单张图片。

    Args:
        file_path:   源图片路径
        target_kb:   目标大小（KB），仅在 mode='size' 时生效
        quality:     压缩质量 1-100，仅在 mode='quality' 时生效
        mode:        'size' 按目标大小 / 'quality' 按质量
        output_dir:  输出目录（空则同源目录）
        max_width:   最大宽度（像素），0=不限制
        max_height:  最大高度（像素），0=不限制
        progress_callback:  进度回调 callable(step, total_steps)，可为 None

    Returns:
        输出文件路径
    """
    def _report(step: int, total: int):
        if progress_callback:
            try:
                progress_callback(step, total)
            except Exception:
                pass

    # 打开图片
    img = Image.open(file_path)

    # 按设定长宽等比缩放（保持宽高比）
    if max_width > 0 or max_height > 0:
        orig_w, orig_h = img.size
        # 计算缩放比例
        ratio_w = max_width / orig_w if max_width > 0 else 1.0
        ratio_h = max_height / orig_h if max_height > 0 else 1.0
        ratio = min(ratio_w, ratio_h)
        if ratio < 1.0:
            new_w = max(1, int(orig_w * ratio))
            new_h = max(1, int(orig_h * ratio))
            img = img.resize((new_w, new_h), Image.LANCZOS)

    # 处理 RGBA → RGB（JPEG 不支持透明通道）
    original_mode = img.mode
    if original_mode in ('RGBA', 'P', 'LA'):
        rgb_img = Image.new('RGB', img.size, (255, 255, 255))
        if original_mode == 'P':
            img = img.convert('RGBA')
        if img.mode == 'RGBA' or img.mode == 'LA':
            rgb_img.paste(img, mask=img.split()[-1] if img.mode in ('RGBA', 'LA') else None)
        img = rgb_img

    # 确定输出路径
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_dir = output_dir or os.path.dirname(file_path)
    os.makedirs(out_dir, exist_ok=True)

    ext = os.path.splitext(file_path)[1].lower()

    if mode == "quality":
        # ---- 按质量压缩 ----
        _report(1, 2)  # 开始
        # 注意：PNG 为无损格式，quality 参数对其不生效
        save_kwargs = _get_save_kwargs(ext, quality)
        out_name = f"{base}_compressed{ext}"
        out_path = os.path.join(out_dir, out_name)
        _safe_save(img, out_path, ext, save_kwargs)
        _report(2, 2)  # 完成
        return out_path

    else:
        # ---- 按目标大小压缩（二分搜索逼近） ----
        out_name = f"{base}_compressed.jpg"
        out_path = os.path.join(out_dir, out_name)

        _report(0, MAX_ITERATIONS + 1)  # 开始

        # 先在高质量保存一次，检查是否已经足够小
        buf = io.BytesIO()
        if ext == '.png':
            img.save(buf, format='JPEG', quality=95, optimize=True)
        else:
            img.save(buf, format='JPEG', quality=95, optimize=True)
        if buf.getbuffer().nbytes / 1024 <= target_kb:
            _report(MAX_ITERATIONS + 1, MAX_ITERATIONS + 1)
            with open(out_path, 'wb') as f:
                f.write(buf.getvalue())
            return out_path

        # 二分搜索最优 quality
        lo, hi = 5, 95
        best_buf = buf
        for i in range(MAX_ITERATIONS):
            if progress_callback:
                _report(i + 1, MAX_ITERATIONS)
            mid = (lo + hi) // 2
            buf = io.BytesIO()
            img.save(buf, format='JPEG', quality=mid, optimize=True)
            size_kb = buf.getbuffer().nbytes / 1024

            if abs(size_kb - target_kb) <= SIZE_TOLERANCE_KB:
                best_buf = buf
                break
            elif size_kb > target_kb:
                hi = mid - 1
            else:
                lo = mid + 1
                best_buf = buf

        _report(MAX_ITERATIONS + 1, MAX_ITERATIONS + 1)  # 完成
        with open(out_path, 'wb') as f:
            f.write(best_buf.getvalue())
        return out_path


def _get_save_kwargs(ext: str, quality: int) -> dict:
    """根据格式生成 PIL save 参数"""
    ext = ext.lower()
    if ext in ('.jpg', '.jpeg'):
        return {'format': 'JPEG', 'quality': quality, 'optimize': True}
    elif ext == '.png':
        # PNG 为无损格式，quality 参数不生效；使用 optimize=True 做最大压缩
        return {'format': 'PNG', 'optimize': True}
    elif ext == '.webp':
        return {'format': 'WEBP', 'quality': quality}
    elif ext == '.bmp':
        return {'format': 'BMP'}
    elif ext == '.tiff':
        return {'format': 'TIFF', 'compression': 'tiff_lzw'}
    else:
        return {'format': 'JPEG', 'quality': quality, 'optimize': True}


def _safe_save(img: Image.Image, path: str, ext: str, kwargs: dict):
    """安全保存图片（防御性浅拷贝 kwargs 避免修改调用方字典）"""
    kwargs = dict(kwargs)
    fmt = kwargs.pop('format', None) or ext.strip('.').upper()
    img.save(path, format=fmt, **kwargs)


def get_image_files_from_dir(directory: str, recursive: bool = False) -> list[str]:
    """从目录中收集所有支持的图片文件"""
    files = []
    pattern = "**/*" if recursive else "*"
    for p in Path(directory).glob(pattern):
        if p.suffix.lower() in SUPPORTED_FORMATS:
            files.append(str(p))
    return files
