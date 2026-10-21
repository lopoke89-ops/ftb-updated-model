"""Preserve NBA PDF text when layout extraction separates glyphs inside words.

Use the existing pypdf layout unchanged when its structural headers are intact.
For affected fonts, PDFium supplies literal text; printed X coordinates retain
HOME / score / VISITOR columns. No name or statistic is repaired by guessing.
"""
import hashlib
import re
import threading
import pypdfium2 as pdfium

VERSION = 'nba-pdf-text-v1'
CODE_HASH = hashlib.sha256(__import__('pathlib').Path(__file__).read_bytes()).hexdigest()
LOCK = threading.RLock()
CLOCK = re.compile(r'^(\d{1,2}:\d{2}(?:\.\d+)?|:\d{2}(?:\.\d+)?)\s+')


def box_text(text):
    lines = []
    for line in text.replace('\r', '').splitlines():
        match = re.match(r'^(\d{1,2}) (.+?) ((?:(?:PG|SG|SF|PF|F|G|C) )?\d{1,2}:\d{2} .+|(?:DNP|DND|NWT)\b.*)$', line)
        lines.append(f'{match[1]} {match[2]}  {match[3]}' if match else line)
    return '\n'.join(lines)


def columns(textpage, text):
    """Rebuild printed columns and join wrapped parts within their clock row."""
    header = re.search(r'(?m)^Time (.+?) Score Lead (.+)\r?$', text)
    if not header:
        raise ValueError('PDFium play-by-play column header unavailable')
    home_x = textpage.get_charbox(header.start(1))[0] - 1
    score_x = textpage.get_charbox(text.index('Score', header.start()))[0] - 1
    away_x = textpage.get_charbox(header.start(2))[0] - 1
    if not 0 < home_x < score_x < away_x:
        raise ValueError('Invalid printed play-by-play column geometry')
    output, spans = [], []
    offset = 0
    in_body = False
    row = None
    def emit(line, source_lines):
        output.append(line)
        spans.append(source_lines)
    def flush():
        nonlocal row
        if row is None: return
        parts = [' '.join(p).strip() for p in row['parts']]
        if re.search(r'Start of Period|End of |JUMP BALL|Coach.s Challenge|Instant Replay|Overturned|Ruling|Double Technical', ' '.join(row['raw'])):
            emit(row['clock'].ljust(12) + ' '.join(row['raw'])[len(row['clock']):].strip(), row['lines'])
        else:
            if len(parts[1]) > 156 or len(parts[2]) > 58:
                raise ValueError('Printed play-by-play column exceeds retained layout')
            emit((row['clock'].ljust(12) + parts[1].ljust(158) + parts[2].ljust(60) + parts[3]).rstrip(), row['lines'])
        row = None
    for lineno, original in enumerate(text.splitlines(keepends=True), 1):
        line = original.rstrip('\r\n')
        clock = re.match(r'^(\d{1,2}:\d{2}(?:\.\d+)?|:\d{2}(?:\.\d+)?)(?:\s|$)', line)
        boundary = re.search(r'End of |FIELD GOALS|FREE THROWS|SCORE:|BIG HOME|BIG VISITOR|Copyright', line)
        if offset == header.start():
            flush()
            emit(('Time'.ljust(12) + header[1].ljust(158) + 'Score Lead'.ljust(60) + header[2]).rstrip(), [lineno])
            in_body = True
        elif in_body and (clock or row is not None and line.strip() and not boundary):
            if clock:
                flush()
                row = {'clock':clock[1], 'parts':[[], [], [], []], 'raw':[], 'lines':[]}
            if row is not None:
                parts = ['', '', '', '']
                for index, char in enumerate(line):
                    x = textpage.get_charbox(offset + index)[0]
                    part = 0 if x < home_x else 1 if x < score_x else 2 if x < away_x else 3
                    parts[part] += char
                for i, part in enumerate(parts):
                    if part.strip(): row['parts'][i].append(part.strip())
                row['raw'].append(line)
                row['lines'].append(lineno)
        else:
            flush()
            emit(line, [lineno])
        offset += len(original)
    flush()
    return {'text':'\n'.join(output), 'sourceLineSpans':spans, 'printedColumnBounds':[home_x, score_x, away_x]}


def extract(raw, page_index, layout=None, kind='play-by-play'):
    usable = layout is not None and (('FINAL BOX' in layout and 'VISITOR:' in layout and 'HOME:' in layout) if kind == 'final-box' else ('QUARTER ONLY' in layout and 'VISITOR:' in layout) if kind == 'quarter-box' else bool(re.search(r'(?m)^Time\s+.+Score\s+Lead', layout)))
    if usable:
        return {'text': layout, 'textEngine': 'pypdf-layout', 'textVersion': VERSION, 'textHash': hashlib.sha256(layout.encode()).hexdigest()}
    with LOCK, pdfium.PdfDocument(raw) as document:
        page = document[page_index]
        textpage = page.get_textpage()
        original = textpage.get_text_range()
        converted = {'text':box_text(original)} if kind in ('final-box', 'quarter-box') else columns(textpage, original)
        text = converted['text']
        textpage.close()
        page.close()
    return {**converted, 'originalText': original, 'textEngine': 'pdfium-printed-columns' if kind == 'play-by-play' else 'pdfium-box', 'textVersion': VERSION, 'textCodeHash': CODE_HASH, 'textHash': hashlib.sha256(text.encode()).hexdigest()}
