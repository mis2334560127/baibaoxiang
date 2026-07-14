"""
百宝箱 - 打包构建脚本
使用 PyInstaller 打包为独立 .exe 文件。
自动下载并集成 FFmpeg，用户无需单独安装。
使用方法: python build.py
"""
import os
import sys
import shutil
import zipfile
import urllib.request
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
BUILD_DIR = PROJECT_ROOT / "build"
FFMPEG_DIR = PROJECT_ROOT / "ffmpeg"

# FFmpeg 下载地址（多个源自动回退）
# 优先级：
# 1. 国内 GitHub 代理（通常最快）
# 2. 直接 GitHub BtbN
# 3. gyan.dev 官方 Windows 构建（备选）
FFMPEG_DOWNLOAD_URLS = [
    # ghproxy 国内代理（GitHub Release 文件加速）
    "https://ghproxy.net/https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    # 直接 GitHub BtbN
    "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-win64-gpl.zip",
    # gyan.dev essentials（官方 Windows 构建，体积较小）
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
]

# 用户可通过环境变量覆盖下载地址（优先级最高）
_CUSTOM_URL = os.environ.get("FFMPEG_DOWNLOAD_URL", "").strip()
if _CUSTOM_URL:
    FFMPEG_DOWNLOAD_URLS.insert(0, _CUSTOM_URL)


_MIN_ZIP_BYTES = 10 * 1024 * 1024       # 最小 zip 体积 10 MB（防止下载到错误页面）
_MIN_FFMPEG_BYTES = 5 * 1024 * 1024     # 最小 ffmpeg.exe 体积 5 MB


def _source_name(url: str) -> str:
    """返回人类可读的下载源名称"""
    if "ghproxy" in url or "mirror" in url or "proxy" in url:
        return "国内 GitHub 代理"
    if "github" in url:
        return "GitHub BtbN"
    if "gyan" in url:
        return "gyan.dev"
    return url[:60]


def _is_valid_ffmpeg_exe(path: str | Path) -> bool:
    """
    校验文件是否为有效的 Windows PE 可执行文件（避免下载到 HTML 错误页面
    或损坏文件导致 WinError 193）。
    """
    p = Path(path)
    if not p.is_file():
        return False
    size = p.stat().st_size
    if size < _MIN_FFMPEG_BYTES:
        return False
    with open(p, "rb") as f:
        header = f.read(2)
    return header == b"MZ"  # Windows PE 可执行文件魔数


