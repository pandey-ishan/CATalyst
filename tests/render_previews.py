"""Render illustrative previews using temporary synthetic data, not user records."""
import os
os.environ['QT_QPA_PLATFORM']='offscreen'
import tempfile
from pathlib import Path
from PySide6.QtWidgets import QApplication
from PySide6.QtGui import QFontDatabase,QFont
from cat_analyst.ui import MainWindow,STYLE
from cat_analyst.reader import QuestionReader
from cat_analyst.core import Question,Session,SECTIONS
app=QApplication([]);app.setQuitOnLastWindowClosed(False);app.setStyle('Fusion')
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeui.ttf')
QFontDatabase.addApplicationFont('C:/Windows/Fonts/segoeuib.ttf')
app.setFont(QFont('Segoe UI',10));app.setStyleSheet(STYLE)
out=Path('_test_artifacts');out.mkdir(exist_ok=True)
with tempfile.TemporaryDirectory() as directory:
    window=MainWindow(Path(directory));window.resize(1580,980)
    for mock in range(4):
        questions={}
        for i in range(1,23):
            topic=['Algebra','Geometry','Profit and Loss','Number System'][(i-1)%4]
            questions[i]=Question(i,text='Find x.',solution='Review the calculation.',correct_answer='15',selected_answer='15' if i%3 else '14',
                topic=topic,difficulty='Easy' if i%2 else 'Medium',attempted='Answered',correctness='Correct' if i%3 else 'Incorrect',
                seconds=80+(i%4)*35+mock*10,bookmark=i==3)
        session=Session(questions=questions,test_date=f'2026-10-{mock*5+1:02d}',created=f'2026-10-{mock*5+1:02d}T10:00:00+05:30')
        scores=[20+mock*3,18+mock*2,21+mock*3]
        metrics={s:dict(score=v,percentile=80+mock*4) for s,v in zip(SECTIONS,[sum(scores)]+scores)}
        window.store.save_paper(session,f'test provider SIMCAT {mock+1:02d} (sample)',metrics)
    window.refresh();window.statusBar().showMessage('Sample data | Local storage');window.show();app.processEvents()
    window.grab().save(str(out/'overview-redesign.png'))
    window.resize(1280,720)
    for _ in range(5):app.processEvents()
    window.grab().save(str(out/'overview-laptop.png'))
    window.tabs.setCurrentIndex(1);window.paper_table.selectRow(0)
    for _ in range(5):app.processEvents()
    window.grab().save(str(out/'notebook-papers.png'))
    window.tabs.setCurrentIndex(2);app.processEvents()
    window.grab().save(str(out/'notebook-bookmarks.png'))
    q=Question(3,text='If 2^{(2+4+6+8+10+...+2x)} = (0.125)^{-80}, the value of x will be _____.\nA 13\nB 14\nC 15\nD 16',
               solution='Since 0.125 = 2^{-3}, the right-hand side is 2^{240}.\nTherefore x(x+1) = 240, giving x = 15.',
               correct_answer='C: 15',attempted='Unattempted',difficulty='Easy',topic='Algebra',seconds=9,
               warnings=['Superscripts recovered from layout; verify the mathematical expression'])
    reader=QuestionReader([('Sample mock / illustrative preview',q)])
    reader.show();reader.reveal.setChecked(True);app.processEvents()
    reader.grab().save(str(out/'question-reader.png'))
    reader.close();window.close()
print('Saved overview-redesign.png and question-reader.png (synthetic preview data).')
