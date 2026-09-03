import sys
import os
from PyQt6.QtWidgets import QApplication
from database.engine import init_db, seed_initial_data
from ui.main_window import MainWindow

def _setup_working_directory():
    if getattr(sys, 'frozen', False):
        base_dir = os.path.dirname(sys.executable)
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    os.chdir(base_dir)

def main():
    _setup_working_directory()

    init_db()
    seed_initial_data()

    app = QApplication(sys.argv)
    app.setStyle("Fusion")

    window = MainWindow()
    window.show()

    sys.exit(app.exec())

if __name__ == "__main__":
    main()