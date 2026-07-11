"""
Emotion Annotator — entry point.
Run: python main.py
"""
import sys
import os

# Ensure local imports resolve correctly
sys.path.insert(0, os.path.dirname(__file__))

from PyQt5.QtWidgets import QApplication
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QIcon

from main_window import MainWindow

def get_asset_path(relative_path):
    """ Finds assets during development or inside the PyInstaller executable """
    try:
        # PyInstaller creates a temporary folder and stores its path in _MEIPASS
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(os.path.dirname(__file__))
    return os.path.join(base_path, relative_path)

def main():
    # High-DPI support
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    QApplication.setAttribute(Qt.AA_UseHighDpiPixmaps, True)

    app = QApplication(sys.argv)
    app.setApplicationName("Emotion Annotator")
    app.setOrganizationName("JUSense")

    # Set the window/taskbar icon using the helper function
    icon_path = get_asset_path("icon.ico")
    app.setWindowIcon(QIcon(icon_path))

    # global font
    font = QFont("Segoe UI", 10)
    app.setFont(font)

    win = MainWindow()
    win.showMaximized()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
