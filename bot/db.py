
import os, sqlite3
from contextlib import closing
from .config import get_config

cfg = get_config()
DB_PATH = os.path.join(cfg.data_dir, "bot.db")

def _table_exists(con, name: str) -> bool:
    try:
        return con.execute("SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)).fetchone() is not None
    except Exception:
        return False

def _col_names(con, table: str):
    try:
        return [r[1] for r in con.execute(f"PRAGMA table_info({table})").fetchall()]
    except Exception:
        return []

def init_db():
    os.makedirs(cfg.data_dir, exist_ok=True)
    with closing(sqlite3.connect(DB_PATH)) as con:
        # базовые PRAGMA
        try:
            con.execute("PRAGMA journal_mode=WAL")
            con.execute("PRAGMA foreign_keys=ON")
        except Exception:
            pass

        # ---- pre-migration: добавим недостающие колонки, если база уже существовала ----
        if _table_exists(con, "feeds"):
            cols = _col_names(con, "feeds")
            if "etag" not in cols:
                try: con.execute("ALTER TABLE feeds ADD COLUMN etag TEXT")
                except Exception: pass
            if "last_modified" not in cols:
                try: con.execute("ALTER TABLE feeds ADD COLUMN last_modified TEXT")
                except Exception: pass

        if _table_exists(con, "feed_entries"):
            cols = _col_names(con, "feed_entries")
            if "hash" not in cols:
                # используется в уникальном индексе uq_feed_entries_hash
                try: con.execute("ALTER TABLE feed_entries ADD COLUMN hash TEXT")
                except Exception: pass

        if _table_exists(con, "drafts"):
            cols = _col_names(con, "drafts")
            if "hash" not in cols:
                try: con.execute("ALTER TABLE drafts ADD COLUMN hash TEXT")
                except Exception: pass
            if "media_url" not in cols:
                try: con.execute("ALTER TABLE drafts ADD COLUMN media_url TEXT")
                except Exception: pass
            if "source_url" not in cols:
                try: con.execute("ALTER TABLE drafts ADD COLUMN source_url TEXT")
                except Exception: pass

        if _table_exists(con, "draft_meta"):
            cols = _col_names(con, "draft_meta")
            if "hash" not in cols:
                try: con.execute("ALTER TABLE draft_meta ADD COLUMN hash TEXT")
                except Exception: pass
            if "media_url" not in cols:
                try: con.execute("ALTER TABLE draft_meta ADD COLUMN media_url TEXT")
                except Exception: pass

        # ---- основная схема ----
        models_path = os.path.join(os.path.dirname(__file__), "models.sql")
        with open(models_path, "r", encoding="utf-8") as f:
            con.executescript(f.read())
        con.commit()

def execute(sql: str, params: tuple = ()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        con.commit()
        return cur

def fetchone(sql: str, params: tuple = ()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        return cur.fetchone()

def fetchall(sql: str, params: tuple = ()):
    with closing(sqlite3.connect(DB_PATH)) as con:
        cur = con.execute(sql, params)
        return cur.fetchall()

def get_setting(key: str):
    row = fetchone("SELECT value FROM settings WHERE key=?", (key,))
    return row[0] if row else None

def set_setting(key: str, value: str):
    execute(
        "INSERT INTO settings(key,value) VALUES(?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value",
        (key, value)
    )
