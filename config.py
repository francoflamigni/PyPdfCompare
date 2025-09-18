from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel,
    QCheckBox, QGroupBox, QSpinBox, QComboBox, QMessageBox, QProgressBar, QTabWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import (QFont, QTextCharFormat, QColor, QPixmap, QPainter,
                         QTextCursor, QTextDocument, QSyntaxHighlighter, QTextFormat)

class ConfigWidget(QWidget):
    """Widget per le configurazioni del confronto"""

    def __init__(self):
        super().__init__()
        self.setup_ui()

    def setup_ui(self):
        layout = QVBoxLayout()

        # Gruppo opzioni testo
        text_group = QGroupBox("Opzioni Testo")
        text_layout = QVBoxLayout()

        self.ignore_case_cb = QCheckBox("Ignora maiuscole/minuscole")
        self.normalize_spaces_cb = QCheckBox("Normalizza spazi multipli")
        self.normalize_spaces_cb.setChecked(True)

        text_layout.addWidget(self.ignore_case_cb)
        text_layout.addWidget(self.normalize_spaces_cb)
        text_group.setLayout(text_layout)

        # Gruppo opzioni pagina
        page_group = QGroupBox("Opzioni Pagina")
        page_layout = QVBoxLayout()

        self.ignore_page_numbers_cb = QCheckBox("Ignora numeri di pagina")
        self.ignore_special_chars_cb = QCheckBox("Ignora linee con solo caratteri speciali")

        # Numero di linee per header/footer
        first_page_layout = QHBoxLayout()
        first_page_layout.addWidget(QLabel("Inizia a Pagina:"))
        self.first_page_spin = QSpinBox()
        self.first_page_spin.setRange(1, 1)
        self.first_page_spin.setValue(1)
        first_page_layout.addWidget(self.first_page_spin)
        first_page_layout.addStretch()

        last_page_layout = QHBoxLayout()
        last_page_layout.addWidget(QLabel("Termina a pagina:"))
        self.last_page_spin = QSpinBox()
        self.last_page_spin.setRange(1, 1)
        self.last_page_spin.setValue(1)
        last_page_layout.addWidget(self.last_page_spin)
        last_page_layout.addStretch()

        page_layout.addLayout(first_page_layout)
        page_layout.addLayout(last_page_layout)
        page_layout.addWidget(self.ignore_page_numbers_cb)
        page_layout.addWidget(self.ignore_special_chars_cb)
        page_group.setLayout(page_layout)

        # Gruppo opzioni visualizzazione
        display_group = QGroupBox("Opzioni Visualizzazione")
        display_layout = QVBoxLayout()

        self.show_pdf_cb = QCheckBox("Mostra rendering PDF")
        self.show_pdf_cb.setChecked(True)
        self.highlight_diffs_cb = QCheckBox("Evidenzia differenze nel testo")
        self.highlight_diffs_cb.setChecked(True)
        self.sync_navigation_cb = QCheckBox("Sincronizza navigazione PDF")
        self.sync_navigation_cb.setChecked(True)

        display_layout.addWidget(self.show_pdf_cb)
        display_layout.addWidget(self.highlight_diffs_cb)
        display_layout.addWidget(self.sync_navigation_cb)
        display_group.setLayout(display_layout)

        layout.addWidget(text_group)
        layout.addWidget(page_group)
        layout.addWidget(display_group)
        layout.addStretch()

        self.setLayout(layout)

    def get_config(self) -> dict:
        """Restituisce la configurazione corrente"""
        return {
            'ignore_case': self.ignore_case_cb.isChecked(),
            'normalize_spaces': self.normalize_spaces_cb.isChecked(),
            'ignore_page_numbers': self.ignore_page_numbers_cb.isChecked(),
            'ignore_special_chars': self.ignore_special_chars_cb.isChecked(),
            'header_lines': self.first_page_spin.value(),
            'footer_lines': self.last_page_spin.value(),
            'show_pdf': self.show_pdf_cb.isChecked(),
            'highlight_diffs': self.highlight_diffs_cb.isChecked(),
            'sync_navigation': self.sync_navigation_cb.isChecked()
        }

    def sync_page_limits(self, first=1, last=-1):
        self.first_page_spin.setRange(first, last)
        self.last_page_spin.setRange(first, last)
        self.first_page_spin.setValue(first)
        self.last_page_spin.setValue(last)
