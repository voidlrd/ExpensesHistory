import pytest

import app_settings
from conftest import filled_products, png_bytes, wait_until
from receipt_ai import AIError
from receipt_inbox import add_receipt, list_receipts, remove_receipt
from ui.views.inbox_dialog import InboxDialog

JPEG = b"\xff\xd8 fake jpeg"
PNG = b"\x89PNG fake png"


# ---------- storage ----------

def test_a_receipt_keeps_its_photos_in_order(scratch_inbox):
    receipt = add_receipt([JPEG, PNG, JPEG])

    assert receipt.folder.parent == scratch_inbox
    assert [p.name for p in receipt.photos] == ["1.jpg", "2.png", "3.jpg"]
    assert receipt.photos[1].read_bytes() == PNG
    assert list_receipts() == [receipt]


def test_receipts_are_listed_in_arrival_order_even_within_a_second(scratch_inbox):
    added = [add_receipt([JPEG]) for _ in range(5)]

    assert list_receipts() == added


def test_receipts_still_arriving_or_empty_are_left_out(scratch_inbox):
    add_receipt([JPEG])
    (scratch_inbox / ".incoming-2026-11-13_10-00-00_abcdef").mkdir()
    (scratch_inbox / "2026-11-13_10-00-00_empty0").mkdir()

    assert len(list_receipts()) == 1


def test_remove_deletes_the_photos(scratch_inbox):
    receipt = add_receipt([JPEG])
    remove_receipt(receipt)
    remove_receipt(receipt)  # already gone: no error

    assert list_receipts() == []
    assert not receipt.folder.exists()


def test_an_empty_inbox_needs_no_folder(scratch_inbox):
    assert list_receipts() == []
    assert not scratch_inbox.exists()


# ---------- inbox window ----------

def test_the_window_lists_receipts_with_their_photo_count(qt_env):
    add_receipt([png_bytes(), png_bytes()])

    dialog = InboxDialog()

    assert dialog.list.count() == 1
    assert "2 photos" in dialog.list.item(0).text()
    assert dialog.scan_btn.isEnabled()


def test_an_empty_window_says_so(qt_env):
    dialog = InboxDialog()

    assert dialog.list.item(0).text() == "The inbox is empty."
    assert not dialog.scan_btn.isEnabled()
    assert not dialog.discard_btn.isEnabled()


def test_discard_after_confirming(qt_env, popups):
    add_receipt([png_bytes()])
    dialog = InboxDialog()

    dialog.discard_selected()

    assert list_receipts() == []
    assert dialog.list.item(0).text() == "The inbox is empty."


def test_picking_a_receipt_to_scan(qt_env):
    receipt = add_receipt([png_bytes()])
    dialog = InboxDialog()

    dialog.scan_selected()

    assert dialog.chosen == receipt


# ---------- New Transaction ----------

@pytest.fixture
def pick_first(monkeypatch):
    """The inbox window picks its first receipt instead of waiting for a click."""
    monkeypatch.setattr(InboxDialog, "exec", lambda self: self.scan_selected() or 1)


def test_the_inbox_button_shows_the_count(form):
    assert form.inbox_btn.text() == "Inbox (0)"
    assert not form.inbox_btn.isEnabled()

    add_receipt([png_bytes()])
    add_receipt([png_bytes()])
    form.load_reference_data()

    assert form.inbox_btn.text() == "Inbox (2)"
    assert form.inbox_btn.isEnabled()


def test_a_scanned_inbox_receipt_leaves_the_inbox_when_saved(form, asks, pick_first):
    app_settings.save_api_key("claude", "sk-ant-1")
    add_receipt([png_bytes(), png_bytes()])
    form.load_reference_data()

    form.open_inbox()
    assert not form.inbox_btn.isEnabled()  # no second scan while one runs
    wait_until(lambda: form.scan_ai_btn.text() == "Scan with AI…")
    assert filled_products(form) == ["Banane", "Paine"]
    assert len(asks.calls) == 1
    assert len(list_receipts()) == 1  # still waiting until saved

    form.save_transaction()

    assert list_receipts() == []
    assert "cleared from the inbox" in form.status_label.text()
    assert form.inbox_btn.text() == "Inbox (0)"


def test_a_failed_scan_keeps_the_receipt_in_the_inbox(form, asks, pick_first):
    app_settings.save_api_key("claude", "sk-ant-1")
    add_receipt([png_bytes()])
    asks.error = AIError("Claude is busy.")

    form.open_inbox()
    wait_until(lambda: "busy" in form.scan_summary.text())

    assert len(list_receipts()) == 1
    assert form.inbox_btn.isEnabled()


def test_a_manual_paste_afterwards_does_not_clear_the_inbox(form, asks, pick_first):
    from receipt_import import parse_scan
    from conftest import RECEIPT_REPLY

    app_settings.save_api_key("claude", "sk-ant-1")
    add_receipt([png_bytes()])
    form.open_inbox()
    wait_until(lambda: form.scan_ai_btn.text() == "Scan with AI…")

    form.apply_scan(parse_scan(RECEIPT_REPLY))  # Paste AI Result, replacing the form
    form.save_transaction()

    assert len(list_receipts()) == 1


def test_inbox_without_a_key_points_to_the_settings(form, asks, pick_first):
    add_receipt([png_bytes()])

    form.open_inbox()

    assert "Set up AI reading first" in form.scan_summary.text()
    assert asks.calls == []
