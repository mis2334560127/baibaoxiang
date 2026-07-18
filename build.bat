@echo off
chcp 65001 >nul
cd /d "%~dp0"

echo ============================================
echo  百宝箱 - 一键打包脚本
echo ============================================
echo.

echo [1/2] 清理旧构建...
.venv\Scripts\python build.py --clean
echo.

echo [2/2] PyInstaller 打包...
.venv\Scripts\python build.py --build
echo.

echo ============================================
echo 打包完成！
echo 输出文件: dist\BaibaoBOX.exe
echo ============================================
pause
