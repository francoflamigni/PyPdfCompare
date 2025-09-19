import fitz  # PyMuPDF
import os
import re
from typing import List, Tuple
import numpy as np

def extract_text_lines_from_pdf(pdf_path, line_height_tolerance=2.0, y_overlap_threshold=0.5):
    """
    Estrae righe di testo da un PDF OCR, ricostruendo le righe anche quando
    sono composte da più span o blocchi.

    Args:
        pdf_path (str): Percorso del file PDF
        line_height_tolerance (float): Tolleranza per raggruppare span sulla stessa riga (punti)
        y_overlap_threshold (float): Soglia di sovrapposizione verticale per considerare span sulla stessa riga

    Returns:
        list: Lista di dizionari con 'text', 'bbox', 'page' per ogni riga
    """

    def spans_on_same_line(span1, span2, tolerance=line_height_tolerance):
        """
        Determina se due span sono sulla stessa riga di testo
        """
        bbox1 = span1['bbox']
        bbox2 = span2['bbox']

        # Calcola l'altezza delle bbox
        height1 = bbox1[3] - bbox1[1]
        height2 = bbox2[3] - bbox2[1]

        # Calcola l'overlap verticale
        y_overlap = min(bbox1[3], bbox2[3]) - max(bbox1[1], bbox2[1])
        min_height = min(height1, height2)

        # Se c'è un overlap significativo o le bbox sono molto vicine verticalmente
        overlap_ratio = y_overlap / min_height if min_height > 0 else 0
        vertical_distance = abs((bbox1[1] + bbox1[3]) / 2 - (bbox2[1] + bbox2[3]) / 2)

        return (overlap_ratio > y_overlap_threshold or
                vertical_distance <= tolerance)

    def merge_bbox(bbox1, bbox2):
        """
        Unisce due bounding box
        """
        return (
            min(bbox1[0], bbox2[0]),  # x0
            min(bbox1[1], bbox2[1]),  # y0
            max(bbox1[2], bbox2[2]),  # x1
            max(bbox1[3], bbox2[3])  # y1
        )

    def group_spans_into_lines(spans):
        """
        Raggruppa gli span in righe di testo
        """
        if not spans:
            return []

        # Ordina gli span per posizione verticale, poi orizzontale
        sorted_spans = sorted(spans, key=lambda s: (s['bbox'][1], s['bbox'][0]))

        lines = []
        current_line_spans = [sorted_spans[0]]

        for span in sorted_spans[1:]:
            # Controlla se questo span appartiene alla riga corrente
            belongs_to_current_line = False

            for existing_span in current_line_spans:
                if spans_on_same_line(span, existing_span):
                    belongs_to_current_line = True
                    break

            if belongs_to_current_line:
                current_line_spans.append(span)
            else:
                # Finalizza la riga corrente
                if current_line_spans:
                    lines.append(current_line_spans)
                current_line_spans = [span]

        # Aggiungi l'ultima riga
        if current_line_spans:
            lines.append(current_line_spans)

        return lines

    def create_line_from_spans(line_spans):
        """
        Crea una riga di testo da un gruppo di span
        """
        if not line_spans:
            return None

        # Ordina gli span per posizione orizzontale
        sorted_spans = sorted(line_spans, key=lambda s: s['bbox'][0])

        # Costruisci il testo della riga
        text_parts = []
        line_bbox = sorted_spans[0]['bbox']

        prev_span_end = None

        for i, span in enumerate(sorted_spans):
            span_text = span['text'].strip()
            span_bbox = span['bbox']

            # Unisci le bounding box
            line_bbox = merge_bbox(line_bbox, span_bbox)

            if span_text:  # Solo se lo span ha del testo
                # Aggiungi spazi tra span se necessario
                if (prev_span_end is not None and
                        span_bbox[0] > prev_span_end + 5):  # Gap di più di 5 punti
                    text_parts.append(' ')

                text_parts.append(span_text)
                prev_span_end = span_bbox[2]

        clean_parts = [part.strip() for part in text_parts if part.strip()]
        text = ' '.join(clean_parts).strip()

        if not text:  # Se non c'è testo significativo
            return None

        return {
            'text': text,
            'bbox': line_bbox,
            'spans_count': len(line_spans)
        }

    # Inizializza il risultato
    all_lines = []

    try:
        # Apri il documento PDF
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]

            # Estrai il testo con informazioni dettagliate
            text_dict = page.get_text("dict")

            # Raccogli tutti gli span da tutti i blocchi
            page_spans = []

            for block in text_dict["blocks"]:
                if "lines" in block:  # Blocco di testo
                    for line in block["lines"]:
                        for span in line["spans"]:
                            if span["text"].strip():  # Solo span con testo
                                page_spans.append({
                                    'text': span["text"],
                                    'bbox': span["bbox"],
                                    'size': span["size"],
                                    'font': span["font"]
                                })

            # Raggruppa gli span in righe
            text_lines = group_spans_into_lines(page_spans)

            # Converti ogni gruppo di span in una riga finale
            for line_spans in text_lines:
                line_data = create_line_from_spans(line_spans)
                if line_data:
                    all_lines.append({
                        'text': line_data['text'],
                        'bbox': line_data['bbox'],
                        'page': page_num + 1  # Numerazione pagine da 1
                    })

        doc.close()

    except Exception as e:
        print(f"Errore nell'elaborazione del PDF: {e}")
        return []

    return all_lines


