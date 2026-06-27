"""
百宝箱 - 打包构建脚本
使用 PyInstaller 打包为独立 .exe 文件。
使用方法: python build.py
"""
import os
import sys
import shutil
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
DATA_DIR = PROJECT_ROOT / "data"
BUILD_DIR = PROJECT_ROOT / "build"

# FFmpeg 路径提示
def find_ffmpeg():
    """查找系统 FFmpeg"""
    locations = [
        os.environ.get("ProgramFiles", r"C:\Program Files") + r"\ffmpeg\bin\ffmpeg.exe",
        os.path.expandvars(r"%LOCALAPPDATA%\ffmpeg\bin\ffmpeg.exe"),
    ]
    for loc in locations:
        if os.path.isfile(loc):
            return loc
    return shutil.which("ffmpeg") or "ffmpeg.exe"


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

    ffmpeg_path = find_ffmpeg()
    print(f"FFmpeg: {ffmpeg_path}")

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

    # 如果有 FFmpeg，打包进去
    if os.path.isfile(ffmpeg_path):
        args.extend([
            "--add-binary", f"{ffmpeg_path}{os.pathsep}.",
        ])
        print("✅ FFmpeg 已包含在打包中")

    print("🔨 正在打包...")
    print(f"命令: pyinstaller {' '.join(args)}")
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
    parser.add_argument("--build", action="store_true", help="执行打包")
    parser.add_argument("--all", action="store_true", help="清理后打包")

    args = parser.parse_args()

    if args.all:
        clean()
        build_exe()
    elif args.clean:
        clean()
    elif args.build:
        build_exe()
    else:
        print("百宝箱 构建脚本")
        print("  --clean   清理构建目录")
        print("  --build   执行 PyInstaller 打包")
        print("  --all     清理后打包")
