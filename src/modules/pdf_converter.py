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
) -> str:
    """
    将 PDF 转换为 Word (.docx) 文档。
    自动检测 PDF 类型，扫描型使用 OCR，文字型使用 pdf2docx。

    Args:
        file_path:             PDF 文件路径
        output_dir:            输出目录（空则同源目录）
        preserve_formatting:   保留原始格式（OCR 模式不支持）
        preserve_images:       保留图片（OCR 模式不支持）
        force_ocr:             强制使用 OCR（即使检测为文字型）

    Returns:
        输出 .docx 文件路径
    """
    if not file_path.lower().endswith('.pdf'):
        raise ValueError(f"不支持的文件格式: {file_path}")

    if not os.path.exists(file_path):
        raise FileNotFoundError(f"文件不存在: {file_path}")

    # 确定输出路径
    base = os.path.splitext(os.path.basename(file_path))[0]
    out_dir = output_dir or os.path.dirname(file_path)
    os.makedirs(out_dir, exist_ok=True)
    out_path = os.path.join(out_dir, f"{base}.docx")

    # 检测 PDF 类型
    pdf_type, text_pages, total_pages = detect_pdf_type(file_path)

    if not force_ocr and pdf_type == "text":
        # 文字型：使用 pdf2docx 直接转换
        return _convert_with_pdf2docx(
            file_path, out_path, out_dir,
            preserve_formatting, preserve_images
        )
    else:
        # 扫描型 / 混合型 / 强制 OCR：使用 OCR 转换
        return _convert_with_ocr(
            file_path, out_path,
            pdf_type=pdf_type, text_pages=text_pages
        )


def _convert_with_pdf2docx(
    file_path: str, out_path: str, out_dir: str,
    preserve_formatting: bool, preserve_images: bool,
) -> str:
    """使用 pdf2docx 库转换文字型 PDF"""
    try:
        from pdf2docx import Converter

        images_folder = None
        if preserve_images:
            images_folder = os.path.join(out_dir, "images")
            os.makedirs(images_folder, exist_ok=True)

        cv = Converter(file_path)
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

    return out_path


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


def _setup_tesseract():
    """配置 pytesseract 的 tesseract_cmd 路径"""
    import pytesseract
    # 如果已经配置过且可用，直接返回
    try:
        pytesseract.get_tesseract_version()
        return
    except Exception:
        pass

    # 自动查找
    tesseract_path = _find_tesseract()
    if tesseract_path:
        pytesseract.pytesseract.tesseract_cmd = tesseract_path
    else:
        raise RuntimeError(
            "未找到 Tesseract OCR 引擎。请从以下地址下载安装：\n"
            "https://github.com/UB-Mannheim/tesseract/wiki\n"
            "安装时请勾选中文简体语言包 (chi_sim)"
        )


def _convert_with_ocr(
    file_path: str, out_path: str,
    pdf_type: str = "scanned", text_pages: int = 0,
    dpi: int = 300, lang: str = "chi_sim+eng",
) -> str:
    """
    使用 OCR 转换扫描型 PDF。
    逐页渲染 → pytesseract 识别 → python-docx 生成。
    """
    try:
        import fitz
        from PIL import Image
        from docx import Document
        from docx.shared import Pt, Inches
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError as e:
        raise ImportError(f"OCR 转换缺少依赖: {e}")

    # 检查并配置 pytesseract（自动查找安装路径）
    try:
        import pytesseract
    except ImportError:
        raise ImportError(
            "pytesseract 未安装。请运行: pip install pytesseract\n"
            "同时需要安装 Tesseract OCR 引擎: https://github.com/UB-Mannheim/tesseract/wiki"
        )

    _setup_tesseract()

    # 打开 PDF
    doc = fitz.open(file_path)
    total = doc.page_count

    # 创建 Word 文档
    docx = Document()

    # 设置默认字体
    style = docx.styles['Normal']
    font = style.font
    font.name = 'SimSun'
    font.size = Pt(10.5)

    for i in range(total):
        page = doc[i]

        # 如果该页有文字层（混合型 PDF），优先提取文字
        page_text = page.get_text().strip()
        if pdf_type == "mixed" and page_text:
            docx.add_paragraph(page_text)
        else:
            # 渲染页面为图片 → OCR 识别
            pix = page.get_pixmap(dpi=dpi)
            img_data = pix.tobytes("png")
            img = Image.open(io.BytesIO(img_data))

            try:
                ocr_text = pytesseract.image_to_string(img, lang=lang)
            except pytesseract.TesseractError as e:
                raise RuntimeError(f"OCR 识别失败 (第{i+1}页): {str(e)}")

            if ocr_text.strip():
                docx.add_paragraph(ocr_text.strip())
            else:
                # 空识别结果，插入提示
                p = docx.add_paragraph()
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
                run = p.add_run(f"[第 {i+1} 页：未识别到文字内容]")
                run.font.color.rgb = None  # 默认黑色
                run.italic = True

        # 页间分隔
        if i < total - 1:
            docx.add_page_break()

    doc.close()

    # 保存
    docx.save(out_path)

    if not os.path.exists(out_path):
        raise RuntimeError("输出文件未生成")

    return out_path


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
