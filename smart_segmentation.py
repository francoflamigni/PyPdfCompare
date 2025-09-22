import fitz  # PyMuPDF
import re
from typing import List, Dict, Tuple
from collections import Counter
import json
import numpy as np

class PDFTextSegmenter:
    def __init__(self):
        self.segments = []

    def detect_text_type(self, text_blocks: List[Dict]) -> str:
        """
        Rileva se il testo è prevalentemente prosa o poesia basandosi su:
        - Lunghezza media delle righe
        - Distribuzione delle lunghezze
        - Pattern di fine riga
        """
        if not text_blocks:
            return "prose"

        lines = []
        for block in text_blocks:
            block_lines = block['text'].strip().split('\n')
            lines.extend([line.strip() for line in block_lines if line.strip()])

        if not lines:
            return "prose"

        # Calcola metriche
        line_lengths = [len(line) for line in lines]
        avg_length = sum(line_lengths) / len(line_lengths)

        # Conta righe corte vs lunghe
        short_lines = sum(1 for length in line_lengths if length < 50)
        long_lines = sum(1 for length in line_lengths if length > 80)

        # Score per poesia
        poetry_score = 0
        prose_score = 0

        # Linee corte suggeriscono poesia
        if avg_length < 60:
            poetry_score += 2
        elif avg_length > 90:
            prose_score += 2

        # Rapporto righe corte/lunghe
        if short_lines > long_lines * 1.5:
            poetry_score += 2
        elif long_lines > short_lines:
            prose_score += 1

        # Verifica pattern di fine riga (poesia spesso non finisce con punteggiatura)
        lines_without_punct = sum(1 for line in lines if not re.search(r'[.!?;,]$', line))
        if lines_without_punct > len(lines) * 0.3:
            poetry_score += 1

        # Verifica presenza di possibili rime (semplificato)
        word_endings = []
        for line in lines[:20]:  # Controlla solo le prime 20 righe per performance
            words = line.split()
            if words:
                last_word = re.sub(r'[^\w]', '', words[-1]).lower()
                if len(last_word) >= 3:
                    word_endings.append(last_word[-2:])  # Ultime 2 lettere

        if word_endings:
            ending_counts = Counter(word_endings)
            # Se ci sono terminazioni ripetute, potrebbe essere poesia
            repeated_endings = sum(1 for count in ending_counts.values() if count > 1)
            if repeated_endings > len(set(word_endings)) * 0.3:
                poetry_score += 1

        return "poetry" if poetry_score > prose_score else "prose"

    def merge_bboxes(self, bboxes: List[Tuple[float, float, float, float]]) -> Tuple[float, float, float, float]:
        """Unisce multiple bounding boxes in una singola"""
        if not bboxes:
            return (0, 0, 0, 0)

        x0 = min(bbox[0] for bbox in bboxes)
        y0 = min(bbox[1] for bbox in bboxes)
        x1 = max(bbox[2] for bbox in bboxes)
        y1 = max(bbox[3] for bbox in bboxes)

        return (x0, y0, x1, y1)

    def normalize_text(self, text: str) -> str:
        """
        Normalizza il testo per il confronto
        """
        import re
        # Rimuovi spazi multipli e normalizza
        text = re.sub(r'\s+', ' ', text.strip())
        # Rimuovi punteggiatura per confronto più flessibile
        text = re.sub(r'[^\w\s]', '', text)
        return text.lower()

    def segment_poetry(self, text_blocks: List[Dict]) -> List[Dict]:
        """Segmenta il testo poetico per versi"""
        segments = []
        segment_id = 1

        for block in text_blocks:
            lines = [block['text'].replace('\n', ' ')]
            #lines = block['text'].strip().split('\n')
            page_num = block['page']

            # Per la poesia, ogni riga è un potenziale verso
            current_verse = ""
            current_bboxes = []

            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    # Riga vuota: se abbiamo testo accumulato, chiudi il verso
                    if current_verse:
                        segments.append({
                            'id': segment_id,
                            'text': self.normalize_text(current_verse),
                            'original': current_verse,
                            'type': 'verse',
                            'page': page_num,
                            'bbox': self.merge_bboxes(current_bboxes)
                        })
                        segment_id += 1
                        current_verse = ""
                        current_bboxes = []
                    continue

                # Se la riga è molto corta o termina senza punteggiatura, probabilmente è un verso
                if len(line) < 60 or not re.search(r'[.!?]$', line):
                    if current_verse:
                        # Chiudi il verso precedente
                        segments.append({
                            'id': segment_id,
                            'text': self.normalize_text(current_verse), #.strip(),
                            'original': current_verse,
                            'type': 'verse',
                            'page': page_num,
                            'bbox': self.merge_bboxes(current_bboxes)
                        })
                        segment_id += 1

                    # Inizia nuovo verso
                    current_verse = line
                    current_bboxes = [block['bbox']]
                else:
                    # Continua il verso corrente
                    current_verse += " " + line
                    current_bboxes.append(block['bbox'])

            # Chiudi l'ultimo verso se presente
            if current_verse:
                segments.append({
                    'id': segment_id,
                    'text': self.normalize_text(current_verse),
                    'original': current_verse,
                    'type': 'verse',
                    'page': page_num,
                    'bbox': self.merge_bboxes(current_bboxes)
                })
                segment_id += 1

        return segments

    def segment_prose(self, text_blocks: List[Dict]) -> List[Dict]:
        """Segmenta il testo in prosa per paragrafi"""
        segments = []
        segment_id = 1

        current_paragraph = ""
        current_bboxes = []
        current_page = None

        for block in text_blocks:
            block_text = block['text']#.strip()
            if not block_text:
                continue

            page_num = block['page']

            # Se cambia pagina e abbiamo testo accumulato, chiudi il paragrafo

            if current_page is not None and current_page != page_num and current_paragraph:
                segments.append({
                    'id': segment_id,
                    'text': current_paragraph.strip(),
                    'type': 'paragraph',
                    'page': current_page,
                    'bbox': self.merge_bboxes(current_bboxes)
                })
                segment_id += 1
                current_paragraph = ""
                current_bboxes = []


            current_page = page_num

            # Dividi il blocco in possibili paragrafi
            paragraphs = re.split(r'\n\s*\n', block_text)

            for para in paragraphs:
                para = para.strip()
                if not para:
                    continue

                # Pulisci il paragrafo (rimuovi a capo singoli, mantieni spazi)
                para = re.sub(r'\n+', ' ', para)
                para = re.sub(r'\s+', ' ', para)

                if current_paragraph:
                    # Se abbiamo già un paragrafo in corso, decidere se continuare o chiudere
                    # Controlla se finisce con punteggiatura forte
                    if re.search(r'[.!?]\s*$', current_paragraph):
                        # Chiudi il paragrafo precedente
                        segments.append({
                            'id': segment_id,
                            'text': current_paragraph.strip(),
                            'type': 'paragraph',
                            'page': current_page,
                            'bbox': self.merge_bboxes(current_bboxes)
                        })
                        segment_id += 1
                        current_paragraph = para
                        current_bboxes = [block['bbox']]
                    else:
                        # Continua il paragrafo
                        current_paragraph += " " + para
                        current_bboxes.append(block['bbox'])
                else:
                    # Inizia nuovo paragrafo
                    current_paragraph = para
                    current_bboxes = [block['bbox']]

                # Se il paragrafo diventa troppo lungo, spezzalo
                if len(current_paragraph) > 1000:
                    sentences = re.split(r'([.!?]+)', current_paragraph)
                    temp_para = ""

                    for i in range(0, len(sentences), 2):
                        if i + 1 < len(sentences):
                            sentence = sentences[i] + sentences[i + 1]
                        else:
                            sentence = sentences[i]

                        if len(temp_para + sentence) > 800 and temp_para:
                            segments.append({
                                'id': segment_id,
                                'text': temp_para.strip(),
                                'type': 'paragraph',
                                'page': current_page,
                                'bbox': self.merge_bboxes(current_bboxes)
                            })
                            segment_id += 1
                            temp_para = sentence
                        else:
                            temp_para += sentence

                    current_paragraph = temp_para

        # Chiudi l'ultimo paragrafo se presente
        if current_paragraph:
            segments.append({
                'id': segment_id,
                'text': current_paragraph.strip(),
                'type': 'paragraph',
                'page': current_page,
                'bbox': self.merge_bboxes(current_bboxes)
            })

        return segments

    def merge_bbox(self, bbox, boxs):
        bb = ( min(bbox[0], boxs[0]),
            min(bbox[1], boxs[1]),
            max(bbox[2], boxs[2]),
            max(bbox[3], boxs[3]) )
        return bb

    def extract_text_blocks(self, pdf_path: str) -> List[Dict]:
        #import pymupdf4llm
        #md_text = pymupdf4llm.to_markdown(pdf_path)
        """Estrae blocchi di testo dal PDF con metadati"""
        doc = fitz.open(pdf_path)
        text_blocks = []

        for page_num in range(doc.page_count):
            page = doc[page_num]

            # Estrai blocchi di testo con posizione
            blocks = page.get_text("dict")
            #blocks1 = page.get_text("blocks")

            for block in blocks["blocks"]:
                if block.get("type") == 0:  # Blocco di testo
                    block_text = ""
                    block_bbox1 = block["bbox"]

                    lastx = -1
                    line_bbox = [10000, 10000, 0, 0]
                    for line in block["lines"]:
                        if line['bbox'][0] < lastx:
                            lastx = -1
                            line_bbox = [10000, 10000, 0, 0]
                            if block_text.strip():
                                text_blocks.append({
                                    'text': block_text.strip(),
                                    'bbox': block_bbox,
                                    'page': page_num + 1  # Numerazione pagine da 1
                                })
                            block_text =''

                        line_text = ""
                        #line_bbox = [10000, 10000, 0, 0]
                        for span in line["spans"]:
                            line_text += span["text"]
                            line_bbox = self.merge_bbox(line_bbox, span["bbox"])
                        block_text += line_text + "\n"
                        block_bbox = line_bbox
                        lastx = line['bbox'][0]

                    if block_text.strip():
                        text_blocks.append({
                            'text': block_text.strip(),
                            'bbox': block_bbox,
                            'page': page_num + 1  # Numerazione pagine da 1
                        })

        doc.close()
        return text_blocks
        v = []
        current = -1
        sp = []
        for i, block in enumerate(text_blocks):
            if block['page'] != current:
                current = block['page']
                v.append(0)
                sp.append(i)
                continue
            v.append(text_blocks[i]['bbox'][1] - text_blocks[i-1]['bbox'][1])
        sp.append(len(text_blocks))

        new_blocks = []
        dev_std_multiplo = 1
        for i in range(1, len(sp)):
            i0 = sp[i-1] + 5
            corpo_testo = np.array(v[i0: sp[i]])
            indice_massimo = self.trova_inizio_note_avanzato( corpo_testo) + i0

            media = np.mean(corpo_testo)
            dev_std = np.std(corpo_testo)
            limite = media + dev_std_multiplo * dev_std

            # Cerca il primo valore che supera il limite
            for i in range(i0, sp[i]):
                if v[i] > limite:
                    indice_massimo = i
                    break


            #valore_massimo = max(v[i0: sp[i]])
            #indice_massimo = v.index(valore_massimo, i0, sp[i])
            for k  in range(sp[i-1], indice_massimo):
                new_blocks.append(text_blocks[k])


        return new_blocks

    def trova_inizio_note_avanzato(self, interlinee, soglia_cambio=1.2, campioni_validazione=3):
        """
        Trova l'indice dell'inizio delle note in un vettore di interlinee,
        considerando il cambio da spaziatura alta a bassa.

        Args:
            interlinee (list or np.array): Vettore di valori di interlinea.
            soglia_cambio (float): Fattore per cui un'interlinea deve essere più grande
                                   rispetto alla media precedente per essere considerata
                                   un punto di stacco. Es. 1.2 per un 20% in più.
            campioni_validazione (int): Numero di interlinee successive da controllare
                                        per confermare che sono più piccole.

        Returns:
            int: L'indice del primo valore anomalo o -1 se non ne viene trovato nessuno.
        """

        for i in range(1, len(interlinee) - campioni_validazione):
            # Calcola la media dei valori precedenti per avere un riferimento
            media_precedente = np.mean(interlinee[max(0, i - 5):i])

            # 1. Cerca un'interlinea che sia significativamente più grande
            if interlinee[i] > media_precedente * soglia_cambio:
                return i

                # 2. Valida la transizione: controlla se i valori successivi sono minori
                valori_successivi = interlinee[i + 1: i + 1 + campioni_validazione]

                # Se la media dei valori successivi è significativamente minore...
                if np.mean(valori_successivi) < media_precedente * 0.8:  # Es. 20% in meno
                    return i

        return -1

    def process_pdf(self, pdf_path: str, type=None) -> List[Dict]:
        """Processa un PDF e restituisce i segmenti organizzati"""

        # Estrai blocchi di testo
        text_blocks = self.extract_text_blocks(pdf_path)
        print(f"Estratti {len(text_blocks)} blocchi di testo")

        if not text_blocks:
            print("Nessun testo trovato nel PDF")
            return []

        # Rileva il tipo di testo
        text_type = type
        if text_type == None:
            text_type = self.detect_text_type(text_blocks)
            print(f"Tipo di testo rilevato: {'Poesia' if text_type == 'poetry' else 'Prosa'}")

        return self.process_txt(text_blocks, type)

    def process_txt(self, text_blocks: List[Dict], text_type) -> List[Dict]:

        # Segmenta in base al tipo
        if text_type == "poetry":
            self.segments = self.segment_poetry(text_blocks)
            print(f"Segmentazione completata: {len(self.segments)} versi")
        else:
            self.segments = self.segment_prose(text_blocks)
            print(f"Segmentazione completata: {len(self.segments)} paragrafi")

        return self.segments

    def save_segments_json(self, output_path: str):
        """Salva i segmenti in formato JSON"""
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(self.segments, f, ensure_ascii=False, indent=2)
        print(f"Segmenti salvati in: {output_path}")

    def print_segments_summary(self, max_chars: int = 100):
        """Stampa un riassunto dei segmenti"""
        print("\n" + "=" * 50)
        print("RIASSUNTO SEGMENTAZIONE")
        print("=" * 50)

        for segment in self.segments[:10]:  # Mostra solo i primi 10
            text_preview = segment['text'][:max_chars]
            if len(segment['text']) > max_chars:
                text_preview += "..."

            print(f"\n{segment['type'].upper()} {segment['id']} (Pagina {segment['page']}):")
            print(f"BBox: ({segment['bbox'][0]:.1f}, {segment['bbox'][1]:.1f}, "
                  f"{segment['bbox'][2]:.1f}, {segment['bbox'][3]:.1f})")
            print(f"Testo: {text_preview}")

        if len(self.segments) > 10:
            print(f"\n... e altri {len(self.segments) - 10} segmenti")


# Esempio di utilizzo
def main():
    # Inizializza il segmentatore
    segmenter = PDFTextSegmenter()

    # Specifica il percorso del PDF
    pdf_file = r'C:\Users\franc\MySoft\PdfCompare\test\Test 2 Edizione 1.pdf'
    #pdf_file = r'C:\Users\franc\MySoft\PdfCompare\test\organizer_1_2.pdf'

    try:
        # Processa il PDF
        segments = segmenter.process_pdf(pdf_file)

        # Mostra riassunto
        segmenter.print_segments_summary()

        # Salva i risultati
        segmenter.save_segments_json("segmenti_output.json")

        # Esempio di accesso ai dati
        print(f"\nTotale segmenti: {len(segments)}")

        if segments:
            print(f"\nEsempio del primo segmento:")
            first_segment = segments[0]
            print(f"ID: {first_segment['id']}")
            print(f"Tipo: {first_segment['type']}")
            print(f"Pagina: {first_segment['page']}")
            print(f"Bounding Box: {first_segment['bbox']}")
            print(f"Testo: {first_segment['text'][:200]}...")

        return segments

    except Exception as e:
        print(f"Errore durante l'elaborazione: {str(e)}")
        return []


if __name__ == "__main__":
    segments = main()
