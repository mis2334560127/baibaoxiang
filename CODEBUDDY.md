# CODEBUDDY.md This file provides guidance to CodeBuddy when working with code in this repository.

## 常用命令

```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 启动应用（开发模式）
.venv\Scripts\python main.py

# 打包为单文件 .exe（清理 + 自动下载 FFmpeg + 构建）
.venv\Scripts\python build.py --all

# 仅下载 FFmpeg（开发模式录屏需要）
.venv\Scripts\python build.py --download-ffmpeg

# 仅打包
.venv\Scripts\python build.py --build

# 仅清理构建文件
.venv\Scripts\python build.py --clean
```

## 架构概览

### 项目定位

百宝箱 (BaibaoBOX) 是一个 Windows 桌面效率工具，基于 Python 3.13 + PyQt6，提供四大核心功能：图片批量压缩、PDF 转 Word、屏幕录制、图片 OCR 文字识别。所有功能本地运行，数据不上传。另有预留的广告位模块，通过远程 API 拉取广告内容（默认关闭）。

### 整体分层

```
main.py                    # 入口：初始化 QApplication → 信号总线 → 配置 → 广告管理器 → 主窗口
└── src/
    ├── config.py          # 全局配置（dataclass + JSON 持久化，懒加载单例）
    ├── database.py        # SQLite 操作（历史记录表 + 广告缓存表）
    ├── signals.py         # Qt 信号总线（全局事件通信，懒加载单例）
    ├── worker_threads.py  # QThread 子类（压缩/转换/录制/广告的后台线程）
    ├── main_window.py     # 主窗口（侧边栏导航 + QStackedWidget 页面切换 + 主题 QSS 加载）
    ├── modules/           # 纯逻辑模块（无 Qt 依赖）
    │   ├── image_compressor.py   # 图片压缩核心算法
    │   ├── pdf_converter.py      # PDF→DOCX 转换（支持 OCR 扫描件）
    │   ├── screen_recorder.py    # 屏幕录制（GDI + FFmpeg）
    │   ├── excel_merger.py       # Excel 批量合并
    │   ├── ocr_recognizer.py     # 图片 OCR 文字识别（pytesseract）
    │   └── ad_manager.py         # 广告拉取（单例，独立线程）
    ├── pages/             # UI 页面（每个功能一个 QWidget）
    │   ├── home_page.py      # 首页仪表盘
    │   ├── compress_page.py  # 图片批量压缩
    │   ├── pdf_word_page.py  # PDF 转 Word
    │   ├── recorder_page.py  # 屏幕录制
    │   ├── excel_merge_page.py # Excel 合并
    │   ├── ocr_page.py       # 图片 OCR 识别
    │   ├── guide_page.py     # 使用指南
    │   └── settings_page.py  # 系统设置
    └── theme/             # 5 套 QSS 样式表
```

### 关键设计决策

**1. 信号总线模式 (SignalBus)**

所有跨页面通信通过 `src/signals.py` 中的 SignalBus 单例完成。页面之间不直接引用对方，而是通过 `bus.navigate_to.emit(page_id)` 导航、`bus.theme_changed.emit(key)` 切换主题、`bus.history_updated.emit()` 刷新记录等。SignalBus 必须在 QApplication 创建后才能实例化，通过 `get_bus()` 懒加载函数和模块级 `__getattr__` 代理确保安全。

**2. 后台线程模式**

所有耗时操作（压缩、转换、录制、广告请求）均放入 QThread 子类中执行，避免阻塞 UI 线程。Worker 线程通过 Qt 信号向页面报告进度/结果，线程内部使用协作式取消标志（`_cancelled` / `_stop_event`）而非 `terminate()`。

**3. 配置管理**

`AppConfig` 是一个 `@dataclass`，支持从 `data/config.json` 加载和保存。通过 `get_config()` 获取全局单例。页面持有 `self._config` 引用直接读写，修改后调用 `_config.save()` 持久化。`reload_config()` 用于设置变更后刷新全局单例。

**4. 数据库**

SQLite 数据库 `data/baibaobox.db` 使用 WAL 模式，包含五张表：
- `compress_history` — 图片压缩记录（文件名、原始/目标大小、质量、模式）
- `convert_history` — PDF 转换记录
- `record_history` — 屏幕录制记录（文件名、时长、文件大小）
- `ocr_history` — OCR 识别记录（文件名、文字长度、语言）
- `ad_cache` — 广告内容缓存

`db_session()` 上下文管理器自动管理 commit/close。

**5. 主题系统**

5 套 QSS 样式表（blue/teal/purple/amber/rose），主窗口通过 `_load_theme()` 读取对应 `.qss` 文件并调用 `setStyleSheet()` 全局应用。主题切换通过 `bus.theme_changed` 信号触发，设置页面和标题栏色点均可发起切换。`THEMES` 字典在 `config.py` 中定义各主题的 primary/accent 色值。