def trova_prima_nota_per_pagina(interlinee: List[float],
                                header_lines: int = 5,
                                min_text_lines: int = 5,
                                threshold_multiplier: float = 1.2) -> List[int]:
    """
    Trova l'indice della prima nota per ogni pagina di un documento PDF.

    Args:
        interlinee: Lista dei valori di interlinea
        header_lines: Numero di righe di header da scartare all'inizio di ogni pagina
        min_text_lines: Numero minimo di righe di testo principale prima delle note
        threshold_multiplier: Moltiplicatore per determinare il salto significativo

    Returns:
        Lista con gli indici della prima nota per ogni pagina (-1 se non trovata)
    """

    # Trova gli indici delle nuove pagine (dove interlinea = 0)
    indici_pagine = [i for i, val in enumerate(interlinee) if val == 0]
    indici_pagine.append(len(interlinee))  # Aggiungi fine documento

    risultati = []

    for i in range(len(indici_pagine) - 1):
        inizio_pagina = indici_pagine[i]
        fine_pagina = indici_pagine[i + 1]

        # Estrai interlinee della pagina corrente (escludendo lo 0 iniziale)
        pagina_interlinee = interlinee[inizio_pagina + 1:fine_pagina]

        if len(pagina_interlinee) <= header_lines + min_text_lines:
            risultati.append(-1)  # Pagina troppo corta
            continue

        # Scarta le righe di header
        testo_interlinee = pagina_interlinee[header_lines:]

        # Calcola l'interlinea mediana del testo principale
        # Usa i primi min_text_lines per evitare di includere le note
        if len(testo_interlinee) < min_text_lines:
            risultati.append(-1)
            continue

        campione_testo = testo_interlinee[:min_text_lines]
        interlinea_mediana = np.median(campione_testo)

        # Cerca il punto dove iniziano le note
        # Cerchiamo un salto significativo seguito da interlinee più piccole
        prima_nota_idx = -1

        for j in range(min_text_lines, len(testo_interlinee) - 2):
            current_val = testo_interlinee[j]

            # Controlla se c'è un salto significativo
            if current_val > interlinea_mediana * threshold_multiplier:
                # Controlla se le righe successive hanno interlinea minore
                # (caratteristica delle note)
                righe_successive = testo_interlinee[j + 1:j + 4]  # Guarda le prossime 3 righe
                prima_nota_idx = inizio_pagina + header_lines + j + 1
                break

        risultati.append(prima_nota_idx)

    return risultati


def analizza_struttura_documento(interlinee: List[float]) -> None:
    """
    Funzione di utilità per analizzare la struttura del documento.
    """
    indici_pagine = [i for i, val in enumerate(interlinee) if val == 0]

    print(f"Documento con {len(indici_pagine)} pagine")
    print(f"Totale righe: {len(interlinee)}")

    for i, idx in enumerate(indici_pagine):
        fine = indici_pagine[i + 1] if i + 1 < len(indici_pagine) else len(interlinee)
        righe_pagina = fine - idx - 1
        print(f"Pagina {i + 1}: righe {idx} to {fine - 1} ({righe_pagina} righe)")

        if righe_pagina > 5:
            pagina_vals = interlinee[idx + 1:fine]
            print(f"  Interlinea min: {min(pagina_vals):.2f}")
            print(f"  Interlinea max: {max(pagina_vals):.2f}")
            print(f"  Interlinea media: {np.mean(pagina_vals):.2f}")


def remove_notes(blocks):
    interlinea = []
    current = -1
    page_star_line = []
    for i, block in enumerate(blocks):
        if block['page'] != current:
            current = block['page']
            interlinea.append(0)
            page_star_line.append(i)
            continue
        interlinea.append(blocks[i]['bbox'][1] - blocks[i - 1]['bbox'][1])
    page_star_line.append(len(blocks))
    for i in range(len(interlinea)):
        print(interlinea[i])

    res = trova_prima_nota_per_pagina(interlinea)
    new_blocks = []
    i0 = page_star_line[0]
    for i, st in enumerate(res):
        i0 = page_star_line[i]
        new_blocks.extend(blocks[i0: st])

    return new_blocks