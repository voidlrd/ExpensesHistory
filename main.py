import sys
import os
from PyQt6.QtWidgets import QApplication

def _setup_working_directory():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(base_dir)

def main():
    _setup_working_directory()

    from app_logging import setup_logging, install_excepthook, log
    log_path = setup_logging()
    install_excepthook()
    log.info("starting up; logging to %s", log_path)

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    try:
        from database.engine import init_db, seed_initial_data
        init_db()
        seed_initial_data()
    except Exception:
        log.exception("database initialisation failed")
        from PyQt6.QtWidgets import QMessageBox
        QMessageBox.critical(
            None, "Database Error",
            f"The database could not be prepared.\n\nSee {log_path} for details."
        )
        return 1

    from ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()

if __name__ == "__main__":
    sys.exit(main())
