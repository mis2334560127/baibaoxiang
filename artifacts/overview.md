# 百宝箱 (BaibaoBox) 项目概览

## 项目简介

百宝箱 (BaibaoBox) 是一款基于 Python 3.13 + PyQt6 构建的 Windows 桌面效率工具，提供图片批量压缩、PDF 转 Word、图片 OCR 文字识别、Excel 批量合并等实用功能。所有数据均在本地处理，不上传任何服务器。

## 技术架构

- **后端**: Python 3.13
- **UI**: PyQt6（QStackedWidget 多页面 + 侧边栏导航）
- **数据库**: SQLite（wal 模式，通过 db_session() 上下文管理器管理连接）
- **配置**: dataclass + JSON 持久化
- **线程**: QThread（所有耗时操作在后台线程执行）
- **主题**: 5 套 QSS 样式表（blue / teal / purple / amber / rose）

## 项目结构

```
main.py — 入口
src/
├── config.py              # 全局配置
├── database.py            # SQLite 操作
├── signals.py             # SignalBus 信号总线
├── worker_threads.py      # QThread 后台线程
├── main_window.py         # 主窗口（侧边栏 + QStackedWidget）
├── modules/
│   ├── image_compressor.py   # 图片压缩
│   ├── pdf_converter.py      # PDF→Word 转换
│   ├── excel_merger.py       # Excel 批量合并
│   ├── ocr_recognizer.py     # OCR 文字识别
│   └── ad_manager.py         # 广告位管理
├── pages/
│   ├── home_page.py         # 首页仪表盘
│   ├── compress_page.py     # 图片压缩
│   ├── pdf_word_page.py     # PDF 转 Word
│   ├── ocr_page.py          # OCR 识别
│   ├── excel_merge_page.py  # Excel 合并
│   ├── guide_page.py        # 使用指南
│   └── settings_page.py     # 系统设置
└── theme/                  # 5 套 QSS 主题
```

## 核心功能

### 1. 图片批量压缩
- 支持按目标文件大小压缩（二分搜索逼近算法）
- 支持按质量百分比压缩
- 批量处理 JPG/JPEG/PNG/BMP/WebP/TIFF
- RGBA/调色板模式自动转 RGB

### 2. PDF 转 Word
- 文字型 PDF：pdf2docx 直接转换
- 扫描型 PDF：PaddleOCR + Tesseract 双引擎识别
- 混合型 PDF：自动路由各页
- 支持保留图片和保留原始格式选项

### 3. 图片 OCR 文字识别
- 基于 pytesseract 批量识别
- 支持中文/英文/日文/韩文等多种语言
- 独立 TXT 输出或合并输出

### 4. Excel 批量合并
- 解压 zip/rar/7z 压缩包
- 提取所有 Excel 文件
- 统一表头后合并写入单个 Excel

### 5. 主题系统
- 5 套 QSS 样式表
- 支持侧边栏色点和设置页面切换
- 偏好自动保存

### 6. 预留广告模块
- 单例模式 + 独立 daemon 线程
- 远程 JSON API 拉取
- 支持 Bearer Token 认证
- 静默降级（失败回退 SQLite 缓存）
- 默认关闭，用户可配置

## 窗口关闭保护

主窗口 `closeEvent` 按顺序：
1. 停止广告拉取线程
2. 保存窗口尺寸和最大化状态到配置

## 数据存储

- **用户配置**: `data/config.json`（打包后 `%APPDATA%\BaibaoBOX\config.json`）
- **历史记录**: `data/baibaobox.db`（SQLite，WAL 模式）
  - `compress_history` — 图片压缩记录
  - `convert_history` — PDF 转换记录
  - `ocr_history` — OCR 识别记录
  - `ad_cache` — 广告缓存
