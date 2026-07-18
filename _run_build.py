"""后台打包脚本 — 清理 + 打包为单文件 exe，输出写入日志"""
import sys, os
sys.stdout.reconfigure(encoding='utf-8')
sys.stderr.reconfigure(encoding='utf-8')

log_path = os.path.join(os.path.dirname(__file__), "_build_log.txt")
with open(log_path, "w", encoding="utf-8") as log:
    def log_print(*args, **kwargs):
        msg = " ".join(str(a) for a in args)
        log.write(msg + "\n")
        log.flush()
        print(msg)

    sys.path.insert(0, os.path.dirname(__file__))
    from build import clean, build_exe

    try:
        log_print("=== 百宝箱 打包开始 ===")
        log_print("[1/2] 清理旧构建...")
        clean()
        log_print("[2/2] PyInstaller 打包 (约 2-5 分钟)...")
        build_exe()
        log_print("=== 打包完成 ===")
    except Exception as e:
        log_print(f"[错误] {e}")
        import traceback
        traceback.print_exc(file=log)
        log.flush()