def find_ffmpeg():
    """
    查找并校验 FFmpeg 可执行文件。

    优先级：
    1. 项目内置 ffmpeg/ffmpeg.exe
    2. 系统常见安装路径
    3. 系统 PATH

    返回空字符串表示未找到或找到的文件无效。
    """
    # 1. 项目内置 ffmpeg
    bundled = FFMPEG_DIR / "ffmpeg.exe"
    if _is_valid_ffmpeg_exe(bundled):
        return str(bundled)

    # 2. 常见安装路径
    locations = [
        os.path.join(os.environ.get("ProgramFiles", r"C:\Program Files"), r"ffmpeg\bin\ffmpeg.exe"),
        os.path.join(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"), r"ffmpeg\bin\ffmpeg.exe"),
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe"),
        os.path.expandvars(r"%USERPROFILE%\ffmpeg\bin\ffmpeg.exe"),
        r"D:\ffmpeg\bin\ffmpeg.exe",
        r"C:\ffmpeg\bin\ffmpeg.exe",
    ]
    for loc in locations:
        if _is_valid_ffmpeg_exe(loc):
            return loc

    # 3. 系统 PATH
    found = shutil.which("ffmpeg")
    if found and _is_valid_ffmpeg_exe(found):
        return found

    return ""  # 未找到有效 FFmpeg


def download_ffmpeg(force: bool = False):
    """
    自动下载 FFmpeg 静态构建到项目 ffmpeg/ 目录。
    多源自动回退：国内 GitHub 代理 → 直接 GitHub → gyan.dev。

    下载约 40-50 MB，解压后提取 ffmpeg.exe（约 120-130 MB）。
    如果 ffmpeg.exe 已存在且有效，并且未指定 force，则跳过。
    可通过环境变量 FFMPEG_DOWNLOAD_URL 指定自定义下载地址。
    """
    target = FFMPEG_DIR / "ffmpeg.exe"
    if target.is_file() and _is_valid_ffmpeg_exe(target) and not force:
        size_mb = os.path.getsize(target) / (1024 * 1024)
        print(f"✅ FFmpeg 已存在且校验通过 ({size_mb:.1f} MB)，跳过下载。使用 --force 强制重新下载。")
        return True

    FFMPEG_DIR.mkdir(parents=True, exist_ok=True)

    # 删除已存在但无效的目标文件（避免残留损坏文件）
    if target.exists():
        target.unlink(missing_ok=True)

    for idx, url in enumerate(FFMPEG_DOWNLOAD_URLS):
        source_name = _source_name(url)
        if idx > 0:
            print(f"\n🔄 回退到备用源: {source_name}")

        # 使用唯一临时文件名，避免上次残留的 ffmpeg_temp.zip 被其他进程占用
        zip_path = PROJECT_ROOT / f"ffmpeg_temp_{idx}.zip"
        try:
            print(f"📥 正在下载 FFmpeg ...")
            print(f"   来源: {source_name}")

            def _report_progress(block_num, block_size, total_size):
                downloaded = block_num * block_size
                if total_size > 0:
                    pct = min(100, downloaded * 100 // total_size)
                    mb = downloaded / (1024 * 1024)
                    total_mb = total_size / (1024 * 1024)
                    print(f"\r   下载进度: {pct}% ({mb:.1f} / {total_mb:.1f} MB)", end="", flush=True)

            # 设置请求头：某些 CDN/代理会拒绝默认 urllib UA
            req = urllib.request.Request(
                url,
                headers={
                    "User-Agent": (
                        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                },
            )
            with urllib.request.urlopen(req, timeout=120) as response:
                # 检查 Content-Length，提前拒绝错误页面
                content_length = response.headers.get("Content-Length")
                if content_length and int(content_length) < _MIN_ZIP_BYTES:
                    raise ValueError(
                        f"文件过小 ({int(content_length)} 字节)，可能是错误页面，而非 FFmpeg 压缩包"
                    )

                with open(zip_path, "wb") as f:
                    block_size = 1024 * 1024
                    block_num = 0
                    while True:
                        chunk = response.read(block_size)
                        if not chunk:
                            break
                        f.write(chunk)
                        block_num += 1
                        _report_progress(block_num, block_size, int(content_length) if content_length else 0)
            print()  # 换行

            # 校验 zip 文件大小
            zip_size = zip_path.stat().st_size
            if zip_size < _MIN_ZIP_BYTES:
                raise ValueError(f"下载文件过小 ({zip_size} 字节)，可能为错误页面或下载不完整")

            # 校验 zip 是否有效
            print("📦 正在解压并校验...")
            try:
                with zipfile.ZipFile(zip_path, 'r') as zf:
                    zf.testzip()
                    # 查找 bin/ffmpeg.exe（兼容各种目录结构）
                    ffmpeg_member = None
                    for name in zf.namelist():
                        if name.endswith("bin/ffmpeg.exe") and not name.startswith("__MACOSX"):
                            ffmpeg_member = name
                            break
                    if not ffmpeg_member:
                        raise ValueError("未在压缩包中找到 bin/ffmpeg.exe")

                    # 提取到临时位置再移动
                    zf.extract(ffmpeg_member, str(FFMPEG_DIR))
                    extracted = FFMPEG_DIR / ffmpeg_member.replace("/", os.sep)
            except zipfile.BadZipFile as e:
                raise ValueError(f"压缩包损坏: {e}")

            if extracted != target:
                shutil.move(str(extracted), str(target))

            # 校验提取出的 ffmpeg.exe 是否有效
            if not _is_valid_ffmpeg_exe(target):
                raise ValueError(f"提取出的 ffmpeg.exe 无效（可能是损坏文件或 HTML 页面）")

            # 清理解压产生的多余目录
            for item in FFMPEG_DIR.iterdir():
                if item != target and item.is_dir():
                    shutil.rmtree(str(item), ignore_errors=True)

            size_mb = os.path.getsize(target) / (1024 * 1024)
            print(f"✅ FFmpeg 下载完成 ({size_mb:.1f} MB) → {target}")
            return True

        except Exception as e:
            print(f"\n❌ {source_name} 失败: {e}")
            # 清理本次下载产生的无效文件
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass
            if target.exists() and not _is_valid_ffmpeg_exe(target):
                try:
                    target.unlink()
                except Exception:
                    pass
            continue  # 尝试下一个源

        finally:
            # 尽量删除临时 zip（即使被占用也不抛异常）
            if zip_path.exists():
                try:
                    zip_path.unlink()
                except Exception:
                    pass

    print("\n❌ 所有下载源均失败。请检查网络连接，或手动设置环境变量:")
    print("   set FFMPEG_DOWNLOAD_URL=<你的镜像地址>")
    print("   然后重新运行: python build.py --download-ffmpeg")
    return False


def clean():
    """清理上次构建"""
    for d in ["build", "dist", "__pycache__"]:
        p = PROJECT_ROOT / d
        if p.exists():
            if d == "build":
                shutil.rmtree(str(p), ignore_errors=True)
            elif d == "dist":
                shutil.rmtree(str(p), ignore_errors=True)

    for pyc in PROJECT_ROOT.rglob("*.pyc"):
        pyc.unlink(missing_ok=True)
    for d in PROJECT_ROOT.rglob("__pycache__"):
        shutil.rmtree(str(d), ignore_errors=True)

    print("✅ 清理完成")


def build_exe():
    """使用 PyInstaller 打包"""
    import PyInstaller.__main__

    # 确保 FFmpeg 已下载
    if not (FFMPEG_DIR / "ffmpeg.exe").is_file():
        print("⚠️ 未找到项目内置 FFmpeg，正在自动下载...")
        if not download_ffmpeg():
            print("❌ FFmpeg 下载失败，录屏功能将不可用。")
            print("   可手动运行: python build.py --download-ffmpeg")

    ffmpeg_path = find_ffmpeg()
    print(f"FFmpeg: {ffmpeg_path or '（未找到）'}")

    # PyInstaller 参数
    args = [
        str(PROJECT_ROOT / "main.py"),
        "--name=BaibaoBOX",
        "--onefile",
        "--windowed",
        f"--distpath={PROJECT_ROOT / 'dist'}",
        f"--workpath={PROJECT_ROOT / 'build' / 'pyinstaller'}",
        "--specpath=build",
        "--add-data", f"{SRC_DIR / 'theme'}{os.pathsep}src/theme",
        "--icon=NONE",
        "--clean",
        "--noconfirm",
    ]

    # 如果有 FFmpeg，打包进 exe 同级 ffmpeg/ 目录
    if ffmpeg_path and os.path.isfile(ffmpeg_path):
        args.extend([
            "--add-binary", f"{ffmpeg_path}{os.pathsep}ffmpeg",
        ])
        print("✅ FFmpeg 已包含在打包中（exe 同级 ffmpeg/ 目录）")
    else:
        print("⚠️ 未找到 FFmpeg，打包后将不含录屏功能。")

    print("🔨 正在打包...")
    PyInstaller.__main__.run(args)

    print("\n🏁 打包完成!")
    exe_path = PROJECT_ROOT / "dist" / "BaibaoBOX.exe"
    if exe_path.exists():
        size_mb = os.path.getsize(exe_path) / (1024 * 1024)
        print(f"📦 输出文件: {exe_path}")
        print(f"📏 文件大小: {size_mb:.1f} MB")
    else:
        print("⚠️ 未找到输出文件，请检查错误信息")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="百宝箱 构建脚本")
    parser.add_argument("--clean", action="store_true", help="清理构建目录")
    parser.add_argument("--build", action="store_true", help="执行 PyInstaller 打包")
    parser.add_argument("--all", action="store_true", help="清理后打包（含自动下载 FFmpeg）")
    parser.add_argument("--download-ffmpeg", action="store_true", help="下载 FFmpeg 到项目目录")
    parser.add_argument("--force", action="store_true", help="强制重新下载 FFmpeg（配合 --download-ffmpeg）")

    args = parser.parse_args()

    if args.download_ffmpeg:
        download_ffmpeg(force=args.force)
    elif args.all:
        clean()
        download_ffmpeg()
        build_exe()
    elif args.clean:
        clean()
    elif args.build:
        build_exe()
    else:
        print("百宝箱 构建脚本")
        print("  --clean             清理构建目录")
        print("  --build             执行 PyInstaller 打包（自动下载 FFmpeg）")
        print("  --all               清理后打包（自动下载 FFmpeg）")
        print("  --download-ffmpeg   下载 FFmpeg 到项目目录")
        print("  --force             强制重新下载（配合 --download-ffmpeg）")
