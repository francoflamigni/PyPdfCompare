import fitz  # PyMuPDF
import os
import re
from collections import Counter


def analyze_font_sizes(pdf_path):
    """
    Analizza le dimensioni dei font nel PDF per identificare
    la soglia tra testo principale e note a piè di pagina.
    """
    doc = fitz.open(pdf_path)
    font_sizes = []
    font_info = {}

    for page_num in range(len(doc)):
        page = doc[page_num]
        try:
            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" in block:  # Blocco di testo
                    for line in block["lines"]:
                        for span in line["spans"]:
                            size = round(span["size"], 1)
                            font_sizes.append(size)

                            # Raccoglie info sui font
                            font_name = span.get("font", "Unknown")
                            if size not in font_info:
                                font_info[size] = set()
                            font_info[size].add(font_name)
        except Exception as e:
            print(f"Errore nell'analisi della pagina {page_num + 1}: {e}")
            continue

    doc.close()

    # Conta le occorrenze di ogni dimensione
    size_counts = Counter(font_sizes)
    print("Dimensioni font trovate:")
    for size, count in sorted(size_counts.items(), reverse=True):
        fonts = ", ".join(list(font_info.get(size, {"Unknown"}))[:3])  # Max 3 font names
        print(f"  {size}pt: {count} occorrenze (font: {fonts})")

    return size_counts


def extract_text_without_footnotes_robust(pdf_path, min_font_size=10.0,
                                          position_threshold=None,
                                          save_to_file=None,
                                          analyze_first=True,
                                          remove_line_numbers=True):
    """
    Versione robusta che estrae il testo senza ricostruire font,
    evitando l'errore "need font file or buffer".

    Args:
        pdf_path (str): Percorso del PDF
        min_font_size (float): Dimensione minima del font da includere
        position_threshold (float): Soglia posizione verticale (None per disabilitare)
        save_to_file (str): Percorso file di output (None per solo stampa)
        analyze_first (bool): Se analizzare prima le dimensioni dei font
        remove_line_numbers (bool): Se rimuovere numeri di riga (comuni nei testi accademici)

    Returns:
        str: Testo estratto
    """

    if analyze_first:
        print("=== ANALISI DIMENSIONI FONT ===")
        analyze_font_sizes(pdf_path)
        print(f"\n=== ESTRAZIONE TESTO (font >= {min_font_size}pt) ===")
        if position_threshold:
            print(f"Escludo anche testo nella parte inferiore (> {position_threshold} dell'altezza pagina)")

    doc = fitz.open(pdf_path)
    extracted_text = []

    stats = {
        'pages_processed': 0,
        'spans_kept': 0,
        'spans_removed': 0,
        'removed_by_font': 0,
        'removed_by_position': 0,
        'errors': 0
    }

    for page_num in range(len(doc)):
        page = doc[page_num]

        try:
            page_height = page.rect.height if position_threshold else None

            # Aggiungi separatore pagina
            if page_num > 0:
                extracted_text.append(f"\n\n=== PAGINA {page_num + 1} ===\n\n")
            else:
                extracted_text.append(f"=== PAGINA {page_num + 1} ===\n\n")

            blocks = page.get_text("dict")["blocks"]

            for block in blocks:
                if "lines" not in block:  # Salta blocchi non testuali
                    continue

                # Analizza il blocco per decidere se mantenerlo
                block_font_sizes = []
                block_positions = []
                block_text_parts = []

                for line in block["lines"]:
                    for span in line["spans"]:
                        span_size = round(span["size"], 1)
                        block_font_sizes.append(span_size)

                        if page_height:
                            span_y = (span["bbox"][1] + span["bbox"][3]) / 2
                            block_positions.append(span_y / page_height)

                # Calcola statistiche del blocco
                if not block_font_sizes:
                    continue

                avg_font_size = sum(block_font_sizes) / len(block_font_sizes)
                max_font_size = max(block_font_sizes)

                avg_position = sum(block_positions) / len(block_positions) if block_positions else 0

                # Decidi se mantenere il blocco
                keep_block = True
                removal_reason = None

                # Filtro per dimensione font
                if max_font_size < min_font_size:
                    keep_block = False
                    removal_reason = "font"

                # Filtro per posizione (solo se il font è piccolo)
                elif position_threshold and avg_position > position_threshold and avg_font_size < (min_font_size + 1):
                    keep_block = False
                    removal_reason = "position"

                if keep_block:
                    # Estrai il testo del blocco mantenuto
                    block_text = []
                    for line in block["lines"]:
                        line_text = ""
                        for span in line["spans"]:
                            if round(span["size"], 1) >= min_font_size:
                                line_text += span["text"]
                        if line_text.strip():
                            block_text.append(line_text)

                    if block_text:
                        # Unisci le righe del blocco
                        full_block_text = " ".join(block_text).strip()

                        # Pulisci il testo se richiesto
                        if remove_line_numbers:
                            full_block_text = clean_academic_text(full_block_text)

                        if full_block_text:
                            extracted_text.append(full_block_text + "\n")
                            stats['spans_kept'] += len(block_font_sizes)
                else:
                    stats['spans_removed'] += len(block_font_sizes)
                    if removal_reason == "font":
                        stats['removed_by_font'] += len(block_font_sizes)
                    elif removal_reason == "position":
                        stats['removed_by_position'] += len(block_font_sizes)

            stats['pages_processed'] += 1
            print(f"Pagina {page_num + 1} elaborata")

        except Exception as e:
            print(f"Errore nell'elaborazione della pagina {page_num + 1}: {e}")
            stats['errors'] += 1
            continue

    doc.close()

    # Unisci tutto il testo e post-processa
    final_text = "".join(extracted_text)
    final_text = post_process_text(final_text)

    # Salva su file se richiesto
    if save_to_file:
        try:
            with open(save_to_file, 'w', encoding='utf-8') as f:
                f.write(final_text)
            print(f"\nTesto salvato in: {save_to_file}")
        except Exception as e:
            print(f"Errore nel salvare il file: {e}")

    # Stampa statistiche
    print(f"\n=== STATISTICHE ===")
    print(f"Pagine elaborate: {stats['pages_processed']}")
    print(f"Errori: {stats['errors']}")
    print(f"Porzioni di testo mantenute: {stats['spans_kept']}")
    print(f"Porzioni di testo rimosse: {stats['spans_removed']}")
    if stats['removed_by_font'] > 0:
        print(f"  - Rimosse per dimensione font: {stats['removed_by_font']}")
    if stats['removed_by_position'] > 0:
        print(f"  - Rimosse per posizione: {stats['removed_by_position']}")

    print(f"Caratteri totali estratti: {len(final_text)}")

    return final_text


