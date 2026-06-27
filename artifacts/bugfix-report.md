# 百宝箱 v1.0 — Bug 修复报告

**修复日期**: 2026-06-25  
**修复人**: 吴八哥（高级开发工程师）  
**修改文件**: 15 个 Python 源文件，语法检查全部通过

---

## 🔴 Blocker 级（4/4 已修复）

| 编号 | 问题 | 修复方式 |
|------|------|---------|
| **BUG-001** | BGRA 逐像素转换性能灾难 | 删除 Python for 循环；FFmpeg 改用 `bgra` 像素格式直接接收 GDI 原始数据，零转换开销 |
| **BUG-002** | QThread.terminate() 危险用法 | CompressWorker / ConvertWorker 添加 `cancel()` 协作式退出 + `_cancelled` 标志；页面调用 `cancel()` + `wait(5000)` |
| **BUG-003** | 关闭窗口时录制未停止 | MainWindow.closeEvent 先停录屏再清理；main.py 添加 `aboutToQuit` 全局清理兜底 |
| **BUG-004** | PDF preserve_images 参数无效 | `pdf_converter.py` 中 `Converter.convert()` 传入 `image_folder` 参数 |

## 🟡 Major 级（5/5 已修复）

| 编号 | 问题 | 修复方式 |
|------|------|---------|
| **BUG-005** | SignalBus QObject 二次初始化 | 将 `QObject.__init__` 从 `__new__` 移到 `__init__`，添加 `_initialized` 防重入 |
| **BUG-006** | 多页面配置不同步 | config.py 添加 `get_config()` / `reload_config()` 全局单例；所有页面统一使用 |
| **BUG-007** | 首页统计面板显示 bug | 用 `stat_value_labels` dict 持有 QLabel 引用；删除 `_find_stat_value` 死代码 |
| **BUG-008** | 快捷卡片无导航 | signals.py 添加 `navigate_to` 信号；main_window.py 连接；home_page.py 使用 |
| **BUG-009** | 录制管道写入阻塞 | 添加 `frame_queue` + `_writer_thread` 解耦截图与编码；BGRA 直接入队无需转换 |

## 🔵 Minor + 💭 Info 级（7/7 已修复）

| 编号 | 问题 | 修复方式 |
|------|------|---------|
| BUG-010 | 数据库连接频繁开关 | `database.py` 添加 `db_session()` context manager；所有 CRUD 函数使用 `with db_session()` |
| BUG-011 | 拖拽样式清空闪烁 | 保存 `_drop_zone_orig_style`，dragLeave/drop 时恢复原始样式 |
| BUG-012 | build.py 中文名 | 输出名改为 `BaibaoBOX` |
| BUG-013 | PNG quality 参数忽略 | 注释标注"PNG 为无损格式，quality 参数不生效" |
| INFO-001 | _safe_save 修改调用方 dict | 添加 `kwargs = dict(kwargs)` 防御性浅拷贝 |
| INFO-002 | 未使用的 import | 删除 `struct` / `tempfile` 导入 |
| INFO-003 | AdFetcher 僵尸代码 | 删除 `worker_threads.py` 中未被使用的 `AdFetcher` 类 |

---

## 变更统计

- **修改文件**: 15 个
- **新增代码行**: ~80 行（context manager、帧队列、导航信号等）
- **删除代码行**: ~70 行（Python 像素循环、AdFetcher、_find_stat_value 死代码等）
- **语法检查**: 15/15 全部通过
- **Bug 修复率**: 16/16 = 100%
