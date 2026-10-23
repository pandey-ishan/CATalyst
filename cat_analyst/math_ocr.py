"""Local recovery of raised exponent runs from screenshot geometry.

This supplements general OCR; it does not infer or solve mathematical content.
"""
from __future__ import annotations
import re
import unicodedata
from collections import Counter
import cv2
import numpy as np
from .parser import Line


def raised_runs(crop: np.ndarray) -> list[tuple[int, int, int, int]]:
    gray = cv2.cvtColor(crop[:, :, :3], cv2.COLOR_BGR2GRAY)
    light = np.median(gray) > 127
    ink = ((gray < 165) if light else (gray > 170)).astype(np.uint8)
    count, _, stats, _ = cv2.connectedComponentsWithStats(ink, 8)
    glyphs = []
    for x, y, w, h, area in stats[1:]:
        if area >= 2 and w < crop.shape[1] * .65:
            glyphs.append([int(x), int(y), int(x+w), int(y+h)])
    # Reunite i/j dots, colons, and equals signs sharing a horizontal footprint.
    merged = []
    for box in sorted(glyphs):
        match = next((g for g in reversed(merged) if min(g[2], box[2])-max(g[0], box[0]) > 0
                      and max(g[3], box[3])-min(g[1], box[1]) < crop.shape[0] * .95), None)
        if match is not None:
            match[:] = [min(match[0],box[0]), min(match[1],box[1]), max(match[2],box[2]), max(match[3],box[3])]
        else:
            merged.append(box)
    substantial = [g for g in merged if g[3]-g[1] >= 5]
    if len(substantial) < 5:
        return []
    bottoms = Counter(g[3] for g in substantial)
    baseline = max(bottoms, key=lambda y: sum(count for yy,count in bottoms.items() if abs(yy-y)<=1))
    normal = [g[3]-g[1] for g in substantial if abs(g[3]-baseline)<=2]
    if len(normal) < 3:
        return []
    height = float(np.median(normal))
    candidates = [g for g in merged if g[3] <= baseline-max(3, height*.26)
                  and g[1] <= baseline-height*.85
                  and g[3]-g[1] <= height*.95]
    runs = []
    for box in sorted(candidates):
        if runs and box[0]-runs[-1][2] <= height*.8:
            previous = runs[-1]
            previous[:] = [previous[0], min(previous[1],box[1]), box[2], max(previous[3],box[3])]
        else:
            runs.append(box.copy())
    return [tuple(g) for g in runs if g[2]-g[0]>=4 and g[3]-g[1]>=4]


def recognize_crop(engine, crop):
    if not crop.size or crop.shape[1] < 2:
        return '', 0.0
    scale = max(2.0, 40 / max(1,crop.shape[0]))
    enlarged = cv2.resize(crop, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
    background = 255 if np.median(enlarged) > 127 else 0
    enlarged = cv2.copyMakeBorder(enlarged, 5, 5, 5, 5, cv2.BORDER_CONSTANT, value=(background,)*3)
    result, _ = engine(enlarged, use_det=False, use_cls=False)
    if not result:
        return '', 0.0
    return str(result[0][0]).strip(), float(result[0][1])


def restore_superscripts(frame, lines, engine):
    bands = []
    for line in sorted(lines, key=lambda l:l.y):
        if bands and line.y <= max(l.bottom for l in bands[-1])+2:
            bands[-1].append(line)
        else:
            bands.append([line])
    restored, notes, originals = [], [], []
    for band in bands:
        original = ' '.join(l.text for l in sorted(band, key=lambda l:l.x))
        if not re.search(r'[0-9]',original) or re.search(r'Question\s*Type|Time\s*Taken|Attempt|Accuracy',original,re.I):
            restored.extend(band)
            continue
        x1=max(0,int(min(l.x for l in band))-2)
        y1=max(0,int(min(l.y for l in band))-3)
        x2=min(frame.shape[1],int(max(l.right for l in band))+3)
        y2=min(frame.shape[0],int(max(l.bottom for l in band))+3)
        crop=frame[y1:y2,x1:x2]
        if crop.shape[0] < 10 or crop.shape[0] > 100 or not crop.size:
            restored.extend(band)
            continue
        runs=raised_runs(crop)
        accepted=[]
        for left,top,right,bottom in runs:
            expression,confidence=recognize_crop(engine,crop[max(0,top-1):bottom+1,max(0,left-1):right+1])
            expression=unicodedata.normalize('NFKC', expression).replace('\u2212','-').replace('\u2013','-')
            # If general OCR already isolated the raised run, its contextual
            # recognition can be better than recognition of a tiny crop.
            for token in band:
                if (token.x >= x1+left-5 and token.right <= x1+right+5
                        and token.y >= y1+top-5 and token.bottom <= y1+bottom+5
                        and token.confidence >= .75):
                    candidate = unicodedata.normalize('NFKC', token.text).replace('\u2212','-')
                    if re.fullmatch(r'[0-9xyzmnk()+\-*/=.\s]+', candidate, re.I):
                        expression, confidence = candidate, token.confidence
                        break
            if confidence>=.65 and re.fullmatch(r'[0-9xyzmnk()+\-*/=.\s]+',expression,re.I) and re.search(r'[0-9xyzmnk]',expression,re.I):
                accepted.append((left,right,expression))
        if not accepted:
            restored.extend(band)
            continue
        parts=[]
        cursor=0
        reliable=True
        for left,right,expression in accepted:
            base,confidence=recognize_crop(engine,crop[:,cursor:left])
            if confidence < .65 or not re.search(r'[\w)\]}]$',base):
                reliable=False
                break
            parts.append(base.rstrip()+'^{'+expression+'}')
            cursor=right
        if reliable:
            suffix,confidence=recognize_crop(engine,crop[:,cursor:])
            if suffix and confidence<.65:
                reliable=False
            if suffix:
                parts.append(suffix)
        if reliable:
            restored.append(Line(' '.join(parts),x1,y1,x2,y2,min(l.confidence for l in band)))
            originals.append(original)
            notes.append('Superscripts recovered from layout; verify the mathematical expression')
        else:
            restored.extend(band)
            notes.append('Raised text detected but uncertain; check exponents in the editor')
    return sorted(restored,key=lambda l:(l.y,l.x)),list(dict.fromkeys(notes)),originals
