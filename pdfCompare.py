import sys
import os

import logging
from typing import List
import difflib
import fitz
from smart_compare import compare_pdf_files

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
    QGroupBox, QSplitter,
    QMessageBox, QProgressBar, QStackedWidget
)
from PyQt6.QtCore import Qt, pyqtSignal
from PyQt6.QtGui import (QFont, QColor,
                         QTextCursor, QMouseEvent)

from config import ConfigWidget

from pdf_txt_viewer import PdfTxtViewer


def doc_page_count(path_file: str) -> int:
    """
    Restituisce il numero di pagine di un documento PDF.

    Args:
        path_file: Il percorso completo del file PDF.

    Returns:
        Il numero di pagine.
    """
    try:
        # Aprire il documento
        doc = fitz.open(path_file)
        # Ottenere il numero di pagine
        num_pagine = doc.page_count
        # Chiudere il documento
        doc.close()
        return num_pagine
    except fitz.FileNotFoundError:
        print(f"Errore: Il file '{path_file}' non è stato trovato.")
        return -1
    except Exception as e:
        print(f"Si è verificato un errore: {e}")
        return -1

def map_index(original, norm, index):

    j = 0
    for i in range(len(norm)):
        if i >= index:
            break
        while norm[i] != original[j].lower() and j < len(original):
            j += 1
        j += 1
    return j



