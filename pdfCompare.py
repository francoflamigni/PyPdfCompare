import sys
import os
import re
import json
import logging
from datetime import datetime
from typing import List, Tuple, Optional, Dict
import difflib
import fitz
from smart_compare import compare_pdf_texts, extract_pdf_text, compare_pdf_files

from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QLineEdit, QTextEdit, QFileDialog,
    QCheckBox, QGroupBox, QSplitter, QScrollArea, QFrame,
    QSpinBox, QComboBox, QMessageBox, QProgressBar, QTabWidget,
    QGraphicsView, QGraphicsScene, QGraphicsPixmapItem
)
from PyQt6.QtCore import Qt, QThread, pyqtSignal, QTimer, QRectF
from PyQt6.QtGui import (QFont, QTextCharFormat, QColor, QPixmap, QPainter,
                         QTextCursor, QTextDocument, QSyntaxHighlighter, QTextFormat, QMouseEvent)

from config import ConfigWidget
#from smart_segmentation import PDFTextSegmenter
from pdf_viewer import PDFViewer


class CustomTextEdit(QTextEdit):
    lineClicked = pyqtSignal(int)
    def __init__(self, parent=None):
        super().__init__(parent)
       # self.setPlainText("Riga 1\nRiga 2\nRiga 3\nRiga 4\nRiga 5")

    def mousePressEvent(self, event: QMouseEvent):
        # Chiama il metodo originale per mantenere il comportamento predefinito
        super().mousePressEvent(event)

        # Pulisce l'evidenziazione precedente se esiste
        self.clear_highlight()

        # Ottiene il cursore del testo nella posizione del clic
        cursor = self.cursorForPosition(event.pos())

        # Ottiene il numero del blocco (che corrisponde al numero della riga)
        line_number = cursor.blockNumber()

        # Evidenzia la nuova riga
        self.highlight_line(cursor)
        self.lineClicked.emit(line_number)

        # Stampa il numero della riga (i blocchi sono indicizzati da 0)
        print(f"Hai cliccato sulla riga: {line_number + 1}")

    def highlight_and_scroll_to_line(self, line_number: int):
        self.clear_highlight()
        """
        Scorre la QTextEdit fino alla riga specificata e la evidenzia.

        Args:
            line_number (int): Il numero della riga da visualizzare (base 1).
        """
        # 1. Pulire qualsiasi evidenziazione precedente
        # Se hai una funzione per pulire l'evidenziazione, è meglio chiamarla qui.
        # Ad esempio: self.clear_highlight()

        # 2. Spostare il cursore alla riga desiderata
        cursor = self.textCursor()

        # Il numero del blocco è a base 0, quindi sottraiamo 1
        target_block_number = line_number - 1

        # Sposta il cursore al blocco (riga) specificato
        cursor.movePosition(QTextCursor.MoveOperation.Start)
        cursor.movePosition(QTextCursor.MoveOperation.NextBlock,
                            QTextCursor.MoveMode.MoveAnchor,
                            target_block_number)

        # 3. Rendere il cursore visibile (scorrere la vista)
        self.setTextCursor(cursor)
        self.ensureCursorVisible()

        # 4. Evidenziare la riga corrente
        # Crea un formato per lo sfondo
        format = QTextCharFormat()
        format.setBackground(QColor("#d9eaff"))  # Un colore azzurro chiaro

        # Seleziona l'intera riga
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)

        # Applica il formato
        cursor.setCharFormat(format)

    def clear_highlight(self):
        # Resetta il formato di tutte le righe
        cursor = self.textCursor()
        cursor.select(QTextCursor.SelectionType.Document)
        format = QTextCharFormat()
        format.setBackground(QColor("transparent"))
        cursor.mergeCharFormat(format)

    def highlight_line(self, cursor: QTextCursor):
        # Salva la posizione attuale per poterla ripulire successivamente
        self.current_highlight_cursor = QTextCursor(cursor)

        # Prepara il formato per l'evidenziazione
        format = QTextCharFormat()
        format.setBackground(QColor("#d9eaff"))  # Un colore azzurro chiaro

        # Seleziona l'intera riga e applica il formato
        cursor.select(QTextCursor.SelectionType.BlockUnderCursor)
        cursor.setCharFormat(format)


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

