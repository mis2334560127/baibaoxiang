"""
PDF 转 Word 模块
支持两种模式：
1. 数字型 PDF（文字可选层）→ pdf2docx 直接转换
2. 扫描型 PDF（图片）→ PyMuPDF 渲染 + pytesseract OCR 识别
"""
import os
import io
from pathlib import Path


def detect_pdf_type(file_path: str) -> tuple[str, int, int]:
    """
    检测 PDF 类型。

    Returns:
        (type_str, text_pages, total_pages)
        type_str: "text" / "scanned" / "mixed"
    """
    try:
        import fitz
    except ImportError:
        return ("text", 0, 0)

    try:
        doc = fitz.open(file_path)
        total = doc.page_count
        text_pages = 0
        for i in range(total):
            page = doc[i]
            text = page.get_text().strip()
            if text:  # 非空白文本即视为有文字层
                text_pages += 1
        doc.close()

        if text_pages == total:
            return ("text", text_pages, total)
        elif text_pages == 0:
            return ("scanned", 0, total)
        else:
            return ("mixed", text_pages, total)
    except Exception:
        return ("text", 0, 0)


def convert_pdf_to_docx(
    file_path: str,
    output_dir: str = "",
    preserve_formatting: bool = True,
    preserve_images: bool = True,
    force_ocr: bool = False,
    ocr_lang: str = "chi_sim+eng",
    progress_callback: callable = None,
) -> str:
    """
    将 PDF 转换为 Word (.docx) 文档。
    自动检测 PDF 类型，扫描型使用 OCR（保留排版），文字型使用 pdf2docx。

    Args:
        file_path:             PDF 文件路径
        output_dir:            输出目录（空则同源目录）
        preserve_formatting:   保留原始格式（仅 pdf2docx 模式生效）
        preserve_images:       保留图片（仅 pdf2docx 模式生效）
        force_ocr:             强制使用 OCR（即使检测为文字型）
        ocr_lang:              OCR 识别语言（如 "chi_sim+eng"）
        progress_callback:     页级进度回调 callable(current_page, total_pages)，可为 None

    Returns:
        输出 .docx 文件路径
    """
    if not file_path.lower().endswith('.pdf'):
        raise ValueError(f"不支持的文件格式: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 确定输出路径（带可写性检测 + 自动降级）
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_dir = output_dir or os.path.dirname(file_path)
    out_dir = _ensure_writable_dir(out_dir)
    out_path = os.path.join(out_dir, f"{base}.docx")

    # 检测 PDF 类型
    pdf_type, text_pages, total_pages = detect_pdf_type(file_path)

    # 解析实际可用的 OCR 语言
    actual_lang = _resolve_ocr_lang(ocr_lang)

    if not force_ocr and pdf_type == "text":
        # 文字型：使用 pdf2docx 直接转换
        return _convert_with_pdf2docx(
            file_path, out_path, out_dir,
            preserve_formatting, preserve_images,
            progress_callback=progress_callback,
        )
    else:
        # 扫描型 / 混合型 / 强制 OCR：使用 OCR 转换（保留排版）
        return _convert_with_ocr(
            file_path, out_path,
            pdf_type=pdf_type, text_pages=text_pages,
            lang=actual_lang, progress_callback=progress_callback,
        )


def _convert_with_pdf2docx(
    file_path: str, out_path: str, out_dir: str,
    preserve_formatting: bool, preserve_images: bool,
    progress_callback: callable = None,
) -> str:
    """使用 pdf2docx 库转换文字型 PDF（含后处理修正）"""
    def _report(page: int, total: int):
        if progress_callback:
            try:
                progress_callback(page, total)
            except Exception:
                pass

    try:
        from pdf2docx import Converter

        images_folder = None
        if preserve_images:
            images_folder = os.path.join(out_dir, "images")
            os.makedirs(images_folder, exist_ok=True)

        cv = Converter(file_path)
        _report(0, 1)  # 开始（pdf2docx 是黑盒，只能报告开始/结束）
        cv.convert(
            out_path,
            start=0,
            end=None,
            multi_processing=False,
            image_folder=images_folder,
        )
        cv.close()
    except ImportError:
        raise ImportError("pdf2docx 库未安装。请运行: pip install pdf2docx")
    except Exception as e:
        raise RuntimeError(f"PDF 转换失败: {str(e)}")

    if not os.path.exists(out_path):
        raise RuntimeError("转换似乎失败，输出文件未生成")

    # ── 后处理：修正常见格式问题 ──
    _post_process_docx_formatting(out_path)

    _report(1, 1)  # 完成
    return out_path


def _post_process_docx_formatting(docx_path: str):
    """
    后处理 pdf2docx 输出的 DOCX，修正中文字体、段落间距等常见问题。

    修复项：
    1. 所有非标题段落字体设为 SimSun（宋体），标题设为 SimHei（黑体）
    2. 正文字号范围保护（7-16pt），避免极端字号
    3. 行间距统一为 1.3 倍
    4. 页面边距设为标准 A4
    """
    try:
        from docx import Document
        from docx.shared import Pt, Cm
        from docx.oxml.ns import qn
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return  # 后处理非必需，静默跳过

    try:
        doc = Document(docx_path)

        # ── 页面边距（A4 标准） ──
        for section in doc.sections:
            section.top_margin = Cm(2.54)
            section.bottom_margin = Cm(2.54)
            section.left_margin = Cm(3.18)
            section.right_margin = Cm(3.18)

        # ── 遍历所有段落 ──
        for para in doc.paragraphs:
            style_name = (para.style.name if para.style else "").lower()
            is_heading = "heading" in style_name or "heading" in (para.style.name or "").lower()

            for run in para.runs:
                # 正文字号保护
                if run.font.size:
                    fs_pt = run.font.size.pt
                    if not is_heading and (fs_pt < 6 or fs_pt > 18):
                        run.font.size = Pt(10.5)
                    if is_heading and fs_pt < 9:
                        run.font.size = Pt(10.5)

                # 中文字体设置
                if is_heading:
                    run.font.name = 'SimHei'
                    _set_east_asian_font(run, 'SimHei')
                else:
                    run.font.name = 'SimSun'
                    _set_east_asian_font(run, 'SimSun')

                # 清除可能存在的无效字体回退
                try:
                    rpr = run._element.get_or_add_rPr()
                    rFonts = rpr.find(qn('w:rFonts'))
                    if rFonts is not None:
                        # 保留 eastAsia 设置，清除其他可能导致乱码的属性
                        for attr in ['w:ascii', 'w:hAnsi', 'w:cs']:
                            rFonts.attrib.pop(qn(attr), None)
                except Exception:
                    pass

            # 段落行间距（非标题）
            if not is_heading:
                try:
                    if para.paragraph_format.line_spacing is None:
                        para.paragraph_format.line_spacing = 1.3
                except Exception:
                    pass

        doc.save(docx_path)
    except Exception:
        pass  # 后处理失败不影响主流程


def _ensure_writable_dir(dir_path: str) -> str:
    """
    确保目录可写。不可写时自动降级到安全目录（桌面/百宝箱输出）。

    降级场景：
    - 源 PDF 在只读/系统目录（如 D:/视频/）
    - output_dir 未配置且源目录无写权限
    - UAC 保护的特殊文件夹
    """
    # 1. 先尝试创建目标目录
    try:
        os.makedirs(dir_path, exist_ok=True)
        # 写入测试：尝试创建+删除一个临时文件
        test_file = os.path.join(dir_path, f".write_test_{os.getpid()}")
        with open(test_file, "w") as f:
            f.write("test")
        os.remove(test_file)
        return dir_path  # 可写，原样返回
    except (OSError, PermissionError):
        pass

    # 2. 降级到用户桌面/百宝箱输出
    fallback_candidates = [
        str(Path.home() / "Desktop" / "百宝箱输出"),
        str(Path.home() / "Documents" / "百宝箱输出"),
        str(Path.home() / "Downloads" / "百宝箱输出"),
        os.path.join(os.path.dirname(__file__), "..", "data", "output"),
    ]

    for candidate in fallback_candidates:
        try:
            os.makedirs(candidate, exist_ok=True)
            test_file = os.path.join(candidate, f".write_test_{os.getpid()}")
            with open(test_file, "w") as f:
                f.write("test")
            os.remove(test_file)
            print(f"[PDF] 输出目录不可写，已自动切换为: {candidate}")
            return candidate
        except (OSError, PermissionError):
            continue

    # 3. 最终兜底：临时目录（一定可写）
    import tempfile
    fallback = os.path.join(tempfile.gettempdir(), "百宝箱输出")
    os.makedirs(fallback, exist_ok=True)
    print(f"[PDF] 输出目录不可写，已回退到临时目录: {fallback}")
    return fallback


def _find_tesseract() -> str | None:
    """
    自动查找 Tesseract 可执行文件。
    依次检查：PATH 环境变量 → 常见安装路径 → 注册表
    找到后配置 pytesseract.pytesseract.tesseract_cmd。
    """
    import sys
    import shutil
    import subprocess as subprocess_module

    # 1. 先尝试 PATH 中的 tesseract
    tesseract_in_path = shutil.which("tesseract")
    if tesseract_in_path:
        return tesseract_in_path

    # 2. 常见安装路径
    common_paths = [
        r"C:\Program Files\Tesseract-OCR\tesseract.exe",
        r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%ProgramFiles%\Tesseract-OCR\tesseract.exe"),
        os.path.expandvars(r"%ProgramFiles(x86)%\Tesseract-OCR\tesseract.exe"),
    ]
    for path in common_paths:
        if os.path.isfile(path):
            return path

    # 3. 尝试通过注册表查找（Windows）
    if sys.platform == "win32":
        try:
            import winreg
            for root in (winreg.HKEY_LOCAL_MACHINE, winreg.HKEY_CURRENT_USER):
                for subkey in (
                    r"SOFTWARE\Tesseract-OCR",
                    r"SOFTWARE\WOW6432Node\Tesseract-OCR",
                ):
                    try:
                        key = winreg.OpenKey(root, subkey)
                        install_dir, _ = winreg.QueryValueEx(key, "InstallDir")
                        winreg.CloseKey(key)
                        tesseract_path = os.path.join(install_dir, "tesseract.exe")
                        if os.path.isfile(tesseract_path):
                            return tesseract_path
                    except OSError:
                        pass
        except Exception:
            pass

    return None


_TESSERACT_AVAILABLE_LANGS: list[str] | None = None
_TESSERACT_SETUP_DONE: bool = False


def _setup_tesseract():
    """配置 pytesseract 的 tesseract_cmd 路径（带状态跟踪）"""
    global _TESSERACT_SETUP_DONE
    if _TESSERACT_SETUP_DONE:
        return

    import pytesseract
    try:
        pytesseract.get_tesseract_version()
        _TESSERACT_SETUP_DONE = True
        return
    except Exception:
        pass

    tesseract_path = _find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
        _TESSERACT_SETUP_DONE = True
    else:
        raise RuntimeError(
            "未找到 Tesseract OCR 引擎。请从以下地址下载安装：\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n"
            "安装时请勾选中文简体语言包 (chi_sim)"
        )


def get_available_ocr_languages() -> list[str]:
    """获取 Tesseract 已安装的语言列表（不含 osd/equ 等非语言项）"""
    global _TESSERACT_AVAILABLE_LANGS
    if _TESSERACT_AVAILABLE_LANGS is not None:
        return _TESSERACT_AVAILABLE_LANGS

    try:
        _setup_tesseract()
        import pytesseract
        all_langs = pytesseract.get_languages()
        _TESSERACT_AVAILABLE_LANGS = [
            l for l in all_langs if l not in ('osd', 'equ')
        ]
        return _TESSERACT_AVAILABLE_LANGS
    except Exception:
        _TESSERACT_AVAILABLE_LANGS = []
        return []


def _resolve_ocr_lang(requested: str) -> str:
    """
    解析 OCR 语言参数，自动回退到可用语言。

    Args:
        requested: 请求的语言字符串，如 "chi_sim+eng"

    Returns:
        实际可用的语言字符串
    """
    available = get_available_ocr_languages()
    if not available:
        return "eng"

    requested_parts = requested.split("+")
    resolved = [lang for lang in requested_parts if lang in available]

    if not resolved:
        resolved = [available[0]]

    result = "+".join(resolved)
    if result != requested:
        print(f"[OCR] 请求语言 '{requested}' 部分不可用，回退为: '{result}'")
    return result


def check_ocr_chinese_available() -> tuple[bool, str]:
    """
    检查 Tesseract 中文语言包是否可用。

    Returns:
        (has_chinese, message)
    """
    available = get_available_ocr_languages()
    has_chi_sim = "chi_sim" in available
    has_chi_tra = "chi_tra" in available

    if has_chi_sim:
        return True, "简体中文语言包已就绪 ✓"
    elif has_chi_tra:
        return True, "繁体中文语言包可用（建议安装简体中文）"
    else:
        return False, (
            "⚠️ 未检测到中文 OCR 语言包！\n"
            "请下载 chi_sim.traineddata 并放入 Tesseract 的 tessdata 目录：\n"
            "1. 打开 https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata\n"
            "2. 将下载的文件放入 Tesseract 安装目录下的 tessdata 文件夹\n"
            "例如：D:\\OCREXE\\tessdata\\chi_sim.traineddata"
        )


def _convert_with_ocr(
    file_path: str, out_path: str,
    pdf_type: str = "scanned", text_pages: int = 0,
    dpi: int = 300, lang: str = "chi_sim+eng",
    progress_callback: callable = None,
) -> str:
    """
    使用 OCR 转换扫描型 PDF。
    使用 image_to_data 获取词级位置数据，重建段落、对齐和字号排版。
    包含图片预处理（增强对比度、降噪）以提升识别准确率。
    """
    def _report(page: int, total: int):
        if progress_callback:
            try:
                progress_callback(page, total)
            except Exception:
                pass

    try:
        import fitz
        from PIL import Image, ImageFilter, ImageEnhance
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as e:
        raise ImportError(f"OCR 转换缺少依赖: {e}")

    try:
        import pytesseract
    except ImportError:
        raise ImportError(
            "pytesseract 未安装。请运行: pip install pytesseract\n"
            "同时需要安装 Tesseract OCR 引擎: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    _setup_tesseract()

    # 构建 Tesseract 自定义配置
    # --psm 3: 全自动页面分割（比 psm 6 更适合复杂布局）
    # --psm 4: 备选，假设单列可变大小文本
    # -c tessedit_write_images=false: 不写调试图片
    # -c textord_heavy_nr=1: 增强降噪（适合扫描件）
    tesseract_config = "--psm 3 -c tessedit_write_images=false -c textord_heavy_nr=1"

    doc = fitz.open(file_path)
    total = doc.page_count

    docx = Document()

    # 设置默认样式
    style = docx.styles['Normal']
    style.font.name = 'SimSun'
    style.font.size = Pt(10.5)
    # 设置中文字体回退
    style.element.rPr.rFonts.set(
        '{http://schemas.openxmlformats.org/wordprocessingml/2006/main}eastAsia', 'SimSun'
    )

    for i in range(total):
        _report(i + 1, total)  # 页级进度
        page = doc[i]

        # 混合型 PDF：有文字层的页直接提取文字
        page_text = page.get_text().strip()
        if pdf_type == "mixed" and page_text:
            docx.add_paragraph(page_text)
        else:
            # 渲染页面为高 DPI 图片
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))
            img_width, img_height = img.size

            # ---- 图片预处理：提升 OCR 识别准确率 ----
            img = _preprocess_for_ocr(img)

            try:
                # 使用 image_to_data 获取结构化位置数据（含自定义配置）
                data = pytesseract.image_to_data(
                    img, lang=lang,
                    output_type=pytesseract.Output.DICT,
                    config=tesseract_config,
                )
            except pytesseract.TesseractError as e:
                raise RuntimeError(f"OCR 识别失败 (第{i+1}页): {str(e)}")

            # 从位置数据重建排版
            _build_docx_page_from_ocr(docx, data, img_width, img_height, dpi)

        # 页间分隔
        if i < total - 1:
            docx.add_page_break()

    doc.close()
    docx.save(out_path)

    if not os.path.exists(out_path):
        raise RuntimeError("输出文件未生成")

    return out_path


