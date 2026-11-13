from PyQt6.QtCore import QObject, pyqtSignal

from app_settings import new_phone_token, phone_port, phone_token
from phone_server import PhoneServer, lan_address


class PhoneLink(QObject):
    """The app's phone page server; receipt_received fires on the UI thread for each upload."""
    receipt_received = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.server = None

    @property
    def running(self):
        return self.server is not None

    def start(self):
        """(Re)start with the saved port and token; raises OSError when the port can't be used."""
        self.stop()
        self.server = PhoneServer(phone_port(), phone_token(), self.receipt_received.emit)

    def stop(self):
        if self.server is not None:
            self.server.stop()
            self.server = None

    def renew_token(self):
        new_phone_token()
        if self.running:
            self.start()

    def url(self):
        port = self.server.port if self.server else phone_port()
        return f"http://{lan_address()}:{port}/{phone_token()}"
