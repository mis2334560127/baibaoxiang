"""
百宝箱 数据库模块
使用 SQLite 存储操作历史记录和广告缓存。
"""
import sqlite3
import os
from datetime import datetime
from pathlib import Path
from contextlib import contextmanager

# 数据目录：与 config.py 保持一致，使用 %APPDATA%/BaibaoBOX
DB_FILE = Path(os.path.expandvars("%APPDATA%")) / "BaibaoBOX" / "baibaobox.db"

# ---- SQL 建表 ----
SCHEMA = """
CREATE TABLE IF NOT EXISTS compress_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name   TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    orig_size_kb REAL NOT NULL,
    final_size_kb REAL NOT NULL,
    quality     INTEGER,
    mode        TEXT    DEFAULT 'size',
    status      TEXT    DEFAULT 'success',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS convert_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name   TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    orig_pages  INTEGER,
    status      TEXT    DEFAULT 'success',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS record_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name   TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    duration_sec INTEGER,
    file_size_mb REAL,
    status      TEXT    DEFAULT 'success',
    created_at  TEXT    NOT NULL
);

CREATE TABLE IF NOT EXISTS ad_cache (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    ad_id       TEXT    UNIQUE NOT NULL,
    title       TEXT,
    image_url   TEXT,
    link_url    TEXT,
    position    TEXT    DEFAULT 'top',
    active      INTEGER DEFAULT 1,
    fetched_at  TEXT,
    expires_at  TEXT
);

CREATE TABLE IF NOT EXISTS ocr_history (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    file_name   TEXT    NOT NULL,
    file_path   TEXT    NOT NULL,
    text_length INTEGER,
    text_preview TEXT,
    lang        TEXT    DEFAULT 'chi_sim+eng',
    status      TEXT    DEFAULT 'success',
    created_at  TEXT    NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_compress_ts ON compress_history(created_at);
CREATE INDEX IF NOT EXISTS idx_convert_ts  ON convert_history(created_at);
CREATE INDEX IF NOT EXISTS idx_record_ts   ON record_history(created_at);
CREATE INDEX IF NOT EXISTS idx_ocr_ts      ON ocr_history(created_at);
"""


def get_db() -> sqlite3.Connection:
    """获取数据库连接（自动建表）"""
    os.makedirs(DB_FILE.parent, exist_ok=True)
    conn = sqlite3.connect(str(DB_FILE))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript(SCHEMA)
    conn.commit()
    return conn


@contextmanager
def db_session():
    """数据库连接上下文管理器：自动 commit/close"""
    conn = get_db()
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


# ---- 操作日志写入 ----

def log_compress(file_name: str, file_path: str, orig_kb: float,
                 final_kb: float, quality: int, mode: str, status: str = "success"):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO compress_history (file_name,file_path,orig_size_kb,final_size_kb,quality,mode,status,created_at) "
            "VALUES (?,?,?,?,?,?,?,?)",
            (file_name, file_path, round(orig_kb, 1), round(final_kb, 1),
             quality, mode, status, datetime.now().isoformat())
        )


def log_convert(file_name: str, file_path: str, orig_pages: int,
                status: str = "success"):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO convert_history (file_name,file_path,orig_pages,status,created_at) "
            "VALUES (?,?,?,?,?)",
            (file_name, file_path, orig_pages, status, datetime.now().isoformat())
        )


def log_record(file_name: str, file_path: str, duration_sec: int,
               file_size_mb: float, status: str = "success"):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO record_history (file_name,file_path,duration_sec,file_size_mb,status,created_at) "
            "VALUES (?,?,?,?,?,?)",
            (file_name, file_path, duration_sec, round(file_size_mb, 1),
             status, datetime.now().isoformat())
        )


def log_ocr(file_name: str, file_path: str, text_length: int,
            text_preview: str = "", lang: str = "chi_sim+eng",
            status: str = "success"):
    with db_session() as conn:
        conn.execute(
            "INSERT INTO ocr_history (file_name,file_path,text_length,text_preview,lang,status,created_at) "
            "VALUES (?,?,?,?,?,?,?)",
            (file_name, file_path, text_length, text_preview[:100],
             lang, status, datetime.now().isoformat())
        )


# ---- 查询接口 ----

def get_recent_compress(limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM compress_history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_convert(limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM convert_history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_records(limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM record_history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_recent_ocr(limit: int = 20) -> list[dict]:
    with db_session() as conn:
        rows = conn.execute(
            "SELECT * FROM ocr_history ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
    return [dict(r) for r in rows]


def get_summary_stats() -> dict:
    """首页统计：总处理文件数、节省空间等"""
    with db_session() as conn:
        total_compress = conn.execute("SELECT COUNT(*) as n FROM compress_history WHERE status='success'").fetchone()["n"]
        total_convert = conn.execute("SELECT COUNT(*) as n FROM convert_history WHERE status='success'").fetchone()["n"]
        total_record = conn.execute("SELECT COUNT(*) as n FROM record_history WHERE status='success'").fetchone()["n"]
        total_ocr = conn.execute("SELECT COUNT(*) as n FROM ocr_history WHERE status='success'").fetchone()["n"]
        row = conn.execute(
            "SELECT SUM(orig_size_kb) as orig, SUM(final_size_kb) as final FROM compress_history WHERE status='success'"
        ).fetchone()
    saved_kb = (row["orig"] or 0) - (row["final"] or 0)
    return {
        "total_compress": total_compress,
        "total_convert": total_convert,
        "total_record": total_record,
        "total_ocr": total_ocr,
        "saved_mb": round(saved_kb / 1024, 1),
    }
