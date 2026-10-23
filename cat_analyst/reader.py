"""A reading-first question window shared by live and saved review."""
import html
import re
from PySide6.QtCore import QUrl
from PySide6.QtGui import QImage,QTextDocument
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (QDialog,QVBoxLayout,QHBoxLayout,QLabel,QPushButton,
                               QTextBrowser,QCheckBox,QSpinBox)
from .icons import line_icon
from PySide6.QtGui import QPainter,QColor
from PySide6.QtWidgets import QToolButton,QSizeGrip,QApplication



def math_html(text: str) -> str:
    output=[]
    i=0
    while i<len(text):
        if text[i]=='^' and i+1<len(text):
            start=i+1
            if text[start] in '{(':
                opening=text[start];closing='}' if opening=='{' else ')'
                depth=1;j=start+1
                while j<len(text) and depth:
                    if text[j]==opening:depth+=1
                    elif text[j]==closing:depth-=1
                    j+=1
                if depth==0:
                    output.append('<sup>'+math_html(text[start+1:j-1])+'</sup>')
                    i=j
                    continue
            else:
                match=re.match(r'-?(?:\d+(?:\.\d+)?|[a-zA-Z])',text[start:])
                if match:
                    output.append('<sup>'+html.escape(match[0])+'</sup>')
                    i=start+len(match[0]);continue
        output.append('<br>' if text[i]=='\n' else html.escape(text[i]))
        i+=1
    return ''.join(output)


def question_html(text: str) -> str:
    lines=text.splitlines()
    choices=[i for i,line in enumerate(lines) if re.match(r'^\s*[A-D][.)]?\s+\S',line)]
    ordered=[]
    for index in choices:
        current=lines[index].lstrip()[0]
        if ordered and current <= lines[ordered[-1]].lstrip()[0]:
            ordered=[]
        ordered.append(index)
    choices=ordered
    if len(choices)<2:
        return '<p>'+math_html(text or 'Question text has not been captured yet.')+'</p>'
    start=choices[0]
    result='<p>'+math_html('\n'.join(lines[:start]))+'</p>'
    for index,i in enumerate(choices):
        end=choices[index+1] if index+1<len(choices) else len(lines)
        match=re.match(r'^\s*([A-D])[.)]?\s+(.*)',lines[i])
        body=match[2]+('\n'+'\n'.join(lines[i+1:end]) if end>i+1 else '')
        result+='<table width="100%" cellspacing="0" cellpadding="6"><tr>'
        result+='<td width="40"><b style="color:#426e9b">'+match[1]+'</b></td><td>'+math_html(body)+'</td></tr></table>'
    return result


class CompactDialog(QDialog):
    def __init__(self,parent=None,title='Review',width=440):
        super().__init__(parent,Qt.WindowType.Dialog|Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setObjectName('compactReview');self.setWindowTitle(title)
        self.setStyleSheet('QDialog#compactReview {background: transparent;}')
        self.outer=QVBoxLayout(self);self.outer.setContentsMargins(14,12,14,10)
        bar=QHBoxLayout();name=QLabel(title);name.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents);bar.addWidget(name);bar.addStretch()
        close=QToolButton();close.setText('Close');close.setAccessibleName('Close review');close.clicked.connect(self.close);bar.addWidget(close)
        self.outer.addLayout(bar)
        self.content=QVBoxLayout();self.content.setSpacing(6);self.outer.addLayout(self.content,1)
        grip=QSizeGrip(self);self.outer.addWidget(grip,0,Qt.AlignmentFlag.AlignRight)
        screen=QApplication.primaryScreen().availableGeometry()
        self.setMinimumSize(360,360);self.resize(min(width,screen.width()-24),min(540,int(screen.height()*.78)))
        self.move(screen.right()-self.width()-12,screen.top()+24)
        self.drag_origin=None
    def paintEvent(self,event):
        painter=QPainter(self);painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(QColor(205,216,225,230));painter.setBrush(QColor(250,247,240,232))
        painter.drawRoundedRect(self.rect().adjusted(1,1,-1,-1),20,20)
    def mousePressEvent(self,event):
        if event.button()==Qt.MouseButton.LeftButton and event.position().y()<48:
            self.drag_origin=event.globalPosition().toPoint()-self.pos();event.accept()
        else:super().mousePressEvent(event)
    def mouseMoveEvent(self,event):
        if self.drag_origin is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint()-self.drag_origin);event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self.drag_origin=None;super().mouseReleaseEvent(event)


class QuestionReader(CompactDialog):
    changed=Signal(object)

    def __init__(self, entries, index=0, parent=None, image_loader=None, image_records_loader=None):
        super().__init__(parent,'Question review',500)
        self.entries=entries
        self.index=max(0,min(index,len(entries)-1))
        self.image_loader=image_loader
        self.image_records_loader=image_records_loader
        self.setWindowTitle('Question review')
        layout=self.content
        top=QHBoxLayout()
        self.heading=QLabel();self.heading.setObjectName('title')
        top.addWidget(self.heading);top.addStretch()
        top.addWidget(QLabel('Text size'))
        self.font_size=QSpinBox();self.font_size.setRange(15,30);self.font_size.setValue(18)
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
        layout.addWidget(self.reveal)
        self.bookmark=QPushButton();self.bookmark.setIcon(line_icon("bookmark"));self.bookmark.clicked.connect(self.toggle_bookmark)
        controls.addWidget(self.bookmark)
        edit=QPushButton('Edit');edit.clicked.connect(self.edit)
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
        self.notice.setText('Review extraction details' if notices else '');self.notice.setToolTip('\n'.join(notices));self.notice.setVisible(bool(notices))
        content=question_html(q.text)
        if self.reveal.isChecked():
            selected=q.selected_answer or ('Not attempted' if q.attempted=='Unattempted' else 'Not captured')
            content+='<hr><h3 style="color:#426e9b">Answer review</h3>'
            content+='<p><b>Correct answer:</b> '+math_html(q.correct_answer or 'Not captured')+'</p>'
            content+='<p><b>Your answer:</b> '+math_html(selected)+' &nbsp; <b>Result:</b> '+html.escape(q.correctness)+'</p>'
            content+='<h3>Text solution</h3><p>'+math_html(q.solution or 'Open Text Solution in test provider while recording to capture it.')+'</p>'
        records=self.image_records_loader(q) if self.image_records_loader else []
        displayed=[]
        for name,data in records:
            is_question=name.startswith('auto-question-')
            if not is_question and not self.reveal.isChecked():continue
            picture=QImage.fromData(data)
            if picture.isNull():continue
            url=QUrl('capture:'+str(len(displayed)))
            displayed.append((url,picture))
            width=min(picture.width(),max(240,self.browser.viewport().width()-40))
            title='Question image' if is_question else 'Solution / captured image'
            content+='<h3>'+title+'</h3><p><img src="'+url.toString()+'" width="'+str(width)+'"></p>'
        size=self.font_size.value()
        self.browser.setHtml(f'<html><head><style>body {{font-family:"Segoe UI";font-size:{size}px;color:#282d2a;}} p {{line-height:125%;margin-top:6px;margin-bottom:10px;}} h3 {{font-size:18px;}} sup {{font-size:75%;}} hr {{color:#d5d8ce;}}</style></head><body>'+content+'</body></html>')
        for url,picture in displayed:
            self.browser.document().addResource(QTextDocument.ResourceType.ImageResource,url,picture)
        self.browser.document().markContentsDirty(0,self.browser.document().characterCount())
        self.browser.viewport().update()
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
