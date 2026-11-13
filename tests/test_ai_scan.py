import threading

import pytest
from PyQt6.QtWidgets import QFileDialog, QMessageBox

import app_settings
from conftest import filled_products, png_bytes, pump_events, wait_until
from receipt_ai import AIError, scan_receipt


# ---------- scan_receipt ----------

def test_scan_receipt_sends_prepared_jpegs_and_parses_the_answer(qapp, asks):
    scan = scan_receipt("claude", "key", "claude-sonnet-5-5", "Read this", [png_bytes()])

    assert scan.store == "Lidl"
    assert [i.name for i in scan.items] == ["Banane", "Paine"]
    (call,) = asks.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert all(image.startswith(b"\xff\xd8") for image in call["images"])


def test_an_unusable_answer_is_explained_and_logged(qapp, asks, caplog):
    asks.reply = "Sorry, I can't see a receipt in this picture."

    with pytest.raises(AIError, match="couldn't be read as a receipt"):
        scan_receipt("gemini", "key", "gemini-4-hydrogen", "p", [png_bytes()])
    assert "can't see a receipt" in caplog.text


# ---------- New Transaction ----------

@pytest.fixture
def photo(tmp_path, monkeypatch, qapp):
    path = tmp_path / "receipt.png"
    path.write_bytes(png_bytes())
    monkeypatch.setattr(QFileDialog, "getOpenFileNames", staticmethod(lambda *a, **k: ([str(path)], "")))
    return path


def test_scan_without_a_key_points_to_the_settings(form, asks, photo):
    form.scan_with_ai()

    assert "Set up AI reading first" in form.scan_summary.text()
    assert asks.calls == []


def test_scan_fills_the_form_for_review(form, asks, photo):
    app_settings.save_api_key("claude", "sk-ant-1")
    form.scan_details_input.setText("Paid 12.49 RON by card")

    form.scan_with_ai()
    assert form.scan_ai_btn.text() == "Cancel Scan"
    wait_until(lambda: form.scan_ai_btn.text() == "Scan with AI…")

    assert filled_products(form) == ["Banane", "Paine"]
    assert form.counterparty_input.currentText() == "Lidl"
    assert form.receipt_number_input.text() == "999111"
    assert "add up to 12.49" in form.scan_summary.text()
    (call,) = asks.calls
    assert call["model"] == "claude-sonnet-5-5"
    assert call["prompt"].endswith("Paid 12.49 RON by card")
    assert app_settings.app_settings().value("ai/photo_folder") == str(photo.parent)


def test_scan_uses_the_chosen_provider_and_model(form, asks, photo):
    app_settings.set_ai_provider("gemini")
    app_settings.set_ai_model("gemini", "gemini-4-argon")
    app_settings.save_api_key("gemini", "AIza-1")

    form.scan_with_ai()
    wait_until(lambda: asks.calls and form.scan_ai_btn.text() == "Scan with AI…")

    assert (asks.calls[0]["provider"], asks.calls[0]["model"]) == ("Gemini", "gemini-4-argon")


def test_scan_failure_is_shown_and_the_form_left_alone(form, asks, photo):
    app_settings.save_api_key("claude", "sk-ant-1")
    asks.error = AIError("Claude didn't accept the API key.")

    form.scan_with_ai()
    wait_until(lambda: "didn't accept" in form.scan_summary.text())

    assert filled_products(form) == [""]
    assert form.scan_ai_btn.text() == "Scan with AI…"


def test_cancelled_scan_ignores_the_late_answer(form, asks, photo):
    app_settings.save_api_key("claude", "sk-ant-1")
    asks.gate = threading.Event()

    form.scan_with_ai()
    wait_until(lambda: asks.calls)
    form.scan_with_ai()  # Cancel Scan
    assert "cancelled" in form.scan_summary.text()

    asks.gate.set()
    pump_events(0.5)  # let the late answer arrive

    assert filled_products(form) == [""]
    assert "cancelled" in form.scan_summary.text()


def test_cancelling_the_photo_picker_does_nothing(form, asks):
    app_settings.save_api_key("claude", "sk-ant-1")

    form.scan_with_ai()

    assert asks.calls == []
    assert form.scan_ai_btn.text() == "Scan with AI…"


def test_scan_keeps_existing_items_when_not_replacing(form, asks, photo, monkeypatch):
    from ui.views.new_transaction import COL_PRODUCT

    app_settings.save_api_key("claude", "sk-ant-1")
    form._cell(0, COL_PRODUCT).setCurrentText("Lapte")
    monkeypatch.setattr(QMessageBox, "question", staticmethod(lambda *a, **k: QMessageBox.StandardButton.No))

    form.scan_with_ai()

    assert asks.calls == []
    assert filled_products(form) == ["Lapte"]
