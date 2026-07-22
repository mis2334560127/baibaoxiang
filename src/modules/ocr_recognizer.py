"""
图片 OCR 识别模块
使用 PaddleOCR（优先）或 pytesseract（降级）批量识别图片中的文字，输出为 .txt 文件。

支持格式：PNG, JPG, JPEG, BMP, WEBP, TIFF
语言支持：中文 (ch)、英文 (en)、日文 (jpn)、韩文 (kor) 等
"""
import os
import sys
import shutil
from pathlib import Path

# 支持的图片格式
SUPPORTED_IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".bmp", ".webp", ".tiff", ".tif"}

# 常见 Tesseract 安装路径（降级备选）
TESSERACT_LOCATIONS = [
    r"C:\Program Files\Tesseract-OCR\tesseract.exe",
    r"C:\Program Files (x86)\Tesseract-OCR\tesseract.exe",
    os.path.expandvars(r"%LOCALAPPDATA%\Tesseract-OCR\tesseract.exe"),
    os.path.expandvars(r"%USERPROFILE%\AppData\Local\Tesseract-OCR\tesseract.exe"),
]

_PADDLEOCR_INSTANCE = None
_PADDLEOCR_AVAILABLE = None  # None=未检测, True/False
_PADDLEOCR_ERROR_MSG = ""   # 记录 PaddleOCR 不可用的具体原因


def _paddleocr_importable() -> bool:
    """检测 paddleocr 是否能正常 import（非阻塞）"""
    global _PADDLEOCR_AVAILABLE, _PADDLEOCR_ERROR_MSG
    if _PADDLEOCR_AVAILABLE is not None:
        return _PADDLEOCR_AVAILABLE
    # 冻结环境中提前强制设置 PADDLE_OCR_HOME（必须在 import paddle 前生效）
    if getattr(sys, "frozen", False):
        ocr_home = os.path.join(_get_appdata_dir(), ".paddleocr")
        os.makedirs(ocr_home, exist_ok=True)
        os.environ["PADDLE_OCR_HOME"] = ocr_home
    try:
        import paddleocr  # noqa: F401
        _PADDLEOCR_AVAILABLE = True
    except Exception as e:
        _PADDLEOCR_AVAILABLE = False
        _PADDLEOCR_ERROR_MSG = str(e)
    return _PADDLEOCR_AVAILABLE


def pre_check_ocr(tesseract_path: str = "") -> dict:
    """
    在启动时预检 OCR 可用性，返回状态报告。
    用于首页/设置页展示。

    Returns:
        {"paddleocr": bool, "tesseract": bool, "tesseract_path": str, "ready": bool}
    """
    # 先检测 import 是否可用
    paddle_importable = _paddleocr_importable()
    paddle_ready = paddle_importable

    # 如果 import 可用，进一步尝试创建 PaddleOCR 实例以验证模型完整性
    if paddle_importable and _PADDLEOCR_INSTANCE is None:
        try:
            _get_paddleocr("en")  # 用英文（模型较小）做预加载
            _PADDLEOCR_AVAILABLE = True
        except Exception as e:
            _PADDLEOCR_AVAILABLE = False
            _PADDLEOCR_ERROR_MSG = str(e)
            paddle_ready = False

    status = {
        "paddleocr": paddle_ready,
        "tesseract": False,
        "tesseract_path": tesseract_path or "",
        "ready": False,
    }
    if tesseract_path:
        status["tesseract"] = is_valid_tesseract(tesseract_path)
    if not status["tesseract"]:
        status["tesseract_path"] = find_tesseract()
        status["tesseract"] = bool(status["tesseract_path"])
    status["ready"] = status["tesseract"] or paddle_ready
    return status


def _get_appdata_dir() -> str:
    """获取应用数据目录，用于存放 PaddleOCR 模型"""
    if getattr(sys, "frozen", False):
        base = os.environ.get("APPDATA", os.path.expanduser("~"))
        app_dir = os.path.join(base, "BaibaoBOX")
    else:
        app_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "data")
    os.makedirs(app_dir, exist_ok=True)
    return app_dir


