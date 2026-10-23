"""Dashboard summaries with explicit sample coverage and no inferred zeroes."""
from .core import analytics


def dashboard_insights(questions):
    summary=analytics(questions)[0]
    topics=analytics(questions)[1:]
    accuracy=sorted([r for r in topics if r['topic']!='Unclassified' and r['graded']>=3],
                    key=lambda r:(r['accuracy'],-r['graded'],r['topic']))[:3]
    timed_topics=[]
    for topic in sorted({q.topic for q in questions if q.topic!='Unclassified'}):
        timed=[q for q in questions if q.topic==topic and q.attempted=='Answered' and q.seconds is not None]
        if len(timed)>=3:
            timed_topics.append(dict(topic=topic,count=len(timed),average=sum(q.seconds for q in timed)/len(timed)))
    timed_topics.sort(key=lambda r:(-r['average'],-r['count'],r['topic']))
    known_attempts=sum(q.attempted in ('Answered','Unattempted') for q in questions)
    incorrect=[q for q in questions if q.attempted=='Answered' and q.correctness=='Incorrect' and q.seconds is not None]
    attempts_with_time=[q for q in questions if q.attempted=='Answered' and q.seconds is not None]
    return dict(summary=summary,weak_accuracy=accuracy,slow_topics=timed_topics[:3],
                known_attempts=known_attempts,attempt_rate=100*summary['attempts']/known_attempts if known_attempts else None,
                wrong_seconds=sum(q.seconds for q in incorrect),wrong_timed=len(incorrect),
                attempt_average=sum(q.seconds for q in attempts_with_time)/len(attempts_with_time) if attempts_with_time else None,
                attempt_timed=len(attempts_with_time),bookmarks=sum(q.bookmark for q in questions),
                easy_misses=sum(q.difficulty=='Easy' and (q.attempted=='Unattempted' or (q.attempted=='Answered' and q.correctness=='Incorrect')) for q in questions),
                needs_review=sum(bool(q.missing() or q.warnings) for q in questions))
