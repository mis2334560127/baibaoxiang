# 百宝箱 (BaibaoBOX) 开发完成

## 项目概览

Windows 桌面效率小工具 · 图片批量压缩 / PDF 转 Word / 图片 OCR 识别 / Excel 批量合并 · 全部本地运行

## 技术栈

- **语言**: Python 3.13
- **UI框架**: PyQt6
- **核心库**: Pillow (图片处理) / pdf2docx (PDF转换) / pytesseract (OCR) / PaddleOCR (扫描型PDF)
- **数据**: SQLite (历史记录) + JSON (用户配置)
- **打包**: PyInstaller → 单文件 .exe

## 项目结构

```
baibaoxiang/
├── main.py                  # 入口文件
├── requirements.txt         # Python 依赖
├── build.py                 # 打包脚本
├── src/
│   ├── config.py            # 全局配置 (JSON 持久化)
│   ├── database.py          # SQLite 操作 (历史记录/广告缓存)
│   ├── signals.py           # Qt 信号总线 (全局事件)
│   ├── worker_threads.py    # 后台线程 (压缩/转换/OCR/Excel合并/广告)
│   ├── main_window.py       # 主窗口 (侧边栏+页面切换+主题)
│   ├── modules/
│   │   ├── image_compressor.py   # 图片压缩 (二分搜索逼近算法)
│   │   ├── pdf_converter.py      # PDF→Word (pdf2docx + OCR)
│   │   ├── excel_merger.py       # Excel 批量解压合并
│   │   ├── ocr_recognizer.py     # 图片 OCR 文字识别 (pytesseract)
│   │   └── ad_manager.py         # 广告位管理 (远程API)
│   ├── pages/
│   │   ├── home_page.py      # 首页仪表盘
│   │   ├── compress_page.py  # 图片批量压缩
│   │   ├── pdf_word_page.py  # PDF转Word
│   │   ├── ocr_page.py       # 图片 OCR 识别
│   │   ├── excel_merge_page.py # Excel 合并
│   │   ├── guide_page.py     # 使用指南
│   │   └── settings_page.py  # 系统设置
│   └── theme/
│       ├── blue.qss    # 海天蓝 (默认)
│       ├── teal.qss    # 青翠绿
│       ├── purple.qss  # 星空紫
│       ├── amber.qss   # 暖阳橙
│       └── rose.qss    # 玫瑰红
└── data/                 # 运行时数据 (SQLite/配置)
```

## 核心功能实现

| 功能 | 实现方式 |
|------|---------|
| 图片批量压缩 | Pillow + 二分搜索逼近目标大小，支持按大小/按质量两种模式 |
| PDF 转 Word | pdf2docx 文字型转换 + PaddleOCR/Tesseract 扫描型识别 |
| 图片 OCR 识别 | pytesseract 批量识别，支持多语言，输出 TXT |
| Excel 批量合并 | 解压 zip/rar/7z → 提取 Excel → 合并写入 |
| 主题切换 | 5套 QSS 样式表 + 全局信号总线即时切换 |
| 广告位 | 独立线程拉取远程 API，静默降级，SQLite 缓存 |

## 启动方式

```bash
# 1. 创建虚拟环境
python -m venv .venv

# 2. 安装依赖
.venv\Scripts\pip install -r requirements.txt

# 3. 启动应用
.venv\Scripts\python main.py
```

## 待补充

- 应用图标 (.ico)
- Inno Setup 安装包脚本