class txt_converter(QWidget):
    def __init__(self):
        statusUpdate = pyqtSignal(str)
        super().__init__()

        main_layout = QVBoxLayout(self)
        self.create_file_section(main_layout)

        self.text_extraction = PdfTxtViewer(self)
        self.text_extraction.clicEvent.connect(self.click_event)
        main_layout.addWidget(self.text_extraction)

    def create_file_section(self, main_layout) -> QWidget:
        """Crea la sezione per la selezione dei file"""
        group = QGroupBox("📁 Selezione File PDF")
        layout = QVBoxLayout()

        # File 1
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("PDF 1:"))
        self.pdf_path = QLineEdit()
        self.pdf_path.setPlaceholderText("Seleziona il file PDF...")
        self.pdf_browse = QPushButton("📂 Sfoglia...")
        self.pdf_browse.clicked.connect(lambda: self.browse_file(self.pdf_path))
        file_layout.addWidget(self.pdf_path, 3)
        file_layout.addWidget(self.pdf_browse, 1)
        main_layout.addLayout(file_layout)

    def browse_file(self, line_edit: QLineEdit):
        """Apre il dialog per selezionare un file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file PDF", "", "File PDF (*.pdf);;Tutti i file (*)"
        )
        if file_path:
            self.pdf_path.setText(file_path)
            self.text_extraction.show_pdf(file_path)
            self.text_extraction.clear_txt()
            self.extract_text(file_path)

    def click_event(self, ev, a1, a2, a3):
        if not self.pages_block:
            return
        if ev == '1':
            # clic sul text
            l = self.pages_block[a1]
            test_bbox = l['bbox']
            current_page = l['page'] -1# (x0, y0, x1, y1)
            test_color = QColor(255, 255, 0, 100)  # Giallo trasparente
            self.text_extraction.highlight_pdf(current_page, test_bbox, test_color)
            #self.diff_viewer.pdf_viewer1.highlight_text_line(current_page, test_bbox, test_color)
        elif ev == '2':
            # click sul pdf
            if self.pages_block:
                page = a3 + 1
                for i, l in enumerate(self.pages_block):
                    if l['page'] == page:
                        if l['bbox'][1] <= a2 and l['bbox'][3] >= a2:
                            self.text_extraction.highlight_txt(i + 1)
                            #self.diff_viewer.left_text.highlight_and_scroll_to_line(i+1)

        a = 0
    def extract_text(self, pdf_path):
        '''
            estrae il testo dal PDF
        '''

        from pdf_processor import extract_text_lines_from_pdf, remove_notes
        blocks = extract_text_lines_from_pdf(pdf_path)
        self.pages_block = remove_notes(blocks)

        pages_text = [t['text'].replace('\n', ' ') for t in self.pages_block]
        for t in pages_text:
            self.text_extraction.print_txt(t)

class pdf_compare(QWidget):
    statusUpdate = pyqtSignal(str)

    def __init__(self):
        super().__init__()

        self.result = None # risultato della comparazione
        self.txt1 = None # righe estratte dal documento 1
        self.txt2 = None # righe estratte dal documento 2

        main_layout = QVBoxLayout(self)

        v1 = QVBoxLayout()
        self.pdf_path1 = self.create_file_section(v1)
        self.file1 = PdfTxtViewer(self)
        self.file1.clicEvent.connect(self.click_event1)
        v1.addWidget(self.file1)
        w1 = QWidget()
        w1.setLayout(v1)


        v2 = QVBoxLayout()
        self.pdf_path2 = self.create_file_section(v2)
        self.file2 = PdfTxtViewer(self)
        self.file2.clicEvent.connect(self.click_event2)
        v2.addWidget(self.file2)
        w2 = QWidget()
        w2.setLayout(v2)

        main_splitter = QSplitter(Qt.Orientation.Horizontal)
        main_splitter.addWidget(w1)
        main_splitter.addWidget(w2)
        #self.text_extraction.clicEvent.connect(self.click_event)
        main_layout.addWidget(main_splitter)
        self.setup_scroll_sync()

    def create_file_section(self, main_layout) -> QWidget:
        """Crea la sezione per la selezione dei file"""
        group = QGroupBox("📁 Selezione File PDF")
        layout = QVBoxLayout()

        # File 1
        file_layout = QHBoxLayout()
        file_layout.addWidget(QLabel("PDF 1:"))
        pdf_path = QLineEdit()
        pdf_path.setPlaceholderText("Seleziona il file PDF...")
        pdf_browse = QPushButton("📂 Sfoglia...")
        pdf_browse.clicked.connect(lambda: self.browse_file(pdf_path))
        file_layout.addWidget(pdf_path, 3)
        file_layout.addWidget(pdf_browse, 1)
        main_layout.addLayout(file_layout)
        return pdf_path

    def browse_file(self, line_edit: QLineEdit):
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file PDF", "", "File PDF (*.pdf);;Tutti i file (*)"
        )
        if file_path:
            line_edit.setText(file_path)
            if line_edit == self.pdf_path1:
                self.file1.show_pdf(file_path)
            elif line_edit == self.pdf_path2:
                self.file2.show_pdf(file_path)
            if self.pdf_path1.text() and self.pdf_path2.text():
                self.compare_files(self.pdf_path1.text(), self.pdf_path2.text())

    def setup_scroll_sync(self):
        """Configura la sincronizzazione dello scroll"""

        left_scroll = self.file1.text_viewer.verticalScrollBar()
        right_scroll = self.file2.text_viewer.verticalScrollBar()

        self.left_scroll_connection = left_scroll.valueChanged.connect(
            lambda v: right_scroll.setValue(v)) # if self.sync_scroll_cb.isChecked() else None

        self.right_scroll_connection = right_scroll.valueChanged.connect(
            lambda v: left_scroll.setValue(v)) # if self.sync_scroll_cb.isChecked() else None


    def compare_files(self, pdf1, pdf2):
        try:
            fitz.open(pdf1).close()
            fitz.open(pdf2).close()
        except Exception as e:
            QMessageBox.warning(self, "⚠️ Errore", f"Errore nell'apertura dei file PDF:\n{str(e)}")
            return

        # Disabilita il pulsante e mostra la progress bar
        '''
        self.compare_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("🔄 Confronto in corso...")

        self.tab_widget.setCurrentIndex(1)
        '''
        self.result, self.txt1, self.txt2 = compare_pdf_files(pdf1, pdf2)
        for r in self.result:
            t1 = self.txt1[r['doc1']]['text']
            t2 = self.txt2[r['doc2']]['text']
            score = r['score']
            self.file1.print_txt(f'score {score:.2f}  {t1}')
            self.file2.print_txt(f'{t2} ')

    def pdf_to_txt(self, pag, y, pages_block):
        page = pag + 1
        for i, l in enumerate(pages_block):
            if l['page'] == page:
                if l['bbox'][1] <= y and l['bbox'][3] >= y:
                    return i + 1
        return -1

    def txt_to_pdf(self, line, idx):
        pages_block = self.txt1 if idx == 0 else self.txt2
        '''
        if idx == 0:
            pages_block = self.txt1
        else:
            pages_block = self.txt2
        '''
        l = pages_block[line]
        text_bbox = l['bbox']
        current_page = l['page'] - 1
        return current_page, text_bbox


    def click_event1(self, ev, a1, a2, a3):
        offset = 12
        r = a1
        if ev == '1' and self.result:
            l0 = self.result[a1]
            #r = l0['doc1']
            r1 = r #l0['doc2']
            diff = l0['diff']
            icol = 0
            self.file1.text_viewer.clear_highlight()
            self.file2.text_viewer.clear_highlight()
            if diff:
                mes = [f"{df['operation']} {df['text1']} : {df['text2']}" for df in diff]
                self.statusUpdate.emit(', '.join(mes))
                for df in diff:
                    if df['operation'] == 'replace':
                        p0 = df['position1'][0]
                        count0 = df['position1'][1] - p0
                        p0 = map_index(self.txt1[r]['text'], self.txt1[r]['normalized'], p0)

                        p1 = df['position2'][0]
                        count1 = df['position2'][1] - p1
                        p1 = map_index(self.txt2[r1]['text'], self.txt2[r1]['normalized'], p1)

                        self.file1.text_viewer.highlight_character_at(a1, p0 + offset, count0, icol)
                        self.file2.text_viewer.highlight_character_at(a1, p1, count1, icol)
                        icol += 1
            #evidenzia pdf
            self.click_event(ev, r, a2, a3, 0)
            self.click_event(ev, r1, a2, a3, 1)
        else:
            # clic su pdf a1 = x, a2 = y, a3 = pag
            self.click_event(ev, a1, a2, a3, 0)

    def click_event2(self, ev, a1, a2, a3):
        self.click_event(ev, a1, a2, a3, 1)

    def click_event(self, ev, a1, a2, a3, idx):
        if idx == 0:
            cnt = self.file1
            pages_block = self.txt1
        else:
            cnt = self.file2
            pages_block = self.txt2

        if not pages_block:
            return
        if ev == '1':
            current_page, bbox = self.txt_to_pdf(a1, idx)
            color = QColor(255, 255, 0, 100)  # Giallo trasparente
            cnt.highlight_pdf(current_page, bbox, color)

        elif ev == '2':
            # click sul pdf
            line = self.pdf_to_txt(a3, a2, pages_block)
            cnt.highlight_txt(line)
            current_page, bbox = self.txt_to_pdf(line-1, idx)
            cnt.highlight_pdf(current_page, bbox, QColor(255, 255, 0, 100))

            idx1 = (idx +1) % 2
            cnt1 = self.file2 if cnt == self.file1 else self.file1
            current_page, bbox = self.txt_to_pdf(line-1, idx1)
            cnt1.highlight_pdf(current_page, bbox, QColor(255, 255, 0, 100))
            cnt1.highlight_txt(line)


class PDFCompareApp(QMainWindow):
    """Applicazione principale per il confronto PDF con rendering visivo e allineamento intelligente"""

    def __init__(self):
        super().__init__()
        self.pages_block = None
        self.setup_ui()
        self.setup_logging()

    def setup_logging(self):
        """Configura il logging"""
        logging.basicConfig(
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s',
            handlers=[
                logging.FileHandler('pdf_compare.log'),
                logging.StreamHandler()
            ]
        )

    def setup_ui(self):
        """Configura l'interfaccia utente"""
        self.setWindowTitle("PDF Comparison Tool - Enhanced Version")
        self.setGeometry(100, 100, 1400, 900)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        main_layout = QVBoxLayout(central_widget)

        # Tab widget per configurazione e risultati
        self.tab_widget = QStackedWidget()

        self.text_extraction = txt_converter()
        self.tab_widget.addWidget(self.text_extraction)

        self.file_compare = pdf_compare()
        self.file_compare.statusUpdate.connect(self.statusBarMes)
        self.tab_widget.addWidget(self.file_compare)

        main_layout.addWidget(self.tab_widget)

        # Progress bar
        self.progress_bar = QProgressBar()
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        # Status bar
        self.statusBar().showMessage("Pronto per il confronto PDF avanzato")

        # Menu bar
        self.create_menu_bar()

    def create_menu_bar(self):
        """Crea la barra dei menu"""
        menubar = self.menuBar()

        # Menu File
        file_menu = menubar.addMenu('File')

        txt_converter_action = file_menu.addAction('Converte in TXT')
        txt_converter_action.triggered.connect(self.show_text_convert)

        pdf_compare_action = file_menu.addAction('Confronta PDF')
        pdf_compare_action.triggered.connect(self.show_pdf_compare)

        open_action = file_menu.addAction('Apri Log Precedente')
        open_action.triggered.connect(self.open_previous_log)

        file_menu.addSeparator()

        export_action = file_menu.addAction('Esporta Risultati')
        export_action.triggered.connect(self.export_results)

        file_menu.addSeparator()

        exit_action = file_menu.addAction('Esci')
        exit_action.triggered.connect(self.close)

        # Menu Visualizza
        view_menu = menubar.addMenu('Visualizza')

        zoom_in_action = view_menu.addAction('Zoom Avanti')
        zoom_in_action.triggered.connect(self.zoom_in_all)

        zoom_out_action = view_menu.addAction('Zoom Indietro')
        zoom_out_action.triggered.connect(self.zoom_out_all)

        # Menu Aiuto
        help_menu = menubar.addMenu('Aiuto')

        about_action = help_menu.addAction('Informazioni')
        about_action.triggered.connect(self.show_about)

    def show_text_convert(self):
        self.tab_widget.setCurrentIndex(0)

    def show_pdf_compare(self):
        self.tab_widget.setCurrentIndex(1)

    def statusBarMes(self, message):
        self.statusBar().showMessage(message)

    '''
    def create_file_section(self) -> QWidget:
        """Crea la sezione per la selezione dei file"""
        group = QGroupBox("📁 Selezione File PDF")
        layout = QVBoxLayout()

        # File 1
        file1_layout = QHBoxLayout()
        file1_layout.addWidget(QLabel("PDF 1:"))
        self.pdf1_path = QLineEdit()
        self.pdf1_path.setPlaceholderText("Seleziona il primo file PDF...")
        self.pdf1_browse = QPushButton("📂 Sfoglia...")
        self.pdf1_browse.clicked.connect(lambda: self.browse_file(self.pdf1_path))
        file1_layout.addWidget(self.pdf1_path, 3)
        file1_layout.addWidget(self.pdf1_browse, 1)

        # File 2
        file2_layout = QHBoxLayout()
        file2_layout.addWidget(QLabel("PDF 2:"))
        self.pdf2_path = QLineEdit()
        self.pdf2_path.setPlaceholderText("Seleziona il secondo file PDF...")
        self.pdf2_browse = QPushButton("📂 Sfoglia...")
        self.pdf2_browse.clicked.connect(lambda: self.browse_file(self.pdf2_path))
        file2_layout.addWidget(self.pdf2_path, 3)
        file2_layout.addWidget(self.pdf2_browse, 1)

        # Pulsanti azione
        button_layout = QHBoxLayout()
        self.compare_button = QPushButton("🔍 Confronta PDF")
        self.compare_button.clicked.connect(self.start_comparison)
        self.compare_button.setStyleSheet("""
            QPushButton {
                font-weight: bold; 
                padding: 12px 24px; 
                font-size: 14px;
                background-color: #4CAF50;
                color: white;
                border: none;
                border-radius: 6px;
            }
            QPushButton:hover {
                background-color: #45a049;
            }
            QPushButton:disabled {
                background-color: #cccccc;
            }
        """)

        self.clear_button = QPushButton("🗑️ Pulisci")
        self.clear_button.clicked.connect(self.clear_files)

        button_layout.addStretch()
        button_layout.addWidget(self.clear_button)
        button_layout.addWidget(self.compare_button)

        layout.addLayout(file1_layout)
        layout.addLayout(file2_layout)
        layout.addLayout(button_layout)

        group.setLayout(layout)
        return group
    '''

    '''
    def browse_file(self, line_edit: QLineEdit):
        """Apre il dialog per selezionare un file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file PDF", "", "File PDF (*.pdf);;Tutti i file (*)"
        )
        if file_path:
            line_edit.setText(file_path)
            if line_edit == self.pdf1_path:
                self.text_extraction.show_pdf(file_path)
                self.text_extraction.clear_txt()
                self.extract_text(file_path)
                #self.diff_viewer.show_pdf(file_path, 0)
               
                n_pages = doc_page_count(file_path)
                if n_pages > 0:
                    self.config_widget.sync_page_limits(1, n_pages)
                
            else:
                self.diff_viewer.show_pdf(file_path, 1)

    def click_event(self, ev, a1, a2, a3):
        if not self.pages_block:
            return
        if ev == '1':
            l = self.pages_block[a1]
            test_bbox = l['bbox']
            current_page = l['page'] -1# (x0, y0, x1, y1)
            test_color = QColor(255, 255, 0, 100)  # Giallo trasparente
            self.text_extraction.highlight_pdf(current_page, test_bbox, test_color)
            #self.diff_viewer.pdf_viewer1.highlight_text_line(current_page, test_bbox, test_color)
        elif ev == '2':
            # click sul pdf
            if self.pages_block:
                page = a3 + 1
                for i, l in enumerate(self.pages_block):
                    if l['page'] == page:
                        if l['bbox'][1] <= a2 and l['bbox'][3] >= a2:
                            self.text_extraction.highlight_txt(i + 1)
                            #self.diff_viewer.left_text.highlight_and_scroll_to_line(i+1)

        a = 0
    '''
    def clear_files(self):
        """Pulisce i campi di selezione file"""
        self.pdf1_path.clear()
        self.pdf2_path.clear()
        self.diff_viewer.pdf_viewer1.unload_pdf()
        self.diff_viewer.left_text.clear()
        self.pages_block = None

    """
    def extract_text(self, pdf_path):
        '''
            estrae il testo dal PDF
        '''

        from pdf_processor import extract_text_lines_from_pdf, remove_notes
        blocks = extract_text_lines_from_pdf(pdf_path)
        self.pages_block = remove_notes(blocks)

        pages_text = [t['text'].replace('\n', ' ') for t in self.pages_block]
        for t in pages_text:
            self.text_extraction.print_txt(t)

        #self.diff_viewer.left_text.highlight_character_at(5, 7, 4)
        #self.diff_viewer.left_text.highlight_character_at(75, 2, 7)

    """

    def start_comparison(self):
        """Avvia il confronto dei PDF"""
        pdf1 = self.pdf1_path.text().strip()
        pdf2 = self.pdf2_path.text().strip()
        self.tab_widget.setCurrentIndex(1)

        if not pdf1 and not pdf2:
            QMessageBox.warning(self, "⚠️ Errore", "Seleziona entrambi i file PDF")
            return
        elif pdf1 and not pdf2:
            # se presente solo pdf1 lo converte in testo
            self.extract_text(pdf1)
            return

        if not os.path.exists(pdf1) or not os.path.exists(pdf2):
            QMessageBox.warning(self, "⚠️ Errore", "Uno o entrambi i file PDF non esistono")
            return

        # Verifica che siano file PDF validi
        try:
            fitz.open(pdf1).close()
            fitz.open(pdf2).close()
        except Exception as e:
            QMessageBox.warning(self, "⚠️ Errore", f"Errore nell'apertura dei file PDF:\n{str(e)}")
            return

        # Disabilita il pulsante e mostra la progress bar
        self.compare_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.statusBar().showMessage("🔄 Confronto in corso...")

        self.tab_widget.setCurrentIndex(1)
        self.result, txt1, txt2 = compare_pdf_files(pdf1, pdf2)
        for r in self.result:
            t1 = txt1[r['doc1']]['text']
            t2 = txt2[r['doc2']]['text']
            score = r['score']
            self.diff_viewer.print_left(f'score {score:.2f}  {t1}')
            self.diff_viewer.print_right(f'{t2} ')

        a = 0
        #self.diff_viewer.load_pdf(pdf1)

        '''
        # Avvia il worker thread
        config = self.config_widget.get_config()
        self.worker = ComparisonWorker(pdf1, pdf2, config)
        self.worker.progress_updated.connect(self.progress_bar.setValue)
        self.worker.comparison_complete.connect(self.on_comparison_complete)
        self.worker.error_occurred.connect(self.on_error)
        self.worker.start()
        '''

    def on_comparison_complete(self, differences: List[dict]):
        """Gestisce il completamento del confronto"""
        self.compare_button.setEnabled(True)
        self.progress_bar.setVisible(False)

        pdf1_path = self.pdf1_path.text()
        pdf2_path = self.pdf2_path.text()

        # Mostra i risultati nel viewer avanzato
        #self.diff_viewer.show_differences(differences, pdf1_path, pdf2_path)
        self.tab_widget.setCurrentIndex(1)  # Passa al tab risultati

        # Aggiorna status bar
        if differences:
            self.statusBar().showMessage(f"✅ Confronto completato: {len(differences)} pagine con differenze")
        else:
            self.statusBar().showMessage("✅ Confronto completato: file identici")

        # Mostra messaggio di completamento
        if differences:
            QMessageBox.information(
                self, "🎉 Confronto Completato",
                f"Trovate {len(differences)} pagine con differenze.\n\n"
                "• Controlla il tab 'Risultati Side-by-Side' per visualizzare le differenze\n"
                "• Il PDF originale è mostrato nella parte superiore\n"
                "• Il testo allineato è mostrato nella parte inferiore\n"
                "• Usa i pulsanti di navigazione per spostarti tra le differenze\n"
                "• Il file di log è stato salvato automaticamente"
            )
        else:
            QMessageBox.information(
                self, "🎉 Confronto Completato",
                "I file sono identici secondo la configurazione specificata.\n\n"
                "Prova a modificare le opzioni di configurazione se il risultato non è quello atteso."
            )

    def on_error(self, error_message: str):
        """Gestisce gli errori durante il confronto"""
        self.compare_button.setEnabled(True)
        self.progress_bar.setVisible(False)
        self.statusBar().showMessage("❌ Errore durante il confronto")

        QMessageBox.critical(self, "❌ Errore", f"Errore durante il confronto:\n\n{error_message}")

    def open_previous_log(self):
        """Apre un log precedente"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Apri Log Confronto", "", "File Log (*.log);;Tutti i file (*)"
        )
        if file_path:
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    content = f.read()

                # Crea una finestra per mostrare il contenuto del log
                log_window = QWidget()
                log_window.setWindowTitle(f"Log: {os.path.basename(file_path)}")
                log_window.resize(800, 600)

                layout = QVBoxLayout()
                text_edit = QTextEdit()
                text_edit.setPlainText(content)
                text_edit.setReadOnly(True)
                text_edit.setFont(QFont("Courier", 10))

                layout.addWidget(text_edit)
                log_window.setLayout(layout)
                log_window.show()

            except Exception as e:
                QMessageBox.warning(self, "Errore", f"Impossibile aprire il file log:\n{str(e)}")

    def export_results(self):
        """Esporta i risultati del confronto"""
        QMessageBox.information(self, "Info", "Funzionalità di esportazione in sviluppo")

    def zoom_in_all(self):
        """Aumenta lo zoom di tutti i viewer PDF"""
        self.diff_viewer.pdf_viewer1.zoom_in_page()
        self.diff_viewer.pdf_viewer2.zoom_in_page()

    def zoom_out_all(self):
        """Diminuisce lo zoom di tutti i viewer PDF"""
        self.diff_viewer.pdf_viewer1.zoom_out_page()
        self.diff_viewer.pdf_viewer2.zoom_out_page()

    def show_about(self):
        """Mostra informazioni sull'applicazione"""
        QMessageBox.about(
            self, "Informazioni",
            "<h2>PDF Comparison Tool - Enhanced</h2>"
            "<p><b>Versione:</b> 2.0</p>"
            "<p><b>Descrizione:</b> Strumento avanzato per il confronto di file PDF con:</p>"
            "<ul>"
            "<li>Visualizzazione side-by-side del PDF originale</li>"
            "<li>Allineamento intelligente delle differenze</li>"
            "<li>Opzioni di configurazione avanzate</li>"
            "<li>Evidenziazione delle differenze</li>"
            "<li>Navigazione sincronizzata</li>"
            "<li>Generazione automatica di log dettagliati</li>"
            "</ul>"
            "<p><b>Librerie utilizzate:</b> PyQt6, PyMuPDF</p>"
        )


def main():
    app = QApplication(sys.argv)
    app.setApplicationName("PDF Comparison Tool - Enhanced")
    app.setOrganizationName("PDF Tools")

    # Stile moderno per l'applicazione
    app.setStyleSheet("""
        QMainWindow {
            background-color: #f5f5f5;
        }
        QGroupBox {
            font-weight: bold;
            border: 2px solid #cccccc;
            border-radius: 8px;
            margin: 10px 0;
            padding-top: 10px;
        }
        QGroupBox::title {
            subcontrol-origin: margin;
            left: 10px;
            padding: 0 8px 0 8px;
        }
        QTabWidget::pane {
            border: 1px solid #cccccc;
            border-radius: 4px;
        }
        QTabBar::tab {
            background-color: #e0e0e0;
            border: 1px solid #cccccc;
            padding: 8px 16px;
            margin-right: 2px;
        }
        QTabBar::tab:selected {
            background-color: white;
            border-bottom-color: white;
        }
    """)

    window = PDFCompareApp()
    window.show()

    sys.exit(app.exec())


if __name__ == "__main__":
    main()