### 各模块实现要点

**图片压缩 (`image_compressor.py`)**
- `compress_image()` 支持两种模式：按目标大小（二分搜索逼近 JPEG quality 参数，精度 ±5KB，最多 12 次迭代）和按质量（直接指定 quality 1-100）
- RGBA/调色板模式图片自动转 RGB（白色背景填充透明通道）
- PNG 为无损格式，quality 参数不生效，按质量模式下仅做 optimize

**PDF 转 Word (`pdf_converter.py`)**
- 使用 `pdf2docx.Converter` 将 PDF 转为 `.docx`
- 支持保留图片（提取到 images 子目录）和保留格式
- 仅支持文字可选型 PDF；扫描型 PDF 暂不支持 OCR

**屏幕录制 (`screen_recorder.py`)**
- Windows GDI（pywin32）逐帧捕获屏幕 → BGRA 原始数据直接写入 FFmpeg 管道进行 H.264 编码
- 采用生产者-消费者模式：截图线程捕获帧放入 `queue.Queue(maxsize=30)`，独立写入线程从队列取帧写入 FFmpeg stdin
- 通过 `threading.Event` 实现外部停止信号
- `_find_ffmpeg()` 按常见路径 → PATH 顺序查找 FFmpeg 可执行文件，并校验文件是否为有效的 Windows PE 可执行文件（避免 WinError 193）
- 录制完成后自动记录到 `record_history` 表


**图片 OCR 识别 (`ocr_recognizer.py`)**
- 基于 `pytesseract`（Tesseract OCR 引擎）进行文字识别
- `recognize_image()` 支持单张图片识别，RGBA/调色板模式自动转 RGB
- `get_image_files()` 递归扫描目录获取支持的图片（PNG/JPG/BMP/WEBP/TIFF）
- `find_tesseract()` 按自定义路径 → 常见安装路径 → PATH 顺序查找 Tesseract 可执行文件，并校验 PE 有效性
- `get_available_languages()` 查询已安装的语言包
- 支持中英文混合识别（默认 `chi_sim+eng`），也可切换为日文、韩文、法文等
- 输出模式支持：每张图片独立 .txt 或合并到单个文件

**广告管理器 (`ad_manager.py`)**
- 单例模式（`__new__` + 线程锁），独立 daemon 线程定期从配置的 API URL 拉取 JSON 广告数据
- 支持 Bearer Token 认证
- API 请求失败时静默降级，回退到 SQLite 缓存
- 可在设置页面配置启用/禁用、API 地址、密钥、刷新间隔

**主窗口关闭 (`main_window.py` 的 `closeEvent`)**
- 优先停止屏幕录制（防止 FFmpeg 孤儿进程）
- 停止广告拉取线程
- 保存窗口尺寸和最大化状态到配置

### 数据流

用户操作 → Page 创建 Worker (QThread) → Worker 调用 modules/ 中的纯逻辑函数 → Worker 通过 Qt signal 报告进度/结果 → Page 更新 UI → 完成时通过 `bus` 发射 `*_all_done` 信号 → 其他页面（如首页）通过 `bus.history_updated` 刷新

配置变更：SettingsPage → `_config.save()` → `reload_config()` → `bus.theme_changed`（如有主题变更）→ MainWindow 接收信号更新全局 QSS

### 外部依赖

- **FFmpeg**：屏幕录制的必要依赖。运行 `python build.py --download-ffmpeg` 自动下载：默认优先使用国内 GitHub 代理（ghproxy.net），失败则回退到 GitHub BtbN 直接地址和 gyan.dev。下载后会校验压缩包完整性及 `ffmpeg.exe` 是否有效 Windows PE 文件，防止下载到错误页面或损坏文件导致 `WinError 193`。也可用环境变量 `FFMPEG_DOWNLOAD_URL` 指定自定义镜像。打包时自动包含。程序通过 `_find_ffmpeg()` 按优先级查找：用户自定义路径 → 项目内置 `ffmpeg/ffmpeg.exe` → 系统常见路径 → PATH，所有路径均会校验有效性。
- **Tesseract OCR**：图片 OCR 识别的必要依赖。需安装 [Tesseract-OCR](https://github.com/UB-Mannheim/tesseract/wiki)（项目根目录提供 `tesseract-ocr-w64-setup-*.exe` 安装包）。安装后程序通过 `find_tesseract()` 自动查找。可在设置页面指定自定义路径。
- **pytesseract**：Python Tesseract 封装库，通过 pip 安装（已加入 `requirements.txt`）
- **pywin32**：Windows GDI 屏幕捕获，仅 Windows 平台可用
- **PyMuPDF (fitz)**：用于获取 PDF 页数（`pdf_converter.py` 中的 `get_pdf_page_count`）
