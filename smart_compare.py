from typing import List, Dict, Tuple, Any
from difflib import SequenceMatcher
import logging
import fitz  # PyMuPDF
import re

from smart_segmentation import PDFTextSegmenter


class PDFTextExtractor:
    """Classe per l'estrazione ottimizzata di testo dai PDF per il confronto"""

    def __init__(self):
        pass

    def clean_text_lines(self, lines: List[str], page_num: int) -> str:
        """
        Pulisce e unisce le righe di testo di una pagina
        Implementa la tua logica di pulizia esistente
        """
        # Rimuovi righe vuote e spazi extra
        cleaned_lines = []
        for line in lines:
            line = line.strip()
            if line:  # Mantieni solo righe non vuote
                cleaned_lines.append(line)

        # Unisci le righe in un testo unico per pagina
        return '\n'.join(cleaned_lines)

    def extract_text_for_comparison(self, pdf_path: str) -> Tuple[List[str], bool]:
        """
        Estrae il testo da PDF ottimizzato per il confronto

        Returns:
            Tuple[List[str], bool]: (lista_testi_per_pagina, successo)
        """
        pages_text = []

        try:
            doc = fitz.open(pdf_path)

            for page_num in range(len(doc)):
                page = doc.load_page(page_num)

                # Estrai testo con informazioni di posizione
                text_dict = page.get_text("dict")
                blocks = text_dict.get("blocks", [])

                # Raccogli tutti i blocchi di testo con posizione
                text_blocks = []
                for block in blocks:
                    if "lines" in block:  # Blocco di testo
                        for line in block["lines"]:
                            line_text = ""
                            for span in line["spans"]:
                                line_text += span["text"]
                            if line_text.strip():
                                text_blocks.append({
                                    'text': line_text.strip(),
                                    'bbox': line["bbox"]
                                })

                # Ordina per posizione Y (top) poi X (left)
                text_blocks.sort(key=lambda x: (x['bbox'][1], x['bbox'][0]))

                # Estrai solo il testo ordinato
                page_lines = [block['text'] for block in text_blocks]

                # Pulisci e unisci il testo della pagina
                page_text = self.clean_text_lines(page_lines, page_num + 1)
                pages_text.append(page_text)

            doc.close()
            return pages_text, True

        except Exception as e:
            logging.error(f"Errore nell'estrazione del testo da {pdf_path}: {e}")
            return [], False


