# 百宝箱 (BaibaoBOX)

> 一站式 Windows 桌面效率工具：图片批量压缩 · PDF 转 Word · 图片 OCR 识别 · Excel 批量合并 · 全部本地运行，数据不上传

![Python](https://img.shields.io/badge/Python-3.13-blue) ![PyQt6](https://img.shields.io/badge/UI-PyQt6-green)

---

## 功能快照

| 功能 | 说明 |
|------|------|
| 🖼️ **图片批量压缩** | 支持按目标大小 / 按质量两种模式，批量处理 JPG/PNG/BMP/WebP/TIFF |
| 📄 **PDF 转 Word** | 文字型直接转换，扫描型 PaddleOCR 识别，混合型自动路由 |
| 🔍 **图片 OCR 识别** | 批量识别图片文字，支持中文/英文/日文/韩文等多语言，输出 TXT |
| 📊 **Excel 批量合并** | 批量解压 zip/rar/7z，提取 Excel 并合并为单一文件 |
| 🎨 **5 套主题** | 海天蓝 / 青翠绿 / 星空紫 / 暖阳橙 / 玫瑰红，一键切换 |
| 📺 **广告位** | 预留广告模块（默认关闭），可配置 API 源和刷新间隔 |

### 与同行差别

- ✅ **完全本地运行** — 图片/PDF/Excel 数据不上传任何服务器
- ✅ **OCR 双引擎** — PDF 扫描件使用 PaddleOCR + Tesseract 双重识别提高准确率
- ✅ **简约高效** — 无广告（默认）、无注册、无需联网

## 开始使用

### 环境要求

| 依赖 | 说明 |
|------|------|
| Windows 10/11 64-bit | 必选 |
| Python 3.13+ | 开发/调试时需要 |
| Tesseract-OCR 5.x | OCR 识别功能必需 |

### 安装指南

#### 1️⃣ 安装 Python 和依赖

```bash
# 克隆或解压项目后
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
```

#### 2️⃣ 安装 Tesseract-OCR

图片 OCR 和部分 PDF 识别功能需要 Tesseract OCR 引擎。

- [Tesseract 下载地址 (UB-Mannheim)](https://github.com/UB-Mannheim/tesseract/wiki)
- 安装时勾选中文简体语言包（`Chinese (Simplified)`）
- 也可使用项目自带的安装包：`tesseract-ocr-w64-setup-*.exe`
- 安装后在软件设置页面配置路径，或确保 `tesseract.exe` 在 PATH 中

#### 3️⃣ 启动应用

```bash
.venv\Scripts\python main.py
```

或双击 `main.py` 在 IDE 中运行。

#### 4️⃣ 打包为单文件 exe

```bash
.venv\Scripts\python build.py --all
```

> 打包后产出 `dist/BaibaoBOX.exe`，可直接发给他人使用（无需安装 Python）。
> 目标电脑仍需安装 Tesseract OCR 才能使用图片识别功能。
> 配置和数据自动保存在 `%APPDATA%\BaibaoBOX\`。

---

## 功能操作手册

### 🖼️ 图片批量压缩

一键批量压缩图片，支持按目标文件大小或按质量百分比两种模式。

**操作步骤：**
1. 添加文件：点击「添加文件」或拖拽图片到窗口
2. 选择模式：
   - **按目标大小** — 设置期望的文件大小（如 500KB），算法自动逼近
   - **按质量压缩** — 拖动滑块选择 5%~100% 的质量
3. 点击「开始压缩」
4. 输出文件自动保存到「百宝箱输出」文件夹

**支持格式：** JPG / JPEG / PNG / BMP / WebP / TIFF

> 📌 PNG 无损格式，`quality` 参数不生效，按质量模式下仅做 _optimize_

### 📄 PDF 转 Word

支持文字型 PDF 直接转换和扫描型 PDF 的 OCR 识别转 Word。

**操作步骤：**
1. 点击「添加 PDF」或拖拽文件到窗口
2. 自动分类：文字型 / 扫描型 / 混合型
3. 可选选项：保留原始格式、保留图片、强制 OCR 识别（扫描型 PDF）
4. 点击「开始转换」
5. 输出 `.docx` 自动保存到「百宝箱输出」文件夹

**支持类型：**
- **文字型** — pdf2docx 直接转换，速度快，格式保留好
- **扫描型** — 自动使用 PaddleOCR + Tesseract 深度学习引擎识别文字
- **混合型** — 文字页直接转换 + 图片页 OCR 识别，自动路由

### 🔍 图片 OCR 识别

批量识别图片中的文字内容，支持多种语言。

**操作步骤：**
1. 添加图片：点击「添加图片」或拖拽到窗口，支持递归扫描目录
2. 选择识别语言（中英文 / 日文 / 韩文 / 法文等）
3. 选择输出模式：每图独立 TXT / 合并为单个 TXT
4. 点击「开始识别」
5. 输出文件自动保存到「百宝箱输出」文件夹

**支持格式：** PNG / JPG / BMP / WebP / TIFF

### 📊 Excel 批量合并

批量解压压缩包中的 Excel 文件并合并为一个完整的 Excel 文件。

**操作步骤：**
1. 添加压缩包（zip / rar / 7z）
2. 自动解压并提取所有 Excel 文件（自动过滤临时文件和 `__MACOSX` 目录）
3. 统一表头后合并数据
4. 点击「开始合并」
5. 输出文件自动保存到「百宝箱输出」文件夹

---

## 技术架构

```
main.py
└── src/
    ├── config.py              # 全局配置
    ├── database.py            # SQLite 数据库
    ├── signals.py             # SignalBus 信号总线
    ├── worker_threads.py      # 后台线程
    ├── main_window.py         # 主窗口
    ├── modules/
    │   ├── image_compressor.py
    │   ├── pdf_converter.py
    │   ├── excel_merger.py
    │   ├── ocr_recognizer.py
    │   └── ad_manager.py
    ├── pages/
    │   ├── home_page.py
    │   ├── compress_page.py
    │   ├── pdf_word_page.py
    │   ├── ocr_page.py
    │   ├── excel_merge_page.py
    │   ├── guide_page.py
    │   └── settings_page.py
    └── theme/
        ├── blue.qss
        ├── teal.qss
        ├── purple.qss
        ├── amber.qss
        └── rose.qss
```

### 架构要点

**SignalBus 信号总线** — 所有页面通过 `signals.py` 的 SignalBus 单例通信，互不直接引用。`get_bus()` 懒加载确保在 QApplication 初始化后才实例化。

**QThread 后台线程** — 压缩/转换/OCR/Excel合并均在独立 QThread 中运行，通过 Qt 信号（`progress`、`finished`、`error`）安全更新 UI。

**主题系统** — 5 套 QSS 样式表，全局切换。`THEMES` 字典定义各主题的 primary/accent 色值，设置保存到 config.json。

**配置持久化** — 用户配置以 JSON 格式保存在 `data/config.json`（打包后为 `%APPDATA%\BaibaoBOX\config.json`）。

### 信号列表

| 信号 | 触发时机 |
|------|---------|
| `navigate_to(page_id)` | 页面跳转请求 |
| `theme_changed(theme_key)` | 主题切换 |
| `history_updated()` | 数据记录更新（首页刷新） |
| `compress_all_done()` | 图片压缩全部完成 |
| `convert_all_done()` | PDF 转换全部完成 |
| `ocr_all_done()` | OCR 识别全部完成 |
| `merge_all_done()` | Excel 合并完成 |
| `ad_updated(ads)` | 广告数据更新 |

### 配置项

| 配置 | 类型 | 说明 |
|------|------|------|
| `theme` | str | 主题名称（blue/teal/purple/amber/rose） |
| `output_dir` | str | 输出目录（空=用户每次选择） |
| `compress_quality` | int | 默认压缩质量（1-100） |
| `compress_mode` | str | 压缩模式（size/quality） |
| `compress_target_size` | int | 目标文件大小（KB） |
| `pdf_keep_format` | bool | 是否保留 PDF 格式 |
| `pdf_keep_images` | bool | 是否保留 PDF 图片 |
| `pdf_force_ocr` | bool | 是否强制 OCR 识别 |
| `ocr_language` | str | OCR 识别语言 |
| `ocr_merge_output` | bool | OCR 是否合并输出 |
| `ocr_tesseract_path` | str | Tesseract 自定义路径 |
| `ad_enabled` | bool | 广告位开关 |
| `ad_api_url` | str | 广告 API 地址 |
| `ad_api_key` | str | 广告 API 密钥 |
| `ad_refresh_interval` | int | 广告刷新间隔（分钟） |

### 数据库表

| 表名 | 用途 |
|------|------|
| `compress_history` | 图片压缩记录 |
| `convert_history` | PDF 转换记录 |
| `ocr_history` | OCR 识别记录 |
| `ad_cache` | 广告内容缓存 |

数据库文件位于 `data/baibaobox.db`，使用 WAL 模式。

---

## 常见问题

**Q: 百宝箱会收集我的数据吗？**
A: 不会。所有功能均在本地运行，不上传任何文件到网络。唯一的网络请求是预留的广告位（默认关闭），且仅在您主动配置后才生效。

**Q: OCR 识别速度慢？**
A: 取决于图片质量和大小。建议使用清晰、分辨率适中的图片。Tesseract 首次启动可能需要加载语言数据。

**Q: 扫描型 PDF 识别不准？**
A: 扫描件识别质量取决于原图清晰度。确保已安装 Tesseract 中文语言包（`chi_sim`），且图片清晰可辨。PaddleOCR 和 Tesseract 双引擎协同提高准确率。

**Q: PDF 转换后格式乱了？**
A: 仅文字型 PDF 支持格式保留；扫描型 PDF 通过 OCR 重建文档，无法保证原始排版。

**Q: 打包后 exe 在其他电脑无法运行？**
A: exe 自带所有 Python 依赖，但 Tesseract-OCR 需要在目标电脑上单独安装。也可在软件设置页面指定已安装的 Tesseract 路径。

**Q: 如何修改输出目录？**
A: 每次处理时可在文件选择窗口中指定。也可在设置页面设置默认输出目录。

---

## 开发信息

- **分支策略**: 主分支 `main`，功能从 `dev` 分支合并
- **Python 版本**: 3.13+
- **UI 框架**: PyQt6（`PyQt6` `PyQt6-sip`）
- **核心依赖**: Pillow (图片处理) / pdf2docx (PDF 转换) / pytesseract (OCR) / pyunpack+patool (解压压缩包) / openpyxl (Excel 处理)
- **打包**: PyInstaller（`build.py --all`）

### 命令速查

```bash
# 开发运行
.venv\Scripts\python main.py

# 打包
.venv\Scripts\python build.py --all
```

---

> 感谢使用百宝箱！如有问题或建议，欢迎提交 Issue。