def _get_paddleocr(lang: str = "ch"):
    """获取/复用 PaddleOCR 单例（避免重复加载模型）"""
    global _PADDLEOCR_INSTANCE, _PADDLEOCR_AVAILABLE, _PADDLEOCR_ERROR_MSG
    if _PADDLEOCR_INSTANCE is not None:
        return _PADDLEOCR_INSTANCE
    if _PADDLEOCR_AVAILABLE is False:
        raise ImportError(f"PaddleOCR 不可用: {_PADDLEOCR_ERROR_MSG or '未知原因'}")

    # 冻结环境中强制设置 PADDLE_OCR_HOME 到用户数据目录，避免写权限问题
    # 必须使用直接赋值（而非 setdefault）以覆盖可能存在的旧值
    if getattr(sys, "frozen", False):
        ocr_home = os.path.join(_get_appdata_dir(), ".paddleocr")
        os.makedirs(ocr_home, exist_ok=True)
        os.environ["PADDLE_OCR_HOME"] = ocr_home

    # 将 lang 映射为 PaddleOCR 格式
    # PaddleOCR 支持: ch, en, japan, korean, french, german, etc.
    paddle_lang = lang
    lang_map = {
        "chi_sim": "ch",
        "chi_sim+eng": "ch",
        "chi_tra": "chinese_cht",
        "eng": "en",
        "jpn": "japan",
        "kor": "korean",
        "fra": "french",
        "deu": "german",
        "rus": "russian",
        "spa": "spanish",
    }
    mapped = lang_map.get(lang, lang)
    try:
        from paddleocr import PaddleOCR
        _PADDLEOCR_INSTANCE = PaddleOCR(
            use_angle_cls=True,
            lang=mapped,
            show_log=False,
            use_gpu=False,
        )
    except Exception as e:
        _PADDLEOCR_AVAILABLE = False
        _PADDLEOCR_ERROR_MSG = str(e)
        raise ImportError(f"PaddleOCR 初始化失败: {e}")
    return _PADDLEOCR_INSTANCE


def is_valid_tesseract(path: str) -> bool:
    """校验给定路径是否为有效的 Tesseract OCR 可执行文件。"""
    if not path or not os.path.isfile(path):
        return False
    if os.path.getsize(path) < 500 * 1024:
        return False
    with open(path, "rb") as f:
        return f.read(2) == b"MZ"


def find_tesseract(custom_path: str = "") -> str:
    """
    查找 Tesseract OCR 可执行文件（降级备选）。
    优先级：自定义路径 → 常见安装路径 → PATH
    """
    if custom_path and is_valid_tesseract(custom_path):
        return custom_path
    for p in TESSERACT_LOCATIONS:
        if is_valid_tesseract(p):
            return p
    found = shutil.which("tesseract")
    if found and is_valid_tesseract(found):
        return found
    return ""


def get_available_languages(tesseract_path: str) -> list[str]:
    """获取 Tesseract 已安装的语言列表（降级备选用）。"""
    if not tesseract_path:
        return []
    try:
        import subprocess
        result = subprocess.run(
            [tesseract_path, "--list-langs"],
            capture_output=True, text=True, timeout=10,
        )
        lines = result.stderr.strip().split("\n")
        langs = []
        in_list = False
        for line in lines:
            line = line.strip()
            if "List of available languages" in line:
                in_list = True
                continue
            if in_list and line and not line.startswith("List of"):
                langs.append(line)
        return langs
    except Exception:
        return []


def _get_tesseract_lang(lang_setting: str) -> str:
    """将用户配置的语言设置转换为 pytesseract 可接受的 lang 参数。"""
    return lang_setting


def get_image_files(paths: list[str], recursive: bool = False) -> list[str]:
    """
    从文件/目录列表获取所有支持的图片文件。

    Args:
        paths: 文件路径或目录路径列表
        recursive: 是否递归搜索子目录

    Returns:
        图片文件路径列表（去重、按文件名排序）
    """
    files: list[str] = []
    seen: set[str] = set()

    for p in paths:
        p = p.strip()
        if not p:
            continue
        if os.path.isfile(p):
            ext = os.path.splitext(p)[1].lower()
            if ext in SUPPORTED_IMAGE_EXTS and p not in seen:
                files.append(p)
                seen.add(p)
        elif os.path.isdir(p):
            for root, dirs, fnames in os.walk(p):
                for fn in sorted(fnames):
                    fp = os.path.join(root, fn)
                    ext = os.path.splitext(fn)[1].lower()
                    if ext in SUPPORTED_IMAGE_EXTS and fp not in seen:
                        files.append(fp)
                        seen.add(fp)
                if not recursive:
                    break

    return files


