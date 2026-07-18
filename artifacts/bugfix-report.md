# 百宝箱 Bug 修复记录

> **注**: 屏幕录制功能及相关代码（screen_recorder.py / recorder_page.py / RecordWorker）已于 2026-07 移除。以下 BUG-001、BUG-003、BUG-009 对应的问题代码已不复存在，记录保留仅供历史参考。

---

## BUG-001: 屏幕录制 BGRA 像素转换方向错误 ✅ 已修复

- **发现时间**: 2025-09-17
- **影响范围**: 屏幕录制输出视频画面顶部出现水平彩色条纹，高频出现于帧率不稳或窗口 Resize 时。
- **根因**: `screen_recorder.py` 中 `BGRA_to_BGR` 的 `numpy` 操作分两步（`bgr = bgra[:,:,:3]` + `np.flip(bgr, axis=2)`），内存布局导致前几行数据为彩虹条纹，区域录制时尤为明显。
- **修复**:
  - 合并为单步 `result_frame = bgra[:, :, [2, 1, 0]]`，零拷贝视图操作，消除临时数组。
  - 防止窗口关闭后继续向队列推送空帧导致计数不准。
- **验证**: 本地录制 30 秒测试视频，条纹完全消失。继续观察一周，未复现。

---

## BUG-002: 扫描型 PDF 转换时应用闪退 ✅ 已修复

- **发现时间**: 2026-03-03
- **影响范围**: 用户反馈将扫描型 PDF 转为 Word 的过程中程序闪退，无有效错误提示。
- **根因**: `convert_scan_pdf_to_docx()` 会将 PDF 每页渲染成图片，再用 PaddleOCR 识别。当内存不足或 PaddleOCR 识别异常时，会在 `executor.submit()` 的结果获取阶段 `result()` 抛出异常，而该异常未被外层 try/except 捕获，导致 QThread 崩溃，进而拖垮整个 QApplication。
- **修复**:
  - 在 `executor.submit()` 外层增加 `try/except Exception as e` 包裹，捕获并封装为 `ConvertError`。
  - 对所有 PDF 页面的处理结果统一包装，确保即使某页转换失败也不影响后续页。
  - 在 worker 线程中增加 `self._cancelled` 检查，允许用户在超长扫描件转换中途取消。
- **验证**: 10 张 1200DPI 扫描件连续转换 3 轮，闪退彻底消失。

---

## BUG-003: 主窗口关闭时 FFmpeg 进程残留 ✅ 已修复（代码已移除）

- **发现时间**: 2026-03-14
- **影响范围**: 录制过程中关闭主窗口，FFmpeg 子进程继续运行，占用摄像头/GDI 资源和磁盘 IO。
- **根因**: `RecordWorker` 的 `_stop_event` 未被触发，`closeEvent` 未尝试停止录屏线程，直接 `close()`。
- **修复**（代码已移除，记录保留供参考）:
  - `closeEvent` 优先检查并停止录制
  - 调用 `QApplication.processEvents()` 确保信号被传递
  - 保存窗口状态前先清理后台进程
- **验证**: 窗口中录制时测试点击 X 关闭，`ffmpeg.exe` 进程树自动终止。

---

## BUG-004: Python 3.13 下 `normcase` 编码异常 ✅ 已修复

- **发现时间**: 2026-03-13
- **影响范围**: Python 3.13 下 `site-packages` 中的测试文件触发了 `normcase` 路径编码异常。
- **根因**: Python 3.13 对路径规范化模块引入了更严格的编码检查。
- **修复**: 升级 PyInstaller 到 6.x 版本，兼容 Python 3.13。

---

## BUG-005: 主题切换后部分组件未跟随 ✅ 已修复

- **发现时间**: 2026-03-16
- **影响范围**: 切换主题后，@QTabWidget、@QGroupBox、@QProgressBar 等容器组件未刷新为新主题色。
- **根因**: QSS 对复合选择器和子控件选择器的应用和覆盖逻辑在 `setStyleSheet()` 时无法彻底刷新。
- **修复**:
  - 在 `_load_theme()` 末尾增加 `self.setStyleSheet(self.styleSheet())` 强制重绘。
  - 对所有全局 QSS 文件补充 `@QTabWidget`、`@QGroupBox` 等复合选择器。
- **验证**: 5 套主题反复切换，所有组件一次性刷入正确颜色。

---

## BUG-006: Windows 11 字体模糊 ✅ 已修复

- **发现时间**: 2026-03-17
- **影响范围**: Windows 11 高 DPI 屏幕上字体模糊、锯齿感明显。
- **根因**: PyQt6 默认未开启字体抗锯齿和高 DPI 支持。
- **修复**:
  - `main.py` 中增加 `QApplication.setHighDpiScaleFactorRoundingPolicy` 配置。
  - 全局设置字体为 `"Microsoft YaHei UI" 10pt`。
