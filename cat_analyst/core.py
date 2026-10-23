from __future__ import annotations

import json
import math
import re
from difflib import SequenceMatcher
import os
import sqlite3
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime, date, timezone, timedelta
from pathlib import Path

TOPICS = ['Unclassified', 'Percentages', 'Profit and Loss', 'Ratio and Proportion',
          'Averages and Mixtures', 'Time and Work', 'Time Speed Distance',
          'Interest', 'Number System', 'Algebra', 'Geometry', 'Mensuration',
          'Logarithms', 'Progressions', 'Permutation and Combination', 'Probability', 'Set Theory']
SECTIONS = ['Overall', 'VARC', 'DILR', 'QA']


def today_local() -> date:
    return datetime.now(timezone(timedelta(hours=5, minutes=30))).date()


def data_directory() -> Path:
    override = os.getenv('CAT_ANALYST_DATA')
    return Path(override) if override else Path(os.getenv('LOCALAPPDATA', str(Path.home()))) / 'CATAnalyst'


def merge_capture_text(old: str, new: str) -> tuple[str, bool]:
    """Merge repeat/overlapping views without losing differing math values."""
    def compact(text):
        return ''.join(c.lower() for c in text if not c.isspace())
    a, b = compact(old), compact(new)
    if b in a:
        return old, False
    if a in b:
        return new, False
    # Only suppress tiny recognition differences when numerical values and
    # mathematical operators are unchanged. Original captures remain in raw_text.
    math = lambda text: re.findall(r'\d+(?:\.\d+)?|[+\-*/=<>^]', text)
    if len(a) >= 40 and math(a) == math(b) and SequenceMatcher(None, a, b, autojunk=False).ratio() >= .96:
        return old, False
    def append_overlap(left, right):
        x, y = compact(left), compact(right)
        for size in range(min(len(x), len(y)), 23, -1):
            if x.endswith(y[:size]):
                count = 0
                for index, char in enumerate(right):
                    if not char.isspace():
                        count += 1
                    if count == size:
                        return left.rstrip() + '\n' + right[index+1:].lstrip()
        return None
    merged = append_overlap(old, new)
    if merged is None:
        merged = append_overlap(new, old)
    return (merged, False) if merged is not None else (old + '\n\n' + new, True)


@dataclass
class Question:
    number: int
    text: str = ''
    solution: str = ''
    correct_answer: str = ''
    selected_answer: str = ''
    difficulty: str = 'Unknown'
    attempted: str = 'Unknown'
    correctness: str = 'Unknown'
    seconds: int | None = None
    topic: str = 'Unclassified'
    bookmark: bool = False
    expected: int = 0
    views: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    locked: list[str] = field(default_factory=list)
    screenshots: list[str] = field(default_factory=list)
    raw_text: str = ''

    def missing(self) -> list[str]:
        result = [label for key, label in [('text', 'question'), ('correct_answer', 'answer'),
                  ('solution', 'solution')] if not getattr(self, key)]
        for key in ['difficulty', 'attempted', 'correctness']:
            if getattr(self, key) == 'Unknown' and not (key == 'correctness' and self.attempted == 'Unattempted'):
                result.append(key)
        if self.seconds is None:
            result.append('time')
        return result

    def merge(self, other: Question) -> None:
        for key in ['text', 'solution', 'correct_answer', 'selected_answer', 'difficulty',
                    'attempted', 'correctness', 'seconds', 'topic']:
            value = getattr(other, key)
            if key in self.locked or value is None or value in ('', 'Unknown', 'Unclassified'):
                continue
            old = getattr(self, key)
            if key in ('text', 'solution') and old:
                value, uncertain = merge_capture_text(old, value)
                if uncertain:
                    warning = f'{key}: combined fragments; check overlap/order'
                    if warning not in self.warnings:
                        self.warnings.append(warning)
            elif old not in ('', 'Unknown', 'Unclassified', None) and old != value:
                warning = f'Conflicting {key}: {old} / {value}; verify manually'
                if warning not in self.warnings:
                    self.warnings.append(warning)
                continue
            setattr(self, key, value)
        self.expected = max(self.expected, other.expected)
        for key in ['views', 'warnings', 'screenshots']:
            values = getattr(self, key)
            values.extend(x for x in getattr(other, key) if x not in values)
        if other.raw_text and other.raw_text not in self.raw_text:
            self.raw_text = (self.raw_text + '\n\n--- Capture ---\n' + other.raw_text).strip()


