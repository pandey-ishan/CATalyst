"""Conservative, spatial parser for visible test provider review content."""
from __future__ import annotations
import re
from dataclasses import dataclass
from .core import Question


@dataclass
class Line:
    text: str
    x: float
    y: float
    right: float
    bottom: float
    confidence: float = 1.0


def ocr_lines(result) -> list[Line]:
    lines = []
    for box, text, confidence in result or []:
        lines.append(Line(text.strip(), min(p[0] for p in box), min(p[1] for p in box),
                          max(p[0] for p in box), max(p[1] for p in box), float(confidence)))
    return sorted(lines, key=lambda row: (row.y, row.x))


def rows(lines: list[Line]) -> list[list[Line]]:
    grouped: list[list[Line]] = []
    for line in sorted(lines, key=lambda item: item.y):
        center = (line.y + line.bottom) / 2
        if grouped and abs(center - sum((x.y + x.bottom) / 2 for x in grouped[-1]) / len(grouped[-1])) < 12:
            grouped[-1].append(line)
        else:
            grouped.append([line])
    return [sorted(row, key=lambda item: item.x) for row in grouped]


def guess_topic(text: str) -> str:
    # A suggestion only; editable in the review window.
    patterns = [('Profit and Loss', r'profit|loss|shopkeeper|discount|selling price'),
                ('Time Speed Distance', r'speed|train|kilomet|km/h|upstream'),
                ('Time and Work', r'work.*days|pipes?|cistern'),
                ('Interest', r'compound interest|simple interest'),
                ('Percentages', r'percent|percentage|%'),
                ('Averages and Mixtures', r'average|mixture|alloy'),
                ('Ratio and Proportion', r'ratio|proportion'),
                ('Probability', r'probability|randomly'),
                ('Permutation and Combination', r'permutation|combination|arrangements'),
                ('Geometry', r'triangle|circle|quadrilateral|angle'),
                ('Mensuration', r'volume|surface area|cylinder|cone'),
                ('Logarithms', r'logarithm|log\s*\('),
                ('Progressions', r'progression|sequence|series'),
                ('Number System', r'divisib|remainder|integer|prime'),
                ('Algebra', r'equation|polynomial|roots|quadratic')]
    return next((topic for topic, pattern in patterns if re.search(pattern, text, re.I)), 'Unclassified')


