"""Charcoal/gold overview with actionable QA statistics and coverage."""
import json
from PySide6.QtCore import Qt,Signal,QTimer
from PySide6.QtGui import QColor,QPainter,QPen
from PySide6.QtWidgets import (QWidget,QVBoxLayout,QHBoxLayout,QLabel,QFrame,QScrollArea,
                               QPushButton,QTableWidget,QTableWidgetItem,QHeaderView,QAbstractItemView,QProgressBar,QGridLayout,QSizePolicy)
from PySide6.QtCharts import QChart,QChartView,QLineSeries,QLegend
from .core import SECTIONS,analytics
from .insights import dashboard_insights
from .tables import ReadableTable
from .icons import line_icon


def duration(value):
    if value is None:return '\u2014'
    value=round(value)
    return f'{value//60}:{value%60:02d}'


class Metric(QFrame):
    def __init__(self,title,accent=False):
        super().__init__()
        self.setObjectName('goldCard' if accent else 'metricCard')
        layout=QVBoxLayout(self);layout.setContentsMargins(20,17,20,17)
        heading=QLabel(title);heading.setObjectName('cardTitle');heading.setWordWrap(True)
        self.value=QLabel('\u2014');self.value.setObjectName('metric')
        self.caption=QLabel('No saved data yet');self.caption.setObjectName('subtitle');self.caption.setWordWrap(True)
        top=QHBoxLayout()
        glyph=QLabel();glyph.setPixmap(line_icon('clock' if 'Time' in title else 'chart' if 'accuracy' in title.lower() or 'score' in title.lower() else 'papers').pixmap(22,22))
        top.addWidget(glyph);top.addWidget(heading,1)
        layout.addLayout(top);layout.addWidget(self.value);layout.addWidget(self.caption)
        self.progress=QProgressBar();self.progress.setRange(0,100);self.progress.setTextVisible(False);self.progress.setFixedHeight(6);self.progress.hide()
        layout.addWidget(self.progress)
        self.setMinimumHeight(138)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)

    def update_value(self,value,caption):
        self.value.setText(str(value));self.caption.setText(caption)


class Ranking(QFrame):
    selected=Signal(str)
    def __init__(self,title,description):
        super().__init__();self.setObjectName('panel')
        layout=QVBoxLayout(self);layout.setContentsMargins(20,18,20,18)
        heading=QLabel(title);heading.setObjectName('sectionTitle');heading.setWordWrap(True);layout.addWidget(heading)
        desc=QLabel(description);desc.setObjectName('subtitle');desc.setWordWrap(True);layout.addWidget(desc)
        self.items=QVBoxLayout();layout.addLayout(self.items);layout.addStretch()
        self.setMinimumHeight(205)

    def populate(self,items,mode):
        while self.items.count():
            child=self.items.takeAt(0)
            if child.widget():
                child.widget().hide()
                child.widget().deleteLater()
        if not items:
            empty=QLabel('More data needed\nAt least 3 '+('graded attempts' if mode=='accuracy' else 'timed attempts')+' per topic.')
            empty.setObjectName('emptyHint');empty.setWordWrap(True);self.items.addWidget(empty)
        for item in items:
            if mode=='accuracy':value=f"{item['accuracy']:.0f}%  /  {item['graded']} graded"
            else:value=f"{duration(item['average'])} avg  /  {item['count']} timed"
            action=QPushButton(f"{item['topic']}\n{value}")
            action.setObjectName('topicRow')
            action.setToolTip('Open saved questions for this topic')
            action.clicked.connect(lambda checked=False,topic=item['topic']:self.selected.emit(topic))
            self.items.addWidget(action)


