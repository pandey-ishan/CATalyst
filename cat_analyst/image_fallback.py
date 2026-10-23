"""Lossless, cropped image fallbacks for uncertain local OCR."""
import hashlib,re
import cv2

def fallback_regions(question,lines,height,width):
    risky=(not question.text and not question.solution) or bool(question.warnings) or any(l.confidence<.85 for l in lines) or bool(re.search(r'[\^√∑∫]|\\frac',question.text+' '+question.solution))
    if not risky:return []
    tabs=[l for l in lines if re.search(r'Statistics|Text\s*Solution|Video\s*Solution',l.text,re.I)]
    boundary=min((l.y for l in tabs),default=height)
    stops=[l.y for l in lines if re.search(r'Enter your response|Backspace|Correct\s*Answer',l.text,re.I)]
    markers=[l.bottom for l in lines if re.fullmatch(r'[0-9Il]{1,2}\s*[/|]\s*\d{1,2}',l.text.strip())]
    top=int(max(markers,default=0)+4)
    regions=[]
    if question.text or (tabs and not question.solution):
        end=int(min([boundary]+stops))
        if end>top+12:regions.append(('question',0,top,width,end))
    if question.solution or (tabs and "Statistics" not in question.views):
        start=int(max((l.bottom for l in tabs),default=top)+4)
        if height>start+12:regions.append(('solution',0,start,width,height))
    if not regions and not question.text and 'Statistics' not in question.views:
        regions.append(('uncertain',0,top,width,height))
    return regions

def retain_fallbacks(question,frame,directory):
    for kind,x,y,right,bottom in getattr(question,'_fallback_regions',[]):
        crop=frame[max(0,y):min(frame.shape[0],bottom),max(0,x):min(frame.shape[1],right)]
        if not crop.size:continue
        ok,encoded=cv2.imencode('.png',crop,[cv2.IMWRITE_PNG_COMPRESSION,9])
        if not ok:raise RuntimeError('Could not compress automatic image fallback')
        data=encoded.tobytes();digest=hashlib.sha256(data).hexdigest()[:24]
        name=f'auto-{kind}-q{question.number}-{digest}.png'
        path=directory/name
        if not path.exists():path.write_bytes(data)
        if name not in question.fallback_images:question.fallback_images.append(name)
