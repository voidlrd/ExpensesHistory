import json
import socket
import struct
import urllib.error
import urllib.request

import pytest

import app_settings
from conftest import png_bytes, wait_until
from phone_server import MAX_PHOTOS, PhoneServer, lan_address, unpack_photos
from receipt_inbox import list_receipts

JPEG = b"\xff\xd8 fake jpeg"
HEIC = b"\x00\x00\x00\x18ftypheic...."
NO_PROXY = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def pack(*photos):
    return b"".join(struct.pack(">I", len(p)) + p for p in photos)


def fetch(url, data=None):
    """(status, body) for a GET, or a POST when data is given."""
    request = urllib.request.Request(url, data=data, method="GET" if data is None else "POST")
    try:
        with NO_PROXY.open(request, timeout=5) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as e:
        return e.code, e.read()


def free_port():
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        return probe.getsockname()[1]


def local_url(port, token):
    return f"http://127.0.0.1:{port}/{token}"


# ---------- upload format ----------

def test_unpack_photos_splits_the_upload():
    assert unpack_photos(pack(JPEG, b"\x89PNG x")) == [JPEG, b"\x89PNG x"]


@pytest.mark.parametrize("body, message", [
    (b"", "No photos"),
    (pack(JPEG)[:-2], "cut off"),
    (pack(JPEG) + b"\x00\x00", "cut off"),
    (pack(b"%PDF-1.7"), "Only photos"),
    (pack(HEIC), "HEIC photos can't be read"),
    (pack(*[JPEG] * (MAX_PHOTOS + 1)), f"at most {MAX_PHOTOS}"),
])
def test_bad_uploads_are_explained(body, message):
    with pytest.raises(ValueError, match=message):
        unpack_photos(body)


def test_lan_address_looks_like_an_ip():
    assert len(lan_address().split(".")) == 4


# ---------- server ----------

@pytest.fixture
def server():
    received = []
    server = PhoneServer(0, "secret-token", lambda: received.append(1))
    server.received = received
    yield server
    server.stop()


def test_the_page_needs_the_token(server):
    status, body = fetch(local_url(server.port, "secret-token"))
    assert status == 200
    assert b"Send a receipt" in body

    assert fetch(local_url(server.port, "secret-token/"))[0] == 200
    assert fetch(local_url(server.port, "wrong"))[0] == 404
    assert fetch(f"http://127.0.0.1:{server.port}/")[0] == 404


def test_an_upload_lands_in_the_inbox(server):
    status, body = fetch(local_url(server.port, "secret-token") + "/receipt", pack(JPEG, JPEG))

    assert status == 200
    assert json.loads(body) == {"ok": True, "photos": 2}
    (receipt,) = list_receipts()
    assert [p.read_bytes() for p in receipt.photos] == [JPEG, JPEG]
    assert server.received == [1]


def test_a_bad_upload_gets_a_readable_error(server):
    status, body = fetch(local_url(server.port, "secret-token") + "/receipt", pack(HEIC))

    assert status == 400
    assert "HEIC" in json.loads(body)["error"]
    assert list_receipts() == []
    assert server.received == []


def test_an_upload_with_the_wrong_token_is_refused(server):
    status, body = fetch(local_url(server.port, "wrong") + "/receipt", pack(JPEG))

    assert status == 404
    assert "no longer works" in json.loads(body)["error"]
    assert list_receipts() == []


def test_a_stopped_server_frees_its_port():
    port = free_port()
    PhoneServer(port, "t", lambda: None).stop()
    PhoneServer(port, "t", lambda: None).stop()


# ---------- AI & Phone tab ----------

@pytest.fixture
def panel(qt_env):
    from ui.views.ai_panel import AIPanel

    app_settings.set_phone_port(free_port())
    panel = AIPanel()
    yield panel
    panel.phone_link.stop()


def test_receiving_starts_and_shows_the_link(panel):
    assert not panel.phone_link.running
    assert panel.phone_details.isHidden()

    panel.phone_toggle.setChecked(True)

    assert panel.phone_link.running
    assert app_settings.phone_enabled()
    assert not panel.phone_details.isHidden()
    token = app_settings.phone_token()
    assert panel.url_label.text().endswith(f":{app_settings.phone_port()}/{token}")
    assert not panel.qr_label.pixmap().isNull()
    assert fetch(local_url(app_settings.phone_port(), token))[0] == 200


def test_receiving_stops_when_switched_off(panel):
    panel.phone_toggle.setChecked(True)
    port = app_settings.phone_port()

    panel.phone_toggle.setChecked(False)

    assert not panel.phone_link.running
    assert not app_settings.phone_enabled()
    with pytest.raises(urllib.error.URLError):
        NO_PROXY.open(local_url(port, app_settings.phone_token()), timeout=2)


def test_a_busy_port_is_explained(panel):
    with socket.socket() as other_program:
        other_program.bind(("127.0.0.1", app_settings.phone_port()))
        other_program.listen()

        panel.phone_toggle.setChecked(True)

    assert not panel.phone_link.running
    assert not panel.phone_toggle.isChecked()
    assert "pick another port" in panel.phone_status.text()


def test_a_new_link_retires_the_old_one(panel):
    panel.phone_toggle.setChecked(True)
    port, old = app_settings.phone_port(), app_settings.phone_token()

    panel.renew_link()

    new = app_settings.phone_token()
    assert new != old
    assert fetch(local_url(port, old))[0] == 404
    assert fetch(local_url(port, new))[0] == 200
    assert panel.url_label.text().endswith(new)


def test_changing_the_port_moves_the_server(panel):
    panel.phone_toggle.setChecked(True)
    port = free_port()

    panel.port_input.setValue(port)
    panel.on_port_changed()

    assert app_settings.phone_port() == port
    assert fetch(local_url(port, app_settings.phone_token()))[0] == 200


def test_the_token_survives_a_restart(qt_env):
    assert app_settings.phone_token() == app_settings.phone_token()


# ---------- whole app ----------

def test_a_receipt_from_the_phone_shows_up_in_the_inbox_right_away(qt_env):
    from ui.main_window import MainWindow

    app_settings.set_phone_port(free_port())
    app_settings.set_phone_enabled(True)
    window = MainWindow()
    try:
        assert window.phone_link.running
        assert window.data_manager_tab.ai_panel.phone_toggle.isChecked()
        assert window.new_transaction_tab.inbox_btn.text() == "Inbox (0)"

        url = local_url(app_settings.phone_port(), app_settings.phone_token())
        assert fetch(url + "/receipt", pack(png_bytes()))[0] == 200

        wait_until(lambda: window.new_transaction_tab.inbox_btn.text() == "Inbox (1)")
    finally:
        window.close()
    assert not window.phone_link.running