@dataclass
class Session:
    id: str = field(default_factory=lambda: uuid.uuid4().hex)
    created: str = field(default_factory=lambda: datetime.now().astimezone().isoformat(timespec='seconds'))
    questions: dict[int, Question] = field(default_factory=dict)
    expected: int = 22
    keep_screenshots: bool = False
    region: dict = field(default_factory=dict)
    test_date: str = field(default_factory=lambda: today_local().isoformat())

    def merge(self, question: Question) -> None:
        if question.number in self.questions:
            self.questions[question.number].merge(question)
        else:
            self.questions[question.number] = question

    def dump(self, directory: Path) -> None:
        directory.mkdir(parents=True, exist_ok=True)
        temporary = directory / 'draft.tmp'
        temporary.write_text(json.dumps(asdict(self), ensure_ascii=False, indent=2), encoding='utf-8')
        temporary.replace(directory / 'draft.json')

    @classmethod
    def read(cls, path: Path) -> Session:
        payload = json.loads(path.read_text(encoding='utf-8-sig'))
        payload.setdefault('test_date', payload.get('created', today_local().isoformat())[:10])
        payload['questions'] = {int(k): Question(**v) for k, v in payload['questions'].items()}
        session = cls(**payload)
        if not session.id or any(c not in '0123456789abcdef' for c in session.id):
            raise ValueError('Invalid session ID')
        return session


def analytics(questions: list[Question]) -> list[dict]:
    groups: dict[str, list[Question]] = {'All QA': questions}
    for q in questions:
        groups.setdefault(q.topic, []).append(q)
    rows = []
    for topic, items in groups.items():
        attempts = sum(q.attempted == 'Answered' for q in items)
        graded = [q for q in items if q.attempted == 'Answered' and q.correctness in ('Correct', 'Incorrect')]
        correct = sum(q.correctness == 'Correct' for q in graded)
        times = [q.seconds for q in items if q.seconds is not None]
        rows.append(dict(topic=topic, questions=len(items), attempts=attempts,
                         unknown_attempts=sum(q.attempted == 'Unknown' for q in items),
                         graded=len(graded), accuracy=100 * correct / len(graded) if graded else None,
                         total_seconds=sum(times), timed=len(times),
                         average_seconds=sum(times) / len(times) if times else None))
    return rows


