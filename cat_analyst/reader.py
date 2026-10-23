"""A reading-first question window shared by live and saved review."""
import html
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
                               QTextBrowser,QCheckBox,QSpinBox)
from .icons import line_icon
from .formatting import math_html,question_html


class QuestionReader(QDialog):
    changed=Signal(object)

    def __init__(self, entries, index=0, parent=None, image_loader=None):
        super().__init__(parent)
        self.entries=entries
        self.index=max(0,min(index,len(entries)-1))
        self.image_loader=image_loader
        self.setWindowTitle('Question review')
        self.resize(1000,800)
        self.setMinimumSize(700,500)
        layout=QVBoxLayout(self)
        layout.setContentsMargins(28,24,28,24)
        top=QHBoxLayout()
        self.heading=QLabel();self.heading.setObjectName('title')
        top.addWidget(self.heading);top.addStretch()
        top.addWidget(QLabel('Text size'))
        self.font_size=QSpinBox();self.font_size.setRange(15,30);self.font_size.setValue(20)
        self.font_size.valueChanged.connect(lambda:self.refresh())
        top.addWidget(self.font_size)
        layout.addLayout(top)
        self.metadata=QLabel();self.metadata.setObjectName('subtitle');self.metadata.setWordWrap(True)
        layout.addWidget(self.metadata)
        self.notice=QLabel();self.notice.setObjectName('warning');self.notice.setWordWrap(True)
        layout.addWidget(self.notice)
        self.browser=QTextBrowser();self.browser.setObjectName('questionReader')
        self.browser.setOpenExternalLinks(False);self.browser.setOpenLinks(False)
        layout.addWidget(self.browser,1)
        controls=QHBoxLayout()
        self.reveal=QCheckBox('Show answer and solution')
        self.reveal.toggled.connect(lambda:self.refresh())
        controls.addWidget(self.reveal)
        self.bookmark=QPushButton();self.bookmark.setIcon(line_icon("bookmark"));self.bookmark.clicked.connect(self.toggle_bookmark)
        controls.addWidget(self.bookmark)
        edit=QPushButton('Edit question');edit.clicked.connect(self.edit)
        controls.addWidget(edit)
        controls.addStretch()
        self.previous=QPushButton('Previous');self.previous.clicked.connect(lambda:self.navigate(-1))
        self.next=QPushButton('Next');self.next.clicked.connect(lambda:self.navigate(1))
        controls.addWidget(self.previous);controls.addWidget(self.next)
        layout.addLayout(controls)
        self.refresh()

    @property
    def question(self):
        return self.entries[self.index][1]

    def refresh(self,preserve_scroll=False):
        scroll=self.browser.verticalScrollBar().value()
        name,q=self.entries[self.index]
        self.heading.setText(f'Question {q.number:02d}')
        seconds='Unknown' if q.seconds is None else f'{q.seconds//60}:{q.seconds%60:02d}'
        self.metadata.setText(f'{name}  |  {q.topic}  |  {q.difficulty}  |  {q.attempted}  |  Time {seconds}')
        notices=[]
        if q.missing():notices.append('Missing: '+', '.join(q.missing()))
        if q.warnings:notices.append('Check extraction: '+'; '.join(q.warnings))
        self.notice.setText('\n'.join(notices));self.notice.setVisible(bool(notices))
        content=question_html(q.text)
        if self.reveal.isChecked():
            selected=q.selected_answer or ('Not attempted' if q.attempted=='Unattempted' else 'Not captured')
            content+='<hr><h3 style="color:#426e9b">Answer review</h3>'
            content+='<p><b>Correct answer:</b> '+math_html(q.correct_answer or 'Not captured')+'</p>'
            content+='<p><b>Your answer:</b> '+math_html(selected)+' &nbsp; <b>Result:</b> '+html.escape(q.correctness)+'</p>'
            content+='<h3>Text solution</h3><p>'+math_html(q.solution or 'Open Text Solution in test provider while recording to capture it.')+'</p>'
        size=self.font_size.value()
        self.browser.setHtml(f'<html><head><style>body {{font-family:"Segoe UI";font-size:{size}px;color:#282d2a;}} p {{line-height:155%;margin-top:16px;margin-bottom:22px;}} h3 {{font-size:18px;}} sup {{font-size:75%;}} hr {{color:#d5d8ce;}}</style></head><body>'+content+'</body></html>')
        self.bookmark.setText('Bookmarked' if q.bookmark else 'Bookmark')
        self.previous.setEnabled(self.index>0);self.next.setEnabled(self.index<len(self.entries)-1)
        if preserve_scroll:self.browser.verticalScrollBar().setValue(scroll)

    def navigate(self,step):
        target=self.index+step
        if 0<=target<len(self.entries):
            self.index=target
            self.reveal.setChecked(False)
            self.refresh()
            self.browser.verticalScrollBar().setValue(0)

    def toggle_bookmark(self):
        self.question.bookmark=not self.question.bookmark
        self.changed.emit(self.question)
        self.refresh(preserve_scroll=True)

    def edit(self):
        from .ui import QuestionEditor
        images=self.image_loader(self.question) if self.image_loader else None
        if QuestionEditor(self.question,self,images).exec():
            self.changed.emit(self.question)
            self.refresh(preserve_scroll=True)