def clean_academic_text(text):
    """
    Pulisce il testo da elementi tipici di testi accademici/critici.
    """
    # Rimuovi numeri di riga isolati (es. "5", "10", "15" all'inizio di riga)
    text = re.sub(r'^\s*\d{1,3}\s*$', '', text, flags=re.MULTILINE)

    # Rimuovi numeri di riga all'inizio di righe (es. "5 INTENTIQVE")
    text = re.sub(r'^\s*\d{1,3}\s+(?=[A-Z])', '', text, flags=re.MULTILINE)

    # Rimuovi riferimenti a pagine isolati (es. "212", "213")
    text = re.sub(r'^\s*\d{3,}\s*$', '', text, flags=re.MULTILINE)

    # Rimuovi linee che contengono solo caratteri speciali o punteggiatura
    text = re.sub(r'^[^\w\s]*$', '', text, flags=re.MULTILINE)

    return text


def post_process_text(text):
    """
    Post-processa il testo estratto per migliorare la leggibilità.
    """
    # Rimuovi righe vuote eccessive
    text = re.sub(r'\n\s*\n\s*\n', '\n\n', text)

    # Correggi spazi multipli
    text = re.sub(r' +', ' ', text)

    # Rimuovi spazi all'inizio e fine delle righe
    lines = text.split('\n')
    lines = [line.strip() for line in lines]
    text = '\n'.join(lines)

    return text


