from __future__ import annotations
import sys
from pathlib import Path
from PySide6.QtCore import QLocale, QTranslator, QLibraryInfo
from PySide6.QtWidgets import QApplication
from batchrename.gui import MainWindow
from batchrename.theme import apply_theme


def main():
    QLocale.setDefault(QLocale("zh_CN"))
    app = QApplication(sys.argv)
    # Qt's own standard controls (file lists, etc.) use simplified Chinese
    # when qtbase_zh_CN.qm is shipped with the local PySide6 installation.
    translator = QTranslator(app)
    translations = [Path(QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath))]
    try:
        import PySide6
        translations.append(Path(PySide6.__file__).parent / "Qt" / "translations")
    except ImportError:
        pass
    for folder in translations:
        if translator.load("qtbase_zh_CN", str(folder)):
            app.installTranslator(translator)
            app._chinese_translator = translator
            break
    app.setApplicationName("批量文件重命名工具")
    apply_theme(app)
    window = MainWindow()
    window.show()
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