def recognize_image(
    file_path: str,
    tesseract_path: str = "",
    lang: str = "chi_sim+eng",
    progress_callback=None,
) -> str:
    """
    对单张图片进行 OCR 识别。
    优先使用 PaddleOCR（纯 Python 包，无需外部安装），
    失败时回退到 pytesseract（需要系统安装 Tesseract）。

    Args:
        file_path: 图片文件路径
        tesseract_path: Tesseract 可执行文件路径（仅降级时使用）
        lang: OCR 识别语言（如 "chi_sim+eng", "eng", "jpn"）
        progress_callback: 可选进度回调 (step, total)

    Returns:
        识别出的文本内容

    Raises:
        RuntimeError: 所有识别方式均失败
        FileNotFoundError: 图片文件不存在
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"图片文件不存在: {file_path}")

    if progress_callback:
        progress_callback(0, 1)

    # ── 方案一：PaddleOCR（推荐，无需外部安装） ──
    try:
        if progress_callback:
            progress_callback(0, 2)

        ocr = _get_paddleocr(lang)
        result = ocr.ocr(file_path, cls=True)

        if progress_callback:
            progress_callback(1, 2)

        if result and result[0]:
            lines = []
            for line_info in result[0]:
                # line_info = [bbox, (text, confidence)]
                text = line_info[1][0].strip()
                if text:
                    lines.append(text)
            return "\n".join(lines)
        else:
            # PaddleOCR 返回空结果，尝试 pytesseract 降级
            return _fallback_tesseract(file_path, tesseract_path, lang, progress_callback)

    except ImportError:
        # paddleocr 不可用，降级到 tesseract
        return _fallback_tesseract(
            file_path, tesseract_path, lang, progress_callback,
            paddle_error=_PADDLEOCR_ERROR_MSG,
        )
    except Exception as e:
        # PaddleOCR 出错，降级到 tesseract
        import warnings
        msg = f"PaddleOCR 识别失败 ({e})，降级到 Tesseract..."
        warnings.warn(msg)
        return _fallback_tesseract(
            file_path, tesseract_path, lang, progress_callback,
            paddle_error=str(e),
        )


def _fallback_tesseract(
    file_path: str,
    tesseract_path: str = "",
    lang: str = "chi_sim+eng",
    progress_callback=None,
    paddle_error: str = "",
) -> str:
    """
    PaddleOCR 不可用时的 Tesseract 降级方案。
    """
    tess_exe = tesseract_path or find_tesseract()
    if not tess_exe:
        detail = ""
        if paddle_error:
            detail = f"\n\n📋 PaddleOCR 失败原因：{paddle_error}"
        raise RuntimeError(
            "未找到可用的 OCR 引擎。\n\n"
            "请尝试以下方案（任选其一）：\n"
            "1. 安装项目附带的 Tesseract-OCR（推荐）：运行项目目录下的\n"
            "   tesseract-ocr-w64-setup-5.5.0.20241111.exe\n"
            "2. 在「设置」页面 > OCR 设置 > 指定已安装的 tesseract.exe 路径\n"
            "3. 确认网络畅通，关闭后重新打开程序，让 PaddleOCR 自动下载模型\n"
            f"{detail}"
        )

    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = tess_exe

    try:
        from PIL import Image

        img = Image.open(file_path)
        # RGBA/调色板模式转 RGB
        if img.mode in ("RGBA", "P", "LA", "PA"):
            img = img.convert("RGB")

        if progress_callback:
            progress_callback(1, 2)

        text = pytesseract.image_to_string(img, lang=lang)

        if progress_callback:
            progress_callback(2, 2)

        return text.strip()

    except Exception as e:
        raise RuntimeError(f"OCR 识别失败: {e}")


def save_text_to_file(text: str, output_path: str) -> str:
    """
    将文本保存到 .txt 文件。

    Args:
        text: 文本内容
        output_path: 输出路径（如 /path/to/file.txt）

    Returns:
        实际写入的文件路径
    """
    output_dir = os.path.dirname(output_path)
    if output_dir:
        os.makedirs(output_dir, exist_ok=True)

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(text)
    return output_path