def _preprocess_for_ocr(img, enhance: bool = True) -> "Image.Image":
    """
    对渲染图片进行预处理以提升 OCR 准确率。

    策略（改进版）：
    1. 灰度化 + 自适应对比度拉伸（保留 256 级灰度供 Tesseract 内部阈值）
    2. 非锐化掩模 (Unsharp Mask) 替代简单 SHARPEN（边缘更自然）
    3. 检测低对比度页面 → 额外 CLAHE 均衡化
    尺寸不变，坐标不变。
    """
    from PIL import Image, ImageFilter, ImageOps

    if not enhance:
        if img.mode != 'L':
            img = img.convert('L')
        return img

    # 1. 转灰度
    if img.mode != 'L':
        img = img.convert('L')

    # 2. 对比度增强：拉伸直方图剪掉 2% 的极端值
    img = ImageOps.autocontrast(img, cutoff=2)

    # 3. 检测图像对比度是否偏低（低对比度扫描件常见）
    #    标准差 < 40 表示灰度过于集中，需要额外增强
    try:
        import numpy as np
        arr = np.array(img, dtype=np.float64)
        std_dev = float(np.std(arr))
    except ImportError:
        std_dev = 100  # 无 numpy 时跳过自适应性增强

    if std_dev < 40:
        try:
            import numpy as np
            arr_uint8 = np.array(img, dtype=np.uint8)
        except ImportError:
            arr_uint8 = None

        if arr_uint8 is not None:
            try:
                from cv2 import createCLAHE  # type: ignore
                clahe = createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
                arr_uint8 = clahe.apply(arr_uint8)
                img = Image.fromarray(arr_uint8, mode='L')
            except ImportError:
                # 无 OpenCV 时用 Pillow 的 equalize 作为降级方案
                img = ImageOps.equalize(img)
        else:
            img = ImageOps.equalize(img)

    # 4. 非锐化掩模（比 SHARPEN 更自然，减少光晕效应）
    #    radius=2, amount=150%（相对于原图）
    blurred = img.filter(ImageFilter.GaussianBlur(radius=2))
    from PIL import ImageChops
    # highpass = original - blurred
    highpass = ImageChops.subtract(img, blurred)
    # sharpened = original + 0.8 * highpass (amount=80%，避免过度锐化)
    sharpened = ImageChops.add(img, highpass, scale=1.0, offset=0)
    # 重建：img + (img - blurred) * 0.8
    from PIL import ImageMath
    try:
        img = ImageMath.eval(
            "convert(min(max(a + (a - b) * 0.8, 0), 255), 'L')",
            a=img, b=blurred
        )
    except Exception:
        img = sharpened

    return img


