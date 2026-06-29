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
    """使用 pdf2docx 库转换文字型 PDF"""
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

    _report(1, 1)  # 完成
    return out_path


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

    # 构建 Tesseract 自定义配置：指定页面分割模式 + 输出优化
    # --psm 6: 将图像视为统一的文本块（适合扫描文档页面）
    # -c tessedit_write_images=false: 不写调试图片
    tesseract_config = "--psm 6 -c tessedit_write_images=false"

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


def _preprocess_for_ocr(img) -> "Image.Image":
    """
    对渲染图片进行预处理以提升 OCR 准确率。

    策略：保留灰度信息让 Tesseract 内部做自适应阈值（避免硬二值化丢失细节），
    仅做对比度增强和轻度锐化。尺寸不变，坐标不变。
    """
    from PIL import Image, ImageFilter, ImageOps

    # 1. 转灰度（保留 256 级灰度供 Tesseract 内部阈值）
    if img.mode != 'L':
        img = img.convert('L')

    # 2. 对比度增强：拉伸直方图剪掉 2% 的极端值
    img = ImageOps.autocontrast(img, cutoff=2)

    # 3. 轻度锐化突出文字边缘
    img = img.filter(ImageFilter.SHARPEN)

    return img


def _build_docx_page_from_ocr(
    docx, data: dict, img_width: int, img_height: int, dpi: int,
):
    """
    从 Tesseract image_to_data 的 DICT 输出重建 Word 页面排版。

    排版分析流水线：
    1. y坐标+重叠度 → 行分组
    2. 逐行属性：字号、左边界、粗体
    3. 空间分析 → 段落边界
    4. 段落分类 → 主标题(H1)/节标题(H2)/小节标题(H3)/正文/列表项
    5. 按分类使用 Word 内置样式输出
    """
    from docx import Document
    from docx.shared import Pt, Cm
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
            (0xAC00 <= cp <= 0xD7AF)
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

    # ==================== 第一步：收集有效词条 ====================
    MIN_CONFIDENCE = 40

    WordEntry = tuple[str, int, int, int, int]  # (text, left, top, width, height)

    raw_words: list[WordEntry] = []
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
        raw_words.append((text, left, top, width, height))

    if not raw_words:
        p = docx.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        run = p.add_run("[此页未识别到文字内容]")
        run.italic = True
        return

    # ==================== 第二步：按 y 坐标 + 重叠度 分组为行 ====================
    # 比 Tesseract 自带的 line_num 更可靠（对中英文混排、上下标等场景）

    # 按 top 排序
    raw_words.sort(key=lambda w: w[2])
    # 估算全局平均行高作为行重叠阈值
    avg_word_height = sum(w[4] for w in raw_words) / len(raw_words)

    lines_raw: list[list[WordEntry]] = []
    current_line: list[WordEntry] = []
    current_line_y_range = (0, 0)  # (top_min, bottom_max)

    for w in raw_words:
        w_top = w[2]
        w_bottom = w[2] + w[4]

        if not current_line:
            current_line = [w]
            current_line_y_range = (w_top, w_bottom)
            continue

        # 当前词与已收集行在 y 方向有足够重叠 → 同一行
        line_top, line_bottom = current_line_y_range
        overlap_top = max(w_top, line_top)
        overlap_bottom = min(w_bottom, line_bottom)
        overlap = overlap_bottom - overlap_top
        # 重叠超过词高的一半 或 词顶在行范围内 → 同一行
        if overlap > w[4] * 0.3 or (line_top <= w_top <= line_bottom):
            current_line.append(w)
            current_line_y_range = (
                min(line_top, w_top),
                max(line_bottom, w_bottom),
            )
        else:
            # 按 left 排序当前行后放入结果
            current_line.sort(key=lambda x: x[1])
            lines_raw.append(current_line)
            current_line = [w]
            current_line_y_range = (w_top, w_bottom)

    if current_line:
        current_line.sort(key=lambda x: x[1])
        lines_raw.append(current_line)

    # ==================== 第三步：计算每行的排版属性 ====================

    LineInfo = tuple[
        list[WordEntry],  # words (sorted by left)
        float,            # line_top (像素)
        float,            # line_bottom
        float,            # line_height
        float,            # font_size_pt (估算字号)
        float,            # left_margin (行左边界)
        bool,             # is_bold (是否粗体)
    ]

    line_infos: list[LineInfo] = []

    for line in lines_raw:
        # 行边界
        l_top = min(w[2] for w in line)
        l_bottom = max(w[2] + w[4] for w in line)
        l_height = l_bottom - l_top
        l_left = min(w[1] for w in line)
        l_right = max(w[1] + w[3] for w in line)

        # 字号：OCR 像素行高 → 物理 pt（不走人为放大/缩小）
        # 公式：pixel_height / DPI * 72 = pt，0.88 补偿 Tesseract 边界框偏大 10-15%
        fs = max(6, min(48, l_height * 72 * 0.88 / dpi))
        fs = round(fs, 1)

        # 粗体检测：如果字符宽高比普遍偏大（粗体字更宽）
        ar_list = [w[3] / max(w[4], 1) for w in line if w[4] > 0]
        avg_ar = sum(ar_list) / len(ar_list) if ar_list else 1.0
        is_bold = avg_ar > 1.1  # 粗体字符宽高比通常更大

        line_infos.append((line, l_top, l_bottom, l_height, fs, l_left, is_bold))

    # ==================== 第四步：空间分析检测段落边界 ====================

    # 计算行间距列表
    line_gaps: list[float] = []
    for i in range(1, len(line_infos)):
        prev_bottom = line_infos[i - 1][2]
        curr_top = line_infos[i][1]
        gap = curr_top - prev_bottom
        if gap > 0:
            line_gaps.append(gap)

    if not line_gaps:
        # 只有一行 → 分类后输出
        med_body_fs_single = line_infos[0][4]  # 唯一样本即正文字号
        single_type = _classify_paragraph_type(
            line_infos, img_width, med_body_fs_single, med_body_fs_single,
            avg_word_height, dpi,
        )
        _output_paragraph(docx, line_infos, single_type,
                          img_width, dpi, _join_words_smart,
                          med_body_fs=med_body_fs_single)
        return

    # 中位数行间距
    sorted_gaps = sorted(line_gaps)
    med_gap = sorted_gaps[len(sorted_gaps) // 2]

    # 段落边界检测：间距 > 1.5×中位数行间距 → 新段落
    # 同时检测左缩进突变（首行缩进）、字号突变（标题）、居中行（标题）
    PARAGRAPH_GAP_RATIO = 1.5
    INDENT_THRESHOLD_PX = avg_word_height * 1.2  # 缩进检测阈值

    paragraph_breaks: list[int] = []  # 每个段落的起始行索引
    paragraph_breaks.append(0)

    for i in range(1, len(line_infos)):
        prev_info = line_infos[i - 1]
        curr_info = line_infos[i]
        gap = curr_info[1] - prev_info[2]  # 行间距
        prev_left = prev_info[5]
        curr_left = curr_info[5]
        prev_fs = prev_info[4]
        curr_fs = curr_info[4]
        prev_is_center = abs(prev_left / max(img_width, 1) - 0.5) < 0.25

        is_new_para = False

        # 条件1：行间距异常大
        if med_gap > 0 and gap > med_gap * PARAGRAPH_GAP_RATIO:
            is_new_para = True

        # 条件2：上行是居中标题 → 下一行必是新段落
        if not is_new_para and prev_is_center and curr_fs < prev_fs * 0.85:
            is_new_para = True

        # 条件3：字号突然变大（新标题/章节开始）
        if not is_new_para and curr_fs > prev_fs * 1.25:
            is_new_para = True

        # 条件4：左缩进明显增大（首行缩进标志新段落）
        if not is_new_para and curr_left - prev_left > INDENT_THRESHOLD_PX:
            # 确认下一行回到正常边界
            if i + 1 < len(line_infos):
                next_left = line_infos[i + 1][5]
                if abs(next_left - prev_left) < INDENT_THRESHOLD_PX * 0.7:
                    is_new_para = True

        if is_new_para:
            paragraph_breaks.append(i)

    # ==================== 第五步：段落分类 ====================

    # 先将段落分组
    paragraph_groups = []  # [(start_line, end_line), ...]
    for p_idx in range(len(paragraph_breaks)):
        start_line = paragraph_breaks[p_idx]
        end_line = (paragraph_breaks[p_idx + 1] - 1
                    if p_idx + 1 < len(paragraph_breaks)
                    else len(line_infos) - 1)
        paragraph_groups.append((start_line, end_line))

    # 计算页级统计量用于分类
    all_font_sizes = [li[4] for li in line_infos]
    sorted_fs = sorted(all_font_sizes)
    med_fs_page = sorted_fs[len(sorted_fs) // 2] if sorted_fs else 10
    max_fs_page = max(all_font_sizes) if all_font_sizes else 10

    # 正文字号中位数（排除明显偏大的标题行）
    body_fs = [fs for fs in all_font_sizes if fs < med_fs_page * 1.25]
    med_body_fs = sorted(body_fs)[len(body_fs) // 2] if body_fs else med_fs_page

    # 行间距统计
    med_line_height_px = sorted_gaps[len(sorted_gaps) // 2] if sorted_gaps else avg_word_height

    # 对每个段落分类
    para_types = []
    for start, end in paragraph_groups:
        para_lines = line_infos[start:end + 1]
        ptype = _classify_paragraph_type(
            para_lines, img_width, med_body_fs, max_fs_page,
            med_line_height_px, dpi,
        )
        para_types.append(ptype)

    # ==================== 第六步：输出段落（按分类使用样式） ====================
    paragraph_spacing_pt = round(med_line_height_px * 72 / dpi, 1) if med_line_height_px > 0 else 6

    for (start, end), ptype in zip(paragraph_groups, para_types):
        para_lines = line_infos[start:end + 1]
        _output_paragraph(
            docx, para_lines, ptype,
            img_width, dpi, _join_words_smart,
            paragraph_spacing_pt=paragraph_spacing_pt,
            med_body_fs=med_body_fs,
        )


# ──────────────────────────────────────────────
#  段落分类器
# ──────────────────────────────────────────────

def _classify_paragraph_type(
    para_lines: list,
    img_width: int,
    med_body_fs: float,      # 页面正文字号中位数
    max_fs_page: float,       # 页面最大字号
    med_line_gap: float,      # 中位数行间距 (px)
    dpi: int,
) -> str:
    """
    将段落分类为：'h1', 'h2', 'h3', 'list', 'body'

    信号权重：
    - 字号（相对正文字号的比例）
    - 对齐方式（居中=标题特征）
    - 粗体
    - 文本长度（标题通常短）
    - 段前段后间距
    """
    if not para_lines:
        return "body"

    # ── 提取段落级特征 ──
    line_count = len(para_lines)
    first_line = para_lines[0]
    first_left = first_line[5]
    para_fs = max(li[4] for li in para_lines)
    is_bold = any(li[6] for li in para_lines)

    # 文本总长
    all_words = [w[0] for li in para_lines for w in li[0]]
    full_text = "".join(all_words)
    text_len = len(full_text)

    # 对齐检测
    all_lefts = [li[5] for li in para_lines]
    all_rights = [max(w[1] + w[3] for w in li[0]) for li in para_lines]
    avg_left = sum(all_lefts) / len(all_lefts) if all_lefts else 0
    avg_right = sum(all_rights) / len(all_rights) if all_rights else img_width
    left_ratio = avg_left / max(img_width, 1)
    right_ratio = (img_width - avg_right) / max(img_width, 1)
    is_centered = left_ratio > 0.25 and right_ratio > 0.25

    # 字号比例
    fs_ratio = para_fs / max(med_body_fs, 1)

    # ── 标题检测优先于列表（避免 "第一章" 之类被误判为列表） ──

    # H1 主标题：居中 + 全页最大字号 + 粗体 + 短文本
    if (is_centered and fs_ratio >= 1.45 and is_bold
            and text_len <= 40 and line_count <= 2
            and para_fs >= max_fs_page * 0.85):
        return "h1"

    # H2 节标题：字号 ≥ 正文 1.35 倍 + 粗体 + 较短
    if (fs_ratio >= 1.30 and is_bold
            and text_len <= 60 and line_count <= 3):
        return "h2"

    # H3 小节标题：字号 ≥ 正文 1.15 倍 + 粗体
    if (fs_ratio >= 1.12 and is_bold
            and text_len <= 100 and line_count <= 5):
        return "h3"

    # 降级：居中 + 略大 + 短 → H2
    if is_centered and fs_ratio >= 1.08 and text_len <= 50 and line_count <= 3:
        return "h2"

    # ── 列表项检测（标题不匹配后才检查） ──
    is_list = _is_list_item(full_text, first_left, img_width, med_body_fs, dpi)
    if is_list:
        return "list"

    return "body"


def _is_list_item(
    text: str, first_left: float, img_width: int,
    med_body_fs: float, dpi: int,
) -> bool:
    """检测段落是否为列表项（编号/项目符号开头）"""
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
        r"^[①②③④⑤⑥⑦⑧⑨⑩]",
        r"^[（(]\d+[）)]",
    ]
    for pat in numbered_patterns:
        if re.match(pat, text):
            return True

    bullet_chars = ('•', '■', '□', '▪', '▫', '◆', '◇', '●', '○',
                    '▶', '▷', '→', '⇒', '☆', '★', '-', '·')
    if text[0] in bullet_chars and len(text) > 2:
        return True

    return False


# ──────────────────────────────────────────────
#  段落输出（支持标题样式 + 正文排版）
# ──────────────────────────────────────────────

def _output_paragraph(
    docx,
    line_infos: list,
    para_type: str,
    img_width: int,
    dpi: int,
    join_func,
    paragraph_spacing_pt: float = 6,
    med_body_fs: float = 10.5,
):
    """
    将一行或多行输出为一个 Word 段落。

    para_type 映射：
    - 'h1' → Heading 1 样式（主标题）
    - 'h2' → Heading 2 样式（节标题）
    - 'h3' → Heading 3 样式（小节标题）
    - 'list' → 列表样式（悬挂缩进）
    - 'body' → Normal 样式（正文 + 首行缩进）
    """
    from docx.shared import Pt, Cm
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml.ns import qn

    if not line_infos:
        return

    # ── 段落对齐 ──
    all_lefts = [li[5] for li in line_infos]
    all_rights = [max(w[1] + w[3] for w in li[0]) for li in line_infos]
    avg_left = sum(all_lefts) / len(all_lefts) if all_lefts else 0
    avg_right = sum(all_rights) / len(all_rights) if all_rights else img_width
    left_ratio = avg_left / max(img_width, 1)
    right_ratio = (img_width - avg_right) / max(img_width, 1)

    if left_ratio > 0.25 and right_ratio > 0.25:
        alignment = WD_ALIGN_PARAGRAPH.CENTER
    elif right_ratio < 0.05 and left_ratio > 0.08:
        alignment = WD_ALIGN_PARAGRAPH.RIGHT
    else:
        alignment = WD_ALIGN_PARAGRAPH.LEFT

    # ── 字号 ──
    para_fs = max(li[4] for li in line_infos)

    # ── 合成文本 ──
    line_texts = []
    for words, _, _, _, _, _, _ in line_infos:
        word_texts = [w[0] for w in words]
        lt = join_func(word_texts).strip()
        if lt:
            line_texts.append(lt)
    full_text = "".join(line_texts)

    # ── 字号（OCR 像素高度 → pt，不做人为放大/缩小） ──
    # 只用宽泛的物理边界防止极端异常值（8pt 以下无法阅读，48pt 以上不物理）
    display_fs = max(8, min(48, para_fs))

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
        p.paragraph_format.space_before = Pt(round(paragraph_spacing_pt * 0.4, 1))
        p.paragraph_format.space_after = Pt(round(paragraph_spacing_pt * 0.3, 1))
        p.paragraph_format.line_spacing = 1.3

        # 首行缩进
        first_indent = _detect_first_line_indent(line_infos, img_width, dpi)
        if first_indent > 0:
            p.paragraph_format.first_line_indent = Pt(first_indent)

        # 逐行输出（保留行级字号+粗体差异）
        for line_idx, (words, _, _, _, font_size_pt, _, is_bold) in enumerate(line_infos):
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


def _detect_first_line_indent(
    line_infos: list, img_width: int, dpi: int
) -> float:
    """检测段落首行缩进（> 1.5 字符宽）"""
    if len(line_infos) < 2:
        return 0

    first_left = line_infos[0][5]
    other_lefts = [l[5] for l in line_infos[1:]]
    if not other_lefts:
        return 0

    other_lefts_sorted = sorted(other_lefts)
    med_other = other_lefts_sorted[len(other_lefts_sorted) // 2]
    indent_px = first_left - med_other

    avg_fs = sum(l[4] for l in line_infos) / len(line_infos)
    char_width_px = avg_fs * dpi / 72
    min_indent_px = char_width_px * 1.5

    if indent_px > min_indent_px:
        indent_pt = indent_px * 72 / dpi
        return round(indent_pt, 1)

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
