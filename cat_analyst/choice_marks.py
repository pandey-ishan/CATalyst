"""Read green test provider answer ticks from pixels; OCR alone may omit the icon."""
from __future__ import annotations
import re
from dataclasses import dataclass
import cv2
import numpy as np
from .parser import Line, rows


@dataclass
class Choice:
    label: str
    text: str
    x: float
    right: float
    y: float
    bottom: float


def choice_rows(lines: list[Line]) -> list[Choice]:
    boundary = min((line.y for line in lines if re.search(
        r'Statistics|Text\s*Solution|Question\s*Type|Correct\s*Answer', line.text, re.I)), default=float('inf'))
    choices = []
    for row in rows([line for line in lines if line.bottom < boundary]):
        first = row[0]
        match = re.fullmatch(r'([A-D])(?:[.)]|\s+)?(?:\s+(.*))?', first.text.strip(), re.I)
        if not match:
            # OCR sometimes combines label and answer without a space: C15.
            match = re.fullmatch(r'([A-D])\s*([0-9][0-9.,/%+\-]*)', first.text.strip())
        if not match:
            continue
        pieces = ([match[2]] if match[2] else []) + [line.text for line in row[1:]
                  if line.text.strip() not in ('\u2713', '\u2714', '\u221a')]
        choices.append(Choice(match[1].upper(), ' '.join(pieces).strip(),
                              first.x, max(line.right for line in row),
                              min(line.y for line in row), max(line.bottom for line in row)))
    # Use the longest aligned A/B/C/D sequence. A stray letter in the stem
    # or an OCR glyph must not invalidate the actual answer options.
    runs=[]
    for start in range(len(choices)):
        run=[choices[start]]
        for candidate in choices[start+1:]:
            if ord(candidate.label)==ord(run[-1].label)+1 and abs(candidate.x-run[0].x)<=max(25,run[0].bottom-run[0].y):
                run.append(candidate)
        runs.append(run)
    if not runs:return []
    choices=max(runs,key=lambda run:(len(run),-(run[-1].y-run[0].y)))
    if len(choices)<2:return []
    # Include wrapped option text in the interval up to the next option.
    for index, choice in enumerate(choices):
        end = choices[index + 1].y if index + 1 < len(choices) else boundary
        extra = [line.text for line in lines if choice.bottom + 4 < line.y < end - 4
                 and line.x > choice.x + 15 and line.text.strip() not in ('\u2713', '\u2714', '\u221a')]
        if extra:
            choice.text += ' ' + ' '.join(extra)
    return choices


def green_ticks(frame: np.ndarray) -> list[tuple[float, float, int]]:
    """Find green round badges containing a white tick, not arbitrary green text."""
    hsv = cv2.cvtColor(frame[:, :, :3], cv2.COLOR_BGR2HSV)
    mask = cv2.inRange(hsv, np.array([35, 45, 90]), np.array([95, 255, 255]))
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    found = []
    for contour in contours:
        x, y, width, height = cv2.boundingRect(contour)
        if not (8 <= width <= 80 and 8 <= height <= 80 and .7 <= width / height <= 1.4):
            continue
        area = cv2.contourArea(contour)
        perimeter = cv2.arcLength(contour, True)
        if not perimeter or not .5 <= area / (width * height) <= .9:
            continue
        if 4 * np.pi * area / (perimeter * perimeter) < .65:
            continue
        # Inspect the bright glyph only inside an eroded filled badge. Exterior
        # page white must not count as a tick on an otherwise solid green dot.
        filled = np.zeros((height, width), np.uint8)
        local_contour = contour - np.array([[[x, y]]])
        cv2.drawContours(filled, [local_contour], -1, 255, -1)
        erosion = max(1, round(min(width, height) * .1))
        inside = cv2.erode(filled, np.ones((erosion * 2 + 1, erosion * 2 + 1), np.uint8))
        crop = frame[y:y + height, x:x + width, :3]
        bright = (crop.min(axis=2) > 195) & ((crop.max(axis=2).astype(int) - crop.min(axis=2)) < 45)
        glyph = (bright & (inside > 0)).astype(np.uint8) * 255
        ys, xs = np.nonzero(glyph)
        if len(xs) < 3 or xs.max() - xs.min() < width * .3:
            continue
        # A tick dips in its middle and rises to the right; a cross, vertical
        # stroke, dot, or plus does not have this column profile.
        left, right = xs.min(), xs.max()
        span = right - left + 1
        parts = [ys[(xs >= left + span * a) & (xs < left + span * b)]
                 for a, b in [(0, .3), (.3, .6), (.75, 1.01)]]
        if any(not len(part) for part in parts):
            continue
        l_y, mid_y, r_y = [float(np.mean(part)) for part in parts]
        if mid_y >= l_y - .5 and mid_y - r_y >= height * .12 and l_y > r_y:
            found.append((x + width / 2, y + height / 2, height))
    return found