class Store:
    def __init__(self, root: Path):
        self.root = root
        root.mkdir(parents=True, exist_ok=True)
        (root / 'sessions').mkdir(exist_ok=True)
        self.db = sqlite3.connect(root / 'analyst.sqlite3')
        self.db.row_factory = sqlite3.Row
        self.db.execute('PRAGMA foreign_keys=ON')
        self.db.executescript('''
            CREATE TABLE IF NOT EXISTS papers (
              id TEXT PRIMARY KEY, name TEXT NOT NULL, created TEXT NOT NULL,
              expected INTEGER NOT NULL, metrics TEXT NOT NULL);
            CREATE TABLE IF NOT EXISTS questions (
              paper_id TEXT NOT NULL REFERENCES papers(id) ON DELETE CASCADE,
              number INTEGER NOT NULL, payload TEXT NOT NULL,
              PRIMARY KEY(paper_id, number));
            CREATE TABLE IF NOT EXISTS screenshots (
              paper_id TEXT NOT NULL, number INTEGER NOT NULL, name TEXT NOT NULL, image BLOB NOT NULL,
              PRIMARY KEY(paper_id, number, name),
              FOREIGN KEY(paper_id, number) REFERENCES questions(paper_id, number) ON DELETE CASCADE);
        ''')
        columns = {row[1] for row in self.db.execute('PRAGMA table_info(papers)')}
        with self.db:
            if 'test_date' not in columns:
                self.db.execute("ALTER TABLE papers ADD COLUMN test_date TEXT NOT NULL DEFAULT ''")
            self.db.execute("UPDATE papers SET test_date=substr(created,1,10) WHERE test_date=''")

    def session_dir(self, session: Session) -> Path:
        if not session.id or any(c not in '0123456789abcdef' for c in session.id):
            raise ValueError('Invalid session ID')
        return self.root / 'sessions' / session.id

    def save_paper(self, session: Session, name: str, metrics: dict) -> None:
        if not name.strip():
            raise ValueError('Paper name is required')
        if not session.questions:
            raise ValueError('Capture or add at least one question before saving')
        for section in SECTIONS:
            values = metrics.get(section, {})
            if not isinstance(values.get('score'), (int, float)) or not math.isfinite(values['score']):
                raise ValueError(f'{section} score is required')
            percentile = values.get('percentile')
            if not isinstance(percentile, (int, float)) or not 0 <= percentile <= 100:
                raise ValueError(f'{section} percentile must be between 0 and 100')
        test_date = date.fromisoformat(session.test_date)
        if test_date > today_local():
            raise ValueError('Test date cannot be in the future')
        directory = self.session_dir(session).resolve()
        # All database rows and optional images commit together. Never delete the video here.
        with self.db:
            self.db.execute('INSERT INTO papers(id,name,created,expected,metrics,test_date) VALUES(?,?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET '
                            'name=excluded.name, expected=excluded.expected, metrics=excluded.metrics, test_date=excluded.test_date',
                            (session.id, name.strip(), session.created, session.expected, json.dumps(metrics), test_date.isoformat()))
            for question in session.questions.values():
                payload = asdict(question)
                payload['screenshots'] = []  # file paths are temporary, images live in SQLite
                self.db.execute('INSERT INTO questions VALUES(?,?,?) ON CONFLICT(paper_id,number) '
                                'DO UPDATE SET payload=excluded.payload',
                                (session.id, question.number, json.dumps(payload)))
                if session.keep_screenshots:
                    for relative in question.screenshots:
                        path = (directory / relative).resolve()
                        if path.parent != directory or path.suffix != '.png':
                            raise ValueError('Invalid screenshot path')
                        self.db.execute('INSERT OR REPLACE INTO screenshots VALUES(?,?,?,?)',
                                        (session.id, question.number, path.name, path.read_bytes()))

    def cleanup_saved_session(self, session: Session) -> None:
        if not self.db.execute('SELECT 1 FROM papers WHERE id=?', (session.id,)).fetchone():
            raise ValueError('Save the paper before deleting its recording')
        directory = self.session_dir(session).resolve()
        if directory.parent != (self.root / 'sessions').resolve():
            raise ValueError('Invalid session directory')
        if directory.exists():
            for path in directory.iterdir():
                if path.is_file() and (path.name in ('draft.json', 'draft.tmp') or path.suffix in ('.avi', '.png')):
                    path.unlink()
            if not any(directory.iterdir()):
                directory.rmdir()

    def papers(self) -> list[dict]:
        return [dict(row) for row in self.db.execute('SELECT * FROM papers ORDER BY test_date, created')]

    def questions(self, paper_id: str | None = None, bookmarks=False) -> list[tuple[str, str, Question]]:
        query = 'SELECT q.paper_id, p.name, q.payload FROM questions q JOIN papers p ON p.id=q.paper_id'
        parameters = ()
        if paper_id:
            query += ' WHERE q.paper_id=?'
            parameters = (paper_id,)
        query += ' ORDER BY p.test_date, p.created, q.number'
        rows = [(r[0], r[1], Question(**json.loads(r[2]))) for r in self.db.execute(query, parameters)]
        return [r for r in rows if not bookmarks or r[2].bookmark]

    def update_question(self, paper_id: str, question: Question) -> None:
        with self.db:
            self.db.execute('UPDATE questions SET payload=? WHERE paper_id=? AND number=?',
                            (json.dumps(asdict(question)), paper_id, question.number))

    def images(self, paper_id: str, number: int) -> list[bytes]:
        return [r[0] for r in self.db.execute('SELECT image FROM screenshots WHERE paper_id=? AND number=?',
                                            (paper_id, number))]


    def delete_paper(self, paper_id: str) -> None:
        with self.db:
            self.db.execute('DELETE FROM papers WHERE id=?', (paper_id,))

    def delete_question(self, paper_id: str, number: int) -> None:
        # Preserve expected count: removing a question makes coverage incomplete.
        with self.db:
            self.db.execute('DELETE FROM questions WHERE paper_id=? AND number=?', (paper_id, number))
