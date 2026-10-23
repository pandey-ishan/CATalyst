"""Exercise the installed OCR engine with generated test provider-like review views, offline."""
import json
import socket
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from rapidocr_onnxruntime import RapidOCR
from cat_analyst.parser import ocr_lines, parse_test_provider

out = Path('_test_artifacts')
out.mkdir(exist_ok=True)
font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 23)

def fixture(solution=False):
    image = Image.new('RGB', (1150, 950), 'white')
    draw = ImageDraw.Draw(image)
    entries = [(30, 25, '01/22'), (30, 90, 'A shopkeeper offers a discount on pairs of shoes.'),
               (30, 130, 'Each pair costs Rs. 2000, or Rs. 1900 when buying more than n pairs.'),
               (30, 170, 'The cost of n pairs equals the cost of n + 1 pairs. What is n?'),
               (30, 230, 'Enter your response (as an integer)'), (70, 280, '38'), (70, 330, 'Backspace')]
    if solution:
        entries += [(30, 440, 'Correct Answer'), (30, 480, '19'),
                    (30, 560, 'Statistics     Text Solution     Video Solution'),
                    (30, 640, 'We have 2000n = 1900(n + 1). Solving for n, we get n = 19.'),
                    (30, 690, 'Therefore, the required answer is 19.')]
    else:
        entries += [(30, 440, 'Statistics     Text Solution     Video Solution'),
                    (30, 510, 'Question Type A'),
                    (30, 570, 'Performance Parameter'), (440, 570, 'You'), (650, 570, 'Toppers'), (850, 570, 'Overall'),
                    (30, 630, 'Attempt'), (440, 630, 'Answered'), (650, 630, '87.5%'), (850, 630, '69.3%'),
                    (30, 690, 'Accuracy'), (440, 690, 'Incorrect'), (650, 690, '92.86%'), (850, 690, '82.65%'),
                    (30, 750, 'Time Taken'), (440, 750, '3:10'), (650, 750, '1:28'), (850, 750, '2:40')]
    for x, y, text in entries:
        draw.text((x, y), text, fill='black', font=font)
    return image

# Any attempted network connection makes the smoke check fail.
with patch.object(socket.socket, 'connect', side_effect=AssertionError('OCR must remain offline')):
    engine = RapidOCR(intra_op_num_threads=2, inter_op_num_threads=1)
    parsed = []
    for name, is_solution in [('statistics', False), ('solution', True)]:
        image = fixture(is_solution)
        image.save(out / f'{name}.png')
        result, elapsed = engine(np.asarray(image))
        question = parse_test_provider(ocr_lines(result), image.width, image.height)
        if question is None:
            raise AssertionError(f'No question found: {result}')
        parsed.append(question)
        print(name, json.dumps(asdict(question), ensure_ascii=True))
    parsed[0].merge(parsed[1])
    assert parsed[0].correct_answer == '19', parsed[0]
    assert parsed[0].seconds == 190, parsed[0]
    assert parsed[0].difficulty == 'Easy', parsed[0]
    assert parsed[0].correctness == 'Incorrect', parsed[0]
    assert parsed[0].solution, parsed[0]
    print('OFFLINE OCR SMOKE PASSED')

# MCQ fixture uses the layout and small tick badge from the user's example.
# It is generated test data, not a retained screenshot of the user's browser.
from cat_analyst.capture import CaptureWorker
import cv2
image = Image.new('RGB', (800, 900), 'white')
draw = ImageDraw.Draw(image)
small_font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 16)
option_font = ImageFont.truetype('C:/Windows/Fonts/arial.ttf', 21)
draw.text((37, 15), '03/22', fill='black', font=small_font)
draw.text((37, 50), 'Find the value of x in the equation shown.', fill='black', font=small_font)
for index, (option, value) in enumerate(zip('ABCD', ('13','14','15','16'))):
    y=92+88*index
    draw.rounded_rectangle((37,y,721,y+69), radius=10, outline='#d8d8d8', width=1)
    draw.rounded_rectangle((56,y+17,92,y+51), radius=7, fill='#d9d9d9')
    draw.text((67,y+21), option, fill='black', font=option_font)
    draw.text((107,y+25), value, fill='black', font=small_font)
for x,y,text in [(60,480,'Statistics   Text Solution   Video Solution'),(60,565,'Question Type A'),
                 (75,620,'Performance Parameter'),(335,620,'You'),(425,620,'Toppers'),(560,620,'Overall'),
                 (100,660,'Attempt'),(315,660,'Skipped'),(425,660,'90.63%'),(560,660,'53.8%'),
                 (100,700,'Accuracy'),(315,700,'-'),(425,700,'96.55%'),(560,700,'92.94%'),
                 (100,735,'Time Taken'),(315,735,'0:09'),(425,735,'0:50'),(560,735,'1:56')]:
    draw.text((x,y),text,fill='black',font=small_font)
frame = np.asarray(image)[:,:,::-1].copy()
cv2.circle(frame,(741,302),9,(139,204,128),-1,cv2.LINE_AA)
cv2.polylines(frame,[np.array([[736,302],[739,305],[746,298]],dtype=np.int32)],False,(255,255,255),1,cv2.LINE_AA)
cv2.imwrite(str(out/'mcq-skipped.png'),frame)
with patch.object(socket.socket, 'connect', side_effect=AssertionError('OCR must remain offline')):
    worker = CaptureWorker({},out,False)
    worker._engine=engine
    q=worker._ocr(frame)
    assert q is not None, 'MCQ question was not identified'
    print('mcq',q.number,q.correct_answer,q.attempted,q.seconds)
    assert q.correct_answer=='C: 15',q
    assert q.attempted=='Unattempted',q
    assert q.selected_answer=='',q
    assert q.seconds==9,q
    print('OFFLINE MCQ TICK SMOKE PASSED')
