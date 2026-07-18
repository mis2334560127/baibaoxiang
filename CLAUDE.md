# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 常用命令

```bash
# 创建虚拟环境并安装依赖
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt

# 启动应用（开发模式）
.venv\Scripts\python main.py

# 打包为单文件 .exe
.venv\Scripts\python build.py --all      # 清理 + 构建
.venv\Scripts\python build.py --build    # 仅打包
.venv\Scripts\python build.py --clean    # 仅清理
```

## 架构概览

百宝箱 (BaibaoBOX) — Windows 桌面效率工具，Python 3.13 + PyQt6。五大功能：图片批量压缩、PDF 转 Word、图片 OCR 识别、Excel 批量解压合并、预留广告位。全部本地运行。

### 分层架构

```
main.py                     # 入口：QApplication → SignalBus → 配置 → 广告管理器 → 主窗口
src/
├── config.py               # 全局配置（dataclass + JSON 持久化，懒加载单例）
├── database.py             # SQLite（WAL 模式），db_session() 上下文管理器
├── signals.py              # Qt SignalBus 单例（跨页面/跨模块通信）
├── worker_threads.py       # QThread 子类（CompressWorker / ConvertWorker / ExcelMergeWorker / OcrWorker）
├── main_window.py          # 主窗口（侧边栏导航 + QStackedWidget + 主题 QSS 加载）
├── modules/                # 纯逻辑模块（无 Qt 依赖）
│   ├── image_compressor.py   # 图片压缩（二分搜索逼近 / 直接质量）
│   ├── pdf_converter.py      # PDF→DOCX（pdf2docx 文字型 / PaddleOCR+Tesseract 扫描型）
│   ├── excel_merger.py       # 批量解压合并 Excel（zip/rar/7z → Excel 提取 → 合并写入）
│   ├── ocr_recognizer.py     # 图片 OCR 文字识别（pytesseract）
│   └── ad_manager.py         # 广告拉取（单例，独立 daemon 线程）
├── pages/                  # UI 页面（每个功能一个 QWidget）
│   ├── home_page.py          # 首页仪表盘（统计 + 历史记录）
│   ├── compress_page.py      # 图片批量压缩
│   ├── pdf_word_page.py      # PDF 转 Word
│   ├── ocr_page.py           # 图片 OCR 识别
│   ├── excel_merge_page.py   # Excel 解压合并
│   ├── guide_page.py         # 使用指南
│   └── settings_page.py      # 系统设置
└── theme/                  # 5 套 QSS 样式表（blue/teal/purple/amber/rose）
```

### 关键设计决策

**信号总线 (SignalBus)** — `src/signals.py`。所有跨页面通信通过 SignalBus 单例完成，页面之间不直接引用。`get_bus()` 懒加载 + 模块级 `__getattr__` 代理确保在 QApplication 之后才实例化。信号包括：`navigate_to`、`theme_changed`、`history_updated`、`compress_all_done`、`convert_all_done`、`merge_all_done`、`ocr_all_done`、`ad_updated`。

**后台线程** — 所有耗时操作放入 QThread 子类，通过 Qt 信号向页面报告进度。线程使用协作式取消（`_cancelled` 标志位），不使用 `terminate()`。

**配置管理** — `AppConfig` 是 `@dataclass`，`get_config()` 获取单例。页面持有 `self._config` 直接读写，修改后调用 `_config.save()` 持久化到 `data/config.json`。

**关闭保护** — 主窗口 `closeEvent` 中停止广告线程，保存窗口状态。

### 各模块要点

**图片压缩** — `compress_image()` 支持两种模式：按目标大小（二分搜索 JPEG quality，精度 ±5KB，最多 12 次迭代）和按质量（直接指定 1-100）。RGBA/调色板模式自动转 RGB（白色背景填充）。PNG 无损格式在按质量模式下仅做 optimize。

**PDF 转 Word** — `detect_pdf_type()` 自动分类文字型/扫描型/混合型。文字型用 pdf2docx 直接转换；扫描型用 PyMuPDF 渲染 + PaddleOCR 识别 + Tesseract 辅助排版重建。OCR 语言自动检测，chi_sim 不可用时回退到 eng。

**图片 OCR 识别** — 基于 pytesseract 进行批量图片文字识别。支持 PNG/JPG/BMP/WEBP/TIFF。默认 chi_sim+eng 混合识别，支持切换为日文、韩文、法文等。输出模式支持独立 .txt 或合并文件。

**Excel 解压合并** — 解压 zip/rar/7z → 提取 Excel 文件（自动过滤 __MACOSX 和临时文件）→ 读取数据行（统一表头）→ 合并写入单个 Excel。

### 新增功能指南

1. **纯逻辑** → `src/modules/` 中创建模块（无 Qt 依赖）
2. **后台线程** → `src/worker_threads.py` 中添加 QThread 子类
3. **UI 页面** → `src/pages/` 中创建 QWidget 子类
4. **注册导航** → `main_window.py` 的导航配置中添加页面
5. **信号** → `signals.py` 的 SignalBus 类中添加 pyqtSignal
6. **配置项** → `config.py` 的 AppConfig dataclass 中添加字段
7. **历史记录** → `database.py` 中添加对应表和日志函数

### 外部依赖

- **PaddleOCR + PaddlePaddle**：扫描型 PDF OCR 识别
- **Tesseract OCR**：图片 OCR 识别及 PDF 排版重建辅助。中文需 `chi_sim.traineddata`
- **pytesseract**：Python Tesseract 封装库
