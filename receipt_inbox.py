import shutil
import uuid
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from database.engine import BASE_DIR

# receipts waiting to be read: one folder of photos each
INBOX_DIR = BASE_DIR / "inbox"
STAMP = "%Y-%m-%d_%H-%M-%S"
INCOMING = ".incoming-"


@dataclass
class InboxReceipt:
    folder: Path
    received: datetime
    photos: list


def _extension(data):
    if data.startswith(b"\xff\xd8"):
        return ".jpg"
    if data.startswith(b"\x89PNG"):
        return ".png"
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return ".webp"
    return ".img"


def _photo_order(path):
    return int(path.stem) if path.stem.isdigit() else 0, path.name


def add_receipt(photos):
    """Store one receipt's photos (bytes, top to bottom); it appears in the list only once complete."""
    INBOX_DIR.mkdir(exist_ok=True)
    # sorting the names sorts by arrival
    now = datetime.now()
    name = f"{now:{STAMP}}_{now:%f}_{uuid.uuid4().hex[:6]}"
    incoming = INBOX_DIR / (INCOMING + name)
    incoming.mkdir()
    for number, data in enumerate(photos, start=1):
        (incoming / f"{number}{_extension(data)}").write_bytes(data)
    folder = incoming.rename(INBOX_DIR / name)
    return _read(folder)


def _read(folder):
    try:
        received = datetime.strptime(folder.name[:19], STAMP)
    except ValueError:
        received = datetime.fromtimestamp(folder.stat().st_mtime)
    photos = sorted((p for p in folder.iterdir() if p.is_file()), key=_photo_order)
    return InboxReceipt(folder, received, photos)


def list_receipts():
    """Waiting receipts, oldest first; folders still being written are left out."""
    if not INBOX_DIR.exists():
        return []
    receipts = [_read(f) for f in INBOX_DIR.iterdir() if f.is_dir() and not f.name.startswith(".")]
    return sorted((r for r in receipts if r.photos), key=lambda r: r.folder.name)


def remove_receipt(receipt):
    shutil.rmtree(receipt.folder, ignore_errors=True)
