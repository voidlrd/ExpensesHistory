import os
import sqlite3
import time
from contextlib import closing
from datetime import date

import pytest

from database import backup


@pytest.fixture
def backups_in(tmp_path, monkeypatch):
    monkeypatch.setattr(backup, "BACKUP_DIR", tmp_path / "backups")
    return tmp_path / "backups"


def test_create_backup_copies_the_database(db, backups_in, save_receipt):
    from conftest import item

    save_receipt(date(2026, 9, 14), "Lidl", [item("Punga", price="0.81")])
    path = backup.create_backup()

    assert path.exists()
    with closing(sqlite3.connect(path)) as copy:
        assert copy.execute("SELECT count(*) FROM transaction_record").fetchone()[0] == 1


def test_auto_backup_skips_when_nothing_changed(db, backups_in):
    first = backup.auto_backup()

    assert first is not None
    assert backup.auto_backup() is None


def test_auto_backup_keeps_only_the_newest_five(db, backups_in):
    from database.engine import DB_PATH

    an_hour_ago = time.time() - 3600
    for minute in range(7):
        path = _write(backups_in, f"{backup.AUTO_PREFIX}2026-09-14_10-0{minute}-00.db")
        os.utime(path, (an_hour_ago, an_hour_ago))
    assert len(backup.auto_backups()) == 7

    DB_PATH.touch()
    backup.auto_backup()

    assert len(backup.auto_backups()) == backup.KEEP_AUTO


def _write(folder, name):
    # closing(), not just connect(): an open handle would stop Windows deleting the file
    folder.mkdir(exist_ok=True)
    path = folder / name
    with closing(sqlite3.connect(path)) as conn:
        conn.execute("CREATE TABLE IF NOT EXISTS t (x int)")
    return path


def test_list_backups_labels_each_kind(db, backups_in):
    backup.create_backup()
    backup.create_backup(backup.AUTO_PREFIX)
    backup.create_backup(backup.PRE_RESTORE_PREFIX)

    kinds = {kind for _, kind, _, _ in backup.list_backups()}
    assert kinds == {"Manual", "Automatic", "Before restore"}


def test_restore_brings_back_the_older_data(db, backups_in, save_receipt):
    from conftest import item
    from repositories.transaction_repo import TransactionRepository

    save_receipt(date(2026, 9, 14), "Lidl", [item("Punga", price="0.81")])
    snapshot = backup.create_backup()

    save_receipt(date(2026, 9, 15), "Dabo", [item("Paine", price="3.50")])
    assert len(TransactionRepository.search_transactions()) == 2

    safety = backup.restore_backup(snapshot)

    assert safety is not None and safety.exists()
    assert len(TransactionRepository.search_transactions()) == 1


def test_restore_refuses_a_file_that_is_not_a_database(db, backups_in, tmp_path):
    junk = tmp_path / "not_a_db.db"
    junk.write_text("hello")

    with pytest.raises(ValueError, match="readable database"):
        backup.restore_backup(junk)


def test_restore_refuses_a_missing_file(db, backups_in, tmp_path):
    with pytest.raises(ValueError, match="no longer exists"):
        backup.restore_backup(tmp_path / "gone.db")
