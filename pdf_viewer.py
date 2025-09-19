import sys
from multiprocessing.pool import CLOSE

import fitz  # PyMuPDF
from PyQt6.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout,
                             QHBoxLayout, QPushButton, QScrollArea, QLabel,
                             QSlider, QSpinBox, QFileDialog, QFrame)
from PyQt6.QtCore import Qt, QRect, pyqtSignal
from PyQt6.QtGui import QPixmap, QPainter, QPen, QColor, QBrush


class PDFPageWidget(QLabel):
    mouse_click = pyqtSignal(int, int)
    """Widget per visualizzare una singola pagina PDF con evidenziazioni"""

    def __init__(self):
        super().__init__()
        self.page_pixmap = None
        self.current_page_highlights = []  # Highlights solo per la pagina corrente
        self.zoom_factor = 1.0
        self.current_page_num = 0
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

    def set_page(self, page, page_num, zoom_factor=1.0):
        """Imposta la pagina PDF da visualizzare"""
        self.zoom_factor = zoom_factor
        self.current_page_num = page_num

        # Calcola la matrice di trasformazione per lo zoom
        mat = fitz.Matrix(zoom_factor, zoom_factor)

        # Renderizza la pagina come pixmap
        pix = page.get_pixmap(matrix=mat)
        img_data = pix.tobytes("ppm")

        # Converti in QPixmap
        pixmap = QPixmap()
        pixmap.loadFromData(img_data)

        self.page_pixmap = pixmap
        self.update_display()

    def set_page_highlights(self, highlights):
        """
        Imposta gli highlight per la pagina corrente
        highlights: lista di (bbox, color) per questa pagina
        """
        self.current_page_highlights = []
        for bbox, color in highlights:
            # Scala la bbox in base al zoom factor
            scaled_bbox = (
                bbox[0] * self.zoom_factor,
                bbox[1] * self.zoom_factor,
                bbox[2] * self.zoom_factor,
                bbox[3] * self.zoom_factor
            )
            self.current_page_highlights.append((scaled_bbox, color))
        self.update_display()

    def add_highlight(self, bbox, color=QColor(255, 255, 0, 100)):
        """
        Aggiunge un'evidenziazione alla pagina corrente
        bbox: tupla (x0, y0, x1, y1) nelle coordinate della pagina PDF
        color: QColor per l'evidenziazione
        """
        # Scala la bbox in base al zoom factor
        scaled_bbox = (
            bbox[0] * self.zoom_factor,
            bbox[1] * self.zoom_factor,
            bbox[2] * self.zoom_factor,
            bbox[3] * self.zoom_factor
        )
        self.current_page_highlights.append((scaled_bbox, color))
        self.update_display()

    def clear_highlights(self):
        """Rimuove tutte le evidenziazioni della pagina corrente"""
        self.current_page_highlights.clear()
        self.update_display()

    def update_display(self):
        """Aggiorna la visualizzazione con le evidenziazioni"""
        if self.page_pixmap is None:
            return

        # Crea una copia del pixmap originale
        display_pixmap = self.page_pixmap.copy()

        if self.current_page_highlights:
            painter = QPainter(display_pixmap)

            # Disegna ogni evidenziazione
            for bbox, color in self.current_page_highlights:
                x0, y0, x1, y1 = bbox
                rect = QRect(int(x0), int(y0), int(x1 - x0), int(y1 - y0))

                # Imposta il pennello per l'evidenziazione
                brush = QBrush(color)
                painter.fillRect(rect, brush)

                # Opzionale: aggiungi un bordo
                pen = QPen(color.darker(150), 1)
                painter.setPen(pen)
                painter.drawRect(rect)

            painter.end()

        self.setPixmap(display_pixmap)
        self.resize(display_pixmap.size())

    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.LeftButton:
            p = event.pos()

            self.mouse_click.emit(event.pos().x(), event.pos().y())