def parse_test_provider(lines: list[Line], width: int = 0, height: int = 0) -> Question | None:
    if not lines:
        return None
    identity = None
    candidates=list(lines)
    # A counter may arrive as separate OCR boxes (14, /, 22).
    for row in rows(lines):
        if 1<len(row)<=4 and all(row[i+1].x-row[i].right<30 for i in range(len(row)-1)):
            candidates.append(Line(''.join(cell.text for cell in row),min(c.x for c in row),min(c.y for c in row),max(c.right for c in row),max(c.bottom for c in row),min(c.confidence for c in row)))
    for line in candidates:
        counter_text=line.text.strip()
        # Restrict lookalike correction to an explicit number/total counter.
        if re.fullmatch(r'[0-9Il]{1,2}\s*/\s*[0-9Il]{1,2}',counter_text):
            counter_text=counter_text.translate(str.maketrans({'I':'1','l':'1'}))
        match = re.fullmatch(r'\s*(\d{1,2})\s*[/|]\s*(\d{1,2})\s*', counter_text)
        if (match and 1 <= int(match[1]) <= int(match[2]) <= 40
                and (not height or line.y < height * .25)
                and (not width or line.x < width * .5)
                and not any(other.bottom < line.y and len(other.text.split()) >= 5 for other in lines)) :
            identity = (line, int(match[1]), int(match[2]))
            break
    if identity is None:
        return None
    marker, number, expected = identity
    q = Question(number=number, expected=expected)
    grouped = rows(lines)
    texts = [' '.join(cell.text for cell in row) for row in grouped]
    q.raw_text = '\n'.join(texts)
    if any(line.confidence < .75 for line in lines):
        q.warnings.append('Low-confidence OCR; verify extracted text')
    if width and any(line.right >= width - 4 for line in lines):
        q.warnings.append('Text may be clipped at the right capture edge')
    if height and any(line.bottom >= height - 4 for line in lines):
        q.warnings.append('Content may continue below the capture area')
    tab_rows = [row for row in grouped if any(re.search(r'Text\s*Solution', x.text, re.I) for x in row)]
    tab_y = min((min(x.y for x in row) for row in tab_rows), default=float('inf'))
    boundary = min((x.y for x in lines if re.search(
        r'Enter your response|Correct Answer|Backspace|Statistics|Text\s*Solution', x.text, re.I)), default=float('inf'))
    question_lines = [row for row in grouped if min(x.y for x in row) > marker.bottom and max(x.bottom for x in row) < boundary]
    q.text = '\n'.join(' '.join(x.text for x in row) for row in question_lines).strip()
    # With tabs scrolled offscreen, the counter alone does not identify the
    # visible body as a question. Keep uncertain bodies in raw_text only.
    if boundary == float('inf') and q.text:
        body = q.text
        solution_cue = re.search(r'(?im)^\s*(?:therefore|thus|hence)[, :]|(?:the required answer|solving for|we (?:have|get)|as the equation has no real roots)', body)
        if solution_cue:
            q.solution = body
            q.views.append('Text Solution')
            q.warnings.append('Solution inferred with tabs offscreen; verify classification')
            q.text = ''
        elif not re.search(r'(?i)\?|\b(?:find|determine|calculate|what|which)\b|_{2,}', body):
            q.text = ''
            q.warnings.append('Unclassified scrolled content retained in raw text; show question or solution tabs')
    q.topic = guess_topic(q.text)
    raw = q.raw_text
    difficulty = re.search(r'Question\s*Type\s*[:\-]?\s*([ABC])\b', raw, re.I)
    if difficulty:
        q.difficulty = {'A': 'Easy', 'B': 'Medium', 'C': 'Hard'}[difficulty[1].upper()]
    stats = bool(re.search(r'Performance\s*Parameter|Time\s*Taken|Question\s*Type', raw, re.I))
    if stats:
        q.views.append('Statistics')
        for text in texts:
            # Read only the first user value after a row label, never topper/overall values.
            attempt = re.search(r'\bAttempt\s+(Not\s*Answered|Unanswered|Unattempted|Skipped|Answered|Attempted)\b', text, re.I)
            if attempt:
                q.attempted = 'Answered' if attempt[1].lower() in ('answered', 'attempted') else 'Unattempted'
            correctness = re.search(r'\bAccuracy\s+(Incorrect|Correct)\b', text, re.I)
            if correctness:
                q.correctness = correctness[1].capitalize()
            time = re.search(r'Time\s*Taken\s+(\d{1,3})\s*:\s*(\d{2})', text, re.I)
            if time and int(time[2]) < 60:
                q.seconds = 60 * int(time[1]) + int(time[2])
    answer_line = next((x for x in lines if re.search(r'Correct\s*Answer', x.text, re.I)), None)
    if answer_line:
        inline = re.sub(r'^.*?Correct\s*Answer\s*[:\-]?\s*', '', answer_line.text, flags=re.I)
        if inline:
            q.correct_answer = inline
        else:
            below = [x for x in lines if x.y > answer_line.bottom and x.bottom < tab_y]
            if below:
                q.correct_answer = min(below, key=lambda x: (x.y, x.x)).text
    if not stats and tab_y < float('inf'):
        bottom = max(x.bottom for row in tab_rows for x in row)
        solution_lines = [row for row in grouped if min(x.y for x in row) > bottom + 3]
        q.solution = '\n'.join(' '.join(x.text for x in row) for row in solution_lines).strip()
        if q.solution:
            q.views.append('Text Solution')
    backspace = next((x for x in lines if 'backspace' in x.text.lower()), None)
    if backspace:
        candidates = [x for x in lines if x.bottom < backspace.y and
                      x.y > marker.bottom and re.fullmatch(r'-?\d+(?:\.\d+)?', x.text)]
        if candidates:
            q.selected_answer = max(candidates, key=lambda x: x.y).text
    return q