class Dashboard(QScrollArea):
    topic_requested=Signal(str)
    review_requested=Signal()

    def __init__(self,parent=None):
        super().__init__(parent);self.setWidgetResizable(True)
        self.setMinimumWidth(0)
        self.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Expanding)
        self.responsive_groups=[]
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        body=QWidget();self.setWidget(body)
        layout=QVBoxLayout(body);layout.setContentsMargins(2,12,14,20);layout.setSpacing(20)
        intro=QVBoxLayout()
        copy=QVBoxLayout()
        self.greeting=QLabel('Welcome back.');self.greeting.setObjectName('heroTitle');copy.addWidget(self.greeting)
        intro.addLayout(copy);intro.addStretch()
        self.latest=QLabel('No mocks saved yet');self.latest.setObjectName('pill');self.latest.setWordWrap(True);self.latest.setMinimumWidth(0);self.latest.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred);intro.addWidget(self.latest,0,Qt.AlignmentFlag.AlignVCenter)
        layout.addLayout(intro)
        first=QGridLayout();first.setSpacing(14)
        self.metrics={};self.cards={}
        for title in ['Latest overall score','Latest percentile','Saved mocks','QA questions']:
            card=Metric(title,accent=title=='Latest overall score');self.metrics[title]=card;self.cards[title]=card.value
            first.addWidget(card,0,len(self.metrics)-1)
        layout.addLayout(first)
        self.responsive_groups.append((first,list(self.metrics.values()),4))
        focus=QGridLayout();focus.setSpacing(14)
        self.weak=Ranking('Accuracy needs attention','Lowest accuracy among classified topics. Click to review.')
        self.slow=Ranking('Where time goes','Slowest average per attempted question. Click to review.')
        self.weak.selected.connect(self.topic_requested);self.slow.selected.connect(self.topic_requested)
        focus.addWidget(self.weak,0,0);focus.addWidget(self.slow,0,1)
        review=QFrame();review.setObjectName('focusCard');inner=QVBoxLayout(review);inner.setContentsMargins(22,18,22,18)
        title=QLabel('Your review queue');title.setObjectName('sectionTitle');inner.addWidget(title)
        self.queue_value=QLabel('0');self.queue_value.setObjectName('metric');inner.addWidget(self.queue_value)
        self.queue_text=QLabel();self.queue_text.setWordWrap(True);self.queue_text.setObjectName('subtitle');inner.addWidget(self.queue_text)
        inner.addStretch();action=QPushButton('Review bookmarks');action.setObjectName('primary')
        action.clicked.connect(self.review_requested);inner.addWidget(action)
        focus.addWidget(review,0,2);layout.addLayout(focus)
        self.responsive_groups.append((focus,[self.weak,self.slow,review],3))
        performance=QGridLayout();performance.setSpacing(14)
        self.performance={}
        for title in ['QA accuracy','Attempt rate','Time per attempt','Time on incorrect answers']:
            metric=Metric(title);self.performance[title]=metric;performance.addWidget(metric,0,len(self.performance)-1)
        layout.addLayout(performance)
        self.responsive_groups.append((performance,list(self.performance.values()),4))
        self.chart=QChart();self.chart.setBackgroundBrush(QColor('#f8f6ee'))
        self.chart.setTitleBrush(QColor('#242d27'));self.chart.legend().setLabelColor(QColor('#5c655d'))
        self.chart.setBackgroundRoundness(22)
        self.chart.legend().setMarkerShape(QLegend.MarkerShape.MarkerShapeCircle)
        self.chart_view=QChartView(self.chart);self.chart_view.setRenderHint(QPainter.RenderHint.Antialiasing)
        self.chart_view.setMinimumWidth(0);self.chart_view.setSizePolicy(QSizePolicy.Policy.Ignored,QSizePolicy.Policy.Preferred)
        self.chart_view.setMinimumHeight(260);self.chart_view.setMaximumHeight(340)
        layout.addWidget(self.chart_view)
        self.coverage=QLabel();self.coverage.setObjectName('subtitle');self.coverage.setWordWrap(True);layout.addWidget(self.coverage)
        heading=QLabel('Topic breakdown');heading.setObjectName('sectionTitle');heading.setWordWrap(True);layout.addWidget(heading)
        self.topic_table=ReadableTable(['Topic','Captured','Attempts','Accuracy','Total time','Avg time','Timed'])
        self.topic_table.setMinimumHeight(300);layout.addWidget(self.topic_table)
        foot=QLabel('Accuracy excludes unknown results. Topic timing cards use attempted questions; the table includes all known QA times. Rankings require 3 observations and show sample sizes.')
        foot.setWordWrap(True);foot.setObjectName('subtitle');layout.addWidget(foot)

    def resizeEvent(self,event):
        super().resizeEvent(event)
        self.reflow()

    def reflow(self):
        width=self.viewport().width()
        for grid,widgets,maximum in self.responsive_groups:
            columns=(4 if width>=900 else 2 if width>=440 else 1) if maximum==4 else min(maximum,max(1,width//245))
            for widget in widgets:grid.removeWidget(widget)
            for column in range(maximum):grid.setColumnStretch(column,0)
            for index,widget in enumerate(widgets):
                grid.addWidget(widget,index//columns,index%columns)
            for column in range(columns):grid.setColumnStretch(column,1)

    def update_data(self,papers,questions):
        data=dashboard_insights(questions);self.insights=data
        summary=data['summary']
        from datetime import datetime, timezone, timedelta
        hour=datetime.now(timezone(timedelta(hours=5,minutes=30))).hour
        self.greeting.setText('Good morning.' if hour<12 else 'Good afternoon.' if hour<17 else 'Good evening.')
        if papers:
            current=json.loads(papers[-1]['metrics'])['Overall']
            delta=None if len(papers)<2 else current['score']-json.loads(papers[-2]['metrics'])['Overall']['score']
            self.metrics['Latest overall score'].update_value(f"{current['score']:g}",'First saved mock' if delta is None else f'{delta:+g} points vs previous mock')
            self.metrics['Latest percentile'].update_value(f"{current['percentile']:.2f}",'Overall percentile, entered by you')
            self.latest.setText(papers[-1]['name']+'  /  '+papers[-1].get('test_date',papers[-1]['created'][:10]))
        else:
            self.latest.setText('No mocks saved yet')
            self.metrics['Latest overall score'].update_value('\u2014','Save your first mock to begin')
            self.metrics['Latest percentile'].update_value('\u2014','Overall percentile')
        self.metrics['Saved mocks'].update_value(len(papers),'All recorded papers')
        expected=sum(p['expected'] for p in papers)
        self.metrics['QA questions'].update_value(len(questions),f'{expected} expected across saved mocks')
        self.weak.populate(data['weak_accuracy'],'accuracy');self.slow.populate(data['slow_topics'],'time')
        self.queue_value.setText(str(data['bookmarks']))
        self.queue_text.setText(f"Bookmarked questions\n{data['easy_misses']} easy questions missed or skipped\n{data['needs_review']} questions need extraction review")
        self.performance['QA accuracy'].update_value('\u2014' if summary['accuracy'] is None else f"{summary['accuracy']:.1f}%",f"{summary['graded']} graded attempts")
        self.performance['Attempt rate'].update_value('\u2014' if data['attempt_rate'] is None else f"{data['attempt_rate']:.1f}%",f"{summary['attempts']} / {data['known_attempts']} with known status")
        self.performance['Time per attempt'].update_value(duration(data['attempt_average']),f"{data['attempt_timed']} timed attempts")
        self.performance['Time on incorrect answers'].update_value(duration(data['wrong_seconds']) if data['wrong_timed'] else '\u2014',f"{data['wrong_timed']} timed incorrect attempts")
        for key,value in [('QA accuracy',summary['accuracy']),('Attempt rate',data['attempt_rate'])]:
            self.performance[key].progress.setVisible(value is not None)
            self.performance[key].progress.setValue(round(value or 0))
        self.metrics['QA questions'].progress.setVisible(expected>0)
        self.metrics['QA questions'].progress.setValue(min(100,round(100*len(questions)/expected)) if expected else 0)
        self.chart.removeAllSeries()
        for axis in self.chart.axes():self.chart.removeAxis(axis)
        self.chart.setTitle('Score progression  /  overall and sections' if papers else 'Your score progression will appear after your first mock')
        for section,color in zip(SECTIONS,['#e58a42','#4a87cd','#8a8ec6','#439caa']):
            series=QLineSeries();series.setName(section);series.setPen(QPen(QColor(color),2.5));series.setPointsVisible(True)
            for index,paper in enumerate(papers,1):series.append(index,json.loads(paper['metrics'])[section]['score'])
            self.chart.addSeries(series)
        self.chart.createDefaultAxes()
        for axis in self.chart.axes():
            axis.setLabelsColor(QColor('#5c655d'));axis.setGridLineColor(QColor('#dedfd5'))
            if axis.orientation()==Qt.Orientation.Horizontal:
                axis.setRange(.5,max(1.5,len(papers)+.5));axis.setLabelFormat('%d')
                axis.setTickType(axis.TickType.TicksDynamic);axis.setTickAnchor(1);axis.setTickInterval(max(1,(len(papers)+7)//8))
        self.coverage.setText(f"Capture coverage: {len(questions)} / {expected} expected QA questions. {summary['unknown_attempts']} unknown attempt statuses; {summary['timed']} / {len(questions)} questions have timing data.")
        stats=analytics(questions);topic_rows=[]
        for i,r in enumerate(stats):
            values=[r['topic'],r['questions'],r['attempts'],'\u2014' if r['accuracy'] is None else f"{r['accuracy']:.1f}% ({r['graded']})",duration(r['total_seconds']) if r['timed'] else '\u2014',duration(r['average_seconds']),f"{r['timed']}/{r['questions']}"]
            topic_rows.append(values)
        self.topic_table.set_rows(topic_rows)
