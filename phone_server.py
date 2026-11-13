import hmac
import json
import logging
import socket
import struct
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from phone_page import PAGE
from receipt_inbox import add_receipt, picture_extension

log = logging.getLogger("expense_tracker")

MAX_PHOTOS = 10
MAX_UPLOAD = 100 * 1024 * 1024
# every network the computer is on, so the phone can reach it
LISTEN_ADDRESS = "0.0.0.0"


def lan_address():
    """This computer's address on the local network (no packet is sent)."""
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as probe:
        try:
            probe.connect(("10.255.255.255", 1))
            return probe.getsockname()[0]
        except OSError:
            return "127.0.0.1"


def unpack_photos(body):
    """Split an upload of [4-byte big-endian length][photo bytes]... into photos."""
    photos, offset = [], 0
    while offset < len(body):
        if offset + 4 > len(body):
            raise ValueError("The upload was cut off. Try sending again.")
        (size,) = struct.unpack_from(">I", body, offset)
        photo = body[offset + 4:offset + 4 + size]
        if len(photo) != size:
            raise ValueError("The upload was cut off. Try sending again.")
        if photo[4:8] == b"ftyp":
            raise ValueError("HEIC photos can't be read yet. Turn off \"high efficiency\" pictures in the "
                             "camera settings, or send a screenshot of the photo.")
        if picture_extension(photo) is None:
            raise ValueError("Only photos (JPEG, PNG or WebP) can be sent.")
        photos.append(photo)
        offset += 4 + size
    if not photos:
        raise ValueError("No photos were sent.")
    if len(photos) > MAX_PHOTOS:
        raise ValueError(f"Send at most {MAX_PHOTOS} photos per receipt.")
    return photos


class _Handler(BaseHTTPRequestHandler):
    server_version = "ExpensesHistory"

    def _authorised(self, path):
        return hmac.compare_digest(path, "/" + self.server.token)

    def _reply(self, status, body, content_type):
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status, payload):
        self._reply(status, json.dumps(payload).encode(), "application/json")

    def do_GET(self):
        if not self._authorised(self.path.rstrip("/")):
            self._reply(404, b"Not found", "text/plain")
            return
        self._reply(200, PAGE.encode(), "text/html; charset=utf-8")

    def do_POST(self):
        path = self.path.rstrip("/")
        if not path.endswith("/receipt") or not self._authorised(path.removesuffix("/receipt")):
            self._json(404, {"error": "This link no longer works. Scan the code in the app again."})
            return

        length = int(self.headers.get("Content-Length") or 0)
        if length > MAX_UPLOAD:
            self.close_connection = True
            self._json(413, {"error": "These photos are too large to send together."})
            return
        try:
            photos = unpack_photos(self.rfile.read(length))
        except ValueError as e:
            self._json(400, {"error": str(e)})
            return

        try:
            add_receipt(photos)
        except OSError:
            log.exception("couldn't store a receipt from the phone")
            self._json(500, {"error": "The computer couldn't save the photos. Check its free disk space."})
            return
        log.info("received a receipt with %d photo(s) from %s", len(photos), self.client_address[0])
        self.server.on_receipt()
        self._json(200, {"ok": True, "photos": len(photos)})

    def log_message(self, format, *args):
        # the packaged app has no console to print to
        log.debug("phone: " + format, *args)


class _Server(ThreadingHTTPServer):
    daemon_threads = True
    # on Windows this would let a second program take the same port
    allow_reuse_address = False


class PhoneServer:
    """Serves the phone page and puts uploaded receipts in the inbox, on its own thread."""

    def __init__(self, port, token, on_receipt):
        self.httpd = _Server((LISTEN_ADDRESS, port), _Handler)
        self.httpd.token = token
        self.httpd.on_receipt = on_receipt
        threading.Thread(target=self.httpd.serve_forever, daemon=True).start()

    @property
    def port(self):
        return self.httpd.server_address[1]

    def stop(self):
        self.httpd.shutdown()
        self.httpd.server_close()