class EnhancedDiffViewer(QWidget):
    diffEvent = pyqtSignal(str, int)
    diffEvent = pyqtSignal(str, int, int, int)
    """Widget avanzato per visualizzare le differenze con PDF rendering e allineamento"""

    def __init__(self, parent):
        super().__init__(parent)
        self.setup_ui()
        self.current_differences = []
        self.current_page_index = 0

    def setup_ui(self):
        main_layout = QVBoxLayout()

        # Controlli di navigazione per le differenze
        nav_layout = QHBoxLayout()
        self.prev_diff_btn = QPushButton("◀ Diff Precedente")
        self.next_diff_btn = QPushButton("Diff Successiva ▶")
        self.diff_label = QLabel("Nessuna differenza")
        self.sync_scroll_cb = QCheckBox("Sincronizza scroll")
        self.sync_scroll_cb.setChecked(True)

        nav_layout.addWidget(self.prev_diff_btn)
        nav_layout.addWidget(self.diff_label)
        nav_layout.addWidget(self.next_diff_btn)
        nav_layout.addStretch()
        nav_layout.addWidget(self.sync_scroll_cb)

        # Splitter principale per PDF e testo
        main_splitter = QSplitter(Qt.Orientation.Vertical)

        # Area PDF (parte superiore)
        pdf_widget = QWidget()
        pdf_layout = QHBoxLayout(pdf_widget)

        pdf_splitter = QSplitter(Qt.Orientation.Horizontal)
        self.pdf_viewer1 = PDFViewer()
        self.pdf_viewer1.mouse_click.connect(self.mouse_click)
        self.pdf_viewer2 = PDFViewer()

        pdf_frame1 = QFrame()
        pdf_frame1.setFrameStyle(QFrame.Shape.Box)
        pdf_layout1 = QVBoxLayout(pdf_frame1)
        self.pdf_label1 = QLabel("PDF 1")
        self.pdf_label1.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout1.addWidget(self.pdf_label1)
        pdf_layout1.addWidget(self.pdf_viewer1)

        pdf_frame2 = QFrame()
        pdf_frame2.setFrameStyle(QFrame.Shape.Box)
        pdf_layout2 = QVBoxLayout(pdf_frame2)
        self.pdf_label2 = QLabel("PDF 2")
        self.pdf_label2.setAlignment(Qt.AlignmentFlag.AlignCenter)
        pdf_layout2.addWidget(self.pdf_label2)
        pdf_layout2.addWidget(self.pdf_viewer2)

        pdf_splitter.addWidget(pdf_frame1)
        pdf_splitter.addWidget(pdf_frame2)
        pdf_splitter.setStretchFactor(0, 1)
        pdf_splitter.setStretchFactor(1, 1)

        pdf_layout.addWidget(pdf_splitter)

        # Area testo (parte inferiore)
        text_widget = QWidget()
        text_layout = QHBoxLayout(text_widget)

        text_splitter = QSplitter(Qt.Orientation.Horizontal)

        # Pannello sinistro (testo allineato)
        left_frame = QFrame()
        left_frame.setFrameStyle(QFrame.Shape.Box)
        left_layout = QVBoxLayout(left_frame)
        self.left_text_label = QLabel("Testo PDF 1 (Allineato)")
        self.left_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.left_text = CustomTextEdit()
        self.left_text.lineClicked.connect(self.left_text_clicked)
        self.left_text.setReadOnly(True)
        self.left_text.setFont(QFont("Courier", 10))  # Font monospace
        left_layout.addWidget(self.left_text_label)
        left_layout.addWidget(self.left_text)

        # Pannello destro (testo allineato)
        right_frame = QFrame()
        right_frame.setFrameStyle(QFrame.Shape.Box)
        right_layout = QVBoxLayout(right_frame)
        self.right_text_label = QLabel("Testo PDF 2 (Allineato)")
        self.right_text_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.right_text = QTextEdit()
        self.right_text.setReadOnly(True)
        self.right_text.setFont(QFont("Courier", 10))  # Font monospace
        right_layout.addWidget(self.right_text_label)
        right_layout.addWidget(self.right_text)

        text_splitter.addWidget(left_frame)
        text_splitter.addWidget(right_frame)
        text_splitter.setStretchFactor(0, 1)
        text_splitter.setStretchFactor(1, 1)

        text_layout.addWidget(text_splitter)

        # Aggiungi al main splitter
        main_splitter.addWidget(pdf_widget)
        main_splitter.addWidget(text_widget)
        main_splitter.setStretchFactor(0, 2)  # PDF area più grande
        main_splitter.setStretchFactor(1, 1)  # Text area più piccola

        # Connessioni
        self.prev_diff_btn.clicked.connect(self.prev_difference)
        self.next_diff_btn.clicked.connect(self.next_difference)
        self.sync_scroll_cb.toggled.connect(self.toggle_sync_scroll)

        main_layout.addLayout(nav_layout)
        main_layout.addWidget(main_splitter)
        self.setLayout(main_layout)

        # Sincronizza scroll di default
        self.setup_scroll_sync()

    def left_text_clicked(self, line):
        self.diffEvent.emit('1', line, 0, 0)

    def mouse_click(self, x, y, page):
        self.diffEvent.emit('2', x, y, page)

    def setup_scroll_sync(self):
        """Configura la sincronizzazione dello scroll"""
        left_scroll = self.left_text.verticalScrollBar()
        right_scroll = self.right_text.verticalScrollBar()

        self.left_scroll_connection = left_scroll.valueChanged.connect(
            lambda v: right_scroll.setValue(v) if self.sync_scroll_cb.isChecked() else None
        )
        self.right_scroll_connection = right_scroll.valueChanged.connect(
            lambda v: left_scroll.setValue(v) if self.sync_scroll_cb.isChecked() else None
        )

    def print_left(self, txt):
        self.left_text.append(txt)

    def print_right(self, txt):
        self.right_text.append(txt)

    def toggle_sync_scroll(self, enabled: bool):
        """Attiva/disattiva la sincronizzazione dello scroll"""
        # La sincronizzazione è già gestita nel setup_scroll_sync
        pass

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

    def show_pdf(self, pdf, pos):
        if pos == 0:
            self.pdf_viewer1.load_pdf(pdf)
        else:
            self.pdf_viewer2.load_pdf(pdf)





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

        # Sezione selezione file
        file_section = self.create_file_section()
        main_layout.addWidget(file_section)

        # Tab widget per configurazione e risultati
        self.tab_widget = QTabWidget()

        # Tab configurazione
        self.config_widget = ConfigWidget()
        self.tab_widget.addTab(self.config_widget, "⚙️ Configurazione")

        # Tab risultati avanzato
        self.diff_viewer = EnhancedDiffViewer(self)
        self.diff_viewer.diffEvent.connect(self.diff_event)
        self.tab_widget.addTab(self.diff_viewer, "📊 Risultati Side-by-Side")

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


    def browse_file(self, line_edit: QLineEdit):
        """Apre il dialog per selezionare un file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Seleziona file PDF", "", "File PDF (*.pdf);;Tutti i file (*)"
        )
        if file_path:
            line_edit.setText(file_path)
            if line_edit == self.pdf1_path:
                self.diff_viewer.show_pdf(file_path, 0)
                n_pages = doc_page_count(file_path)
                if n_pages > 0:
                    self.config_widget.sync_page_limits(1, n_pages)
            else:
                self.diff_viewer.show_pdf(file_path, 1)

    def diff_event(self, ev, a1, a2, a3):
        if not self.pages_block:
            return
        if ev == '1':
            l = self.pages_block[a1]
            test_bbox = l['bbox']
            current_page = l['page'] -1# (x0, y0, x1, y1)
            test_color = QColor(255, 255, 0, 100)  # Giallo trasparente
            self.diff_viewer.pdf_viewer1.highlight_text_line(current_page, test_bbox, test_color)
        elif ev == '2':
            if self.pages_block:
                page = a3 + 1
                for i, l in enumerate(self.pages_block):
                    if l['page'] == page:
                        if l['bbox'][1] <= a2 and l['bbox'][3] >= a2:
                            self.diff_viewer.left_text.highlight_and_scroll_to_line(i+1)

        a = 0

    def clear_files(self):
        """Pulisce i campi di selezione file"""
        self.pdf1_path.clear()
        self.pdf2_path.clear()
        self.diff_viewer.pdf_viewer1.unload_pdf()
        self.diff_viewer.left_text.clear()
        self.pages_block = None

    def extract_text(self, pdf_path):
        '''
            estrae il testo dal PDF
        '''

        from pdf_processor import extract_text_lines_from_pdf, remove_notes
        blocks = extract_text_lines_from_pdf(pdf_path)
        self.pages_block = remove_notes(blocks)

        pages_text = [t['text'].replace('\n', ' ') for t in self.pages_block]
        for t in pages_text:
            self.diff_viewer.print_left(t)

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