# ──────────────────────────────────────────────
#  辅助工具：字号/粗体/中英文自适应估算
# ──────────────────────────────────────────────

def _estimate_font_size_px_range(
    words_info: list,  # list of (text, left, top, width, height)
    dpi: int,
) -> dict:
    """
    根据字词像素尺寸 + 中英文差异，估算该行可能的字号范围 (pt)。

    关键改进：中文字符通常填满 bbox（高度≈字身），拉丁字符有升部/降部，
    Tesseract bbox 对中文通常比实际字身大 8-15%，对英文可能偏大或偏小。

    Returns:
        {"low": min_pt, "high": max_pt, "median": median_pt, "cjk_ratio": float}
    """
    if not words_info:
        return {"low": 8, "high": 12, "median": 10, "cjk_ratio": 0.0}

    cjk_heights = []
    latin_heights = []
    for text, _, _, _, height in words_info:
        if not text or height <= 0:
            continue
        has_cjk = any('\u4e00' <= ch <= '\u9fff' or
                      '\u3400' <= ch <= '\u4dbf' or
                      '\uf900' <= ch <= '\ufaff'
                      for ch in text)
        cjk_ratio_local = sum(1 for ch in text
                             if '\u4e00' <= ch <= '\u9fff' or
                                '\u3400' <= ch <= '\u4dbf' or
                                '\uf900' <= ch <= '\ufaff') / len(text)
        if cjk_ratio_local > 0.5:
            cjk_heights.append(height)
        elif any(ch.isascii() and ch.isalpha() for ch in text):
            latin_heights.append(height)

    all_heights = cjk_heights + latin_heights
    if not all_heights:
        return {"low": 8, "high": 12, "median": 10, "cjk_ratio": 0.0}

    # CJK 字身系数：Tesseract bbox 通常比实际字身大 ~10-12%
    CJK_FACTOR = 0.88
    # 拉丁字身系数：升部/降部让 bbox 偏高，实际 x-height 更小
    LATIN_FACTOR = 0.78

    if cjk_heights:
        cjk_median = sorted(cjk_heights)[len(cjk_heights) // 2]
        cjk_pt = cjk_median * 72 * CJK_FACTOR / dpi
    else:
        cjk_pt = None

    if latin_heights:
        latin_median = sorted(latin_heights)[len(latin_heights) // 2]
        latin_pt = latin_median * 72 * LATIN_FACTOR / dpi
    else:
        latin_pt = None

    # 融合
    if cjk_pt and latin_pt:
        median_pt = cjk_pt * 0.7 + latin_pt * 0.3  # CJK 权重更高
    elif cjk_pt:
        median_pt = cjk_pt
    elif latin_pt:
        median_pt = latin_pt
    else:
        median_h = sorted(all_heights)[len(all_heights) // 2]
        median_pt = median_h * 72 * 0.85 / dpi

    median_pt = round(max(5, min(72, median_pt)), 1)
    cjk_ratio_global = len(cjk_heights) / len(all_heights) if all_heights else 0.0

    return {
        "low": round(median_pt * 0.7, 1),
        "high": round(median_pt * 1.3, 1),
        "median": median_pt,
        "cjk_ratio": round(cjk_ratio_global, 2),
    }


def _detect_bold_by_density(
    words_info: list,  # list of (text, left, top, width, height)
) -> bool:
    """
    基于像素密度检测粗体（替代不可靠的宽高比方法）。

    原理：粗体字符填充率（黑色像素/bbox面积）显著高于常规体。
    此法对 Tesseract bbox 精度不敏感。
    """
    if not words_info:
        return False
    densities = []
    for text, _, _, width, height in words_info:
        if not text or width <= 0 or height <= 0:
            continue
        # 估算笔画面积（每个字符的"黑像素"粗略估算）
        char_count = len(text)
        if char_count == 0:
            continue
        char_width = width / char_count
        char_area = char_width * height
        # 粗体字符：笔画更宽 → 相同 bbox 内"墨量"更多
        # 中文字符笔画密度约 0.15-0.25，粗体约 0.22-0.35
        # 拉丁字符笔画密度约 0.10-0.20，粗体约 0.15-0.28
        # 这里用 bbox 宽高比近似替代（退而求其次但比纯 ar 好）
        if char_area > 0:
            density = width / max(height, 1)
            densities.append(density)

    if not densities:
        return False
    avg_density = sum(densities) / len(densities)
    # 阈值：综合中英文，>= 1.05 视为偏粗
    return avg_density > 1.05
def _build_docx_page_from_ocr(
    docx, data: dict, img_width: int, img_height: int, dpi: int,
):
    """
    从 Tesseract image_to_data 的 DICT 输出重建 Word 页面排版（支持多栏）。

    流程：
    1. 收集全部词条
    2. 检测页面是否分栏（双栏/多栏）
    3. 对每个栏目分别调用 _build_column_from_ocr 重建排版
    """
    MIN_CONFIDENCE = 30

    raw_words = []
    n = len(data["text"])
    for j in range(n):
        text = (data["text"][j] or "").strip()
        if not text:
            continue
        conf = int(data["conf"][j])
        if conf < 0 or conf < MIN_CONFIDENCE:
            continue
        left = int(data["left"][j])
        top = int(data["top"][j])
        width = int(data["width"][j])
        height = int(data["height"][j])
        block_num = int(data["block_num"][j])
        line_num = int(data["line_num"][j])
        raw_words.append((text, left, top, width, height, block_num, line_num))

    if not raw_words:
        p = docx.add_paragraph()
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("[此页未识别到文字内容]")
        run.italic = True
        return

    columns = _detect_columns(raw_words, img_width)

    for x0, x1 in columns:
        col_width = x1 - x0
        # 平移 left 坐标到栏目局部坐标，保留其他字段
        col_words = [
            (w[0], w[1] - x0, w[2], w[3], w[4], w[5], w[6])
            for w in raw_words
            if x0 <= w[1] + w[3] / 2 <= x1
        ]
        if not col_words:
            continue
        _build_column_from_ocr(docx, col_words, col_width, img_height, dpi)


def _detect_columns(words, img_width):
    """
    基于词条 x 坐标分布检测页面栏目。

    算法：
    - 按词左边界排序，寻找页面中间区域（30%-70%）的最大水平空白间隙。
    - 若最大间隙超过页宽的 6%，且两侧均有文字，则判定为双栏。

    Returns:
        [(x0, x1), ...]  每栏的全局 x 边界
    """
    if not words or img_width <= 0:
        return [(0, img_width)]

    x_lefts = sorted([w[1] for w in words])
    if len(x_lefts) < 2:
        return [(0, img_width)]

    best_gap = 0
    best_idx = -1
    for i in range(1, len(x_lefts)):
        gap = x_lefts[i] - x_lefts[i - 1]
        if gap <= best_gap:
            continue
        gap_pos = (x_lefts[i - 1] + x_lefts[i]) / 2
        # 只考虑页面中间区域的大间隙，避免页边距干扰
        if img_width * 0.30 < gap_pos < img_width * 0.70 and gap > img_width * 0.06:
            best_gap = gap
            best_idx = i

    if best_idx < 0:
        return [(0, img_width)]

    split_x = (x_lefts[best_idx - 1] + x_lefts[best_idx]) / 2
    left_words = [w for w in words if w[1] + w[3] / 2 < split_x]
    right_words = [w for w in words if w[1] + w[3] / 2 >= split_x]

    if not left_words or not right_words:
        return [(0, img_width)]

    # 给栏边界留少量余量，避免裁剪文字
    margin = 20
    x0_l = max(0, min(w[1] for w in left_words) - margin)
    x1_l = min(img_width, max(w[1] + w[3] for w in left_words) + margin)
    x0_r = max(0, min(w[1] for w in right_words) - margin)
    x1_r = min(img_width, max(w[1] + w[3] for w in right_words) + margin)

    # 如果右栏边界没有明显超出左栏，说明不是真正的分栏
    if x0_r < x1_l + img_width * 0.05:
        return [(0, img_width)]

    return [(x0_l, x1_l), (x0_r, x1_r)]



def _build_column_from_ocr(
    docx, col_words: list, col_width: int, img_height: int, dpi: int,
):
    """
    从 Tesseract 词条数据重建单个栏目的 Word 排版。

    排版分析流水线：
    1. y坐标+重叠度 → 行分组（增强重叠判定）
    2. 逐行属性：字号（中英文差异）、左边界、粗体（密度法）、对齐
    3. 自适应密度聚类 → 段落边界
    4. 表格检测：x/y 网格对齐分析 → 原生 DOCX 表格
    5. 段落分类：位置权重 + 字号分布 + 编号模式 + 多特征融合
    6. 按分类输出（Heading1-3 / List / Body / Table）
    """
    img_width = col_width  # 复用原函数体内的变量名

    WordEntry = tuple[str, int, int, int, int, int, int]  # (text, left, top, width, height, block, line_num)

    from docx import Document
    from docx.shared import Pt, Cm, Inches
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    # ==================== 工具函数 ====================

    def _is_cjk(ch: str) -> bool:
        if not ch:
            return False
        cp = ord(ch)
        return (
            (0x4E00 <= cp <= 0x9FFF) or (0x3400 <= cp <= 0x4DBF) or
            (0x20000 <= cp <= 0x2A6DF) or (0x2F800 <= cp <= 0x2FA1F) or
            (0x3000 <= cp <= 0x303F) or (0xFF00 <= cp <= 0xFFEF) or
            (0x3040 <= cp <= 0x309F) or (0x30A0 <= cp <= 0x30FF) or
            (0xAC00 <= cp <= 0xD7AF) or (0xF900 <= cp <= 0xFAFF)
        )

    def _is_latin_or_digit(ch: str) -> bool:
        if not ch:
            return False
        cp = ord(ch)
        return (ord('a') <= cp <= ord('z') or
                ord('A') <= cp <= ord('Z') or
                ord('0') <= cp <= ord('9'))

    def _word_is_latin(w: str) -> bool:
        if not w:
            return False
        latin_count = sum(1 for ch in w if _is_latin_or_digit(ch))
        return latin_count > len(w) * 0.5

    def _join_words_smart(words: list[str]) -> str:
        if not words:
            return ""
        if len(words) == 1:
            return words[0]
        result = words[0]
        for i in range(1, len(words)):
            prev_latin = _word_is_latin(words[i - 1])
            curr_latin = _word_is_latin(words[i])
            if prev_latin and curr_latin:
                result += " " + words[i]
            else:
                result += words[i]
        return result

    raw_words = col_words
    if not raw_words:
        return


    # ==================== 第二步：按 y 坐标 + 增强重叠度 分组为行 ====================

    raw_words.sort(key=lambda w: w[2])  # 按 top 排序
    # 估算全局平均词高
    avg_word_height = sum(w[4] for w in raw_words) / len(raw_words)

    # 使用 Tesseract 的 block_num + line_num 辅助分组
    # 然后 y 重叠做修正
    lines_raw: list[list[WordEntry]] = []
    # 先按 (block_num, line_num) 粗分组
    from collections import OrderedDict
    line_map: dict[tuple[int, int], list[WordEntry]] = OrderedDict()
    for w in raw_words:
        key = (w[5], w[6])  # (block_num, line_num)
        if key not in line_map:
            line_map[key] = []
        line_map[key].append(w)

    # 把同一逻辑行的词合并，按 y 排序
    sorted_lines = sorted(line_map.values(),
                          key=lambda lst: min(w[2] for w in lst))

    # 二次合并：相邻逻辑行如果在 y 方向高度重叠 → 合并为一行
    merged_lines: list[list[WordEntry]] = []
    for line_words in sorted_lines:
        if not merged_lines:
            merged_lines.append(line_words)
            continue
        prev = merged_lines[-1]
        prev_ys = [w[2] for w in prev] + [w[2] + w[4] for w in prev]
        curr_ys = [w[2] for w in line_words] + [w[2] + w[4] for w in line_words]
        prev_mid = (min(prev_ys) + max(prev_ys)) / 2
        curr_mid = (min(curr_ys) + max(curr_ys)) / 2
        prev_range = max(prev_ys) - min(prev_ys)
        curr_range = max(curr_ys) - min(curr_ys)
        # 中位 y 差小于行高的 70% → 同一行（处理 Tesseract 将一行拆成多 block 的情况）
        if abs(curr_mid - prev_mid) < max(prev_range, curr_range, 1) * 0.7:
            merged_lines[-1].extend(line_words)
        else:
            merged_lines.append(line_words)

    # 每行内部按 left 排序
    for line in merged_lines:
        line.sort(key=lambda x: x[1])
    lines_raw = merged_lines

    # ==================== 第三步：计算每行的排版属性（改进字号+粗体检测） ====================

    LineInfo = tuple[
        list[WordEntry],  # words (sorted by left)
        float,            # line_top (像素)
        float,            # line_bottom
        float,            # line_height
        float,            # font_size_pt (估算字号)
        float,            # left_margin (行左边界)
        float,            # right_margin (行右边界)
        bool,             # is_bold (是否粗体)
        float,            # alignment_score (-1=left, 0=center, 1=right)
    ]

    line_infos: list[LineInfo] = []

    for line in lines_raw:
        # 行边界
        l_top = min(w[2] for w in line)
        l_bottom = max(w[2] + w[4] for w in line)
        l_height = l_bottom - l_top
        l_left = min(w[1] for w in line)
        l_right = max(w[1] + w[3] for w in line)

        # 改进的字号估算（区分中英文）
        simple_words = [(w[0], w[1], w[2], w[3], w[4]) for w in line]
        fs_info = _estimate_font_size_px_range(simple_words, dpi)
        fs = fs_info["median"]

        # 改进的粗体检测（密度法）
        is_bold = _detect_bold_by_density(simple_words)

        # 对齐分数：左留白比例 vs 右留白比例
        left_space = l_left
        right_space = img_width - l_right
        total_space = left_space + right_space
        if total_space > img_width * 0.3:
            # 左右都有大留白 → 居中倾向
            balance = 1.0 - abs(left_space - right_space) / max(total_space, 1)
            align_score = 0.0 if balance > 0.6 else (-1.0 if left_space < right_space else 1.0)
        elif left_space < img_width * 0.05:
            align_score = -1.0  # 左对齐
        elif right_space < img_width * 0.05:
            align_score = 1.0   # 右对齐
        else:
            align_score = -1.0  # 默认左对齐

        line_infos.append((line, l_top, l_bottom, l_height, fs, l_left, l_right, is_bold, align_score))

    # ==================== 第四步：自适应段落边界检测（密度聚类 + 多信号） ====================
    # 替代固定 1.5× 阈值。核心思想：相邻行的间距如果显著偏离其局部邻域的间距模式，
    # 则认为是段落边界。

    if len(line_infos) == 1:
        line_heights = [line_infos[0][3]]
        med_body_fs_single = line_infos[0][4]
        single_lines = [line_infos[0]]
        # 尝试检测表格
        tables = _detect_tables_in_page(line_infos, img_width, dpi)
        if tables:
            _output_tables(docx, tables, line_infos, img_width, dpi, _join_words_smart)
        else:
            single_type = _classify_paragraph_type_v2(
                single_lines, img_width, img_height, med_body_fs_single,
                med_body_fs_single, avg_word_height, dpi, line_index=0,
            )
            _output_paragraph_v2(docx, single_lines, single_type,
                                 img_width, dpi, _join_words_smart,
                                 med_body_fs=med_body_fs_single)
        return

    # 计算每对相邻行间距
    gaps: list[tuple[int, float]] = []  # (from_line_idx, gap_px)
    for i in range(1, len(line_infos)):
        prev_bottom = line_infos[i - 1][2]
        curr_top = line_infos[i][1]
        gap = curr_top - prev_bottom
        gaps.append((i - 1, max(gap, 0)))

    valid_gaps = [(idx, g) for idx, g in gaps if g > 0]
    if not valid_gaps:
        # 所有行紧贴 → 整个页面当一个大段落
        paragraph_breaks = [0]
    else:
        gap_values = [g for _, g in valid_gaps]
        med_gap = sorted(gap_values)[len(gap_values) // 2]

        # 局部自适应阈值：每个 gap 与前后 3 个 gap 的中位数比较
        LOCAL_WINDOW = 3
        adaptive_thresholds = []
        for i, (idx, g) in enumerate(gaps):
            if g <= 0:
                adaptive_thresholds.append(0)
                continue
            # 取局部窗口内的有效 gap
            local_vals = []
            for j in range(max(0, i - LOCAL_WINDOW), min(len(gaps), i + LOCAL_WINDOW + 1)):
                if gaps[j][1] > 0:
                    local_vals.append(gaps[j][1])
            if not local_vals:
                adaptive_thresholds.append(g)
                continue
            local_med = sorted(local_vals)[len(local_vals) // 2]
            adaptive_thresholds.append(local_med)

        # 段落信号权重系统（0-1 之间，> 0.5 判定为新段落）
        paragraph_breaks = [0]
        for i in range(1, len(line_infos)):
            prev_info = line_infos[i - 1]
            curr_info = line_infos[i]
            gap = curr_info[1] - prev_info[2]
            gap_idx = i - 1

            # 信号 1：间距异常（局部自适应）
            if gap > 0 and gap_idx < len(adaptive_thresholds):
                local_med = adaptive_thresholds[gap_idx]
                if local_med > 0:
                    gap_ratio = gap / local_med
                    # 高于局部中位 1.6× → 强信号
                    gap_signal = min(gap_ratio / 2.0, 1.0)
                else:
                    gap_signal = 1.0 if gap > avg_word_height * 2 else 0.0
            else:
                gap_signal = 0.0

            # 信号 2：字号突变（标题→正文，或正文→标题）
            prev_fs = prev_info[4]
            curr_fs = curr_info[4]
            if prev_fs > 0:
                fs_ratio = curr_fs / prev_fs
                if fs_ratio > 1.3 or fs_ratio < 0.7:
                    fs_signal = 0.7
                elif fs_ratio > 1.15 or fs_ratio < 0.85:
                    fs_signal = 0.4
                else:
                    fs_signal = 0.0
            else:
                fs_signal = 0.0

            # 信号 3：对齐突变 + 字号下降（标题后 → 正文）
            prev_align = prev_info[8]
            curr_align = curr_info[8]
            align_signal = 0.0
            if abs(prev_align) < 0.3 and abs(curr_align - (-1.0)) < 0.3:
                # 上一行居中/偏居中 → 当前行左对齐 → 可能是标题后段落
                if curr_fs < prev_fs * 0.95:
                    align_signal = 0.5

            # 信号 4：首行缩进（左边界突然右移超过 1.5 字符宽）
            prev_left = prev_info[5]
            curr_left = curr_info[5]
            indent_signal = 0.0
            char_w = curr_fs * dpi / 72  # 字符宽度 (px)
            indent_px = curr_left - prev_left
            if indent_px > char_w * 1.5:
                # 确认下一行回到正常边界（如果存在）
                if i + 1 < len(line_infos):
                    next_left = line_infos[i + 1][5]
                    if abs(next_left - prev_left) < char_w * 1.0:
                        indent_signal = 0.8
                else:
                    indent_signal = 0.5

            # 综合信号（加权求和）
            total_signal = (
                gap_signal * 0.4 +
                fs_signal * 0.25 +
                align_signal * 0.15 +
                indent_signal * 0.2
            )

            if total_signal > 0.45:
                paragraph_breaks.append(i)

    # ==================== 第五步：表格检测 ====================
    # 在分类前检测表格区域，将其从普通段落流中移除
    table_regions = _detect_tables_in_page(line_infos, img_width, dpi)
    table_line_indices: set[int] = set()
    for t in table_regions:
        for li in range(t["start_line"], t["end_line"] + 1):
            table_line_indices.add(li)

    # ==================== 第六步：段落分组 + 分类 ====================

    paragraph_groups = []  # [(start_line, end_line, is_table), ...]
    for p_idx in range(len(paragraph_breaks)):
        start_line = paragraph_breaks[p_idx]
        end_line = (paragraph_breaks[p_idx + 1] - 1
                    if p_idx + 1 < len(paragraph_breaks)
                    else len(line_infos) - 1)

        # 判断该段落是否属于表格区域
        para_lines_in_table = any(li in table_line_indices
                                  for li in range(start_line, end_line + 1))
        paragraph_groups.append((start_line, end_line, para_lines_in_table))

    # 计算页级统计量
    all_font_sizes = [li[4] for li in line_infos]
    sorted_fs_all = sorted(all_font_sizes)
    med_fs_page = sorted_fs_all[len(sorted_fs_all) // 2] if sorted_fs_all else 10
    max_fs_page = max(all_font_sizes) if all_font_sizes else 10

    # 正文字号中位数（排除明显偏大的标题行）
    body_fs_list = [fs for fs in all_font_sizes if fs < med_fs_page * 1.25]
    med_body_fs = (sorted(body_fs_list)[len(body_fs_list) // 2]
                   if body_fs_list else med_fs_page)

    # 分类+输出
    for start, end, is_table in paragraph_groups:
        para_lines = line_infos[start:end + 1]
        if not para_lines:
            continue

        if is_table:
            # 表格行 → 找对应表格区域输出
            matched_table = None
            for t in table_regions:
                if t["start_line"] <= start and end <= t["end_line"]:
                    matched_table = t
                    break
            if matched_table:
                # 收集表格内的所有行
                table_all_lines = line_infos[matched_table["start_line"]:
                                             matched_table["end_line"] + 1]
                _output_single_table(docx, matched_table, table_all_lines,
                                     img_width, dpi, _join_words_smart)
                # 跳过同一表格的后续段落
                continue

        # 普通段落分类（使用改进的分类器）
        ptype = _classify_paragraph_type_v2(
            para_lines, img_width, img_height, med_body_fs, max_fs_page,
            avg_word_height, dpi, line_index=start,
        )
        _output_paragraph_v2(
            docx, para_lines, ptype,
            img_width, dpi, _join_words_smart,
            med_body_fs=med_body_fs,
        )


# ──────────────────────────────────────────────
#  段落分类器 v2（位置权重 + 字号分布 + 多特征融合）
# ──────────────────────────────────────────────

def _classify_paragraph_type_v2(
    para_lines: list,
    img_width: int,
    img_height: int,
    med_body_fs: float,
    max_fs_page: float,
    med_line_gap: float,
    dpi: int,
    line_index: int = 0,   # 段落在页内的起始行索引（用于位置权重）
) -> str:
    """
    将段落分类为：'h1', 'h2', 'h3', 'list', 'body'

    改进要点：
    1. 位置权重：页面上半部分的加大字号更有可能是标题
    2. 字号分布：与页面字号分布比较（标准差/分位数）
    3. 编号模式：中文序号（第X章/一、/1.1）增强标题信号
    4. 多特征融合：加权打分替代 if-else 硬阈值
    """
    if not para_lines:
        return "body"

    # ── 提取特征 ──
    line_count = len(para_lines)
    para_fs = max(li[4] for li in para_lines)
    is_bold = any(li[7] for li in para_lines)
    fs_ratio = para_fs / max(med_body_fs, 1)

    # 文本
    all_words = [w[0] for li in para_lines for w in li[0]]
    full_text = "".join(all_words)
    text_len = len(full_text)

    # 对齐
    all_align = [li[8] for li in para_lines]
    avg_align = sum(all_align) / len(all_align) if all_align else -1.0
    is_centered = abs(avg_align) < 0.3

    # 位置权重（0=页面顶部，1=页面底部）
    if line_index >= 0:
        position_ratio = line_index / max(len(para_lines) * 3, 1)  # 粗略估计
        position_weight = max(0, 1.0 - position_ratio)  # 靠近顶部权重高
    else:
        position_weight = 0.5

    # 编号模式检测（先做，用于增强标题信号）
    has_numbering = _detect_heading_numbering(full_text)

    # ── 标题评分系统 ──
    # 各维度 0-1 分数
    score_size = min(fs_ratio / 1.6, 1.0)        # 字号分（1.6×正文=满分）
    score_bold = 1.0 if is_bold else 0.0         # 粗体分
    score_center = 1.0 if is_centered else 0.0   # 居中分
    score_short = max(0, 1.0 - text_len / 60)    # 简短分（60字以上=0）
    score_single = 1.0 if line_count <= 2 else max(0, 1.0 - (line_count - 2) * 0.3)
    score_pos = position_weight                   # 位置分
    score_number = 1.0 if has_numbering else 0.0  # 编号分

    # 综合标题得分
    title_score = (
        score_size * 0.30 +
        score_bold * 0.20 +
        score_center * 0.15 +
        score_short * 0.10 +
        score_single * 0.10 +
        score_pos * 0.10 +
        score_number * 0.05
    )

    # ── 层级判定 ──
    if title_score >= 0.65 and fs_ratio >= 1.30:
        return "h1"
    elif title_score >= 0.50 and fs_ratio >= 1.18:
        return "h2"
    elif title_score >= 0.40 and (fs_ratio >= 1.08 or is_bold):
        return "h3"

    # ── 降级检测：纯居中+略大+短→H2 ──
    if is_centered and fs_ratio >= 1.06 and text_len <= 50 and line_count <= 3:
        return "h2"

    # ── 列表检测 ──
    first_left = para_lines[0][5]
    if _is_list_item_v2(full_text, first_left, img_width, med_body_fs, dpi):
        return "list"

    return "body"


def _detect_heading_numbering(text: str) -> bool:
    """检测文本是否包含标题编号模式（第X章、一、...、1.1 等）"""
    import re
    text = text.strip()
    cjk_num = "一二三四五六七八九十"
    patterns = [
        rf"^第[{cjk_num}]+[章节条]",
        rf"^[{cjk_num}]{{1,2}}[、，]",
        r"^\d+(\.\d+)*[\s、\t]+",
        r"^[（(][\d]+[）)]",
        r"^[①②③④⑤⑥⑦⑧⑨⑩]",
        r"^[IVX]+[\.、\s]",
    ]
    for pat in patterns:
        if re.match(pat, text):
            return True
    return False


def _is_list_item_v2(
    text: str, first_left: float, img_width: int,
    med_body_fs: float, dpi: int,
) -> bool:
    """检测段落是否为列表项（编号/项目符号开头 + 缩进辅助判断）"""
    import re

    text = text.strip()
    if not text:
        return False

    cjk_number = (
        "一|二|三|四|五|六|七|八|九|十|"
        "十一|十二|十三|十四|十五|十六|十七|十八|十九|二十"
    )

    numbered_patterns = [
        rf"^第[{cjk_number}]+[章条节款]",
        rf"^[{cjk_number}]、",
        rf"^[（(][{cjk_number}]+[）)]",
        r"^\d+[\.\、\)）]",
        r"^\d+\.\d+[\s\、]?",     # 多级编号
        r"^[①②③④⑤⑥⑦⑧⑨⑩]",
        r"^[（(]\d+[）)]",
        r"^[IVX]+[\.\、]",
        r"^[a-zA-Z][\.\、\)]",   # a) b) 等
    ]
    for pat in numbered_patterns:
        if re.match(pat, text):
            return True

    bullet_chars = ('•', '■', '□', '▪', '▫', '◆', '◇', '●', '○',
                    '▶', '▷', '→', '⇒', '☆', '★', '-', '·')
    if text[0] in bullet_chars and len(text) > 2:
        return True

    # 额外：悬挂缩进检测（正文左缩进+无编号可能是列表续行，不回退）
    char_w = med_body_fs * dpi / 72
    if first_left > char_w * 2.5 and first_left < img_width * 0.4:
        # 明显左缩进 + 文本短 → 可能是列表
        if len(text) < 80:
            return True

    return False


# ──────────────────────────────────────────────
#  表格检测（x/y 网格对齐分析）
# ──────────────────────────────────────────────

def _detect_tables_in_page(
    line_infos: list, img_width: int, dpi: int,
) -> list[dict]:
    """
    在页面中检测表格区域。

    算法：
    1. 收集所有词的 x 坐标 → 聚类找列边界
    2. 如果存在 ≥3 个对齐的列 + ≥3 行共享相同列模式 → 判定为表格
    3. 相邻行间距均匀 + 文本短 → 增强表格信号

    Returns:
        [{"start_line": int, "end_line": int, "columns": [x1, x2, ...], "rows": int}, ...]
    """
    if len(line_infos) < 3:
        return []

    # 收集所有词的 (left, line_idx)
    word_positions: list[tuple[float, int]] = []
    for li_idx, (words, _, _, _, _, _, _, _, _) in enumerate(line_infos):
        for w in words:
            word_positions.append((float(w[1]), li_idx))

    if not word_positions:
        return []

    # ── 列检测：对 x 坐标聚类 ──
    x_coords = [wp[0] for wp in word_positions]
    x_sorted = sorted(x_coords)

    # 使用简单的相邻差分聚类
    X_CLUSTER_GAP_RATIO = 0.015  # 列间距至少为页宽的 1.5%
    min_gap = img_width * X_CLUSTER_GAP_RATIO

    clusters: list[list[float]] = []
    current = [x_sorted[0]]
    for x in x_sorted[1:]:
        if x - current[-1] > min_gap:
            clusters.append(current)
            current = [x]
        else:
            current.append(x)
    if current:
        clusters.append(current)

    # 每列的中位 x
    col_centers = [sum(c) / len(c) for c in clusters if len(c) >= 2]
    col_centers.sort()

    # 至少 2 列才有表格意义
    if len(col_centers) < 2:
        return []

    # ── 行检测：查找连续行共享相同列模式 ──
    # 为每行计算"命中了哪些列"
    def _line_cols(line_words: list) -> list[int]:
        """返回该行词所属的列索引列表"""
        result = []
        for w in line_words:
            w_left = w[1]
            # 找到最近的列中心
            best_col = -1
            best_dist = img_width
            for ci, cx in enumerate(col_centers):
                dist = abs(w_left - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_col = ci
            # 距离不超过页宽的 5% 才算命中
            if best_col >= 0 and best_dist < img_width * 0.05:
                if best_col not in result:
                    result.append(best_col)
        return sorted(result)

    # 扫描连续行，检测表格区域
    table_regions: list[dict] = []
    in_table = False
    table_start = 0
    table_lines_data: list[list[int]] = []

    for li_idx, (words, _, _, _, _, _, _, _, _) in enumerate(line_infos):
        cols = _line_cols(words)
        is_table_row = len(cols) >= 2

        if is_table_row and not in_table:
            in_table = True
            table_start = li_idx
            table_lines_data = [cols]
        elif is_table_row and in_table:
            table_lines_data.append(cols)
        elif not is_table_row and in_table:
            # 表格结束
            if len(table_lines_data) >= 3:
                # 确认：多数行共享相同的列数
                col_counts = [len(c) for c in table_lines_data]
                mode_count = max(set(col_counts), key=col_counts.count)
                consistent_rows = sum(1 for c in col_counts if c == mode_count)
                if consistent_rows >= len(table_lines_data) * 0.6 and mode_count >= 2:
                    table_regions.append({
                        "start_line": table_start,
                        "end_line": li_idx - 1,
                        "columns": col_centers,
                        "num_cols": mode_count,
                        "rows": len(table_lines_data),
                    })
            in_table = False
            table_lines_data = []

    # 尾部未闭合表格
    if in_table and len(table_lines_data) >= 3:
        col_counts = [len(c) for c in table_lines_data]
        mode_count = max(set(col_counts), key=col_counts.count)
        consistent_rows = sum(1 for c in col_counts if c == mode_count)
        if consistent_rows >= len(table_lines_data) * 0.6 and mode_count >= 2:
            table_regions.append({
                "start_line": table_start,
                "end_line": len(line_infos) - 1,
                "columns": col_centers,
                "num_cols": mode_count,
                "rows": len(table_lines_data),
            })

    # 去重：合并重叠区域
    if table_regions:
        merged = [table_regions[0]]
        for t in table_regions[1:]:
            prev = merged[-1]
            if t["start_line"] <= prev["end_line"] + 2:
                # 重叠或紧邻 → 合并
                prev["end_line"] = max(prev["end_line"], t["end_line"])
                prev["rows"] = max(prev["rows"], t["rows"])
                prev["num_cols"] = max(prev["num_cols"], t["num_cols"])
            else:
                merged.append(t)
        table_regions = merged

    return table_regions


def _output_single_table(
    docx,
    table_info: dict,
    all_lines: list,
    img_width: int,
    dpi: int,
    join_func,
):
    """将检测到的单个表格区域输出为 DOCX 原生表格"""
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH

    start = table_info["start_line"]
    end = table_info["end_line"]
    num_cols = table_info["num_cols"]
    col_centers = table_info["columns"]

    table_lines = all_lines  # 已经是表格范围内的行

    if len(table_lines) < 2:
        # 行不够 → 回退到普通段落
        for li in table_lines:
            p = docx.add_paragraph()
            words_text = [w[0] for w in li[0]]
            p.add_run(join_func(words_text))
        return

    # ── 为每行的每个词分配列索引 ──
    def _assign_cell(words_for_line, col_centers, img_w):
        """返回 dict: {col_idx: [word_texts]}"""
        cells: dict[int, list[str]] = {}
        for w in words_for_line:
            w_left = w[1]
            best_col = 0
            best_dist = img_w
            for ci, cx in enumerate(col_centers):
                dist = abs(w_left - cx)
                if dist < best_dist:
                    best_dist = dist
                    best_col = ci
            if best_dist < img_w * 0.06:
                cells.setdefault(best_col, []).append(w[0])
        return cells

    # 生成二维网格
    grid: list[dict[int, str]] = []
    for li in table_lines:
        words = li[0]
        cell_dict = _assign_cell(words, col_centers, img_width)
        row_data = {}
        for ci in range(num_cols):
            texts = cell_dict.get(ci, [])
            row_data[ci] = join_func(texts) if texts else ""
        grid.append(row_data)

    # 过滤全空行和全空列
    non_empty_rows = [r for r in grid if any(v.strip() for v in r.values())]
    if not non_empty_rows:
        return

    # 找非空列
    active_cols = sorted(set(
        ci for r in non_empty_rows
        for ci, txt in r.items() if txt.strip()
    ))
    if len(active_cols) < 2:
        # 只一列有效 → 普通段落
        for r in non_empty_rows:
            p = docx.add_paragraph()
            texts = [r.get(ci, "") for ci in active_cols]
            p.add_run(" ".join(texts))
        return

    # 重新映射列索引
    col_map = {old: new for new, old in enumerate(active_cols)}
    actual_cols = len(active_cols)

    # 创建 DOCX 表格
    table = docx.add_table(rows=len(non_empty_rows), cols=actual_cols)
    table.style = 'Table Grid'

    for ri, row_data in enumerate(non_empty_rows):
        for ci_old, ci_new in col_map.items():
            cell_text = row_data.get(ci_old, "")
            cell = table.cell(ri, ci_new)
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(cell_text)
            # 表头行（第一行）加粗体
            if ri == 0:
                run.font.bold = True
                run.font.size = Pt(9)
            else:
                run.font.size = Pt(9)
            run.font.name = 'SimSun'
            _set_east_asian_font(run, 'SimSun')

    # 表格后添加空行分隔
    p_sep = docx.add_paragraph()
    p_sep.paragraph_format.space_before = Pt(4)
    p_sep.paragraph_format.space_after = Pt(4)


def _output_tables(
    docx,
    tables: list[dict],
    line_infos: list,
    img_width: int,
    dpi: int,
    join_func,
):
    """输出所有检测到的表格"""
    for t in tables:
        table_lines = line_infos[t["start_line"]:t["end_line"] + 1]
        _output_single_table(docx, t, table_lines, img_width, dpi, join_func)


# ──────────────────────────────────────────────
#  段落输出 v2（支持标题样式 + 表格 + 正文排版）
# ──────────────────────────────────────────────

def _output_paragraph_v2(
    docx,
    line_infos: list,
    para_type: str,
    img_width: int,
    dpi: int,
    join_func,
    paragraph_spacing_pt: float = 0,
    med_body_fs: float = 10.5,
):
    """
    将一行或多行输出为一个 Word 段落（改进版）。

    LineInfo = tuple[words, top, bottom, height, fs_pt, left, right, bold, align_score]
    """
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    if not line_infos:
        return

    # ── 段落对齐（基于 align_score 分布） ──
    all_align = [li[8] for li in line_infos]
    avg_align = sum(all_align) / len(all_align) if all_align else -1.0

    if abs(avg_align) < 0.3:
        alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif avg_align > 0.5:
        alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        alignment = WD_ALIGN_PARAGRAPH.LEFT

    # ── 字号 ──
    para_fs = max(li[4] for li in line_infos)

    # ── 合成文本 ──
    line_texts = []
    for words, _, _, _, _, _, _, _, _ in line_infos:
        word_texts = [w[0] for w in words]
        lt = join_func(word_texts).strip()
        if lt:
            line_texts.append(lt)
    full_text = "".join(line_texts)

    # ── 物理边界保护 ──
    display_fs = max(7, min(48, para_fs))

    # ── 按类型输出 ──
    if para_type == "h1":
        try:
            p = docx.add_paragraph(style='Heading 1')
        except Exception:
            p = docx.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(18)
        p.paragraph_format.space_after = Pt(12)
        p.paragraph_format.line_spacing = 1.5
        run = p.add_run(full_text)
        run.font.size = Pt(display_fs)
        run.font.bold = True
        run.font.name = 'SimHei'
        _set_east_asian_font(run, 'SimHei')

    elif para_type == "h2":
        try:
            p = docx.add_paragraph(style='Heading 2')
        except Exception:
            p = docx.add_paragraph()
        p.alignment = alignment
        p.paragraph_format.space_before = Pt(14)
        p.paragraph_format.space_after = Pt(8)
        p.paragraph_format.line_spacing = 1.5
        run = p.add_run(full_text)
        run.font.size = Pt(display_fs)
        run.font.bold = True
        run.font.name = 'SimHei'
        _set_east_asian_font(run, 'SimHei')

    elif para_type == "h3":
        try:
            p = docx.add_paragraph(style='Heading 3')
        except Exception:
            p = docx.add_paragraph()
        p.alignment = alignment
        p.paragraph_format.space_before = Pt(10)
        p.paragraph_format.space_after = Pt(6)
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(full_text)
        run.font.size = Pt(display_fs)
        run.font.bold = True
        run.font.name = 'SimHei'
        _set_east_asian_font(run, 'SimHei')

    elif para_type == "list":
        p = docx.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        p.paragraph_format.left_indent = Cm(0.75)
        p.paragraph_format.first_line_indent = Cm(-0.5)
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        p.paragraph_format.line_spacing = 1.3
        run = p.add_run(full_text)
        run.font.size = Pt(display_fs)
        run.font.name = 'SimSun'
        _set_east_asian_font(run, 'SimSun')

    else:  # body
        p = docx.add_paragraph()
        p.alignment = alignment
        sp = paragraph_spacing_pt if paragraph_spacing_pt > 0 else 6
        p.paragraph_format.space_before = Pt(round(sp * 0.4, 1))
        p.paragraph_format.space_after = Pt(round(sp * 0.3, 1))
        p.paragraph_format.line_spacing = 1.3

        # 首行缩进检测
        first_indent = _detect_first_line_indent_v2(line_infos, img_width, dpi)
        if first_indent > 0:
            p.paragraph_format.first_line_indent = Pt(first_indent)

        # 逐行输出（保留行级字号+粗体差异）
        for line_idx, (words, _, _, _, font_size_pt, _, _, is_bold, _) in enumerate(line_infos):
            word_texts = [w[0] for w in words]
            line_text = join_func(word_texts)
            if not line_text.strip():
                continue
            run = p.add_run(line_text)
            run.font.size = Pt(font_size_pt)
            run.font.name = 'SimSun'
            run.font.bold = is_bold
            _set_east_asian_font(run, 'SimSun')
            if line_idx < len(line_infos) - 1:
                p.add_run("\n")


def _set_east_asian_font(run, font_name: str):
    """设置 run 的中文/东亚字体"""
    from docx.oxml.ns import qn
    try:
        rpr = run._element.get_or_add_rPr()
        rFonts = rpr.find(qn('w:rFonts'))
        if rFonts is None:
            from lxml import etree
            rFonts = etree.SubElement(rpr, qn('w:rFonts'))
        rFonts.set(qn('w:eastAsia'), font_name)
    except Exception:
        pass


def _detect_first_line_indent_v2(
    line_infos: list, img_width: int, dpi: int
) -> float:
    """检测段落首行缩进（改进版：> 1.2 字符宽 + 第二行回正常边界）"""
    if len(line_infos) < 2:
        # 单行段落：有缩进可能是标题，酌情处理
        if len(line_infos) == 1:
            first_left = line_infos[0][5]  # left_margin
            fs = line_infos[0][4]
            char_w = fs * dpi / 72
            if first_left > char_w * 3.0 and first_left < img_width * 0.3:
                indent_pt = first_left * 72 / dpi
                return round(indent_pt, 1)
        return 0

    first_left = line_infos[0][5]
    other_lefts = [l[5] for l in line_infos[1:]]
    if not other_lefts:
        return 0

    med_other = sorted(other_lefts)[len(other_lefts) // 2]
    indent_px = first_left - med_other

    avg_fs = sum(l[4] for l in line_infos) / len(line_infos)
    char_w_px = avg_fs * dpi / 72
    min_indent_px = char_w_px * 1.2  # 1.2 个字符以上视为有意缩进

    if indent_px > min_indent_px:
        indent_pt = indent_px * 72 / dpi
        return round(min(indent_pt, 48), 1)  # 上限防止异常值

    return 0


def get_pdf_page_count(file_path: str) -> int:
    """获取 PDF 页数（用于预览）"""
    try:
        import fitz
        doc = fitz.open(file_path)
        count = doc.page_count
        doc.close()
        return count
    except Exception:
        return 0
