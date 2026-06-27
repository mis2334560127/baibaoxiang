# 百宝箱 (BaibaoBOX)

> Windows 桌面效率工具 · 图片批量压缩 / PDF 转 Word / 屏幕录制 · 全部本地运行，数据不上传。

---

## 目录

- [功能概览](#功能概览)
- [系统要求](#系统要求)
- [安装与启动](#安装与启动)
  - [开发环境](#开发环境)
  - [外部依赖安装](#外部依赖安装)
  - [打包为 EXE](#打包为-exe)
- [操作手册](#操作手册)
  - [图片批量压缩](#图片批量压缩)
  - [PDF 转 Word](#pdf-转-word)
  - [屏幕录制](#屏幕录制)
  - [主题切换](#主题切换)
  - [系统设置](#系统设置)
- [项目架构](#项目架构)
  - [目录结构](#目录结构)
  - [架构分层](#架构分层)
  - [数据流](#数据流)
  - [关键设计决策](#关键设计决策)
- [技术细节](#技术细节)
  - [图片压缩算法](#图片压缩算法)
  - [PDF 转换与 OCR](#pdf-转换与-ocr)
  - [屏幕录制管线](#屏幕录制管线)
  - [信号总线](#信号总线)
  - [配置管理](#配置管理)
  - [数据库设计](#数据库设计)
  - [主题系统](#主题系统)
- [配置参考](#配置参考)
- [常见问题](#常见问题)
- [开发指南](#开发指南)

---

## 功能概览

| 功能 | 描述 | 核心能力 |
|------|------|----------|
| 📷 图片批量压缩 | 批量压缩图片，支持按目标大小或按质量 | 二分搜索逼近 ±5KB · 等比缩放 · JPG/PNG/WebP/BMP/TIFF |
| 📄 PDF 转 Word | PDF 转可编辑 .docx 文档 | 文字型直接转换 · 扫描型 OCR 识别 · 混合型自动路由 |
| 🎬 屏幕录制 | 屏幕录像输出 MP4 | H.264 硬编码 · 全屏/区域录制 · 实时 FFmpeg 管道 |
| 🎨 主题切换 | 5 套配色方案一键切换 | 海天蓝 / 青翠绿 / 星空紫 / 暖阳橙 / 玫瑰红 |

---

## 系统要求

| 项目 | 要求 |
|------|------|
| 操作系统 | Windows 10 / 11（64 位） |
| Python | 3.13+（开发环境） |
| 内存 | ≥ 4GB |
| 磁盘 | ≥ 500MB 可用空间 |

**可选外部依赖**：

| 依赖 | 用途 | 必需？ |
|------|------|--------|
| [FFmpeg](https://ffmpeg.org/download.html) | 屏幕录制编码 | 仅录屏需要 |
| [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) | 扫描型 PDF 文字识别 | 仅 OCR 需要 |

---

## 安装与启动

### 开发环境

```bash
# 1. 克隆项目
git clone <repo-url>
cd baibaoxiang

# 2. 创建虚拟环境
python -m venv .venv

# 3. 安装 Python 依赖
.venv\Scripts\pip install -r requirements.txt

# 4. 启动应用
.venv\Scripts\python main.py
```

### 外部依赖安装

#### FFmpeg（录屏必需）

1. 从 https://ffmpeg.org/download.html 下载 Windows 版本
2. 解压后将 `bin` 目录添加到系统 `PATH` 环境变量
3. 或将 `ffmpeg.exe` 放在项目根目录下
4. 程序启动时自动查找（常见路径 → PATH → 注册表）

#### Tesseract OCR（扫描型 PDF 转换必需）

1. 从 https://github.com/UB-Mannheim/tesseract/wiki 下载 Windows 安装包
2. 安装时务必勾选 **Chinese (Simplified)** 语言包
3. 如果忘记勾选，可手动下载 `chi_sim.traineddata`：
   ```
   https://github.com/tesseract-ocr/tessdata/raw/main/chi_sim.traineddata
   ```
4. 放入 Tesseract 安装目录下的 `tessdata` 文件夹
5. 程序自动检测（PATH → 常见安装路径 → 注册表）

### 打包为 EXE

```bash
# 清理 + 构建
.venv\Scripts\python build.py --all

# 仅打包
.venv\Scripts\python build.py --build

# 仅清理
.venv\Scripts\python build.py --clean
```

输出文件：`dist/BaibaoBOX.exe`（单文件，含 PyInstaller 打包）

---

## 操作手册

### 图片批量压缩

**入口**：左侧导航 → 📷 图片压缩

**支持格式**：JPG、JPEG、PNG、BMP、WebP、TIFF、GIF

**操作步骤**：

1. **添加文件**：点击「添加文件」选择图片，或直接从文件夹拖拽图片到窗口
2. **选择压缩模式**：
   - **按目标大小**：设置期望的文件体积（如 500KB），算法通过二分搜索自动逼近
   - **按质量压缩**：拖动滑块选择 1-100 的 JPEG 质量参数
3. **（可选）限制尺寸**：勾选「📐 限制图片尺寸」，设置最大宽度/高度，图片将等比缩放
4. **开始压缩**：点击「开始压缩」，查看实时进度和日志
5. **查看结果**：压缩后的文件自动保存到 `桌面\百宝箱输出` 文件夹

**注意事项**：
- PNG 带透明通道的图片会自动转 JPG（白色背景填充透明区域）
- 按目标大小模式使用二分搜索，精度 ±5KB，最多 12 次迭代
- 尺寸限制采用等比缩放，只缩小不放大

### PDF 转 Word

**入口**：左侧导航 → 📄 PDF 转 Word

**操作步骤**：

1. **添加 PDF**：点击「添加 PDF」或拖拽文件到窗口
2. **查看类型**：文件列表自动显示 PDF 类型
   - 📝 **文字型**：PDF 含有可选文字层，直接转换
   - 🖼️ **扫描型**：图片型 PDF，需 OCR 识别
   - 📝🖼️ **混合型**：部分页有文字，部分页需 OCR
3. **设置选项**：
   - 「保留原始格式」：尽可能保持排版结构（仅文字型生效）
   - 「保留图片」：提取文档中的图片至 images 子目录（仅文字型生效）
   - 「强制 OCR 识别」：即使检测为文字型也使用 OCR
4. **选择 OCR 语言**：默认可选的中文语言包，若未安装中文则仅显示 eng
5. **开始转换**：点击「开始转换」，等待完成
6. **输出**：.docx 文件保存到输出文件夹

**OCR 转换流程**：
```
PDF 页面 → PyMuPDF 渲染 (300dpi) → pytesseract OCR 识别 → python-docx 生成
```

**注意事项**：
- OCR 速度取决于页数和 DPI，通常每页 3-10 秒
- 中文 OCR 必须安装 Tesseract 的中文语言包
- OCR 结果质量取决于原图清晰度

### 屏幕录制

**入口**：左侧导航 → 🎬 屏幕录制

**操作步骤**：

1. **设置参数**：
   - 帧率：默认 15 FPS，教程录制建议 30 FPS
   - 编码器：默认 H.264（libx264），兼容性最佳
   - 格式：MP4
2. **选择模式**：全屏 或 自定义区域
3. **开始录制**：点击「开始录制」
4. **结束录制**：点击「停止」
5. **查看视频**：录制文件自动保存到输出文件夹

**技术流程**：
```
Windows GDI 逐帧截图 → BGRA 原始数据 → FFmpeg stdin 管道 → H.264 编码 → MP4 文件
```

**注意事项**：
- 必须安装 FFmpeg
- 录制时在窗口可看到计时器
- 关闭主窗口时会自动停止录制（防止 FFmpeg 孤儿进程）

### 主题切换

**入口**：标题栏右侧色点 或 系统设置页面

5 套预设主题：海天蓝（默认）、青翠绿、星空紫、暖阳橙、玫瑰红

切换即时生效，无重启。主题偏好自动保存到配置文件。

### 系统设置

**入口**：左侧导航 → ⚙️ 系统设置

| 设置项 | 说明 |
|--------|------|
| 主题颜色 | 5 套配色方案 |
| 输出目录 | 自定义文件保存位置（默认：桌面\百宝箱输出） |
| FFmpeg 路径 | 手动指定 FFmpeg 位置（留空则自动查找） |
| 广告位 | 启用/禁用广告 API（默认关闭），配置 API 地址和密钥 |

---

## 项目架构

### 目录结构

```
baibaoxiang/
├── main.py                     # 入口：初始化 App → 信号总线 → 配置 → 主窗口
├── build.py                    # PyInstaller 打包脚本
├── requirements.txt            # Python 依赖清单
├── README.md                   # 本文档
├── PROJECT.md                  # 项目开发说明
├── CODEBUDDY.md               # AI 编码助手指引
│
├── src/
│   ├── config.py               # 全局配置 (dataclass + JSON 持久化，单例)
│   ├── database.py             # SQLite 操作 (历史记录 + 广告缓存)
│   ├── signals.py              # Qt 信号总线 (全局事件通信，单例)
│   ├── worker_threads.py       # 后台线程 (QThread 子类)
│   ├── main_window.py          # 主窗口 (侧边栏导航 + 页面栈 + 主题)
│   │
│   ├── modules/                # 纯逻辑模块 (无 Qt 依赖)
│   │   ├── image_compressor.py     # 图片压缩核心算法
│   │   ├── pdf_converter.py        # PDF 转 Word (pdf2docx + OCR)
│   │   ├── screen_recorder.py      # 屏幕录制 (GDI + FFmpeg)
│   │   └── ad_manager.py           # 广告管理 (API 拉取 + 缓存)
│   │
│   ├── pages/                  # UI 页面 (每个功能一个 QWidget)
│   │   ├── home_page.py            # 首页仪表盘 (统计 + 历史)
│   │   ├── compress_page.py        # 图片批量压缩
│   │   ├── pdf_word_page.py        # PDF 转 Word
│   │   ├── recorder_page.py        # 屏幕录制
│   │   ├── guide_page.py           # 使用指南 (安装步骤 + 功能说明 + FAQ)
│   │   └── settings_page.py        # 系统设置
│   │
│   └── theme/                  # 5 套 QSS 样式表
│       ├── blue.qss
│       ├── teal.qss
│       ├── purple.qss
│       ├── amber.qss
│       └── rose.qss
│
└── data/                       # 运行时数据
    ├── baibaobox.db            # SQLite 数据库
    └── config.json             # 用户配置文件
```

### 架构分层

```
┌──────────────────────────────────────────┐
│  main.py — 应用入口                        │
│    初始化 QApplication → 信号总线 → 配置    │
│    → 广告管理器 → 主窗口                   │
├──────────────────────────────────────────┤
│  pages/ — UI 层 (QWidget)                 │
│    接受用户输入，显示进度/结果              │
├──────────────────────────────────────────┤
│  worker_threads.py — 线程层 (QThread)      │
│    将耗时操作放入后台，通过信号通信         │
├──────────────────────────────────────────┤
│  modules/ — 业务逻辑层 (纯 Python)         │
│    图片压缩 / PDF 转换 / 屏幕录制 / 广告    │
├──────────────────────────────────────────┤
│  config.py + database.py — 数据层          │
│    JSON 配置 + SQLite 持久化               │
└──────────────────────────────────────────┘
```

### 数据流

```
用户操作
  ↓
Page 创建 Worker (QThread)
  ↓
Worker 调用 modules/ 中的纯逻辑函数
  ↓
Worker 通过 Qt signal 报告进度/结果
  ↓
Page 更新 UI (进度条、日志)
  ↓
完成时通过 SignalBus 发射 *_all_done 信号
  ↓
首页 → bus.history_updated → 刷新统计
```

配置变更流程：
```
SettingsPage → _config.save() → reload_config()
→ bus.theme_changed (如有主题变更)
→ MainWindow 接收信号 → 重新加载 QSS
```

### 关键设计决策

#### 1. 信号总线模式 (SignalBus)

所有跨页面/跨模块通信通过 `src/signals.py` 中的 SignalBus 单例完成：

- 导航：`bus.navigate_to.emit(page_id)`
- 主题：`bus.theme_changed.emit(key)`
- 历史更新：`bus.history_updated.emit()`
- 任务完成：`bus.compress_all_done.emit(s, f)` / `bus.convert_all_done.emit(s, f)` / `bus.record_done.emit(path, dur)`

页面之间不直接引用对方，完全解耦。SignalBus 在 QApplication 创建后懒加载。

#### 2. 后台线程模式

所有耗时操作放入 QThread 子类，避免阻塞 UI：

- `CompressWorker` — 图片压缩
- `ConvertWorker` — PDF 转换
- `RecordWorker` — 屏幕录制
- `AdFetcher` — 广告拉取

线程使用**协作式取消**（`_cancelled` / `_stop_event` 标志位），不使用强制 `terminate()`。

#### 3. 配置管理

`AppConfig` 是一个 `@dataclass`，从 `data/config.json` 加载/保存。通过 `get_config()` 获取全局单例。页面持有 `self._config` 直接读写，修改后调用 `_config.save()` 持久化。

#### 4. 关闭保护

主窗口 `closeEvent` 中执行：
1. 优先停止屏幕录制（防止 FFmpeg 孤儿进程）
2. 停止广告拉取线程
3. 保存窗口尺寸和最大化状态

---

## 技术细节

### 图片压缩算法

核心函数：`compress_image()`（`src/modules/image_compressor.py`）

**两种模式**：

| 模式 | 参数 | 原理 |
|------|------|------|
| 按目标大小 (`size`) | `target_kb` | 二分搜索逼近 JPEG quality，精度 ±5KB，最多 12 次迭代 |
| 按质量 (`quality`) | `quality` (1-100) | 直接指定 JPEG 压缩质量 |

**预处理**：
- 尺寸限制：开启后等比缩放，取宽/高中较小的缩放比例，只缩小不放大，使用 `Image.LANCZOS` 高质量采样
- 透明通道处理：RGBA/P/LA 模式自动转 RGB，白色背景填充
- PNG 在按质量模式下仅做 `optimize`（PNG 无损，quality 参数不生效）

### PDF 转换与 OCR

核心函数：`convert_pdf_to_docx()`（`src/modules/pdf_converter.py`）

**自动路由逻辑**：

```
                      ┌───────────────────┐
                      │  检测 PDF 类型      │
                      │  detect_pdf_type() │
                      └────────┬──────────┘
                               │
              ┌────────────────┼────────────────┐
              ▼                ▼                ▼
        ┌──────────┐   ┌──────────────┐  ┌──────────────┐
        │ 文字型    │   │ 扫描型        │  │ 混合型        │
        │ (100%)   │   │ (0% 文字层)   │  │ (部分有文字)  │
        └────┬─────┘   └──────┬───────┘  └──────┬───────┘
             │                │                  │
             ▼                └────────┬─────────┘
     ┌──────────────┐                  ▼
     │ pdf2docx     │        ┌─────────────────┐
     │ 直接转换      │        │ OCR 识别流程     │
     │ 保留格式+图片  │        │ PyMuPDF 渲染     │
     └──────────────┘        │ → pytesseract   │
                             │ → python-docx   │
                             └─────────────────┘
```

**OCR 语言自动检测**：
- 启动时检测已安装的 Tesseract 语言包
- 请求 `chi_sim+eng` 时，若 `chi_sim` 不可用则自动回退到 `eng` 并告警
- UI 下拉框显示可用语言，缺少中文时显示橙色警告
- 支持手动下载 `chi_sim.traineddata` 的指引

**Tesseract 查找策略**：
1. `PATH` 环境变量
2. 常见安装路径（`Program Files\Tesseract-OCR` 等）
3. Windows 注册表（`HKLM` / `HKCU`）

### 屏幕录制管线

核心模块：`src/modules/screen_recorder.py`

**技术栈**：
- **截图**：`pywin32` 调用 Windows GDI (`GetDC` / `BitBlt`)
- **编码**：FFmpeg 管道接收 BGRA 原始数据 → H.264 编码
- **容器**：MP4

**生产者-消费者模式**：
```
截图线程 (Producer)             写入线程 (Consumer)
      │                              │
      ├─ GetDC / BitBlt              │
      ├─ 捕获 BGRA 帧                │
      ├─ frame_queue.put(frame) ──→  ├─ frame_queue.get()
      │                              ├─ ffmpeg.stdin.write(frame)
      │                              └─ 循环直到 _stop_event
      │
      └─ 队列容量: maxsize=30
```

- `queue.Queue(maxsize=30)` 防止生产者过快导致内存溢出
- `threading.Event` 实现外部停止信号
- 录制完成后自动写入 `record_history` 表

### 信号总线

文件：`src/signals.py`

所有跨页面通信信号定义在 `SignalBus` 类中：

| 信号 | 参数 | 用途 |
|------|------|------|
| `navigate_to` | `str` page_id | 页面导航 |
| `theme_changed` | `str` theme_key | 主题切换 |
| `history_updated` | — | 刷新首页历史记录 |
| `compress_all_done` | `int` success, `int` fail | 压缩任务完成 |
| `convert_all_done` | `int` success, `int` fail | 转换任务完成 |
| `record_done` | `str` path, `int` duration | 录制完成 |

使用懒加载模式：`get_bus()` 返回全局唯一实例，模块级 `__getattr__` 代理确保在 `QApplication` 存在后才实例化。

### 配置管理

文件：`src/config.py`

`AppConfig` 是一个 `@dataclass`，字段包括：

| 字段 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `theme` | `str` | `"blue"` | 主题名称 |
| `output_dir` | `str` | `""` | 输出目录（空=桌面） |
| `ffmpeg_path` | `str` | `""` | FFmpeg 路径（空=自动查找） |
| `compress_target_size_kb` | `int` | `500` | 压缩目标大小 |
| `compress_quality` | `int` | `75` | 压缩质量 |
| `compress_mode` | `str` | `"size"` | 压缩模式 |
| `compress_max_width` | `int` | `0` | 最大宽度限制（0=不限） |
| `compress_max_height` | `int` | `0` | 最大高度限制（0=不限） |
| `record_fps` | `int` | `15` | 录制帧率 |
| `pdf_preserve_formatting` | `bool` | `True` | PDF 保留格式 |
| `pdf_preserve_images` | `bool` | `True` | PDF 保留图片 |
| `pdf_ocr_lang` | `str` | `"chi_sim+eng"` | OCR 语言 |
| `ad_enabled` | `bool` | `False` | 广告位开关 |
| `window_width/height` | `int` | `1100/720` | 窗口尺寸 |

**持久化流程**：
```
config.save() → json.dumps(asdict(self)) → data/config.json
config.load() ← json.loads(file) ← data/config.json
```

### 数据库设计

文件：`src/database.py`  
数据库：`data/baibaobox.db`（SQLite，WAL 模式）

**四张核心表**：

| 表名 | 用途 | 主要字段 |
|------|------|----------|
| `compress_history` | 图片压缩记录 | file_name, orig_size_kb, final_size_kb, quality, mode |
| `convert_history` | PDF 转换记录 | file_name, orig_pages, status |
| `record_history` | 屏幕录制记录 | file_name, duration_sec, file_size_mb |
| `ad_cache` | 广告内容缓存 | ad_id, title, image_url, link_url, active |

使用 `db_session()` 上下文管理器自动管理 commit/close。

### 主题系统

5 套 QSS 样式表位于 `src/theme/`：

| 文件 | 名称 | 主色 |
|------|------|------|
| `blue.qss` | 海天蓝 | `#1877F2` |
| `teal.qss` | 青翠绿 | `#0D9488` |
| `purple.qss` | 星空紫 | `#7C3AED` |
| `amber.qss` | 暖阳橙 | `#D97706` |
| `rose.qss` | 玫瑰红 | `#E11D48` |

主题切换流程：
```
bus.theme_changed.emit(key)
→ MainWindow._on_theme_changed(key)
→ _load_theme() 读取 .qss 文件
→ app.setStyleSheet(qss_content)
```

---

## 配置参考

### data/config.json 示例

```json
{
  "theme": "blue",
  "output_dir": "",
  "ffmpeg_path": "",
  "ad_enabled": false,
  "ad_api_url": "",
  "ad_api_key": "",
  "ad_refresh_minutes": 30,
  "window_width": 1100,
  "window_height": 720,
  "window_maximized": false,
  "compress_target_size_kb": 500,
  "compress_quality": 75,
  "compress_mode": "size",
  "compress_max_width": 0,
  "compress_max_height": 0,
  "record_fps": 15,
  "record_codec": "libx264",
  "record_format": "mp4",
  "pdf_preserve_formatting": true,
  "pdf_preserve_images": true,
  "pdf_ocr_lang": "chi_sim+eng"
}
```

---

## 常见问题

| 问题 | 解答 |
|------|------|
| **百宝箱会收集我的数据吗？** | 不会。所有功能均在本地运行，不上传任何文件。唯一的网络请求是预留广告位（默认关闭）。 |
| **为什么压缩后比目标大？** | 算法二分搜索逼近，精度 ±5KB。超大原始文件可能需要多次迭代。也可尝试「按质量压缩」模式。 |
| **PDF 转 Word 后全是英文乱码？** | Tesseract 未安装中文语言包。请下载 `chi_sim.traineddata` 放入 tessdata 目录，或重新运行安装程序勾选中文。 |
| **PDF 转 Word 后还是图片无法编辑？** | 这是扫描型 PDF，文字是图片的一部分。需安装 Tesseract OCR，程序会自动切换为 OCR 模式。 |
| **屏幕录制报错「找不到 FFmpeg」？** | 录屏依赖 FFmpeg。下载 Windows 版 FFmpeg，将 bin 目录加入 PATH，或放 ffmpeg.exe 到软件目录。 |
| **可以自定义输出路径吗？** | 可以。在「系统设置」中修改默认输出目录。 |
| **支持哪些 Windows 版本？** | Windows 10 / 11（64 位）。32 位系统未经测试。 |

---

## 开发指南

### Python 依赖

```txt
PyQt6>=6.6.0          # UI 框架
Pillow>=10.2.0        # 图片处理
pdf2docx>=0.5.8       # PDF 文字型转换
python-docx>=1.1.0    # Word 文档生成
PyMuPDF>=1.23.0       # PDF 页数/类型检测 + OCR 渲染
pytesseract>=0.3.10   # OCR 文字识别
pywin32>=306          # Windows GDI 屏幕捕获
psutil>=5.9.0         # 系统工具
pyinstaller>=6.3.0    # 打包（开发期）
```

### 常用命令

```bash
# 启动开发模式
.venv\Scripts\python main.py

# 打包
.venv\Scripts\python build.py --all

# 仅测试核心逻辑
.venv\Scripts\python -c "from src.modules.image_compressor import compress_image; ..."
```

### 新增功能指南

1. **纯逻辑** → 在 `src/modules/` 中创建模块（无 Qt 依赖）
2. **后台线程** → 在 `src/worker_threads.py` 中添加 QThread 子类
3. **UI 页面** → 在 `src/pages/` 中创建 QWidget 子类
4. **注册导航** → 在 `main_window.py` 的导航配置中添加页面
5. **配置项** → 在 `config.py` 的 `AppConfig` dataclass 中添加字段
6. **历史记录** → 在 `database.py` 中添加对应的日志表和查询函数

### 代码规范

- 类型注解：所有函数参数和返回值使用 Python 类型注解
- 编码风格：UTF-8，4 空格缩进
- 线程安全：使用协作式取消标志，不使用 `thread.terminate()`
- 错误处理：静默降级，向用户展示友好错误提示
- 中文优先：UI 文字使用中文，代码注释中英皆可

---

## 许可证

内部项目，仅供学习和个人使用。

---

<p align="center">
  <sub>Made with ❤️ by BaibaoBOX Team · 2025-2026</sub>
</p>
