import os
from PyQt6.QtCore import pyqtSignal, Qt
from PyQt6.QtGui import QFont
from PyQt6.QtWidgets import QWidget, QVBoxLayout, QHBoxLayout, QPushButton, QLabel, QSplitter, QFrame

from pdf_viewer import PDFViewer
from txt_viewer import CustomTextEdit


class PdfTxtViewer(QWidget):
    clicEvent = pyqtSignal(str, int, int, int)
    """Widget avanzato per visualizzare le differenze con PDF rendering e allineamento"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()
        self.current_differences = []
        self.current_page_index = 0

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # Controlli di navigazione per le differenze

        # Splitter principale per PDF e testo
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        pdf_widget = QFrame()
        pdf_widget.setFrameStyle(QFrame.Shape.Box)
        pdf_layout = QVBoxLayout()
        pdf_widget.setLayout(pdf_layout)

        self.pdf_viewer = PDFViewer()
        self.pdf_viewer.mouse_click.connect(self.pdf_clicked)
        self.pdf_label = QLabel("PDF")
        self.pdf_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout.addWidget(self.pdf_label)
        pdf_layout.addWidget(self.pdf_viewer)

        # Area testo (parte inferiore)
        text_widget = QFrame()
        text_widget.setFrameStyle(QFrame.Shape.Box)
        text_layout = QVBoxLayout()
        text_widget.setLayout(text_layout)

        self.text_label = QLabel("Testo PDF")
        self.text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.text_viewer = CustomTextEdit()

        self.text_viewer.lineClicked.connect(self.text_clicked)
        self.text_viewer.setReadOnly(True)
        self.text_viewer.setFont(QFont("Courier", 10))  # Font monospace
        text_layout.addWidget(self.text_label)
        text_layout.addWidget(self.text_viewer)

        # Aggiungi al main splitter
        main_splitter.addWidget(pdf_widget)
        main_splitter.addWidget(text_widget)
        main_splitter.setStretchFactor(0, 2)  # PDF area più grande
        main_splitter.setStretchFactor(1, 1)  # Text area più piccola

        main_layout.addWidget(main_splitter)
        self.setLayout(main_layout)

        # Sincronizza scroll di default
        self.setup_scroll_sync()

    def text_clicked(self, line):
        self.clicEvent.emit('1', line, 0, 0)

    def pdf_clicked(self, x, y, page):
        self.clicEvent.emit('2', x, y, page)

    def highlight_pdf(self, page, bbox, color):
        self.pdf_viewer.highlight_text_line(page, bbox, color)

    def highlight_txt(self, line):
        self.text_viewer.highlight_and_scroll_to_line(line)

    def show_pdf(self, pdf):
        self.pdf_viewer.load_pdf(pdf)
        basename = os.path.basename(pdf)
        self.pdf_label.setText(os.path.basename(pdf))


    def setup_scroll_sync(self):
        """Configura la sincronizzazione dello scroll"""
        '''
        left_scroll = self.left_text.verticalScrollBar()
        right_scroll = self.right_text.verticalScrollBar()

        self.left_scroll_connection = left_scroll.valueChanged.connect(
            lambda v: right_scroll.setValue(v) if self.sync_scroll_cb.isChecked() else None
        )
        self.right_scroll_connection = right_scroll.valueChanged.connect(
            lambda v: left_scroll.setValue(v) if self.sync_scroll_cb.isChecked() else None
        )
        '''

    def clear_txt(self):
        self.text_viewer.clear()

    def print_txt(self, txt):
        self.text_viewer.append(txt)

    def toggle_sync_scroll(self, enabled: bool):
        """Attiva/disattiva la sincronizzazione dello scroll"""
        # La sincronizzazione è già gestita nel setup_scroll_sync
        pass

    '''
    def show_differences(self, differences: List[dict], pdf1_path: str, pdf2_path: str):
        """Mostra le differenze nei widget"""
        self.current_differences = differences
        self.current_page_index = 0

        # Carica i PDF nei viewer
        self.pdf_viewer1.load_pdf(pdf1_path)
        self.pdf_viewer2.load_pdf(pdf2_path)

        # Aggiorna le etichette
        pdf1_name = os.path.basename(pdf1_path)
        pdf2_name = os.path.basename(pdf2_path)
        self.pdf_label1.setText(f"PDF 1: {pdf1_name}")
        self.pdf_label2.setText(f"PDF 2: {pdf2_name}")
        self.left_text_label.setText(f"Testo PDF 1: {pdf1_name} (Allineato)")
        self.right_text_label.setText(f"Testo PDF 2: {pdf2_name} (Allineato)")

        if not differences:
            self.left_text.setPlainText("I file sono identici secondo la configurazione specificata.")
            self.right_text.setPlainText("I file sono identici secondo la configurazione specificata.")
            self.diff_label.setText("Nessuna differenza trovata")
            self.prev_diff_btn.setEnabled(False)
            self.next_diff_btn.setEnabled(False)
        else:
            self.update_difference_display()
            self.update_navigation()
    '''

    def update_difference_display(self):
        """Aggiorna la visualizzazione della differenza corrente"""
        if not self.current_differences:
            return

        diff = self.current_differences[self.current_page_index]
        page_num = diff['page']

        # Aggiorna i viewer PDF alla pagina corrente
        self.pdf_viewer1.set_page(page_num - 1)
        self.pdf_viewer2.set_page(page_num - 1)

        # Mostra il testo allineato con evidenziazione
        left_text = '\n'.join(diff['aligned_lines1'])
        right_text = '\n'.join(diff['aligned_lines2'])

        self.left_text.setPlainText(left_text)
        self.right_text.setPlainText(right_text)

        # Applica evidenziazione delle differenze
        self.highlight_differences(diff)

    def highlight_differences(self, diff: dict):
        """Evidenzia le differenze nel testo"""
        # Evidenziazione per il pannello sinistro
        left_cursor = self.left_text.textCursor()
        left_cursor.select(QTextCursor.SelectionType.Document)
        left_cursor.setCharFormat(QTextCharFormat())  # Reset formato

        # Evidenziazione per il pannello destro
        right_cursor = self.right_text.textCursor()
        right_cursor.select(QTextCursor.SelectionType.Document)
        right_cursor.setCharFormat(QTextCharFormat())  # Reset formato

        # Applica evidenziazione per ogni blocco di differenze
        for block in diff.get('diff_blocks', []):
            if block.block_type == 'equal':
                continue

            # Formato di evidenziazione
            format = QTextCharFormat()
            if block.block_type == 'delete':
                format.setBackground(QColor(255, 200, 200))  # Rosso chiaro
            elif block.block_type == 'insert':
                format.setBackground(QColor(200, 255, 200))  # Verde chiaro
            elif block.block_type == 'replace':
                format.setBackground(QColor(255, 255, 200))  # Giallo chiaro

            # Applica formato (implementazione semplificata)
            # In una versione più completa, si dovrebbe tracciare le posizioni esatte

    def update_navigation(self):
        """Aggiorna i controlli di navigazione"""
        if not self.current_differences:
            return

        total_diffs = len(self.current_differences)
        current_page = self.current_differences[self.current_page_index]['page']

        self.diff_label.setText(f"Differenza {self.current_page_index + 1}/{total_diffs} (Pagina {current_page})")

        self.prev_diff_btn.setEnabled(self.current_page_index > 0)
        self.next_diff_btn.setEnabled(self.current_page_index < total_diffs - 1)

    def prev_difference(self):
        """Va alla differenza precedente"""
        if self.current_page_index > 0:
            self.current_page_index -= 1
            self.update_difference_display()
            self.update_navigation()

    def next_difference(self):
        """Va alla differenza successiva"""
        if self.current_page_index < len(self.current_differences) - 1:
            self.current_page_index += 1
            self.update_difference_display()
            self.update_navigation()