class PDFViewer(QWidget):
    mouse_click = pyqtSignal(int, int, int)
    """Widget principale per visualizzare PDF con controlli"""

    def __init__(self):
        super().__init__()
        self.pdf_document = None
        self.current_page = 0
        self.zoom_factor = 1.0
        self.page_highlights = {}  # Dizionario {page_num: [(bbox, color), ...]}
        self.init_ui()

    def init_ui(self):
        layout = QVBoxLayout()

        # Toolbar con controlli
        toolbar = self.create_toolbar()
        layout.addWidget(toolbar)

        # Area di scroll per il PDF
        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setAlignment(Qt.AlignmentFlag.AlignCenter)

        # Widget per la pagina PDF
        self.pdf_page_widget = PDFPageWidget()
        self.pdf_page_widget.mouse_click.connect(self.mouse_click_man)
        self.scroll_area.setWidget(self.pdf_page_widget)

        layout.addWidget(self.scroll_area)
        self.setLayout(layout)

    def create_toolbar(self):
        """Crea la toolbar con i controlli"""
        toolbar = QFrame()
        toolbar.setFrameStyle(QFrame.Shape.StyledPanel)
        layout = QHBoxLayout()

        # Pulsante per aprire PDF
        self.open_btn = QPushButton("Apri PDF")
        self.open_btn.clicked.connect(self.open_pdf)
        layout.addWidget(self.open_btn)

        layout.addWidget(QLabel("Pagina:"))

        # Controlli pagina
        self.prev_btn = QPushButton("◀")
        self.prev_btn.clicked.connect(self.prev_page)
        layout.addWidget(self.prev_btn)

        self.page_spinbox = QSpinBox()
        self.page_spinbox.setMinimum(1)
        self.page_spinbox.valueChanged.connect(self.goto_page)
        layout.addWidget(self.page_spinbox)

        self.page_label = QLabel("/ 0")
        layout.addWidget(self.page_label)

        self.next_btn = QPushButton("▶")
        self.next_btn.clicked.connect(self.next_page)
        layout.addWidget(self.next_btn)

        layout.addWidget(QLabel("Zoom:"))

        # Controlli zoom
        self.zoom_out_btn = QPushButton("-")
        self.zoom_out_btn.clicked.connect(self.zoom_out)
        layout.addWidget(self.zoom_out_btn)

        self.zoom_slider = QSlider(Qt.Orientation.Horizontal)
        self.zoom_slider.setMinimum(25)
        self.zoom_slider.setMaximum(300)
        self.zoom_slider.setValue(100)
        self.zoom_slider.valueChanged.connect(self.set_zoom)
        layout.addWidget(self.zoom_slider)

        self.zoom_in_btn = QPushButton("+")
        self.zoom_in_btn.clicked.connect(self.zoom_in)
        layout.addWidget(self.zoom_in_btn)

        self.zoom_label = QLabel("100%")
        layout.addWidget(self.zoom_label)

        # Pulsanti per evidenziazioni di test
        layout.addWidget(QLabel("|"))

        self.highlight_btn = QPushButton("Evidenzia Test")
        self.highlight_btn.clicked.connect(self.add_test_highlight)
        layout.addWidget(self.highlight_btn)

        self.clear_btn = QPushButton("Pulisci")
        self.clear_btn.clicked.connect(self.clear_highlights)
        layout.addWidget(self.clear_btn)

        layout.addStretch()
        toolbar.setLayout(layout)
        return toolbar

    def mouse_click_man(self, x, y):

        y_scroll_bar = self.scroll_area.verticalScrollBar().value()

        # 3. Calcola la coordinata Y del documento
        y_documento = (y / self.zoom_factor) + y_scroll_bar

        self.mouse_click.emit(x, y, self.current_page)

    def open_pdf(self):
        """Apre un file PDF"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "Apri PDF", "", "PDF files (*.pdf)"
        )

        if file_path:
            self.load_pdf(file_path)

    def load_pdf(self, file_path):
        """Carica un file PDF"""
        try:
            self.pdf_document = fitz.open(file_path)
            self.current_page = 0
            self.page_highlights.clear()  # Reset highlights quando si carica nuovo PDF

            # Aggiorna i controlli
            total_pages = len(self.pdf_document)
            self.page_spinbox.setMaximum(total_pages)
            self.page_spinbox.setValue(1)
            self.page_label.setText(f"/ {total_pages}")

            self.display_page()

        except Exception as e:
            print(f"Errore nel caricamento del PDF: {e}")

    def unload_pdf(self):
        """Scarica e chiude il PDF corrente"""
        try:
            # Chiudi il documento se aperto
            if self.pdf_document is not None:
                self.pdf_document.close()
                self.pdf_document = None

            # Reset delle variabili
            self.current_page = 0
            self.page_highlights.clear()

            # Pulisci la visualizzazione
            self.pdf_page_widget.clear()
            self.pdf_page_widget.current_page_highlights.clear()

            # Disabilita i controlli
            self.update_controls_state(False)

            # Reset dei controlli
            self.page_spinbox.setMaximum(1)
            self.page_spinbox.setValue(1)
            self.page_label.setText("/ 0")
            self.zoom_slider.setValue(100)
            self.zoom_label.setText("100%")
            self.zoom_factor = 1.0

        except Exception as e:
            print(f"Errore nello scaricamento del PDF: {e}")

    def update_controls_state(self, enabled):
        """Abilita/disabilita i controlli in base allo stato del PDF"""
        # Controlli di navigazione
        self.prev_btn.setEnabled(enabled)
        self.next_btn.setEnabled(enabled)
        self.page_spinbox.setEnabled(enabled)

        # Controlli di zoom
        self.zoom_in_btn.setEnabled(enabled)
        self.zoom_out_btn.setEnabled(enabled)
        self.zoom_slider.setEnabled(enabled)

        # Controlli di evidenziazione
        self.highlight_btn.setEnabled(enabled)
        self.scroll_to_btn.setEnabled(enabled)
        self.clear_btn.setEnabled(enabled)

        # Pulsante chiudi PDF
        self.close_btn.setEnabled(enabled)

    def display_page(self):
        """Visualizza la pagina corrente"""
        if self.pdf_document is None:
            return

        try:
            page = self.pdf_document[self.current_page]
            self.pdf_page_widget.set_page(page, self.current_page, self.zoom_factor)

            # Carica gli highlight per questa pagina
            page_highlights = self.page_highlights.get(self.current_page, [])
            self.pdf_page_widget.set_page_highlights(page_highlights)

        except Exception as e:
            print(f"Errore nella visualizzazione della pagina: {e}")

    def prev_page(self):
        """Vai alla pagina precedente"""
        if self.pdf_document and self.current_page > 0:
            self.current_page -= 1
            self.page_spinbox.setValue(self.current_page + 1)
            self.display_page()

    def next_page(self):
        """Vai alla pagina successiva"""
        if self.pdf_document and self.current_page < len(self.pdf_document) - 1:
            self.current_page += 1
            self.page_spinbox.setValue(self.current_page + 1)
            self.display_page()

    def goto_page(self, page_num):
        """Vai a una pagina specifica"""
        if self.pdf_document:
            self.current_page = page_num - 1
            self.display_page()

    def zoom_in(self):
        """Aumenta lo zoom"""
        new_value = min(self.zoom_slider.value() + 25, 300)
        self.zoom_slider.setValue(new_value)

    def zoom_out(self):
        """Diminuisce lo zoom"""
        new_value = max(self.zoom_slider.value() - 25, 25)
        self.zoom_slider.setValue(new_value)

    def set_zoom(self, value):
        """Imposta il livello di zoom"""
        self.zoom_factor = value / 100.0
        self.zoom_label.setText(f"{value}%")
        self.display_page()

    def highlight_text_line(self, page_num, bbox, color=QColor(255, 255, 0, 100)):
        """
        Evidenzia una riga di testo specificando pagina, bounding box e colore

        Args:
            page_num: numero della pagina (0-based)
            bbox: tupla (x0, y0, x1, y1) nelle coordinate della pagina PDF
            color: QColor per l'evidenziazione (default: giallo trasparente)
        """
        if self.pdf_document is None:
            print("Nessun PDF caricato")
            return

        if page_num < 0 or page_num >= len(self.pdf_document):
            print(f"Numero pagina non valido: {page_num}")
            return

        # Aggiungi l'highlight al dizionario della pagina specifica
        self.page_highlights = {}
        self.clear_all_highlights()
        if page_num not in self.page_highlights:
            self.page_highlights[page_num] = []

        self.page_highlights[page_num].append((bbox, color))

        if page_num != self.current_page:
            self.goto_page(page_num + 1)
        self.scroll_to_bbox(bbox)

        # Se stiamo visualizzando questa pagina, aggiorna la visualizzazione
        if page_num == self.current_page:
            self.pdf_page_widget.add_highlight(bbox, color)

    def clear_page_highlights(self, page_num=None):
        """
        Rimuove le evidenziazioni da una pagina specifica o dalla pagina corrente

        Args:
            page_num: numero della pagina (0-based). Se None, usa la pagina corrente
        """
        if page_num is None:
            page_num = self.current_page

        if page_num in self.page_highlights:
            del self.page_highlights[page_num]

        # Se stiamo visualizzando questa pagina, aggiorna la visualizzazione
        if page_num == self.current_page:
            self.pdf_page_widget.clear_highlights()

    def clear_all_highlights(self):
        """Rimuove tutte le evidenziazioni da tutte le pagine"""
        self.page_highlights.clear()
        self.pdf_page_widget.clear_highlights()

    def get_page_highlights(self, page_num):
        """
        Restituisce gli highlight di una pagina specifica

        Args:
            page_num: numero della pagina (0-based)

        Returns:
            Lista di (bbox, color) per la pagina specificata
        """
        return self.page_highlights.get(page_num, [])

    def add_test_highlight(self):
        """Aggiunge un'evidenziazione di test alla pagina corrente"""
        if self.pdf_document is None:
            return

        # Esempio di evidenziazione - dovrai adattare le coordinate
        # alle tue esigenze specifiche
        test_bbox = (100, 200, 400, 220)  # (x0, y0, x1, y1)
        test_color = QColor(255, 255, 0, 100)  # Giallo trasparente

        self.highlight_text_line(self.current_page, test_bbox, test_color)

        # Aggiungi un secondo highlight di test in rosso
        test_bbox2 = (100, 240, 350, 260)
        test_color2 = QColor(255, 0, 0, 100)  # Rosso trasparente
        self.highlight_text_line(self.current_page, test_bbox2, test_color2)

    def clear_highlights(self):
        """Rimuove tutte le evidenziazioni della pagina corrente"""
        self.clear_page_highlights()

    def scroll_to_bbox(self, bbox):
        """
        Fa scroll per assicurarsi che una bbox sia visibile nell'area di visualizzazione

        Args:
            bbox: tupla (x0, y0, x1, y1) nelle coordinate della pagina PDF corrente
        """
        if self.pdf_document is None:
            return

        # Scala la bbox in base al zoom factor corrente
        scaled_bbox = (
            bbox[0] * self.zoom_factor,
            bbox[1] * self.zoom_factor,
            bbox[2] * self.zoom_factor,
            bbox[3] * self.zoom_factor
        )

        x0, y0, x1, y1 = scaled_bbox

        # Calcola il centro della bbox
        bbox_center_x = (x0 + x1) / 2
        bbox_center_y = (y0 + y1) / 2

        # Dimensioni dell'area visibile del scroll area
        viewport = self.scroll_area.viewport()
        visible_width = viewport.width()
        visible_height = viewport.height()

        # Dimensioni totali del widget della pagina
        page_widget_size = self.pdf_page_widget.size()
        total_width = page_widget_size.width()
        total_height = page_widget_size.height()

        # Se il widget della pagina è più piccolo dell'area visibile, non serve fare scroll
        if total_width <= visible_width and total_height <= visible_height:
            return

        # Calcola la posizione del scroll per centrare la bbox
        # Consideriamo anche l'offset per centrare il widget nell'area di scroll
        widget_offset_x = max(0, (visible_width - total_width) / 2)
        widget_offset_y = max(0, (visible_height - total_height) / 2)

        # Posizione target per centrare la bbox
        target_x = bbox_center_x + widget_offset_x - visible_width / 2
        target_y = bbox_center_y + widget_offset_y - visible_height / 2

        # Limita i valori di scroll ai range validi
        scrollbar_h = self.scroll_area.horizontalScrollBar()
        scrollbar_v = self.scroll_area.verticalScrollBar()

        max_scroll_x = scrollbar_h.maximum()
        max_scroll_y = scrollbar_v.maximum()

        target_x = max(0, min(target_x, max_scroll_x))
        target_y = max(0, min(target_y, max_scroll_y))

        # Esegui il scroll
        scrollbar_h.setValue(int(target_x))
        scrollbar_v.setValue(int(target_y))

    def scroll_to_highlight(self, page_num, highlight_index=0):
        """
        Fa scroll per mostrare uno specifico highlight su una pagina

        Args:
            page_num: numero della pagina (0-based)
            highlight_index: indice dell'highlight nella lista della pagina (default: 0)
        """
        if page_num not in self.page_highlights:
            print(f"Nessun highlight trovato nella pagina {page_num}")
            return

        highlights = self.page_highlights[page_num]
        if highlight_index >= len(highlights):
            print(f"Indice highlight non valido: {highlight_index}")
            return

        # Se non stiamo visualizzando la pagina corretta, vai a quella pagina
        if page_num != self.current_page:
            self.current_page = page_num
            self.page_spinbox.setValue(page_num + 1)
            self.display_page()

        # Ottieni la bbox dell'highlight e fai scroll
        bbox, _ = highlights[highlight_index]
        self.scroll_to_bbox(bbox)


class MainWindow(QMainWindow):
    """Finestra principale dell'applicazione"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("PDF Viewer con Evidenziazione")
        self.setGeometry(100, 100, 1000, 700)

        # Widget principale
        self.pdf_viewer = PDFViewer()
        self.setCentralWidget(self.pdf_viewer)


def main():
    app = QApplication(sys.argv)

    window = MainWindow()
    window.show()

    # Esempio di come utilizzare l'evidenziazione programmaticamente
    # Carica un PDF e poi chiama:
    # window.pdf_viewer.highlight_text_line(page_num, (x0, y0, x1, y1), QColor(255, 0, 0, 100))
    #
    # Esempi:
    # window.pdf_viewer.highlight_text_line(0, (100, 200, 400, 220))  # Pagina 1, giallo
    # window.pdf_viewer.highlight_text_line(1, (150, 300, 450, 320), QColor(0, 255, 0, 100))  # Pagina 2, verde

    sys.exit(app.exec())


if __name__ == "__main__":
    main()