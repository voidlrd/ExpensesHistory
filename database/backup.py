import sqlite3
from contextlib import closing
from datetime import datetime
from pathlib import Path

from .engine import BASE_DIR, DB_PATH, engine

BACKUP_DIR = BASE_DIR / "backups"
MANUAL_PREFIX = "expense_tracker_"
AUTO_PREFIX = "auto_expense_tracker_"
PRE_RESTORE_PREFIX = "before_restore_"
KEEP_AUTO = 5


def create_backup(prefix=MANUAL_PREFIX):
    BACKUP_DIR.mkdir(exist_ok=True)
    path = BACKUP_DIR / f"{prefix}{datetime.now():%Y-%m-%d_%H-%M-%S}.db"
    with closing(sqlite3.connect(DB_PATH)) as src, closing(sqlite3.connect(path)) as dst:
        src.backup(dst)
    return path


def auto_backups():
    return sorted(BACKUP_DIR.glob(AUTO_PREFIX + "*.db")) if BACKUP_DIR.exists() else []


def auto_backup():
    """Back up the database if it changed since the newest automatic backup, keeping the newest KEEP_AUTO."""
    if not DB_PATH.exists():
        return None
    existing = auto_backups()
    if existing and existing[-1].stat().st_mtime >= DB_PATH.stat().st_mtime:
        return None

    path = create_backup(AUTO_PREFIX)
    for old in auto_backups()[:-KEEP_AUTO]:
        old.unlink()
    return path


def describe_kind(name):
    if name.startswith(AUTO_PREFIX):
        return "Automatic"
    if name.startswith(PRE_RESTORE_PREFIX):
        return "Before restore"
    return "Manual"


def list_backups():
    """(path, kind, when, size in bytes) for every backup, newest first."""
    if not BACKUP_DIR.exists():
        return []
    entries = []
    for path in BACKUP_DIR.glob("*.db"):
        stat = path.stat()
        entries.append((path, describe_kind(path.name), datetime.fromtimestamp(stat.st_mtime), stat.st_size))
    return sorted(entries, key=lambda entry: entry[2], reverse=True)


def restore_backup(path):
    """Replace the live database with a backup, keeping a copy of what it replaces; returns that copy."""
    path = Path(path)
    if not path.exists():
        raise ValueError("That backup file no longer exists.")

    try:
        with closing(sqlite3.connect(f"file:{path}?mode=ro", uri=True)) as probe:
            probe.execute("SELECT count(*) FROM sqlite_master").fetchone()
    except sqlite3.DatabaseError:
        raise ValueError("That file isn't a readable database, so nothing was changed.") from None

    safety = create_backup(PRE_RESTORE_PREFIX) if DB_PATH.exists() else None
    engine.dispose()
    with closing(sqlite3.connect(path)) as src, closing(sqlite3.connect(DB_PATH)) as dst:
        src.backup(dst)
    return safety