- **验证**: 175% 缩放下字体清晰无锯齿。

---

## BUG-007: 图片压缩中文名输出乱码 ✅ 已修复

- **发现时间**: 2026-03-08
- **影响范围**: 原始文件名包含中文日文等非 ASCII 字符时，压缩后的输出文件名变为 `????.jpg`。
- **根因**: `Pillow` 在 `save()` 阶段的默认编码无法正确处理 Unicode 文件名。
- **修复**: 输出路径统一使用 `Path` 对象，调用 `.write_bytes()` 写入而非 `save()` 直接传字符串路径。
- **验证**: 测试中文（你好世界.png）、日文（こんにちは.png）、韩文（안녕하세요.png）均正常。

---

## BUG-008: 图片压缩偶现空文件 ✅ 已修复

- **发现时间**: 2026-03-09
- **影响范围**: 部分大图压缩后输出文件大小为 0 字节。
- **根因**: 二分搜索过程中 `save()` 的中间文件与最终输出同名，当搜索回退时若写 IO 异常或内存不足，生成 0 字节空文件覆盖原位置。
- **修复**:
  - 先写入临时 `.tmp` 文件。
  - 确认 `tmp` 文件大小 > 0 后再 `rename` 为目标文件。
- **验证**: 批量压缩 100 张 20MB+ 大图，无空文件产生。

---

## BUG-009: 屏幕录制停止后视频损坏 ✅ 已修复（代码已移除）

- **发现时间**: 2026-03-10
- **影响范围**: 停止录制后视频文件无法播放。
- **根因**: `threading.Event` 停止后，FFmpeg stdin 立即关闭，尾部未写入 moov atom。
- **修复**（代码已移除，记录保留供参考）:
  - 发送 `q` 命令给 FFmpeg stdin 让其自然结束编码再关闭管道。
  - 添加 `ffmpeg_pipe.stdin.flush()` 和 `ffmpeg_pipe.stdin.close()` 的顺序保证。
- **验证**: 生成的 MP4 文件可正常播放，mediainfo 显示视频流完整。

---

## BUG-010: build.py 在 Windows GBK 终端崩溃 ✅ 已修复

- **发现时间**: 2026-07-18
- **影响范围**: 在 Windows cmd 或 IDE 终端中运行 `build.py` 时，因输出包含 emoji（✅❌📥等）导致 UnicodeEncodeError 崩溃。
- **根因**: Windows 终端默认编码 GBK，而 python 的 `print()` 输出的 emoji 字符无法被 GBK 编码。
- **修复**:
  - 将 `build.py` 中所有 emoji 替换为 ASCII 安全文本（如 `[OK]`、`[失败]`、`[下载]`）。
  - 用户也可通过 `$env:PYTHONIOENCODING='utf-8'` 环境变量绕过。
- **验证**: `build.py` 可在 Windows cmd 和 PowerShell 中正常输出中文进度，不再崩溃。

---

## BUG-011: OCR 双语言识别在缺失语言包时无提示 ✅ 已修复

- **发现时间**: 2026-07-16
- **影响范围**: 用户选择 `chi_sim+eng` 但未安装 `chi_sim` 语言包时，tesseract 静默失败，识别结果为空白。
- **根因**: `get_available_languages()` 在启动时被调用，但 page 未根据实际可用语言动态更新选择器，用户首选语言可能不可用。
- **修复**:
  - 在 page 初始化时调用 `get_available_languages()` 获取语言列表。
  - 若首选语言不可用，自动降级到可用列表中的第一项，并弹出提示。
  - 在 `run()` 中再次校验语言可用性，避免静默失败。
- **验证**: 卸载 `chi_sim` 后重新打开应用，自动降级到 `eng` 并提示用户。

---

## BUG-012: 扫描型 PDF 转换时 PaddleOCR 自动下载失败无回退 ✅ 已修复

- **发现时间**: 2026-07-17
- **影响范围**: 首次使用 PaddleOCR 时自动下载模型，网络差或下载中断时程序卡住无反馈。
- **根因**: PaddleOCR 首次使用会在主线程中下载模型，无超时和进度提示。
- **修复**:
  - 在 worker 线程中预初始化 PaddleOCR，通过信号 `paddle_downloading` 通知用户下载进度。
  - 设置超时 60 秒，超时后自动降级到纯 Tesseract 方案。
  - 下载失败时在页面状态栏显示提示但不中断流程。
- **验证**: 断开网络测试，PaddleOCR 下载超时后自动降级为 Tesseract 识别。
