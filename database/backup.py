import sqlite3
from contextlib import closing
from datetime import datetime

from .engine import BASE_DIR, DB_PATH

BACKUP_DIR = BASE_DIR / "backups"
MANUAL_PREFIX = "expense_tracker_"
AUTO_PREFIX = "auto_expense_tracker_"
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
