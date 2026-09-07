import logging
import sys
import traceback
from logging.handlers import RotatingFileHandler

from database.engine import BASE_DIR

LOG_DIR = BASE_DIR / "logs"
LOG_PATH = LOG_DIR / "expense_tracker.log"

log = logging.getLogger("expense_tracker")


def setup_logging():
    LOG_DIR.mkdir(exist_ok=True)

    handler = RotatingFileHandler(LOG_PATH, maxBytes=1_000_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-8s %(name)s: %(message)s"))

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    root.addHandler(handler)

    if sys.stderr is not None:
        root.addHandler(logging.StreamHandler(sys.stderr))

    return LOG_PATH


def install_excepthook():
    """Log uncaught exceptions and show them, instead of letting PyQt abort."""
    def hook(exc_type, exc_value, exc_tb):
        if issubclass(exc_type, KeyboardInterrupt):
            sys.__excepthook__(exc_type, exc_value, exc_tb)
            return

        logging.getLogger("expense_tracker").critical(
            "Unhandled exception", exc_info=(exc_type, exc_value, exc_tb)
        )

        details = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
        try:
            from PyQt6.QtWidgets import QApplication, QMessageBox
            if QApplication.instance() is None:
                return
            box = QMessageBox()
            box.setIcon(QMessageBox.Icon.Critical)
            box.setWindowTitle("Unexpected Error")
            box.setText(f"{exc_type.__name__}: {exc_value}")
            box.setInformativeText(f"The error was written to:\n{LOG_PATH}")
            box.setDetailedText(details)
            box.exec()
        except Exception:
            pass

    sys.excepthook = hook
