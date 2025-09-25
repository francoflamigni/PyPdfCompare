from PyQt6.QtCore import pyqtSignal
from PyQt6.QtGui import QTextCursor, QTextCharFormat, QColor, QMouseEvent
from PyQt6.QtWidgets import QTextEdit


txt_colors = [
    '#FFFF99',  # Giallo chiaro (lightyellow) - classico per evidenziazione
    '#FFB3BA',  # Rosa chiaro - delicato e visibile
    '#BAFFC9',  # Verde chiaro - fresco e rilassante
    '#BAE1FF',  # Azzurro chiaro - professionale
    '#E6B3FF'   # Viola chiaro - distintivo ma delicato
]

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
        #self.highlight_line(cursor)
        self.lineClicked.emit(line_number)

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


    def highlight_character_at(self, line_number: int, position: int, count=1, icol=0):
        """
        Evidenzia caratteri in un QTextEdit.

        Args:
            line_number (int): Il numero della riga (base 1).
            position (int): La posizione del carattere nella riga (base 0).
            count (int): Numero di caratteri da evidenziare.
            color (str): Colore di evidenziazione.

        Returns:
            bool: True se l'evidenziazione è avvenuta con successo, False altrimenti.
        """

        try:
            # Validazione input
            if line_number < 1:
                return False
            if position < 0 or count < 1:
                return False

            # Crea un nuovo cursore per la formattazione
            cursor = QTextCursor(self.document())

            # Sposta alla riga desiderata
            cursor.movePosition(QTextCursor.MoveOperation.Start)

            # Verifica che la riga esista
            total_blocks = self.document().blockCount()
            if line_number > total_blocks:
                return False

            cursor.movePosition(QTextCursor.MoveOperation.NextBlock,
                                QTextCursor.MoveMode.MoveAnchor,
                                line_number)

            # Verifica che la posizione sia valida nella riga
            current_block = cursor.block()
            block_length = len(current_block.text())
            if position >= block_length:
                return False

            # Calcola il numero effettivo di caratteri da evidenziare
            # (non oltre la fine della riga)
            actual_count = min(count, block_length - position)
            if actual_count <= 0:
                return False

            # Sposta alla posizione e seleziona
            cursor.movePosition(QTextCursor.MoveOperation.Right,
                                QTextCursor.MoveMode.MoveAnchor,
                                position)

            cursor.movePosition(QTextCursor.MoveOperation.Right,
                                QTextCursor.MoveMode.KeepAnchor,
                                actual_count)

            # Applica la formattazione
            format = QTextCharFormat()
            color = txt_colors[icol]
            format.setBackground(QColor(color))
            cursor.setCharFormat(format)

            # Posiziona il cursore principale senza selezione
            main_cursor = self.textCursor()
            main_cursor.setPosition(cursor.selectionEnd())
            self.setTextCursor(main_cursor)
            self.ensureCursorVisible()

            return True

        except Exception as e:
            print(f"Errore nell'evidenziazione: {e}")
            return False