class PDFComparator:
    """Classe per il confronto di testi estratti da PDF"""

    def __init__(self, similarity_threshold: float = 0.7, min_block_words: int = 3):
        """
        Inizializza il comparatore

        Args:
            similarity_threshold: Soglia di similarità per considerare due blocchi simili
            min_block_words: Numero minimo di parole per considerare un blocco valido
        """
        self.similarity_threshold = similarity_threshold
        self.min_block_words = min_block_words

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

    def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        Calcola la similarità tra due stringhe
        """
        if not text1 or not text2:
            return 0.0

        normalized1 = self.normalize_text(text1)
        normalized2 = self.normalize_text(text2)

        if not normalized1 or not normalized2:
            return 0.0

        return SequenceMatcher(None, normalized1, normalized2).ratio()

    def get_detailed_differences(self, text1: str, text2: str) -> List[Dict]:
        """
        Ottiene le differenze dettagliate tra due testi
        """
        matcher = SequenceMatcher(None, text1, text2)
        differences = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag != 'equal':
                diff_entry = {
                    'operation': tag,  # 'replace', 'delete', 'insert'
                    'text1': text1[i1:i2] if tag != 'insert' else '',
                    'text2': text2[j1:j2] if tag != 'delete' else '',
                    'position1': (i1, i2),
                    'position2': (j1, j2)
                }
                differences.append(diff_entry)

        return differences

    def get_lines(self, pages_text):
        doc = []
        for page_num, page_text in enumerate(pages_text):
            if not page_text or not page_text.strip():
                continue
            lines = page_text.split('\n')
            for line in lines:
                t = self.normalize_text(line)
                #h =  abs(hash(t))
                l = {
                    'txt': t,
                    'page': page_num
                }
                doc.append(l)

        return doc

    def find_closest_string(self, vs, s, j0):
        """
        Trova l'indice della stringa in un vettore che è più simile a una stringa di riferimento.

        Args:
            vs (List[str]): Un vettore di stringhe.
            s (str): La stringa di riferimento.

        Returns:
            Optional[int]: L'indice della stringa più simile in vs, o None se il vettore è vuoto.
        """
        if not vs:
            return None

        max_similarity = -1.0
        closest_index = None

        # Itera sul vettore per trovare la stringa con il punteggio di similitudine più alto
        for i, vector_string in enumerate(vs[j0:], start=j0):
            # Utilizza SequenceMatcher per calcolare la similitudine
            s2 = vector_string['text']
            matcher = SequenceMatcher(None, s, s2)
            similarity_ratio = matcher.ratio()

            if similarity_ratio > max_similarity and similarity_ratio > self.similarity_threshold:
                max_similarity = similarity_ratio
                closest_index = i
                break

        return closest_index, max_similarity

    def match_lines(self, pages_text1, pages_text2):
        #doc1 = self.get_lines(pages_text1)
        #doc2 = self.get_lines(pages_text2)

        matches = []
        j0 = 0
        for i, l in enumerate(pages_text1):
            try:
                j, score = self.find_closest_string(pages_text2, l['text'], j0)
                if j is not None:
                    matches.append({
                        'doc1': i,
                        'doc2': j,
                        'score': score
                    }
                    )
                    if score > 0.93:
                        j0 = j + 1
                else:
                    a = 0
            except Exception as e:
                b = 0
            a1 = 0


        return matches

    def create_semantic_blocks(self, pages_text: List[str]) -> List[Dict]:
        """
        Crea blocchi semantici dal testo delle pagine
        """
        blocks = []
        block_id = 0

        for page_num, page_text in enumerate(pages_text):
            if not page_text or not page_text.strip():
                continue

            # Dividi in paragrafi usando pattern più sofisticati
            paragraphs = self._extract_paragraphs(page_text)

            for para_num, paragraph in enumerate(paragraphs):
                word_count = len(paragraph.split())

                # Filtra blocchi troppo piccoli
                if word_count >= self.min_block_words:
                    blocks.append({
                        'id': block_id,
                        'page': page_num + 1,
                        'paragraph': para_num + 1,
                        'text': paragraph,
                        'normalized_text': self.normalize_text(paragraph),
                        'word_count': word_count,
                        'hash': hash(self.normalize_text(paragraph))
                    })
                    block_id += 1

        return blocks

    def _extract_paragraphs(self, text: str) -> List[str]:
        """
        Estrae paragrafi dal testo usando euristiche avanzate
        """
        import re

        # Prima prova con doppie newline
        paragraphs = re.split(r'\n\s*\n', text)

        # Se pochi paragrafi, prova con singole newline ma raggruppa righe correlate
        if len(paragraphs) <= 2:
            lines = [line.strip() for line in text.split('\n') if line.strip()]
            paragraphs = []
            current_paragraph = []

            for i, line in enumerate(lines):
                current_paragraph.append(line)

                # Nuove euristiche per fine paragrafo
                is_end_paragraph = False

                # Fine paragrafo se la riga finisce con punto e la prossima inizia maiuscola
                if line.endswith('.') and i < len(lines) - 1:
                    next_line = lines[i + 1]
                    if next_line and next_line[0].isupper():
                        is_end_paragraph = True

                # Fine paragrafo se cambio significativo di lunghezza
                if i < len(lines) - 1:
                    next_line = lines[i + 1]
                    if len(line) > 50 and len(next_line) < 30:
                        is_end_paragraph = True

                # Forza fine paragrafo ogni N righe per evitare blocchi troppo grandi
                if len(current_paragraph) >= 10:
                    is_end_paragraph = True

                if is_end_paragraph or i == len(lines) - 1:
                    if current_paragraph:
                        paragraph_text = ' '.join(current_paragraph).strip()
                        if paragraph_text:
                            paragraphs.append(paragraph_text)
                        current_paragraph = []

        return [p.strip() for p in paragraphs if p.strip()]

    def find_best_matches(self, block: Dict, candidates: List[Dict],
                          max_matches: int = 3) -> List[Tuple[Dict, float]]:
        """
        Trova i migliori match per un blocco
        """
        matches = []

        # Prima verifica hash identici (match perfetto)
        for candidate in candidates:
            if block['hash'] == candidate['hash']:
                matches.append((candidate, 1.0))

        if matches:
            return matches[:max_matches]

        # Altrimenti calcola similarità
        for candidate in candidates:
            similarity = self.calculate_similarity(block['text'], candidate['text'])
            if similarity > 0.1:  # Soglia minima per considerare un match
                matches.append((candidate, similarity))

        # Ordina per similarità decrescente
        matches.sort(key=lambda x: x[1], reverse=True)
        return matches[:max_matches]

    def align_blocks_advanced(self, blocks1: List[Dict], blocks2: List[Dict]) -> List[Dict]:
        """
        Allineamento avanzato dei blocchi con gestione di inserimenti/cancellazioni
        """
        alignments = []
        used_blocks2 = set()

        # Prima passata: match esatti e ad alta similarità
        for block1 in blocks1:
            candidates = [b for b in blocks2 if b['id'] not in used_blocks2]
            matches = self.find_best_matches(block1, candidates, max_matches=1)

            if matches:
                best_match, similarity = matches[0]

                if similarity >= self.similarity_threshold:
                    alignment = {
                        'block1': block1,
                        'block2': best_match,
                        'similarity': similarity,
                        'status': 'identical' if similarity == 1.0 else 'matched',
                        'differences': None
                    }
                    used_blocks2.add(best_match['id'])
                else:
                    # Similarità troppo bassa, considera come modificato o cancellato
                    alignment = {
                        'block1': block1,
                        'block2': best_match if similarity > 0.3 else None,
                        'similarity': similarity,
                        'status': 'modified' if similarity > 0.3 else 'deleted',
                        'differences': None
                    }
                    if similarity > 0.3:
                        used_blocks2.add(best_match['id'])
            else:
                # Nessun match trovato
                alignment = {
                    'block1': block1,
                    'block2': None,
                    'similarity': 0.0,
                    'status': 'deleted',
                    'differences': None
                }

            alignments.append(alignment)

        # Aggiungi i blocchi del secondo documento non utilizzati
        for block2 in blocks2:
            if block2['id'] not in used_blocks2:
                alignment = {
                    'block1': None,
                    'block2': block2,
                    'similarity': 0.0,
                    'status': 'added',
                    'differences': None
                }
                alignments.append(alignment)

        return alignments

    def add_difference_details(self, alignments: List[Dict]) -> None:
        """
        Aggiunge dettagli delle differenze agli allineamenti modificati
        """
        for alignment in alignments:
            if (alignment['status'] in ['modified', 'matched'] and
                    alignment['block1'] and alignment['block2'] and
                    alignment['similarity'] < 1.0):
                alignment['differences'] = self.get_detailed_differences(
                    alignment['block1']['text'],
                    alignment['block2']['text']
                )

    def compare_pdfs(self, pages_text1: List[str], pages_text2: List[str]) -> Dict:
        """
        Confronta il testo di due PDF e ritorna le differenze strutturate
        """
        try:
            # Crea blocchi semantici
            blocks1 = self.create_semantic_blocks(pages_text1)
            blocks2 = self.create_semantic_blocks(pages_text2)

            if not blocks1 and not blocks2:
                return {
                    'status': 'success',
                    'message': 'Entrambi i documenti sono vuoti',
                    'statistics': self._create_empty_stats(),
                    'alignments': [],
                    'summary': 'Documenti identici (vuoti)'
                }

            # Allinea i blocchi
            alignments = self.align_blocks_advanced(blocks1, blocks2)

            # Aggiungi dettagli delle differenze
            self.add_difference_details(alignments)

            # Calcola statistiche
            statistics = self._calculate_comprehensive_stats(alignments, blocks1, blocks2)

            # Genera riassunto
            summary = self._generate_summary(statistics)

            return {
                'status': 'success',
                'statistics': statistics,
                'alignments': alignments,
                'summary': summary,
                'blocks_info': {
                    'pdf1_blocks': len(blocks1),
                    'pdf2_blocks': len(blocks2),
                    'total_alignments': len(alignments)
                }
            }

        except Exception as e:
            logging.error(f"Errore nel confronto PDF: {e}")
            return {
                'status': 'error',
                'error': str(e),
                'statistics': None,
                'alignments': [],
                'summary': f'Errore durante il confronto: {str(e)}'
            }

    def _calculate_comprehensive_stats(self, alignments: List[Dict],
                                       blocks1: List[Dict], blocks2: List[Dict]) -> Dict:
        """Calcola statistiche complete"""
        stats = {
            'identical': 0,
            'matched': 0,
            'modified': 0,
            'added': 0,
            'deleted': 0,
            'total_alignments': len(alignments)
        }

        for alignment in alignments:
            stats[alignment['status']] += 1

        # Calcola percentuali e metriche
        total_blocks = max(len(blocks1), len(blocks2))
        if total_blocks > 0:
            stats['similarity_percentage'] = ((stats['identical'] + stats['matched']) / total_blocks) * 100
            stats['difference_percentage'] = ((stats['modified'] + stats['added'] + stats[
                'deleted']) / total_blocks) * 100
        else:
            stats['similarity_percentage'] = 100.0
            stats['difference_percentage'] = 0.0

        stats['total_blocks_pdf1'] = len(blocks1)
        stats['total_blocks_pdf2'] = len(blocks2)

        return stats

    def _create_empty_stats(self) -> Dict:
        """Crea statistiche vuote"""
        return {
            'identical': 0, 'matched': 0, 'modified': 0, 'added': 0, 'deleted': 0,
            'total_alignments': 0, 'similarity_percentage': 100.0, 'difference_percentage': 0.0,
            'total_blocks_pdf1': 0, 'total_blocks_pdf2': 0
        }

    def _generate_summary(self, stats: Dict) -> str:
        """Genera un riassunto del confronto"""
        if stats['total_alignments'] == 0:
            return "Documenti vuoti"

        similarity = stats['similarity_percentage']

        if similarity == 100.0:
            return "Documenti identici"
        elif similarity >= 90.0:
            return f"Documenti molto simili ({similarity:.1f}% di similarità)"
        elif similarity >= 70.0:
            return f"Documenti simili con alcune differenze ({similarity:.1f}% di similarità)"
        elif similarity >= 50.0:
            return f"Documenti con differenze significative ({similarity:.1f}% di similarità)"
        else:
            return f"Documenti molto diversi ({similarity:.1f}% di similarità)"


# Funzioni di convenienza
def extract_pdf_text(pdf_path: str) -> Tuple[List[str], bool]:
    """
    Estrae testo da PDF per il confronto

    Returns:
        Tuple[List[str], bool]: (testi_per_pagina, successo)
    """
    extractor = PDFTextExtractor()
    return extractor.extract_text_for_comparison(pdf_path)


def compare_pdf_files(pdf_path1: str, pdf_path2: str,
                      similarity_threshold: float = 0.7) -> Dict:
    """
    Confronta due file PDF direttamente

    Args:
        pdf_path1: Percorso del primo PDF
        pdf_path2: Percorso del secondo PDF
        similarity_threshold: Soglia di similarità (0-1)

    Returns:
        Dizionario con risultati del confronto
    """

    # Estrai testo da entrambi i PDF
    segmenter = PDFTextSegmenter()
    pages_text1 = segmenter.process_pdf(pdf_path1)
    pages_text2 = segmenter.process_pdf(pdf_path2)

    # Confronta
    comparator = PDFComparator(similarity_threshold)
    result = comparator.match_lines(pages_text1, pages_text2)
    return result, pages_text1, pages_text2


    '''
    result = comparator.compare_pdfs(pages_text1, pages_text2)

    # Aggiungi informazioni sui file
    result['files'] = {
        'pdf1': pdf_path1,
        'pdf2': pdf_path2,
        'pdf1_pages': len(pages_text1),
        'pdf2_pages': len(pages_text2)
    }

    return result
    '''


def compare_pdf_texts(pages_text1: List[str], pages_text2: List[str],
                      similarity_threshold: float = 0.7) -> Dict:
    """
    Confronta testi già estratti da PDF

    Args:
        pages_text1: Testi del primo PDF (lista per pagina)
        pages_text2: Testi del secondo PDF (lista per pagina)
        similarity_threshold: Soglia di similarità (0-1)

    Returns:
        Dizionario con risultati del confronto
    """
    comparator = PDFComparator(similarity_threshold)
    return comparator.compare_pdfs(pages_text1, pages_text2)