def extract_text_by_patterns(pdf_path, save_to_file=None):
    """
    Alternativa che usa pattern per identificare e rimuovere le note.
    Utile quando l'analisi dei font non è sufficiente.
    """
    doc = fitz.open(pdf_path)
    extracted_text = []

    footnote_patterns = [
        r'^\s*\d{1,2}\s+[a-z]',  # Note che iniziano con numero + lettera minuscola
        r'^\s*\|\|',  # Note che iniziano con ||
        r'^\s*\d+\s*$',  # Righe che contengono solo numeri
        r'cf\.\s+',  # Riferimenti (cf.)
        r'exscr\.',  # Excerpta
        r'vulgo:',  # Varianti
    ]

    for page_num in range(len(doc)):
        page = doc[page_num]

        try:
            # Estrai testo semplice
            text = page.get_text()
            lines = text.split('\n')

            # Filtra le righe
            filtered_lines = []
            for line in lines:
                line = line.strip()
                if not line:
                    continue

                # Controlla se la riga corrisponde a pattern di note
                is_footnote = False
                for pattern in footnote_patterns:
                    if re.search(pattern, line):
                        is_footnote = True
                        break

                if not is_footnote and len(line) > 3:  # Mantieni solo righe significative
                    filtered_lines.append(line)

            if filtered_lines:
                extracted_text.append(f"\n=== PAGINA {page_num + 1} ===\n")
                extracted_text.extend([line + '\n' for line in filtered_lines])

        except Exception as e:
            print(f"Errore nella pagina {page_num + 1}: {e}")
            continue

    doc.close()

    final_text = ''.join(extracted_text)
    final_text = post_process_text(final_text)

    if save_to_file:
        with open(save_to_file, 'w', encoding='utf-8') as f:
            f.write(final_text)

    return final_text


def interactive_extraction(pdf_path):
    """
    Modalità interattiva robusta per l'estrazione del testo.
    """
    if not os.path.exists(pdf_path):
        print(f"Errore: File {pdf_path} non trovato!")
        return None

    print("=== ESTRATTORE DI TESTO SENZA NOTE (Versione Robusta) ===\n")

    # Analizza le dimensioni dei font
    print("Analizzando il documento...")
    try:
        font_analysis = analyze_font_sizes(pdf_path)

        # Suggerisci una soglia
        sorted_sizes = sorted(font_analysis.keys(), reverse=True)
        if len(sorted_sizes) >= 2:
            suggested_threshold = sorted_sizes[1]  # Seconda dimensione più comune
        else:
            suggested_threshold = 10.0

        print(f"\nSoglia suggerita: {suggested_threshold}pt")

    except Exception as e:
        print(f"Errore nell'analisi: {e}")
        suggested_threshold = 10.0
        print(f"Usando soglia di default: {suggested_threshold}pt")

    # Scegli il metodo
    print("\nMetodi disponibili:")
    print("1. Estrazione basata su dimensione font (raccomandato)")
    print("2. Estrazione basata su pattern di testo")

    method = '2' #input("Scegli il metodo (1 o 2, default: 1): ").strip()

    if method == "2":
        print("\nUsando estrazione basata su pattern...")
        text = extract_text_by_patterns(pdf_path)
    else:
        # Input utente per soglia font
        try:
            user_threshold = input(f"Dimensione minima font da mantenere (default: {suggested_threshold}): ")
            if user_threshold.strip():
                font_threshold = float(user_threshold)
            else:
                font_threshold = suggested_threshold
        except ValueError:
            font_threshold = suggested_threshold

        font_threshold = 6

        # Input per filtri aggiuntivi
        '''
        use_position = input("Escludere testo nella parte inferiore delle pagine? (s/n, default: n): ")
        position_threshold = None
        if use_position.lower().startswith('s'):
            try:
                pos_input = input("Soglia posizione (0.8 = escludi ultimo 20%, default: 0.8): ")
                position_threshold = float(pos_input.strip()) if pos_input.strip() else 0.8
            except ValueError:
                position_threshold = 0.8
        '''

        remove_numbers = input("Rimuovere numeri di riga? (s/n, default: s): ")
        clean_text = True #not remove_numbers.lower().startswith('n')

        # Input per salvare su file
        save_file = input("Nome file per salvare (premi Enter per solo visualizzazione): ")
        if not save_file.strip():
            save_file = None

        # Estrai il testo
        print("\n" + "=" * 50)
        text = extract_text_without_footnotes_robust(
            pdf_path,
            min_font_size=font_threshold,
            position_threshold=position_threshold,
            save_to_file=save_file,
            analyze_first=False,
            remove_line_numbers=clean_text
        )

    # Mostra un'anteprima
    print(f"\n=== ANTEPRIMA TESTO ESTRATTO ===")
    preview = text[:1500]  # Prime 1500 caratteri
    print(preview)
    if len(text) > 1500:
        print(f"\n... (e altri {len(text) - 1500} caratteri)")

    return text