def apply_choice_marks(question, lines: list[Line], frame: np.ndarray) -> None:
    ticks = green_ticks(frame)
    # OCR may represent a small tick as V, v, or a slash. Exclude only boxes
    # geometrically contained in the detected icon, never the option text.
    text_lines = [line for line in lines if not any(
        abs((line.x + line.right) / 2 - x) <= size * .65
        and abs((line.y + line.bottom) / 2 - y) <= size * .65
        and line.right - line.x <= size * 1.5
        and line.bottom - line.y <= size * 1.5
        for x, y, size in ticks)]
    choices = choice_rows(text_lines)
    if not choices:
        return
    matches = []
    for x, y, size in ticks:
        # Match only the answer list, to the right of the option label. Icons in
        # the statistics panel or browser chrome cannot become correct answers.
        candidates = []
        for index, choice in enumerate(choices):
            center = (choice.y + choice.bottom) / 2
            gaps = [abs(center - (c.y + c.bottom) / 2) for c in choices if c is not choice]
            tolerance = min(min(gaps) * .45, max(20, (choice.bottom - choice.y) * 2))
            if x > choice.x + 40 and abs(y - center) <= tolerance:
                candidates.append(choice)
        if len(candidates) == 1:
            choice = candidates[0]
            answer = f'{choice.label}: {choice.text}' if choice.text else choice.label
            if answer not in matches:
                matches.append(answer)
    if len(matches) == 1:
        if not question.correct_answer:
            question.correct_answer = matches[0]
        elif question.correct_answer not in (matches[0], matches[0].split(':', 1)[0]):
            question.warnings.append('Tick and text answers differ; verify the correct option')
    elif len(matches) > 1:
        question.warnings.append('Multiple green answer ticks found; verify the correct option')
    # A green tick reveals the answer key even when the user skipped the question.
    # Never infer an attempted answer or correctness from the tick alone.


def readable_option_frame(frame):
    """Normalize large blue option fills for local OCR; keep original for ticks."""
    hsv=cv2.cvtColor(frame[:,:,:3],cv2.COLOR_BGR2HSV)
    mask=cv2.inRange(hsv,np.array([90,55,65]),np.array([135,255,255]))
    contours,_=cv2.findContours(mask,cv2.RETR_EXTERNAL,cv2.CHAIN_APPROX_SIMPLE)
    result=frame.copy()
    for contour in contours:
        x,y,w,h=cv2.boundingRect(contour)
        if w<frame.shape[1]*.35 or not 25<=h<=frame.shape[0]*.25:continue
        if cv2.contourArea(contour)<w*h*.65:continue
        crop=frame[y:y+h,x:x+w,:3]
        blue=mask[y:y+h,x:x+w]>0
        white=crop.min(axis=2)>205
        dark=crop.max(axis=2)<90
        output=np.full_like(crop,255)
        # Both white-on-blue and dark-on-pale-blue text become dark-on-white.
        output[(white|dark)&~blue]=0
        result[y:y+h,x:x+w,:3]=output
    return result