'''
********************************************************************
'''

import fitz  # PyMuPDF
from collections import defaultdict
import re


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


def extract_text_lines_simple(pdf_path):
    """
    Versione semplificata che usa direttamente le righe già identificate da PyMuPDF
    Utile per PDF con OCR di buona qualità
    """
    all_lines = []

    try:
        doc = fitz.open(pdf_path)

        for page_num in range(len(doc)):
            page = doc[page_num]
            text_dict = page.get_text("dict")

            for block in text_dict["blocks"]:
                if "lines" in block:  # Blocco di testo
                    for line in block["lines"]:
                        # Combina tutti gli span della riga
                        line_text_parts = []
                        line_bbox = None

                        for span in line["spans"]:
                            span_text = span["text"].strip()
                            if span_text:
                                line_text_parts.append(span_text)

                                # Calcola/aggiorna la bbox della riga
                                if line_bbox is None:
                                    line_bbox = list(span["bbox"])
                                else:
                                    line_bbox[0] = min(line_bbox[0], span["bbox"][0])  # x0
                                    line_bbox[1] = min(line_bbox[1], span["bbox"][1])  # y0
                                    line_bbox[2] = max(line_bbox[2], span["bbox"][2])  # x1
                                    line_bbox[3] = max(line_bbox[3], span["bbox"][3])  # y1

                        # Se la riga ha del testo
                        if line_text_parts and line_bbox:
                            combined_text = ' '.join(line_text_parts).strip()
                            if combined_text:
                                all_lines.append({
                                    'text': combined_text,
                                    'bbox': tuple(line_bbox),
                                    'page': page_num + 1
                                })

        doc.close()

    except Exception as e:
        print(f"Errore nell'elaborazione del PDF: {e}")
        return []

    return all_lines


def print_text_lines_sample(text_lines, max_lines=10):
    """
    Stampa un campione delle righe estratte per verifica
    """
    print(f"Estratte {len(text_lines)} righe di testo totali")
    print(f"Prime {min(max_lines, len(text_lines))} righe:\n")

    for i, line in enumerate(text_lines[:max_lines]):
        bbox = line['bbox']
        print(f"Riga {i + 1} (Pagina {line['page']}):")
        print(f"  Testo: '{line['text'][:100]}{'...' if len(line['text']) > 100 else ''}'")
        print(f"  BBox: ({bbox[0]:.1f}, {bbox[1]:.1f}, {bbox[2]:.1f}, {bbox[3]:.1f})")
        print()


# Esempio di utilizzo
def proc_pdf(pdf_path):
    # Percorso del PDF da analizzare
    #pdf_path = "example.pdf"  # Sostituisci con il tuo percorso

    print("Metodo avanzato (ricostruzione righe):")
    lines_advanced = extract_text_lines_from_pdf(pdf_path)
    return lines_advanced
    print_text_lines_sample(lines_advanced)

    print("\n" + "=" * 50 + "\n")

    print("Metodo semplice (righe PyMuPDF):")
    lines_simple = extract_text_lines_simple(pdf_path)
    print_text_lines_sample(lines_simple)

    # Esempio di come salvare i risultati
    # import json
    # with open('extracted_lines.json', 'w', encoding='utf-8') as f:
    #     json.dump(lines_advanced, f, ensure_ascii=False, indent=2)